"""
In-memory TTL cache for Wikipedia API calls.

Used by WikipediaEntityResolver and WikipediaMediaProvider to avoid repeated
calls on keystroke/query repetition. Configurable via env or constructor.
See WIKIPEDIA_CACHE_OPERATIONAL_LIMITS for recommended defaults.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# --- TTL defaults (seconds). Override via CINEMIND_WIKI_CACHE_* env vars. ---
CACHE_TTL_SEARCH = int(os.getenv("CINEMIND_WIKI_CACHE_TTL_SEARCH", "3600"))  # 1h
CACHE_TTL_CATEGORIES = int(os.getenv("CINEMIND_WIKI_CACHE_TTL_CATEGORIES", "3600"))  # 1h
CACHE_TTL_PAGEIMAGE = int(os.getenv("CINEMIND_WIKI_CACHE_TTL_PAGEIMAGE", "86400"))  # 24h
CACHE_TTL_ENRICH = int(os.getenv("CINEMIND_WIKI_CACHE_TTL_ENRICH", "1800"))  # 30m
CACHE_TTL_TMDB_POSTER = int(os.getenv("CINEMIND_WIKI_CACHE_TTL_TMDB_POSTER", "86400"))  # 24h
CACHE_MAX_ENTRIES = int(os.getenv("CINEMIND_WIKI_CACHE_MAX_ENTRIES", "500"))


def _normalize_search_key(query: str) -> str:
    """Normalize search query for cache key: collapse whitespace, strip, lowercase."""
    if not query or not isinstance(query, str):
        return ""
    return " ".join(query.split()).strip().lower()


def _normalize_page_title_key(title: str) -> str:
    """Normalize page title for cache key: canonical form (spaces→underscores, trim)."""
    if not title or not isinstance(title, str):
        return ""
    return title.replace(" ", "_").strip()


def _normalize_categories_key(titles: list[str]) -> str:
    """Normalize title list for categories cache key: sorted, pipe-joined."""
    if not titles:
        return ""
    normalized = sorted(_normalize_page_title_key(t) for t in titles if t)
    return "|".join(normalized)


def _normalize_tmdb_poster_key(title: str, year: Optional[int]) -> str:
    """Normalize (title, year) for TMDB poster cache key. Consistent with enrich key style."""
    t = (title or "").strip().lower()
    t = " ".join(t.split())
    y = (str(year) if year is not None else "")
    return f"{t}|{y}"


class TTLCache:
    """
    Thread-safe in-memory TTL cache with optional max size (LRU eviction).
    """

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES):
        self._max_entries = max(1, max_entries)
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()
        self._access_order: list[str] = []

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if present and not expired, else None."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return None
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store value with TTL. Evict oldest if at capacity."""
        with self._lock:
            self._evict_if_needed()
            expiry = time.monotonic() + ttl_seconds
            self._cache[key] = (value, expiry)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def _evict_if_needed(self) -> None:
        """Remove oldest entries if over max_entries."""
        while len(self._cache) >= self._max_entries and self._access_order:
            oldest = self._access_order.pop(0)
            if oldest in self._cache:
                del self._cache[oldest]

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()


class WikipediaCache:
    """
    Shared cache for Wikipedia API responses.
    Cache keys are normalized; failures are cached as None/sentinel to avoid retry storms.
    """

    def __init__(
        self,
        ttl_search: int = CACHE_TTL_SEARCH,
        ttl_categories: int = CACHE_TTL_CATEGORIES,
        ttl_pageimage: int = CACHE_TTL_PAGEIMAGE,
        ttl_tmdb_poster: int = CACHE_TTL_TMDB_POSTER,
        max_entries: int = CACHE_MAX_ENTRIES,
    ):
        self._cache = TTLCache(max_entries=max_entries)
        self._ttl_search = ttl_search
        self._ttl_categories = ttl_categories
        self._ttl_pageimage = ttl_pageimage
        self._ttl_tmdb_poster = ttl_tmdb_poster

    def get_search(self, query: str) -> Optional[list]:
        """Get cached search results. Returns None if miss or expired."""
        key = "search:" + _normalize_search_key(query)
        return self._cache.get(key)

    def set_search(self, query: str, results: list) -> None:
        """Cache search results."""
        key = "search:" + _normalize_search_key(query)
        self._cache.set(key, results, self._ttl_search)

    def get_categories(self, titles: list[str]) -> Optional[dict]:
        """Get cached categories map. Returns None if miss or expired."""
        key = "cat:" + _normalize_categories_key(titles)
        return self._cache.get(key)

    def set_categories(self, titles: list[str], data: dict) -> None:
        """Cache categories map."""
        key = "cat:" + _normalize_categories_key(titles)
        self._cache.set(key, data, self._ttl_categories)

    # Sentinel: cached "no image" result to avoid repeated failed lookups
    _NO_IMAGE = "__NO_IMAGE__"

    def get_pageimage(self, page_title: str) -> tuple[Optional[str], bool]:
        """
        Get cached page image URL.
        Returns (url_or_none, hit).
        - hit=False: cache miss, caller should fetch.
        - hit=True: use url_or_none (None means we cached no-image).
        """
        key = "img:" + _normalize_page_title_key(page_title)
        val = self._cache.get(key)
        if val is None:
            return (None, False)
        return (None if val == self._NO_IMAGE else val, True)

    def set_pageimage(self, page_title: str, url: Optional[str]) -> None:
        """Cache page image URL. Use _NO_IMAGE for no-image to avoid re-fetch."""
        key = "img:" + _normalize_page_title_key(page_title)
        self._cache.set(key, url if url else self._NO_IMAGE, self._ttl_pageimage)

    # TMDB poster URL cache (title + year) — reduces repeated TMDB calls on cache hits
    _NO_POSTER = "__NO_POSTER__"

    def get_tmdb_poster(self, title: str, year: Optional[int]) -> tuple[Optional[str], bool]:
        """
        Get cached TMDB poster URL for (title, year).
        Returns (url_or_none, hit). hit=True and url_or_none=None means we cached no-poster.
        """
        key = "tmdb_poster:" + _normalize_tmdb_poster_key(title, year)
        val = self._cache.get(key)
        if val is None:
            return (None, False)
        return (None if val == self._NO_POSTER else val, True)

    def set_tmdb_poster(self, title: str, year: Optional[int], url: Optional[str]) -> None:
        """Cache TMDB poster URL (or no-poster sentinel) for (title, year)."""
        key = "tmdb_poster:" + _normalize_tmdb_poster_key(title, year)
        self._cache.set(key, url if url else self._NO_POSTER, self._ttl_tmdb_poster)

    def get_enrich(self, query_key: str) -> Optional[Any]:
        """Get cached full enrich result. Returns None if miss/expired."""
        key = "enrich:" + query_key
        return self._cache.get(key)

    def set_enrich(self, query_key: str, result: Any, ttl: int = CACHE_TTL_ENRICH) -> None:
        """Cache full enrich result."""
        key = "enrich:" + query_key
        self._cache.set(key, result, ttl)


# Module-level shared cache instance for enrichment layer
_default_cache: Optional[WikipediaCache] = None


def get_default_wikipedia_cache() -> WikipediaCache:
    """Return shared Wikipedia cache (lazy init)."""
    global _default_cache
    if _default_cache is None:
        _default_cache = WikipediaCache()
    return _default_cache


def set_default_wikipedia_cache(cache: Optional[WikipediaCache]) -> None:
    """Set shared cache (for testing)."""
    global _default_cache
    _default_cache = cache


# --- Operational limits and recommended defaults ---
WIKIPEDIA_CACHE_OPERATIONAL_LIMITS = """
Wikipedia cache — operational limits and TTL defaults

TTLs (seconds):
  - Search:       3600 (1h)   — search results change slowly
  - Categories:   3600 (1h)   — category metadata is stable
  - Page images:  86400 (24h) — poster images rarely change
  - Enrich result: 1800 (30m) — base enrichment by query (Wikipedia resolution)
  - TMDB poster:  86400 (24h) — poster URLs by (title, year) to reduce TMDB calls on cache hits

Override via env:
  CINEMIND_WIKI_CACHE_TTL_SEARCH
  CINEMIND_WIKI_CACHE_TTL_CATEGORIES
  CINEMIND_WIKI_CACHE_TTL_PAGEIMAGE
  CINEMIND_WIKI_CACHE_TTL_ENRICH
  CINEMIND_WIKI_CACHE_TTL_TMDB_POSTER
  CINEMIND_WIKI_CACHE_MAX_ENTRIES (default 500)

Cache key normalization:
  - Search: lowercase, collapse whitespace, trim
  - Page title: spaces→underscores, trim
  - Categories: sorted pipe-joined titles

Failure handling: timeouts/errors do not cache; next request will retry.
No-image results are cached to avoid repeated failed lookups.
"""
