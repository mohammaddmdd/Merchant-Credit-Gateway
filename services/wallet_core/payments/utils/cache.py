"""
Lightweight Redis-backed caching and rate-limiting helpers.
Relies on the existing `redis` Python package which is already in requirements.
"""

from __future__ import annotations
import os
import time
import redis

# Initialize a Redis connection using REDIS_URL or default to the docker-compose service
_redis = redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'), decode_responses=True)

def cache_get(key: str) -> str | None:
    """Return cached string or None."""
    return _redis.get(key)

def cache_set(key: str, value: str, ttl_sec: int) -> None:
    """Set a cache key with TTL."""
    _redis.setex(key, ttl_sec, value)

def cache_del(key: str) -> None:
    """Delete a cache key if exists."""
    _redis.delete(key)

def rate_limit_allow(key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    """
    Token-bucket style rate limiting using Redis. Returns a tuple:
    (allowed: bool, remaining: int).
    Uses a simple counter per window bucket (current epoch/window).
    """
    now = int(time.time())
    bucket = now // window_seconds
    rkey = f"rl:{key}:{bucket}"
    pipe = _redis.pipeline()
    pipe.incr(rkey, 1)
    pipe.expire(rkey, window_seconds + 2)
    count, _ = pipe.execute()
    remaining = max(0, max_requests - int(count))
    return count <= max_requests, remaining