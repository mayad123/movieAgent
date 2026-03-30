"""
Intent-based media focus: single-movie vs multi-movie.

Used to decide whether to populate scenes (single-movie intent) or only posters
(multi-movie intent). Classification is based on request_type and query patterns.

Single-movie intent: summary, explain ending, key scenes, analysis, single-movie info
  → Display poster + scenes carousel.

Multi-movie intent: comparisons, similar movies, recommendations, rankings, lists
  → Display only poster images; do not render scene carousels.
"""

from __future__ import annotations

import re
from typing import Literal

# Focus values for attachment behavior
MEDIA_FOCUS_SINGLE = "single_movie"
MEDIA_FOCUS_MULTI = "multi_movie"


# Request types that imply multi-movie intent (never show scenes)
_MULTI_MOVIE_REQUEST_TYPES = frozenset({"comparison", "recs", "recommendation"})

# Query patterns that imply multi-movie intent (lists, rankings, similar)
_MULTI_MOVIE_PATTERNS = [
    r"\b(compare|comparison|vs\.?|versus)\b",
    r"\b(similar to|like|alike)\s+.*\b(movie|film)s?\b",
    r"\b(recommend|suggest)\s+(me\s+)?(a|some|any)\s+(movie|film)",
    r"\b(movies|films)\s+(like|similar to)\b",
    r"\b(top|best|worst|greatest)\s+\d*\s*(movie|film)s?\b",
    r"\b(rank|ranking|list)\s+(of\s+)?(movie|film)s?\b",
    r"\b(which\s+)?(movie|film)s?\s+(should|to watch|worth)\b",
    r"\b\d+\s+(movie|film)s?\b",  # "5 movies", "10 films"
]

# Query patterns that imply single-movie intent (summary, ending, scenes, analysis)
_SINGLE_MOVIE_PATTERNS = [
    r"\b(summary|summarize|synopsis|overview)\b",
    r"\b(explain\s+the\s+ending|explain\s+ending|ending\s+of)\b",
    r"\b(key\s+scenes?|iconic\s+scenes?|notable\s+scenes?|best\s+scenes?)\b",
    r"\b(analysis|analyze|breakdown)\s+(of\s+)?(the\s+)?(movie|film)\b",
    r"\b(the\s+)?(movie|film)\s+(summary|ending|analysis)\b",
    r"\b(what\s+(happens|happened)|how\s+does\s+it\s+end)\b",
    r"\b(behind\s+the\s+scenes|making\s+of)\b",
]


def get_media_focus(
    user_query: str,
    request_type: str | None = None,
) -> Literal["single_movie", "multi_movie"]:
    """
    Classify whether the user intent is single-movie focused or multi-movie focused.

    Single-movie: show poster + scenes. Multi-movie: show only posters (no scenes).

    Args:
        user_query: The user's question or prompt.
        request_type: Optional classified request type (info, recs, comparison, etc.).

    Returns:
        "single_movie" or "multi_movie".
    """
    query_lower = (user_query or "").lower().strip()

    # 1. Request type: comparison/recs → always multi_movie
    if request_type and request_type in _MULTI_MOVIE_REQUEST_TYPES:
        return MEDIA_FOCUS_MULTI

    # 2. Query patterns: multi-movie (lists, compare, similar, rankings)
    for pattern in _MULTI_MOVIE_PATTERNS:
        if re.search(pattern, query_lower):
            return MEDIA_FOCUS_MULTI

    # 3. Query patterns: single-movie (summary, ending, key scenes, analysis)
    for pattern in _SINGLE_MOVIE_PATTERNS:
        if re.search(pattern, query_lower):
            return MEDIA_FOCUS_SINGLE

    # 4. Default: single_movie (preserve existing behavior for "Inception" etc.)
    return MEDIA_FOCUS_SINGLE
