"""Redis helpers. If Redis is missing or down, everything still works (just slower)."""
import redis

from .config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    if not settings.redis_url:
        return None
    _client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    return _client


def cache_get(key: str) -> str | None:
    r = get_redis()
    if r is None:
        return None
    try:
        return r.get(key)
    except redis.RedisError:
        return None


def cache_set(key: str, value: str, ttl: int) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.set(key, value, ex=ttl)
    except redis.RedisError:
        pass


def cache_delete(key: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(key)
    except redis.RedisError:
        pass


def rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Fixed-window limiter. Returns True if the request is allowed."""
    r = get_redis()
    if r is None:
        return True
    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, window_seconds)
        return count <= limit
    except redis.RedisError:
        return True
