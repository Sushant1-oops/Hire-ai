import json
import time
from typing import Any, Optional

from core.config import REDIS_URL
from core.utils import logger

_redis = None
_redis_failed = False


def get_redis():
    """Shared Redis client, or None when REDIS_URL is unset or unreachable.
    Every caller treats None as "run without Redis" so local dev needs nothing."""
    global _redis, _redis_failed
    if not REDIS_URL or _redis_failed:
        return None
    if _redis is None:
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
            client.ping()
            _redis = client
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}); falling back to in-process cache/queue")
            _redis_failed = True
            return None
    return _redis


class Cache:
    """JSON cache with a namespace and TTL. Redis-backed when configured (so it
    is shared across API replicas), otherwise an in-process dict. Best effort:
    a Redis error degrades to a cache miss, never to a failed request."""

    def __init__(self, namespace: str, ttl_seconds: int):
        self.namespace = namespace
        self.ttl = ttl_seconds
        self._local: dict = {}

    def _key(self, key: str) -> str:
        return f"hireai:{self.namespace}:{key}"

    def get(self, key: str) -> Optional[Any]:
        client = get_redis()
        if client is not None:
            try:
                raw = client.get(self._key(key))
                return json.loads(raw) if raw is not None else None
            except Exception:
                return None
        entry = self._local.get(key)
        if not entry:
            return None
        value, expires = entry
        if expires < time.time():
            self._local.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        client = get_redis()
        if client is not None:
            try:
                client.setex(self._key(key), self.ttl, json.dumps(value, default=str))
            except Exception:
                pass
            return
        self._local[key] = (value, time.time() + self.ttl)

    def delete(self, key: str) -> None:
        client = get_redis()
        if client is not None:
            try:
                client.delete(self._key(key))
            except Exception:
                pass
            return
        self._local.pop(key, None)
