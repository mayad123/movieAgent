"""
TMDB image configuration fetch, cache, and URL building (no hardcoded base URLs).

Fetches /configuration once (or when cache expires), caches base_url and supported
sizes, and provides a centralized URL builder for posters vs backdrops/scenes.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
CONFIG_PATH = "/configuration"

# Fallbacks when config is unavailable (per TMDB docs; avoid hardcoding elsewhere).
FALLBACK_SECURE_BASE = "https://image.tmdb.org/t/p/"
FALLBACK_BACKDROP_SIZE = "w780"
FALLBACK_POSTER_THUMB_SIZE = "w185"
FALLBACK_POSTER_GALLERY_SIZE = "w500"

# Centralized size keys for UI needs (thumbnail vs gallery).
# Poster: small UI thumbnails vs larger gallery.
# Backdrop: wider images for scenes/gallery.
SIZE_POSTER_THUMBNAIL = "poster_thumbnail"
SIZE_POSTER_GALLERY = "poster_gallery"
SIZE_BACKDROP_GALLERY = "backdrop_gallery"
SIZE_BACKDROP_ORIGINAL = "backdrop_original"

# Preferred size when multiple exist (order of preference).
PREFERRED_BACKDROP_SIZES = ["w780", "w1280", "w300", "original"]
PREFERRED_POSTER_THUMB_SIZES = ["w185", "w154", "w92"]
PREFERRED_POSTER_GALLERY_SIZES = ["w500", "w342", "w780", "original"]

# Default TTL 24 hours (TMDB configuration rarely changes).
DEFAULT_CONFIG_TTL_SECONDS = 86400


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


@dataclass
class TMDBImageConfig:
    """Cached image configuration from TMDB /configuration."""
    secure_base_url: str = FALLBACK_SECURE_BASE
    backdrop_sizes: list[str] = field(default_factory=lambda: [FALLBACK_BACKDROP_SIZE])
    poster_sizes: list[str] = field(default_factory=lambda: [FALLBACK_POSTER_THUMB_SIZE])
    _size_cache: dict[str, str] = field(default_factory=dict, repr=False)

    def get_size(self, size_key: str) -> str:
        """Return the concrete size string (e.g. w780) for a size key. Cached per key."""
        if size_key in self._size_cache:
            return self._size_cache[size_key]
        if size_key == SIZE_POSTER_THUMBNAIL:
            size = self._pick_first_of(self.poster_sizes, PREFERRED_POSTER_THUMB_SIZES) or FALLBACK_POSTER_THUMB_SIZE
        elif size_key == SIZE_POSTER_GALLERY:
            size = self._pick_first_of(self.poster_sizes, PREFERRED_POSTER_GALLERY_SIZES) or FALLBACK_POSTER_GALLERY_SIZE
        elif size_key == SIZE_BACKDROP_GALLERY:
            size = self._pick_first_of(self.backdrop_sizes, PREFERRED_BACKDROP_SIZES) or FALLBACK_BACKDROP_SIZE
        elif size_key == SIZE_BACKDROP_ORIGINAL:
            size = "original" if "original" in self.backdrop_sizes else (self.backdrop_sizes[-1] if self.backdrop_sizes else FALLBACK_BACKDROP_SIZE)
        else:
            size = FALLBACK_BACKDROP_SIZE
        self._size_cache[size_key] = size
        return size

    @staticmethod
    def _pick_first_of(available: list[str], preferred: list[str]) -> Optional[str]:
        for p in preferred:
            if p in (available or []):
                return p
        return available[0] if available else None


_cache: Optional[tuple[TMDBImageConfig, float]] = None
_cache_lock = threading.Lock()


def fetch_config(access_token: str, timeout: float = 10.0) -> TMDBImageConfig:
    """
    Call TMDB GET /configuration and return parsed image config.
    Does not use cache; for cached access use get_config().
    """
    config = TMDBImageConfig()
    if not access_token:
        return config
    try:
        url = f"{BASE_URL}{CONFIG_PATH}"
        req = urllib.request.Request(url, headers=_bearer_headers(access_token))
        with urllib.request.urlopen(req, timeout=max(1.0, timeout)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        images = (data or {}).get("images") or {}
        base = (images.get("secure_base_url") or images.get("base_url") or "").strip()
        if base and not base.endswith("/"):
            base += "/"
        if base:
            config.secure_base_url = base
        backs = images.get("backdrop_sizes")
        if isinstance(backs, list) and backs:
            config.backdrop_sizes = [str(s) for s in backs]
        posts = images.get("poster_sizes")
        if isinstance(posts, list) and posts:
            config.poster_sizes = [str(s) for s in posts]
    except Exception as e:
        logger.debug("TMDB configuration fetch failed: %s", e)
    return config


def get_config(
    access_token: str,
    timeout: float = 10.0,
    ttl_seconds: float = DEFAULT_CONFIG_TTL_SECONDS,
) -> TMDBImageConfig:
    """
    Return cached TMDB image configuration, or fetch and cache it.
    Thread-safe; TTL-based cache invalidation.
    """
    global _cache
    now = time.monotonic()
    with _cache_lock:
        if _cache is not None:
            cached_config, cached_at = _cache
            if (now - cached_at) < ttl_seconds:
                return cached_config
        config = fetch_config(access_token, timeout=timeout)
        _cache = (config, now)
    return config


def build_image_url(
    file_path: str,
    size_key: str,
    config: Optional[TMDBImageConfig] = None,
) -> str:
    """
    Build full image URL from TMDB file_path and size key.

    Uses config if provided; otherwise uses fallback base URL and size for the key.
    file_path should be the path returned by TMDB (e.g. /abc.jpg); leading slash is handled.
    """
    path = (file_path or "").strip()
    if not path:
        return ""
    if path.startswith("http"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    base = (config.secure_base_url if config else FALLBACK_SECURE_BASE).rstrip("/") + "/"
    size = config.get_size(size_key) if config else _fallback_size_for_key(size_key)
    return f"{base}{size}{path}"


def _fallback_size_for_key(size_key: str) -> str:
    """When no config is available, return a safe default size per key."""
    if size_key == SIZE_POSTER_THUMBNAIL:
        return FALLBACK_POSTER_THUMB_SIZE
    if size_key == SIZE_POSTER_GALLERY:
        return FALLBACK_POSTER_GALLERY_SIZE
    if size_key in (SIZE_BACKDROP_GALLERY, SIZE_BACKDROP_ORIGINAL):
        return FALLBACK_BACKDROP_SIZE
    return FALLBACK_BACKDROP_SIZE


def clear_config_cache() -> None:
    """Clear the config cache (e.g. for tests)."""
    global _cache
    with _cache_lock:
        _cache = None


__all__ = [
    "TMDBImageConfig",
    "fetch_config",
    "get_config",
    "build_image_url",
    "clear_config_cache",
    "SIZE_POSTER_THUMBNAIL",
    "SIZE_POSTER_GALLERY",
    "SIZE_BACKDROP_GALLERY",
    "SIZE_BACKDROP_ORIGINAL",
]
