"""
TMDB movie metadata helpers for Sub-context Movie Hub filtering.

These helpers are deterministic, server-side only, and must not raise:
- return [] on any failure (bad token, network, malformed JSON)
- Parse TMDB JSON into deterministic lists

Uses shared httpx pooling via http_client. Prefer fetch_movie_filter_bundle for one RTT
(genres + cast + keywords) via append_to_response.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from .http_client import tmdb_request_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"


def _env_float(name: str, default: float, *, minimum: float = 1.0) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return max(minimum, float(raw))
    except Exception:
        return max(minimum, default)


# Short memo so sequential fetch_movie_genre_names + fetch_movie_cast_names share one HTTP call.
_bundle_memo: dict[int, tuple[dict[str, Any], float]] = {}
_bundle_lock = threading.Lock()
BUNDLE_MEMO_TTL_SECONDS = _env_float("CINEMIND_TMDB_METADATA_BUNDLE_MEMO_TTL_SECONDS", 300.0)
_bundle_hits = 0
_bundle_misses = 0
_bundle_evictions = 0


def _safe_int(x: Any) -> int | None:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def clear_movie_metadata_bundle_cache() -> None:
    """Clear in-process bundle memo (tests)."""
    global _bundle_hits, _bundle_misses, _bundle_evictions
    with _bundle_lock:
        _bundle_memo.clear()
        _bundle_hits = 0
        _bundle_misses = 0
        _bundle_evictions = 0


def movie_metadata_bundle_stats() -> dict[str, int]:
    with _bundle_lock:
        return {
            "size": len(_bundle_memo),
            "hits": _bundle_hits,
            "misses": _bundle_misses,
            "expired": _bundle_evictions,
        }


def fetch_movie_filter_bundle(
    movie_id: Any,
    token: str,
    *,
    timeout: float = 10.0,
) -> dict[str, Any] | None:
    """
    Single GET /movie/{id}?append_to_response=credits,keywords.

    Returns:
      {"genres": list[str], "cast": list[str], "keywords": list[str]}
    or None on failure.
    """
    mid = _safe_int(movie_id)
    if mid is None:
        return None
    url = f"{BASE_URL}/movie/{mid}?append_to_response=credits%2Ckeywords"
    data = tmdb_request_json(url, token, timeout=timeout, log_label="TMDB_movie_bundle")
    if not isinstance(data, dict):
        return None

    genres: list[str] = []
    for g in data.get("genres") or []:
        if isinstance(g, dict) and g.get("name"):
            genres.append(str(g["name"]))

    credits = data.get("credits") if isinstance(data.get("credits"), dict) else {}
    cast_raw = credits.get("cast") if isinstance(credits.get("cast"), list) else []
    cast_names: list[str] = []
    if isinstance(cast_raw, list):
        for item in cast_raw:
            if isinstance(item, dict) and item.get("name"):
                cast_names.append(str(item["name"]))
                if len(cast_names) >= 80:
                    break

    kw_block = data.get("keywords") if isinstance(data.get("keywords"), dict) else {}
    kws = kw_block.get("keywords") if isinstance(kw_block.get("keywords"), list) else []
    keyword_names: list[str] = []
    if isinstance(kws, list):
        for kw in kws:
            if isinstance(kw, dict) and kw.get("name"):
                keyword_names.append(str(kw["name"]))

    return {"genres": genres, "cast": cast_names, "keywords": keyword_names}


def _memoized_bundle(movie_id: Any, token: str) -> dict[str, Any] | None:
    global _bundle_hits, _bundle_misses, _bundle_evictions
    mid = _safe_int(movie_id)
    if mid is None:
        return None
    now = time.monotonic()
    with _bundle_lock:
        ent = _bundle_memo.get(mid)
        if ent:
            data, exp = ent
            if now < exp:
                _bundle_hits += 1
                logger.debug("TMDB bundle_memo hit movie_id=%s", mid)
                return data
            _bundle_evictions += 1
        _bundle_misses += 1
        logger.debug("TMDB bundle_memo miss movie_id=%s", mid)
        fresh = fetch_movie_filter_bundle(mid, token)
        if fresh:
            _bundle_memo[mid] = (fresh, now + BUNDLE_MEMO_TTL_SECONDS)
            return fresh
        return None


def fetch_movie_cast_names(movie_id: Any, token: str, *, max_names: int = 80) -> list[str]:
    """Return cast member names for `movie_id` (append_to_response bundle)."""
    b = _memoized_bundle(movie_id, token)
    if not b:
        return []
    names = list(b.get("cast") or [])
    return names[: max(0, max_names)]


def fetch_movie_genre_names(movie_id: Any, token: str) -> list[str]:
    """Return genre names for `movie_id` (append_to_response bundle)."""
    b = _memoized_bundle(movie_id, token)
    if not b:
        return []
    return list(b.get("genres") or [])


def fetch_movie_keyword_names(movie_id: Any, token: str) -> list[str]:
    """Return keyword names for `movie_id` (append_to_response bundle)."""
    b = _memoized_bundle(movie_id, token)
    if not b:
        return []
    return list(b.get("keywords") or [])


__all__ = [
    "clear_movie_metadata_bundle_cache",
    "fetch_movie_cast_names",
    "fetch_movie_filter_bundle",
    "fetch_movie_genre_names",
    "fetch_movie_keyword_names",
    "movie_metadata_bundle_stats",
]
