"""
In-memory TTL cache for media enrichment (TMDB poster URLs and enrich results).

Used by media_enrichment to avoid repeated TMDB calls on repeated queries.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return max(minimum, int(raw))
    except Exception:
        return max(minimum, default)


# --- TTL defaults (seconds). Override via CINEMIND_MEDIA_CACHE_* env vars. ---
CACHE_TTL_ENRICH = _env_int("CINEMIND_MEDIA_CACHE_TTL_ENRICH", 1800)  # 30m
CACHE_TTL_TMDB_POSTER = _env_int("CINEMIND_MEDIA_CACHE_TTL_TMDB_POSTER", 86400)  # 24h
CACHE_MAX_ENTRIES = _env_int("CINEMIND_MEDIA_CACHE_MAX_ENTRIES", 500)


def _normalize_enrich_key(query: str) -> str:
    if not query or not isinstance(query, str):
        return ""
    return " ".join((query or "").strip().lower().split())


def _normalize_tmdb_poster_key(title: str, year: Optional[int]) -> str:
    t = (title or "").strip().lower()
    t = " ".join(t.split())
    y = (str(year) if year is not None else "")
    return f"{t}|{y}"


class TTLCache:
    """Thread-safe in-memory TTL cache with optional max size (LRU eviction)."""

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES):
        self._max_entries = max(1, max_entries)
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()
        self._access_order: list[str] = []
        self._hits = 0
        self._misses = 0
        self._expired = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._expired += 1
                self._misses += 1
                return None
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._evict_if_needed()
            expiry = time.monotonic() + ttl_seconds
            self._cache[key] = (value, expiry)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def _evict_if_needed(self) -> None:
        while len(self._cache) >= self._max_entries and self._access_order:
            oldest = self._access_order.pop(0)
            if oldest in self._cache:
                del self._cache[oldest]
                self._evictions += 1

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._cache),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "expired": self._expired,
                "evictions": self._evictions,
            }


class MediaCache:
    """
    Cache for media enrichment: enrich results by query and TMDB poster URLs by (title, year).
    """

    _NO_POSTER = "__NO_POSTER__"

    def __init__(
        self,
        ttl_enrich: int = CACHE_TTL_ENRICH,
        ttl_tmdb_poster: int = CACHE_TTL_TMDB_POSTER,
        max_entries: int = CACHE_MAX_ENTRIES,
    ):
        self._cache = TTLCache(max_entries=max_entries)
        self._ttl_enrich = ttl_enrich
        self._ttl_tmdb_poster = ttl_tmdb_poster

    def get_enrich(self, query_key: str) -> Optional[Any]:
        key = "enrich:" + query_key
        val = self._cache.get(key)
        logger.debug("MediaCache enrich %s", "hit" if val is not None else "miss")
        return val

    def set_enrich(self, query_key: str, result: Any) -> None:
        key = "enrich:" + query_key
        self._cache.set(key, result, self._ttl_enrich)

    def get_tmdb_poster(self, title: str, year: Optional[int]) -> tuple[Optional[str], bool]:
        key = "tmdb_poster:" + _normalize_tmdb_poster_key(title, year)
        val = self._cache.get(key)
        if val is None:
            logger.debug("MediaCache tmdb_poster miss title=%r year=%s", (title or "")[:60], year)
            return (None, False)
        logger.debug("MediaCache tmdb_poster hit title=%r year=%s", (title or "")[:60], year)
        return (None if val == self._NO_POSTER else val, True)

    def set_tmdb_poster(self, title: str, year: Optional[int], url: Optional[str]) -> None:
        key = "tmdb_poster:" + _normalize_tmdb_poster_key(title, year)
        self._cache.set(key, url if url else self._NO_POSTER, self._ttl_tmdb_poster)

    def stats(self) -> dict[str, int]:
        return self._cache.stats()


_default_cache: Optional[MediaCache] = None


def get_default_media_cache() -> MediaCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = MediaCache()
    return _default_cache


def set_default_media_cache(cache: Optional[MediaCache]) -> None:
    global _default_cache
    _default_cache = cache
