"""In-process TTL + LRU cache for TMDB resolve_movie results."""

from __future__ import annotations

import copy
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return max(minimum, int(raw))
    except Exception:
        return max(minimum, default)


# Override via env (seconds / max entries)
RESOLVE_CACHE_TTL = _env_int("CINEMIND_TMDB_RESOLVE_CACHE_TTL_SECONDS", 3600)
RESOLVE_CACHE_MAX = _env_int("CINEMIND_TMDB_RESOLVE_CACHE_MAX_ENTRIES", 2000)


class _TTLCache:
    """Thread-safe TTL cache with LRU eviction."""

    def __init__(self, max_entries: int) -> None:
        self._max_entries = max(1, max_entries)
        self._data: dict[str, tuple[Any, float]] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._expired = 0
        self._evictions = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            ent = self._data.get(key)
            if ent is None:
                self._misses += 1
                return None
            value, expiry = ent
            if time.monotonic() > expiry:
                del self._data[key]
                if key in self._order:
                    self._order.remove(key)
                self._expired += 1
                self._misses += 1
                return None
            if key in self._order:
                self._order.remove(key)
            self._order.append(key)
            self._hits += 1
            return copy.deepcopy(value)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            while len(self._data) >= self._max_entries and self._order:
                oldest = self._order.pop(0)
                if oldest in self._data:
                    del self._data[oldest]
                    self._evictions += 1
            expiry = time.monotonic() + ttl_seconds
            self._data[key] = (value, expiry)
            if key in self._order:
                self._order.remove(key)
            self._order.append(key)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._order.clear()
            self._hits = 0
            self._misses = 0
            self._expired = 0
            self._evictions = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._data),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "expired": self._expired,
                "evictions": self._evictions,
            }


_resolve_cache = _TTLCache(RESOLVE_CACHE_MAX)


def cache_key(
    title: str,
    year: int | None,
    min_confidence: float,
    min_score_gap: float,
    max_candidates: int,
) -> str:
    t = " ".join((title or "").strip().lower().split())
    y = "" if year is None else str(year)
    return f"{min_confidence}|{min_score_gap}|{max_candidates}|{t}|{y}"


def get_cached(key: str) -> Any | None:
    val = _resolve_cache.get(key)
    logger.debug("TMDB resolve_cache %s", "hit" if val is not None else "miss")
    return val


def set_cached(key: str, value: Any) -> None:
    _resolve_cache.set(key, value, RESOLVE_CACHE_TTL)


def clear_resolve_cache() -> None:
    _resolve_cache.clear()


def resolve_cache_stats() -> dict[str, int]:
    return _resolve_cache.stats()


__all__ = [
    "RESOLVE_CACHE_TTL",
    "cache_key",
    "clear_resolve_cache",
    "get_cached",
    "resolve_cache_stats",
    "set_cached",
]
