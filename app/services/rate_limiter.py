import time
from typing import Tuple, Optional, Dict 
import os

from app.core.config import settings

class RateLimiter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RateLimiter, cls).__new__(cls)
            # Structure: { "user_uid": {"count": 0, "reset_date": day_since_epoch} }
            cls._instance.user_counters: Dict[str, Dict[str, int]] = {} 
        return cls._instance

    def _get_quota_for_tier(self, tier: str) -> int:
        # Treat any tier string that is not 'free', empty, or None as premium.
        # This handles cases like "premium_monthly", "premium_yearly", "pro", etc.
        if tier and tier.lower().strip() not in ["free", "", None]: 
            return settings.PREMIUM_DAILY_QUOTA
        return settings.FREE_DAILY_QUOTA

    async def check_limit(self, user_uid: str, subscription_tier: str) -> Tuple[int, bool]:
        """
        Check if the rate limit has been exceeded for a specific user and tier using Redis.
        Returns (remaining_requests, limit_reached)
        """
        if not hasattr(self, 'redis') or self.redis is None:
            print("WARNING: Redis client not available in RedisRateLimiter.check_limit. Falling back to in-memory.")
            fallback = RateLimiter()
            return await fallback.check_limit(user_uid, subscription_tier)

        day_key = f"{self.key_prefix}u:{user_uid}:d:{int(time.time() // 86400)}" 
        
        try:
            count_bytes = self.redis.get(day_key)
            count = int(count_bytes) if count_bytes is not None else 0
        except redis.exceptions.RedisError as e:
            print(f"Redis GET error in check_limit for key {day_key}: {e}. Falling back to in-memory.")
            fallback = RateLimiter()
            return await fallback.check_limit(user_uid, subscription_tier)
        except ValueError:
            print(f"Redis value for key {day_key} is not an integer. Falling back to in-memory.")
            fallback = RateLimiter()
            return await fallback.check_limit(user_uid, subscription_tier)
        except Exception as e:
            print(f"Unexpected error in Redis check_limit: {e}. Falling back to in-memory.")
            fallback = RateLimiter()
            return await fallback.check_limit(user_uid, subscription_tier)

        quota_for_tier = self._get_quota_for_tier(subscription_tier)
        remaining = max(0, quota_for_tier - count) 
        limit_reached = remaining <= 0 
        
        return remaining, limit_reached

    async def increment(self, user_uid: str, subscription_tier: str) -> int: 
        """
        Increment the request counter for a specific user in Redis.
        Returns the new count.
        """
        if not hasattr(self, 'redis') or self.redis is None:
            print("WARNING: Redis client not available in RedisRateLimiter.increment. Falling back to in-memory.")
            fallback = RateLimiter()
            return await fallback.increment(user_uid, subscription_tier)

        day_key = f"{self.key_prefix}u:{user_uid}:d:{int(time.time() // 86400)}" 
        
        new_count = 0
        try:
            pipe = self.redis.pipeline() 
            pipe.incr(day_key) 
            pipe.expire(day_key, 60 * 60 * 48) # 48 hours 
            results = pipe.execute() 
            new_count = results[0] if results and len(results) > 0 else 0
        except redis.exceptions.RedisError as e:
            print(f"Redis pipeline error in increment for key {day_key}: {e}. Falling back to in-memory.")
            fallback = RateLimiter()
            return await fallback.increment(user_uid, subscription_tier)
        except Exception as e:
            print(f"Unexpected error in Redis increment: {e}. Falling back to in-memory.")
            fallback = RateLimiter()
            return await fallback.increment(user_uid, subscription_tier)
        
        return new_count


# If Redis is configured, use a Redis-based rate limiter instead
if settings.REDIS_URL: 
    import redis 
    
    class RedisRateLimiter:
        _instance = None
        
        def __new__(cls):
            if cls._instance is None:
                cls._instance = super(RedisRateLimiter, cls).__new__(cls)
                try:
                    cls._instance.redis = redis.from_url(settings.REDIS_URL) 
                    cls._instance.redis.ping() # Test connection
                    print("Successfully connected to Redis for rate limiting.")
                except redis.exceptions.ConnectionError as e:
                    print(f"WARNING: Could not connect to Redis at {settings.REDIS_URL}. Error: {e}")
                    print("Rate limiting will NOT use Redis. Falling back to in-memory (if not overridden).")
                    # To prevent falling back, you might raise an error or exit,
                    # or ensure the global RateLimiter is not replaced.
                    # For now, it will be replaced, but calls might fail if Redis is expected.
                    # A better approach might be to not replace RateLimiter if connection fails.
                    # However, the original code replaces it directly.
                cls._instance.key_prefix = "jobhunter_rl:" 
            return cls._instance

        def _get_quota_for_tier(self, tier: str) -> int:
            if tier and tier.lower().strip() not in ["free", "", None]: 
                return settings.PREMIUM_DAILY_QUOTA
            return settings.FREE_DAILY_QUOTA

        async def check_limit(self, user_uid: str, subscription_tier: str) -> Tuple[int, bool]:
            """
            Check if the rate limit has been exceeded for a specific user and tier using Redis.
            Returns (remaining_requests, limit_reached)
            """
            if not hasattr(self.redis, 'get'): # Check if redis client initialized properly
                print("WARNING: Redis client not available in RedisRateLimiter.check_limit. Defaulting to unlimited.") # Or some other safe default
                return settings.PREMIUM_DAILY_QUOTA, False # Fallback if Redis connection failed earlier

            day_key = f"{self.key_prefix}u:{user_uid}:d:{int(time.time() // 86400)}" 
            
            try:
                count_bytes = self.redis.get(day_key)
                count = int(count_bytes) if count_bytes is not None else 0
            except redis.exceptions.RedisError as e:
                print(f"Redis GET error in check_limit for key {day_key}: {e}. Assuming 0 count.")
                count = 0 # Be lenient on Redis error, or re-raise
            except ValueError: # Handle case where value in Redis is not an int
                print(f"Redis value for key {day_key} is not an integer. Assuming 0 count.")
                count = 0


            quota_for_tier = self._get_quota_for_tier(subscription_tier)
            remaining = max(0, quota_for_tier - count) 
            limit_reached = remaining <= 0 
            
            return remaining, limit_reached

        async def increment(self, user_uid: str, subscription_tier: str) -> int: 
            """
            Increment the request counter for a specific user in Redis.
            Returns the new count.
            """
            if not hasattr(self.redis, 'pipeline'): # Check if redis client initialized properly
                print("WARNING: Redis client not available in RedisRateLimiter.increment. Defaulting to count 1.") # Or some other safe default
                return 1 # Fallback

            day_key = f"{self.key_prefix}u:{user_uid}:d:{int(time.time() // 86400)}" 
            
            new_count = 0
            try:
                pipe = self.redis.pipeline() 
                pipe.incr(day_key) 
                # Set expiry to 2 days (in seconds) to handle daily resets and some clock drift.
                # If the key is new, INCR sets it to 1, then EXPIRE sets the TTL.
                # If it exists, INCR increments, then EXPIRE updates/sets the TTL.
                pipe.expire(day_key, 60 * 60 * 48) # 48 hours 
                results = pipe.execute() 
                new_count = results[0] if results and len(results) > 0 else 0
            except redis.exceptions.RedisError as e:
                print(f"Redis pipeline error in increment for key {day_key}: {e}. Assuming count 0.")
                # Decide how to handle error: re-raise, or return a safe value
                new_count = 0 # Or perhaps the previous count if obtainable, or 1 if it's a fresh increment
            
            return new_count
    
    # Attempt to connect to Redis and replace RateLimiter if successful
    try:
        # Temporarily instantiate to check connection without replacing global instance yet
        temp_redis_limiter = RedisRateLimiter()
        if hasattr(temp_redis_limiter, 'redis'):
            try:
                temp_redis_limiter.redis.ping()
                RateLimiter = RedisRateLimiter 
                print("Using RedisRateLimiter.")
            except Exception as e:
                print(f"Redis ping failed: {e}. Using in-memory RateLimiter.")
                # RateLimiter remains the default in-memory version
        else:
            print("Redis client not initialized. Using in-memory RateLimiter.")
            # RateLimiter remains the default in-memory version
    except Exception as e:
        print(f"Error during RedisRateLimiter setup: {e}. Using in-memory RateLimiter.")
        # RateLimiter remains the default in-memory version