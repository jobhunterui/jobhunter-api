# app/core/rate_limiter.py
import time
from typing import Tuple, Optional, Dict, Union # Added Union
import os

from app.core.config import settings

# Default In-Memory RateLimiter (as a class, not instance initially)
class InMemoryRateLimiter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InMemoryRateLimiter, cls).__new__(cls)
            cls._instance.user_counters: Dict[str, Dict[str, Union[int, float]]] = {}
            print("INFO: [RateLimiter] Initialized InMemoryRateLimiter instance.")
        return cls._instance

    def _get_current_day_identifier(self) -> int: # Helper for daily reset
        return int(time.time() // 86400)

    def _get_quota_for_tier(self, tier: str) -> int:
        tier_lower = tier.lower().strip() if tier else "free"
        if tier_lower not in ["free", ""]:
            return settings.PREMIUM_DAILY_QUOTA
        return settings.FREE_DAILY_QUOTA

    async def check_limit(self, user_uid: str, subscription_tier: str) -> Tuple[int, bool]:
        current_day_id = self._get_current_day_identifier()
        user_data = self.user_counters.get(user_uid)

        count = 0
        if user_data and user_data.get("reset_day_identifier") == current_day_id:
            count = int(user_data.get("count", 0))
        else:
            # Reset for a new day or new user
            self.user_counters[user_uid] = {"count": 0, "reset_day_identifier": current_day_id}
        
        quota_for_tier = self._get_quota_for_tier(subscription_tier)
        remaining = max(0, quota_for_tier - count)
        limit_reached = count >= quota_for_tier
        return remaining, limit_reached

    async def increment(self, user_uid: str, subscription_tier: str) -> int:
        current_day_id = self._get_current_day_identifier()
        user_data = self.user_counters.get(user_uid)

        new_count = 0
        if user_data and user_data.get("reset_day_identifier") == current_day_id:
            new_count = int(user_data.get("count", 0)) + 1
            self.user_counters[user_uid]["count"] = new_count
        else:
            new_count = 1
            self.user_counters[user_uid] = {"count": new_count, "reset_day_identifier": current_day_id}
        
        return new_count

# Initially, RateLimiter points to the InMemory implementation
RateLimiter = InMemoryRateLimiter

if settings.REDIS_URL:
    try:
        import redis.asyncio as redis_async # Use asyncio version of redis library
        print("INFO: [RateLimiter] Redis URL is set. Attempting to use RedisRateLimiter.")

        class RedisRateLimiterImpl(InMemoryRateLimiter): # Inherit for shared methods like _get_quota_for_tier
            _redis_client: Optional[redis_async.Redis] = None
            _key_prefix = "jobhunter_rl:"

            @classmethod
            async def get_client(cls) -> Optional[redis_async.Redis]:
                if cls._redis_client is None:
                    try:
                        print(f"INFO: [RateLimiter] Connecting to Redis at {settings.REDIS_URL}")
                        cls._redis_client = redis_async.from_url(settings.REDIS_URL)
                        await cls._redis_client.ping()
                        print("INFO: [RateLimiter] Successfully connected to Redis.")
                    except Exception as e:
                        cls._redis_client = None
                        print(f"WARNING: [RateLimiter] Could not connect to Redis. Error: {e}. Will use in-memory fallback.")
                return cls._redis_client

            async def check_limit(self, user_uid: str, subscription_tier: str) -> Tuple[int, bool]:
                redis_client = await self.get_client()
                if not redis_client:
                    # print("DEBUG: [RedisRateLimiter] Falling back to InMemory for check_limit.")
                    return await super().check_limit(user_uid, subscription_tier)

                day_key = f"{self._key_prefix}u:{user_uid}:d:{self._get_current_day_identifier()}"
                count = 0
                try:
                    count_bytes = await redis_client.get(day_key)
                    count = int(count_bytes) if count_bytes is not None else 0
                except Exception as e:
                    print(f"WARNING: [RedisRateLimiter] Redis GET error: {e}. Falling back for check_limit.")
                    return await super().check_limit(user_uid, subscription_tier)

                quota_for_tier = self._get_quota_for_tier(subscription_tier)
                remaining = max(0, quota_for_tier - count)
                limit_reached = count >= quota_for_tier
                return remaining, limit_reached

            async def increment(self, user_uid: str, subscription_tier: str) -> int:
                redis_client = await self.get_client()
                if not redis_client:
                    # print("DEBUG: [RedisRateLimiter] Falling back to InMemory for increment.")
                    return await super().increment(user_uid, subscription_tier)

                day_key = f"{self._key_prefix}u:{user_uid}:d:{self._get_current_day_identifier()}"
                new_count = 0
                try:
                    async with redis_client.pipeline() as pipe: # Corrected pipeline usage
                        await pipe.incr(day_key)
                        await pipe.expire(day_key, 60 * 60 * 48) # 48 hours
                        results = await pipe.execute()
                    new_count = results[0] if results and isinstance(results[0], int) else 0
                except Exception as e:
                    print(f"WARNING: [RedisRateLimiter] Redis pipeline error: {e}. Falling back for increment.")
                    return await super().increment(user_uid, subscription_tier)
                return new_count
        
        # If Redis is configured and library is available, try to use it
        RateLimiter = RedisRateLimiterImpl
        print("INFO: [RateLimiter] RateLimiter implementation set to RedisRateLimiterImpl.")

    except ImportError:
        print("WARNING: [RateLimiter] 'redis.asyncio' library not found. Using in-memory rate limiter.")
    except Exception as e:
        print(f"WARNING: [RateLimiter] Error setting up RedisRateLimiter: {e}. Using in-memory rate limiter.")

# The RateLimiter that gets instantiated by `RateLimiter()` in your routes
# will now be the chosen implementation (InMemory or Redis).