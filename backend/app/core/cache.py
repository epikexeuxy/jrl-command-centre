"""TTL cache abstraction: Redis when REDIS_URL is set, in-process dict otherwise."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("app.cache")


class _MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl_seconds, value)


class _RedisCache:
    def __init__(self, url: str) -> None:
        import redis  # lazy import so the package stays optional at runtime

        self._client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=3)
        self._client.ping()

    def get(self, key: str) -> Any | None:
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:  # pragma: no cover - network dependent
            logger.warning("Redis GET failed; treating as cache miss", exc_info=True)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, json.dumps(value))
        except Exception:  # pragma: no cover
            logger.warning("Redis SET failed; value not cached", exc_info=True)


_cache_instance: Any = None


def get_cache():
    global _cache_instance
    if _cache_instance is None:
        settings = get_settings()
        if settings.REDIS_URL:
            try:
                _cache_instance = _RedisCache(settings.REDIS_URL)
                logger.info("Cache backend: redis")
            except Exception:
                logger.warning("Redis unavailable, using in-memory cache", exc_info=True)
                _cache_instance = _MemoryCache()
        else:
            _cache_instance = _MemoryCache()
    return _cache_instance
