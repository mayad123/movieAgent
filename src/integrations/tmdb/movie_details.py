"""
TMDB movie details + credits normalization for the "Movie Details" modal.

Design goals:
- Server-side only deterministic normalization helpers.
- Must not raise: return a minimal payload (tmdbId-only) on any failure.
- Provide graceful fallbacks so the frontend never gets stuck.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from typing import Any, Optional

from config import get_tmdb_access_token, is_tmdb_enabled
from integrations.tmdb.image_config import (
    build_image_url,
    get_config,
    SIZE_BACKDROP_GALLERY,
    SIZE_POSTER_GALLERY,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
YEAR_RE = re.compile(r"^\s*(\d{4})")


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


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _safe_year(release_date: Any) -> Optional[int]:
    s = _safe_str(release_date)
    if not s:
        return None
    m = YEAR_RE.match(s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


def _fetch_json(url: str, token: str, timeout: float = 6.0) -> Any:
    token = _safe_str(token)
    if not token:
        return None
    try:
        req = urllib.request.Request(url, headers=_bearer_headers(token))
        with urllib.request.urlopen(req, timeout=max(1.0, timeout)) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug("TMDB request failed (%s): %s", url, e)
        return None


def _build_primary_and_backdrop(
    *,
    poster_path: Any,
    backdrop_path: Any,
    token: str,
) -> tuple[str, str]:
    cfg = get_config(token)
    primary = build_image_url(str(poster_path or ""), SIZE_POSTER_GALLERY, cfg) if poster_path else ""
    backdrop = build_image_url(str(backdrop_path or ""), SIZE_BACKDROP_GALLERY, cfg) if backdrop_path else ""
    return primary, backdrop


def _map_details(movie: dict[str, Any], *, token: str) -> dict[str, Any]:
    title = movie.get("title")
    release_date = movie.get("release_date")
    year = _safe_year(release_date)

    genres_out: list[str] = []
    genres = movie.get("genres") or []
    if isinstance(genres, list):
        for g in genres:
            if isinstance(g, dict) and _safe_str(g.get("name")):
                genres_out.append(str(g.get("name")).strip())

    spoken_languages = movie.get("spoken_languages") or []
    language: Optional[str] = None
    if isinstance(spoken_languages, list) and spoken_languages:
        first = spoken_languages[0]
        if isinstance(first, dict):
            language = _safe_str(first.get("english_name")) or _safe_str(first.get("iso_639_1"))
            language = language or None

    production_countries = movie.get("production_countries") or []
    country: Optional[str] = None
    if isinstance(production_countries, list) and production_countries:
        first = production_countries[0]
        if isinstance(first, dict):
            country = _safe_str(first.get("name")) or None

    runtime = movie.get("runtime")
    rating = movie.get("vote_average")
    vote_count = movie.get("vote_count")

    # Images
    primary_image_url, backdrop_url = _build_primary_and_backdrop(
        poster_path=movie.get("poster_path"),
        backdrop_path=movie.get("backdrop_path"),
        token=token,
    )

    return {
        "movie_title": _safe_str(title) or None,
        "year": year,
        "tagline": _safe_str(movie.get("tagline")) or None,
        "overview": _safe_str(movie.get("overview")) or None,
        "runtime_minutes": _safe_int(runtime),
        "genres": genres_out or None,
        "release_date": _safe_str(release_date) or None,
        "language": language,
        "country": country,
        "rating": float(rating) if rating is not None and _safe_str(rating) != "" else None,
        "vote_count": _safe_int(vote_count),
        "primary_image_url": primary_image_url or None,
        "backdrop_url": backdrop_url or None,
    }


def _map_credits(credits: dict[str, Any]) -> dict[str, Any]:
    directors: list[str] = []
    cast: list[str] = []

    crew = credits.get("crew") or []
    if isinstance(crew, list):
        for item in crew:
            if not isinstance(item, dict):
                continue
            if item.get("job") == "Director":
                name = _safe_str(item.get("name"))
                if name:
                    directors.append(name)

    cast_items = credits.get("cast") or []
    if isinstance(cast_items, list):
        for item in cast_items:
            if not isinstance(item, dict):
                continue
            name = _safe_str(item.get("name"))
            if name:
                cast.append(name)

    # Keep payload small and UI-friendly.
    return {
        "directors": directors[:10] or None,
        "cast": cast[:50] or None,
    }


def _map_related_results(
    similar_data: Any,
    *,
    token: str,
    tmdb_id: int,
    limit: int = 12,
) -> list[dict[str, Any]]:
    if not isinstance(similar_data, dict):
        return []
    results = similar_data.get("results") or []
    if not isinstance(results, list):
        return []

    cfg = get_config(token)
    out: list[dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        rid = _safe_int(r.get("id"))
        if rid is None:
            continue
        title = _safe_str(r.get("title")) or _safe_str(r.get("name"))
        if not title:
            continue
        year = _safe_year(r.get("release_date"))
        poster_path = r.get("poster_path")
        primary_image_url = (
            build_image_url(str(poster_path or ""), SIZE_POSTER_GALLERY, cfg) if poster_path else ""
        )
        item = {
            "movie_title": title,
            "year": year,
            "tmdbId": rid,
            "primary_image_url": primary_image_url or None,
        }
        out.append(item)
        if len(out) >= max(0, int(limit)):
            break
    return out


def build_movie_details_payload(
    tmdb_id: Any,
    *,
    token: Optional[str] = None,
    timeout: float = 6.0,
    include_related: bool = True,
) -> dict[str, Any]:
    """
    Return a payload compatible with `MovieDetailsResponse`.
    Never raises; returns at least {"tmdbId": <int>}.
    """

    mid = _safe_int(tmdb_id)
    if mid is None:
        return {"tmdbId": 0}

    if not is_tmdb_enabled():
        return {"tmdbId": mid}

    use_token = token if token is not None else (get_tmdb_access_token() or "")
    use_token = _safe_str(use_token)
    if not use_token:
        return {"tmdbId": mid}

    try:
        details = _fetch_json(f"{BASE_URL}/movie/{mid}", use_token, timeout=timeout)
        credits = _fetch_json(f"{BASE_URL}/movie/{mid}/credits", use_token, timeout=timeout)

        if not isinstance(details, dict):
            details = {}
        if not isinstance(credits, dict):
            credits = {}

        mapped = {}
        mapped.update(_map_details(details, token=use_token) if details else {})
        mapped.update(_map_credits(credits) if credits else {})

        payload: dict[str, Any] = {"tmdbId": mid}
        payload.update(mapped)

        if include_related:
            similar = _fetch_json(f"{BASE_URL}/movie/{mid}/similar", use_token, timeout=timeout)
            related = _map_related_results(similar, token=use_token, tmdb_id=mid, limit=12)
            payload["relatedMovies"] = related or None

        return payload
    except Exception as e:
        logger.debug("build_movie_details_payload failed for %s: %s", mid, e)
        return {"tmdbId": mid}


__all__ = ["build_movie_details_payload"]

