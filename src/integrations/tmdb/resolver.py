"""
TMDB Search → ID → Details resolver (deterministic, server-side only).

Resolves a user/title string to a TMDB movie_id using:
1. TMDB "search movie" to get results[]
2. Deterministic scoring: exact/normalized title match, year proximity, popularity/vote_count tie-breaker
3. If confidence is high and top candidate is clear: return movie_id.
4. If confidence is low or top two are close: return "ambiguous" with candidates for "Did you mean?".
"""

from __future__ import annotations

import logging
import math
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from .http_client import tmdb_request_json
from .resolve_cache import cache_key, get_cached, set_cached
from .resolve_cache import clear_resolve_cache as _clear_resolve_cache

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"

# Minimum confidence to auto-select a single movie (else return ambiguous).
MIN_CONFIDENCE_AUTO_SELECT = 0.6
# Minimum score gap between first and second to auto-select (else "Did you mean?").
MIN_SCORE_GAP_AUTO_SELECT = 0.15


def _normalize_title(s: str) -> str:
    """Normalize for comparison: lowercase, collapse whitespace, strip punctuation."""
    if not s or not isinstance(s, str):
        return ""
    t = re.sub(r"\s+", " ", s.strip().lower())
    return t.strip()


def _extract_year(release_date: Any) -> int | None:
    """From TMDB release_date (YYYY-MM-DD or empty) return 4-digit year or None."""
    if not release_date or not isinstance(release_date, str):
        return None
    part = (release_date.strip())[:4]
    if len(part) == 4 and part.isdigit():
        y = int(part)
        if 1900 <= y <= 2100:
            return y
    return None


def _score_candidate(
    r: dict[str, Any],
    query_title: str,
    query_year: int | None,
) -> float:
    """
    Deterministic score for one search result (higher = better match).

    Scoring (documented):
    1. Title: exact normalized match = 1.0; normalized match = 0.9; contains = 0.7; else 0.3 base.
    2. Year: if query_year given, exact match +0.2; else 1-year diff +0.1; else small penalty by distance.
    3. Tie-breaker: popularity (log10) and vote_count (log10) added as small decimals so order is stable.

    All operations are deterministic; no randomness.
    """
    score = 0.0
    raw_title = (r.get("title") or r.get("original_title") or "").strip()
    norm_query = _normalize_title(query_title)
    norm_title = _normalize_title(raw_title)
    if not norm_query:
        return 0.0
    if norm_title == norm_query:
        score += 1.0
    elif norm_query in norm_title or norm_title in norm_query:
        score += 0.7
    else:
        # Same words / overlap could be added; keep simple
        score += 0.3

    release_year = _extract_year(r.get("release_date"))
    if query_year is not None:
        if release_year == query_year:
            score += 0.2
        elif release_year is not None:
            diff = abs(release_year - query_year)
            if diff == 1:
                score += 0.1
            elif diff <= 3:
                score += 0.05
            # else no year bonus

    # Tie-breaker: popularity and vote_count (log scale so one big value doesn't dominate)
    pop = float(r.get("popularity") or 0)
    votes = int(r.get("vote_count") or 0)
    pop_log = math.log10(pop + 1) * 0.01
    vote_log = math.log10(votes + 1) * 0.01
    score += pop_log + vote_log
    return score


@dataclass
class TMDBCandidate:
    """One candidate for display in 'Did you mean?' (id, title, year, optional poster_path)."""
    id: int
    title: str
    year: int | None = None
    poster_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "title": self.title}
        if self.year is not None:
            out["year"] = self.year
        if self.poster_path is not None:
            out["poster_path"] = self.poster_path
        return out


@dataclass
class TMDBResolveResult:
    """
    Result of resolving a title to TMDB.

    - status: "resolved" | "ambiguous" | "not_found"
    - movie_id: set when status is "resolved"
    - poster_path: TMDB poster path (e.g. /abc.jpg) when resolved and available; for building poster URL
    - confidence: 0.0-1.0 when resolved
    - candidates: list for "Did you mean?" when ambiguous or for reference
    """
    status: str  # "resolved" | "ambiguous" | "not_found"
    movie_id: int | None = None
    poster_path: str | None = None
    confidence: float = 0.0
    candidates: list[TMDBCandidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.status,
            "confidence": self.confidence,
            "candidates": [c.to_dict() for c in self.candidates],
        }
        if self.movie_id is not None:
            out["movie_id"] = self.movie_id
        if self.poster_path is not None:
            out["poster_path"] = self.poster_path
        return out


def _resolve_from_results(
    results: list[dict[str, Any]],
    title: str,
    year: int | None,
    min_confidence: float,
    min_score_gap: float,
    max_candidates: int,
) -> TMDBResolveResult:
    """Score TMDB search results into a TMDBResolveResult (no I/O)."""
    if not results:
        return TMDBResolveResult(status="not_found")

    scored = [(r, _score_candidate(r, title, year)) for r in results]
    scored.sort(key=lambda x: (-x[1], x[0].get("id") or 0))

    top_result, top_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    gap = top_score - second_score

    candidates = [
        TMDBCandidate(
            id=int(r.get("id") or 0),
            title=(r.get("title") or r.get("original_title") or "").strip() or "Unknown",
            year=_extract_year(r.get("release_date")),
            poster_path=(r.get("poster_path") or "").strip() or None,
        )
        for r, _ in scored[:max_candidates]
    ]
    candidates = [c for c in candidates if c.id > 0]

    confidence = min(1.0, top_score)
    poster_path = (top_result.get("poster_path") or "").strip() or None

    if confidence >= min_confidence and gap >= min_score_gap:
        return TMDBResolveResult(
            status="resolved",
            movie_id=int(top_result.get("id") or 0),
            poster_path=poster_path,
            confidence=confidence,
            candidates=candidates[:1],
        )
    return TMDBResolveResult(
        status="ambiguous",
        poster_path=poster_path,
        confidence=confidence,
        candidates=candidates,
    )


def resolve_movie(
    title: str,
    year: int | None = None,
    *,
    access_token: str,
    timeout: float = 10.0,
    min_confidence: float = MIN_CONFIDENCE_AUTO_SELECT,
    min_score_gap: float = MIN_SCORE_GAP_AUTO_SELECT,
    max_candidates: int = 5,
) -> TMDBResolveResult:
    """
    Search → score → resolve or ambiguous.

    1. Call TMDB search movie for the title (and optional year).
    2. Score each result deterministically (title match, year proximity, popularity/vote_count).
    3. If top score >= min_confidence and gap to second >= min_score_gap: return resolved + movie_id.
    4. Else if we have results: return ambiguous with top candidates for "Did you mean?".
    5. Else: not_found.
    """
    title = (title or "").strip()
    if not title or not access_token:
        return TMDBResolveResult(status="not_found")

    key = cache_key(title, year, min_confidence, min_score_gap, max_candidates)
    cached = get_cached(key)
    if cached is not None:
        logger.debug(
            "TMDB resolve_movie cache_hit title=%r year=%s",
            title[:60] if title else "",
            year,
        )
        return cached

    t0 = time.perf_counter()
    logger.debug("TMDB resolve_movie attempt title=%r year=%s", title[:60] if title else "", year)
    try:
        qs: dict[str, str] = {"query": title, "page": "1"}
        if year is not None:
            qs["year"] = str(year)
        url = f"{BASE_URL}/search/movie?{urllib.parse.urlencode(qs)}"
        data = tmdb_request_json(url, access_token, timeout=timeout, log_label="TMDB_resolve")
        if not isinstance(data, dict):
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.debug("TMDB resolve_movie not_found ms=%.1f (no data)", elapsed_ms)
            out = TMDBResolveResult(status="not_found")
            set_cached(key, out)
            return out
        results = data.get("results") or []
        logger.debug("TMDB resolve_movie response title=%r results_count=%s", title[:60] if title else "", len(results))
    except Exception as e:
        logger.debug("TMDB resolve_movie failed for %r: %s", title[:60] if title else "", e)
        return TMDBResolveResult(status="not_found")

    if not results:
        out = TMDBResolveResult(status="not_found")
        set_cached(key, out)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug("TMDB resolve_movie not_found ms=%.1f", elapsed_ms)
        return out

    out = _resolve_from_results(
        results,
        title,
        year,
        min_confidence=min_confidence,
        min_score_gap=min_score_gap,
        max_candidates=max_candidates,
    )
    set_cached(key, out)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "TMDB resolve_movie done status=%s ms=%.1f title=%r",
        out.status,
        elapsed_ms,
        title[:60] if title else "",
    )
    return out


clear_resolve_cache = _clear_resolve_cache

__all__ = [
    "MIN_CONFIDENCE_AUTO_SELECT",
    "MIN_SCORE_GAP_AUTO_SELECT",
    "TMDBCandidate",
    "TMDBResolveResult",
    "_extract_year",
    "_normalize_title",
    "_score_candidate",
    "clear_resolve_cache",
    "resolve_movie",
]
