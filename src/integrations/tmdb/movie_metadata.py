"""
TMDB movie metadata helpers for Sub-context Movie Hub filtering.

These helpers are deterministic, server-side only, and must not raise:
- return [] on any failure.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _fetch_json(url: str, token: str, timeout: float = 10.0) -> Any:
    token = (token or "").strip()
    if not token:
        return None
    try:
        req = urllib.request.Request(url, headers=_bearer_headers(token))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug("TMDB metadata fetch failed (%s): %s", url, e)
        return None


def fetch_movie_cast_names(movie_id: Any, token: str, *, max_names: int = 80) -> list[str]:
    """Return cast member names for `movie_id` using TMDB /movie/{id}/credits."""
    mid = _safe_int(movie_id)
    if mid is None:
        return []
    url = f"{BASE_URL}/movie/{mid}/credits"
    data = _fetch_json(url, token)
    if not isinstance(data, dict):
        return []
    cast = data.get("cast") or []
    if not isinstance(cast, list):
        return []
    names: list[str] = []
    for item in cast:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        names.append(str(name))
        if len(names) >= max_names:
            break
    return names


def fetch_movie_genre_names(movie_id: Any, token: str) -> list[str]:
    """Return genre names for `movie_id` using TMDB /movie/{id}."""
    mid = _safe_int(movie_id)
    if mid is None:
        return []
    url = f"{BASE_URL}/movie/{mid}"
    data = _fetch_json(url, token)
    if not isinstance(data, dict):
        return []
    genres = data.get("genres") or []
    if not isinstance(genres, list):
        return []
    out: list[str] = []
    for g in genres:
        if isinstance(g, dict) and g.get("name"):
            out.append(str(g["name"]))
    return out


def fetch_movie_keyword_names(movie_id: Any, token: str) -> list[str]:
    """Return keyword names for `movie_id` using TMDB /movie/{id}/keywords."""
    mid = _safe_int(movie_id)
    if mid is None:
        return []
    url = f"{BASE_URL}/movie/{mid}/keywords"
    data = _fetch_json(url, token)
    if not isinstance(data, dict):
        return []
    keywords = data.get("keywords") or []
    if not isinstance(keywords, list):
        return []
    out: list[str] = []
    for kw in keywords:
        if isinstance(kw, dict) and kw.get("name"):
            out.append(str(kw["name"]))
    return out

