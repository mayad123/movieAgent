"""
Deterministic movie title extraction for media enrichment (no LLM).

Extracts candidate movie titles from user queries using pattern-based rules.
Supports: direct titles, "movies like X", "show me images for X", etc.
Used by media_enrichment to decide what to resolve and display.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Prefixes ordered by length descending so longer matches win (e.g. "show me images for" before "images for").
# After stripping, the rest is treated as the movie title phrase.
_TITLE_PREFIXES = (
    "show me images for ",
    "show me images of ",
    "show me the poster for ",
    "get me images for ",
    "get me images of ",
    "images for ",
    "images of ",
    "picture of ",
    "poster for ",
    "poster of ",
    "who directed ",
    "who directed the ",
    "when was ",
    "when did ",
    "what is ",
    "what was ",
    "tell me about ",
    "information about ",
    "info about ",
    "recommend movies like ",
    "movies like ",
    "films like ",
    "similar to ",
    "similar movies to ",
    "about ",
    "compare ",
    "difference between ",
)


@dataclass
class TitleExtractionResult:
    """
    Result of deterministic title extraction.
    - titles: Candidate title string(s) to try for resolution (in priority order)
    - reason: Heuristic that matched (e.g. "direct", "prefix:movies_like")
    - intent: Routing hint ("single_title" | "seed_for_similar" | "compare")
    """

    titles: tuple[str, ...]
    reason: str
    intent: str = "single_title"


def _normalize_phrase(s: str) -> str:
    """Trim and collapse whitespace; strip trailing '?'."""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.rstrip("?").strip())


def _split_and(titles: list[str]) -> list[str]:
    """Split 'X and Y' or 'X & Y' into [X, Y]. Returns original if no split."""
    out: list[str] = []
    for t in titles:
        t = _normalize_phrase(t)
        if not t:
            continue
        # "X and Y" or "X & Y" (common in comparisons)
        m = re.match(r"^(.+?)\s+(?:and|&)\s+(.+)$", t, re.IGNORECASE)
        if m:
            a, b = _normalize_phrase(m.group(1)), _normalize_phrase(m.group(2))
            if len(a) >= 2 and len(b) >= 2:
                out.extend([a, b])
                continue
        out.append(t)
    return out


def extract_movie_titles(user_query: str) -> TitleExtractionResult:
    """
    Extract candidate movie title(s) from a user query using deterministic patterns.

    Supports:
    - Direct: "How to Train Your Dragon", "Inception"
    - Images: "show me images for How to Train Your Dragon", "images for X"
    - Similar: "movies like How to Train Your Dragon", "similar to X"
    - Info: "who directed The Matrix?", "tell me about Inception"
    - Compare: "compare X and Y" (returns [X, Y] for potential multi-card)

    Returns:
        TitleExtractionResult with titles (priority order), reason, and intent.
        Never returns empty titles; falls back to full query.
    """
    q = _normalize_phrase(user_query or "")
    if not q:
        return TitleExtractionResult(titles=(), reason="empty", intent="single_title")

    low = q.lower()
    candidates: list[str] = []

    # Check for prefix match
    for prefix in _TITLE_PREFIXES:
        if low.startswith(prefix.lower()):
            rest = q[len(prefix) :].strip()
            rest = _normalize_phrase(rest)
            if len(rest) < 2:
                break
            # Determine intent from prefix; prefer extracted title(s) over full query
            if "movies like" in prefix or "films like" in prefix or "similar to" in prefix or "similar movies" in prefix:
                reason = f"prefix:{prefix.strip().replace(' ', '_')}"
                intent = "seed_for_similar"
                candidates = [rest]
            elif "compare" in prefix or "difference between" in prefix:
                reason = f"prefix:{prefix.strip().replace(' ', '_')}"
                intent = "compare"
                candidates = [s for s in _split_and([rest]) if s]
            else:
                reason = f"prefix:{prefix.strip().replace(' ', '_')}"
                intent = "single_title"
                candidates = [rest]
            if q and q not in candidates:
                candidates.append(q)
            return TitleExtractionResult(
                titles=tuple(candidates),
                reason=reason,
                intent=intent,
            )

    # No prefix matched: check for "X and Y" (direct multi-title)
    split = _split_and([q])
    if len(split) >= 2:
        return TitleExtractionResult(
            titles=tuple(split),
            reason="direct_and",
            intent="compare",
        )
    return TitleExtractionResult(
        titles=(q,),
        reason="direct",
        intent="single_title",
    )


def get_search_phrases(user_query: str) -> list[str]:
    """
    Return search strings to try (for media_enrichment compatibility).
    Same order as TitleExtractionResult.titles; used by enrich() loop.
    """
    r = extract_movie_titles(user_query)
    return list(r.titles)
