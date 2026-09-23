import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import HTTPException, Request

from services.cache_service import get_redis
from core.config import RATE_LIMIT_ENABLED, TRUST_PROXY
from core.utils import logger

_local_hits: dict = defaultdict(deque)


def client_ip(request: Request) -> str:
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _hit(key: str, limit: int, window: int) -> int:
    """Records a hit and returns seconds until the window frees up (0 = allowed)."""
    client = get_redis()
    if client is not None:
        try:
            redis_key = f"hireai:rl:{key}"
            count = client.incr(redis_key)
            if count == 1:
                client.expire(redis_key, window)
            if count > limit:
                return max(client.ttl(redis_key), 1)
            return 0
        except Exception:
            pass
    now = time.time()
    hits = _local_hits[key]
    while hits and hits[0] <= now - window:
        hits.popleft()
    if len(hits) >= limit:
        return max(int(hits[0] + window - now) + 1, 1)
    hits.append(now)
    return 0


def enforce(name: str, ident, limit: int, window_seconds: int) -> None:
    if not RATE_LIMIT_ENABLED:
        return
    retry_after = _hit(f"{name}:{ident}", limit, window_seconds)
    if retry_after:
        logger.warning(f"rate limit hit: {name} ident={ident}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )


def ip_limit(name: str, limit: int, window_seconds: int) -> Callable:
    """FastAPI dependency limiting by caller address. Use on public and auth
    endpoints. Per-user limits live in deps.py because they need the user."""

    async def dependency(request: Request):
        enforce(name, client_ip(request), limit, window_seconds)

    return dependency
