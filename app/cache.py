"""Redis helpers. If Redis is missing or down, everything still works (just slower)."""
import time

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


_local: dict[str, tuple[int, float]] = {}  # key -> (count, window end); one per worker


def _local_limit(key: str, limit: int, window_seconds: int) -> bool:
    now = time.monotonic()
    if len(_local) > 10_000:  # keep memory bounded
        for k in [k for k, (_, end) in _local.items() if end <= now]:
            del _local[k]
    count, end = _local.get(key, (0, 0.0))
    if now >= end:
        count, end = 0, now + window_seconds
    _local[key] = (count + 1, end)
    return count + 1 <= limit


def rate_limit(key: str, limit: int, window_seconds: int, local_fallback: bool = False) -> bool:
    """Fixed-window limiter. Returns True if the request is allowed.

    Uses Redis. If Redis is unavailable it allows everything, unless ``local_fallback``
    is set (used for guarding passwords): then a per-process counter is used instead.
    """
    r = get_redis()
    if r is not None:
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, window_seconds)
            return count <= limit
        except redis.RedisError:
            pass
    return _local_limit(key, limit, window_seconds) if local_fallback else True
