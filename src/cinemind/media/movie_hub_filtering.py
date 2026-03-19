"""
Deterministic filtering for Sub-context Movie Hub candidates.

Input:
- candidate clusters (same shape as SimilarMoviesResponse.clusters)
- user question (with the hub context marker stripped)

Output:
- clusters narrowed/re-ranked to match recognized constraints
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from config import get_tmdb_access_token, is_tmdb_enabled

from integrations.tmdb.movie_metadata import (
    fetch_movie_cast_names,
    fetch_movie_genre_names,
    fetch_movie_keyword_names,
)


def _norm_text(s: Any) -> str:
    t = (s or "")
    return re.sub(r"[^a-z0-9]+", " ", str(t).lower()).strip()


def extract_actor_constraint(question: str) -> Optional[str]:
    """
    Extract an actor name from patterns like:
    - "which movies star leonardo dicaprio?"
    - "movies starring Tom Hanks"
    """
    if not question:
        return None
    q = question.strip()
    q_lower = q.lower()

    # Capture after "star/stars/starring" until the first punctuation or end.
    m = re.search(r"\b(?:star|stars|starring)\b\s+([^?!.]+)", q_lower, flags=re.IGNORECASE)
    if not m:
        return None
    actor = m.group(1).strip()
    # Drop leading determiners if the regex captured them.
    actor = re.sub(r"^(the|a|an)\s+", "", actor).strip()
    if not actor:
        return None
    return actor


def extract_horror_constraint(question: str) -> Tuple[bool, bool]:
    """
    Returns (include_horror, exclude_horror).
    - include_horror: question implies positive interest in horror/scary
    - exclude_horror: question implies "not scary"/"not horror"
    """
    if not question:
        return (False, False)
    q = question.lower()

    exclude = bool(re.search(r"\b(?:not\s+scary|aren't\s+scary|arent\s+scary|not\s+horror|no\s+horror)\b", q))
    include = bool(re.search(r"\b(?:scary|horror)\b", q)) and not exclude
    return (include, exclude)


def extract_like_movie_title(question: str) -> Optional[str]:
    """
    Extract a referenced movie title from patterns like:
    - "What movies like Scary Movie?"
    - "Movies like 'Scary Movie'?"
    """
    if not question:
        return None
    q = question.strip()
    # Capture the text right after "like" until the next common end delimiter.
    m = re.search(r"\blike\s+['\"]?([^?!.]+?)['\"]?(?=\s*\?|$)", q, flags=re.IGNORECASE)
    if not m:
        # Fallback: allow end-of-string without requiring '?'.
        m = re.search(r"\blike\s+['\"]?([^?!.]+?)['\"]?\s*$", q, flags=re.IGNORECASE)
    if not m:
        return None
    title = (m.group(1) or "").strip()
    title = re.sub(r"\s+", " ", title)
    return title or None


def _is_horror_movie(tmdb_id: int, token: str, cache: Dict[int, Dict[str, Any]]) -> bool:
    cached = cache.get(tmdb_id) or {}
    if "is_horror" in cached:
        return bool(cached["is_horror"])

    genres = fetch_movie_genre_names(tmdb_id, token)
    genre_norm = {_norm_text(g) for g in genres if g}
    has_horror_genre = any(g in ("horror",) for g in genre_norm)

    keywords = fetch_movie_keyword_names(tmdb_id, token)
    kw_norm = {_norm_text(k) for k in keywords if k}
    horror_kw = {"horror", "scary", "scare", "fear"}
    has_horror_kw = any(k in horror_kw for k in kw_norm)

    is_horror = has_horror_genre or has_horror_kw
    cache[tmdb_id] = {**cached, "is_horror": is_horror, "genres": genres, "keywords": keywords}
    return is_horror


def _cast_matches_actor(tmdb_id: int, token: str, actor_norm: str, cache: Dict[int, Dict[str, Any]]) -> bool:
    cached = cache.get(tmdb_id) or {}
    if "cast" not in cached:
        cached["cast"] = fetch_movie_cast_names(tmdb_id, token)
        cache[tmdb_id] = cached

    for name in cached.get("cast") or []:
        if not name:
            continue
        n = _norm_text(name)
        # Allow substring matching for partial actor captures.
        if actor_norm in n or n in actor_norm:
            return True
    return False


def filter_movie_hub_clusters_by_question(
    clusters: List[Dict[str, Any]],
    question: str,
) -> List[Dict[str, Any]]:
    """
    Deterministically filter candidates.

    If TMDB metadata is unavailable, returns clusters unchanged.
    """
    if not clusters:
        return clusters

    like_title = extract_like_movie_title(question or "")

    # If we can interpret the question as "movies like <X>", narrow by TMDB similarity-to-X
    # via intersection with the anchored candidate universe.
    if like_title and is_tmdb_enabled():
        token = (get_tmdb_access_token() or "").strip()
        if token:
            try:
                from cinemind.media.media_enrichment import build_similar_movie_clusters

                target_hub = build_similar_movie_clusters(
                    title=like_title,
                    year=None,
                    tmdb_id=None,
                    media_type="movie",
                    max_results=30,
                )
                target_clusters = (target_hub or {}).get("clusters") or []

                target_ids: set[int] = set()
                for c in target_clusters:
                    movies = (c or {}).get("movies") or []
                    for mv in movies:
                        if not isinstance(mv, dict):
                            continue
                        tmdb_id = mv.get("tmdbId") or mv.get("tmdb_id")
                        if tmdb_id is None:
                            continue
                        try:
                            target_ids.add(int(tmdb_id))
                        except Exception:
                            continue

                if target_ids:
                    out_like: List[Dict[str, Any]] = []
                    for c in clusters:
                        if not isinstance(c, dict):
                            continue
                        kind = c.get("kind")
                        label = c.get("label")
                        movies = c.get("movies") or []
                        if not isinstance(movies, list):
                            movies = []
                        filtered_movies = []
                        for mv in movies:
                            if not isinstance(mv, dict):
                                continue
                            tmdb_id = mv.get("tmdbId") or mv.get("tmdb_id")
                            if tmdb_id is None:
                                continue
                            try:
                                if int(tmdb_id) in target_ids:
                                    filtered_movies.append(mv)
                            except Exception:
                                continue

                        out_like.append({"kind": kind, "label": label, "movies": filtered_movies})

                    # Avoid collapsing UX into an empty hub; fall back if intersection is empty.
                    if any((c.get("movies") or []) for c in out_like):
                        return out_like
            except Exception:
                # Any TMDB/network failure should preserve the anchored universe.
                pass

    include_horror, exclude_horror = extract_horror_constraint(question or "")
    actor = extract_actor_constraint(question or "")

    # If we can't recognize any constraints, do not filter.
    if not actor and not include_horror and not exclude_horror:
        return clusters

    if not is_tmdb_enabled():
        return clusters

    token = (get_tmdb_access_token() or "").strip()
    if not token:
        return clusters

    actor_norm = _norm_text(actor) if actor else ""

    # Cache per TMDB id during one filtering pass.
    cache: Dict[int, Dict[str, Any]] = {}

    def movie_matches(movie: Dict[str, Any]) -> bool:
        tmdb_id = movie.get("tmdbId") or movie.get("tmdb_id")
        if tmdb_id is None:
            # Missing identifiers can't be reliably matched.
            return False
        try:
            tmid_int = int(tmdb_id)
        except Exception:
            return False

        if actor_norm:
            if not _cast_matches_actor(tmid_int, token, actor_norm, cache):
                return False

        if include_horror or exclude_horror:
            is_horror = _is_horror_movie(tmid_int, token, cache)
            if exclude_horror and is_horror:
                return False
            if include_horror and not is_horror:
                return False

        return True

    out: List[Dict[str, Any]] = []
    for c in clusters:
        if not isinstance(c, dict):
            continue
        kind = c.get("kind")
        label = c.get("label")
        movies = c.get("movies") or []
        if not isinstance(movies, list):
            movies = []
        filtered_movies = [m for m in movies if isinstance(m, dict) and movie_matches(m)]
        out.append({
            "kind": kind,
            "label": label,
            "movies": filtered_movies,
        })

    # If filtering yields an empty hub, preserve the original candidate universe.
    if not any((c.get("movies") or []) for c in out):
        return clusters

    return out

