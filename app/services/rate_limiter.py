import time
from typing import Tuple, Optional
import os

from app.core.config import settings


class RateLimiter:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RateLimiter, cls).__new__(cls)
            # Initialize counter
            cls._instance.counter = 0
            cls._instance.reset_date = int(time.time() // 86400)  # Current day (in days since epoch)
            cls._instance.daily_quota = settings.DAILY_QUOTA
        return cls._instance
    
    async def check_limit(self) -> Tuple[int, bool]:
        """
        Check if the rate limit has been exceeded.
        Returns (remaining_requests, limit_reached)
        """
        # Check if we need to reset the counter (new day)
        current_day = int(time.time() // 86400)
        if current_day > self.reset_date:
            self.counter = 0
            self.reset_date = current_day
        
        # Calculate remaining requests
        remaining = max(0, self.daily_quota - self.counter)
        limit_reached = remaining <= 0
        
        return remaining, limit_reached
    
    async def increment(self) -> int:
        """
        Increment the request counter.
        Returns the new count.
        """
        self.counter += 1
        return self.counter


# If Redis is configured, use a Redis-based rate limiter instead
if settings.REDIS_URL:
    import redis
    
    class RedisRateLimiter:
        _instance = None
        
        def __new__(cls):
            if cls._instance is None:
                cls._instance = super(RedisRateLimiter, cls).__new__(cls)
                # Initialize Redis connection
                cls._instance.redis = redis.from_url(settings.REDIS_URL)
                cls._instance.daily_quota = settings.DAILY_QUOTA
                cls._instance.key_prefix = "jobhunter_cv_generator:"
            return cls._instance
        
        async def check_limit(self) -> Tuple[int, bool]:
            """
            Check if the rate limit has been exceeded.
            Returns (remaining_requests, limit_reached)
            """
            # Get current day key
            day_key = f"{self.key_prefix}counter:{int(time.time() // 86400)}"
            
            # Get current count
            count = int(self.redis.get(day_key) or 0)
            
            # Calculate remaining requests
            remaining = max(0, self.daily_quota - count)
            limit_reached = remaining <= 0
            
            return remaining, limit_reached
        
        async def increment(self) -> int:
            """
            Increment the request counter.
            Returns the new count.
            """
            # Get current day key
            day_key = f"{self.key_prefix}counter:{int(time.time() // 86400)}"
            
            # Increment the counter and set expiry (48 hours to be safe)
            pipe = self.redis.pipeline()
            pipe.incr(day_key)
            pipe.expire(day_key, 60 * 60 * 48)  # 48 hours in seconds
            result = pipe.execute()
            
            return result[0]  # New count
    
    # Replace the RateLimiter class with the Redis version
    RateLimiter = RedisRateLimiter