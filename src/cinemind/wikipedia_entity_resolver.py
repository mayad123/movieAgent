"""
Wikipedia-only entity resolution layer.

Converts raw user input into either a resolved movie page or a candidate list
for disambiguation. No AI or Tavily; Wikipedia APIs only. No UI logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import quote

import requests

if TYPE_CHECKING:
    from .wikipedia_cache import WikipediaCache

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
REQUEST_TIMEOUT = 10

# Wikimedia requires a descriptive User-Agent; default python-requests gets 403 Forbidden.
WIKIPEDIA_USER_AGENT = "CineMind/1.0 (https://github.com/; MovieAgent) Python-requests"
MAX_CANDIDATES = 7
SEARCH_LIMIT = 15
CATEGORY_BATCH_SIZE = 10


@dataclass(frozen=True)
class ResolvedEntity:
    """A single resolved Wikipedia page (movie)."""
    page_title: str   # canonical title as in URL (underscores)
    display_title: str  # human-readable (spaces, etc.)


# Minimum score gap between top two candidates to auto-resolve (else return ambiguous / did_you_mean)
FILM_CONFIDENCE_SCORE_GAP = 1
# Film confidence threshold above which we prefer Wikipedia poster when it has an image
FILM_CONFIDENCE_THRESHOLD = 0.5


@dataclass
class ResolverResult:
    """
    Standard return shape for WikipediaEntityResolver.
    status: resolved | ambiguous | not_found | error.
    film_confidence: 0.0–1.0 for the chosen entity (or first candidate when ambiguous).
    film_confidence_reasons: human-readable reasons for confidence score.
    """
    status: str  # "resolved" | "ambiguous" | "not_found" | "error"
    resolved_entity: Optional[ResolvedEntity] = None
    candidates: list[dict[str, Any]] = field(default_factory=list)  # pageTitle, displayTitle, year, score, film_confidence, film_confidence_reasons, page_url
    error_message: Optional[str] = None
    film_confidence: float = 0.0
    film_confidence_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status}
        if self.resolved_entity is not None:
            out["resolvedEntity"] = {
                "pageTitle": self.resolved_entity.page_title,
                "displayTitle": self.resolved_entity.display_title,
            }
        if self.candidates:
            out["candidates"] = self.candidates
        if self.error_message is not None:
            out["errorMessage"] = self.error_message
        if self.film_confidence > 0 or self.film_confidence_reasons:
            out["filmConfidence"] = self.film_confidence
            out["filmConfidenceReasons"] = self.film_confidence_reasons
        return out


def _normalize_query(raw: str) -> str:
    """Collapse whitespace and strip."""
    if not raw or not isinstance(raw, str):
        return ""
    return " ".join(raw.split()).strip()


def _title_looks_like_movie(title: str) -> bool:
    """Heuristic: (film), (movie), (franchise), or year suffix often indicates film page."""
    t = title.lower()
    if "(film)" in t or "(movie)" in t:
        return True
    if "(franchise)" in t or "(film series)" in t:
        return True
    # Year in parentheses at end, e.g. "Something (2024)"
    if re.search(r"\s*\(\d{4}\)\s*$", title):
        return True
    return False


def _title_looks_like_non_film(title: str) -> bool:
    """True if title suggests a non-film work (novel, book series, TV series, game, soundtrack). Prefer film over these."""
    t = title.lower()
    if "(novel" in t or "(book" in t or "novel series" in t or "(book series" in t:
        return True
    if "(tv series)" in t or "(television series)" in t or "(tv show)" in t:
        return True
    if "(video game)" in t or "(video game series)" in t:
        return True
    if "(play)" in t or "(musical)" in t:
        return True
    if "(soundtrack)" in t or "(album)" in t:
        return True
    return False


def _movie_score(title: str, categories: list[dict[str, Any]]) -> int:
    """Score for ranking: higher = prefer this page. Film pages score higher; non-film get penalty."""
    score = 0
    if _title_looks_like_non_film(title):
        score -= 3
    if _title_looks_like_movie(title):
        score += 3
    if _has_film_category(categories):
        score += 2
    return score


def _has_film_category(categories: list[dict[str, Any]]) -> bool:
    """True if any category title suggests a film (e.g. 'Films', 'American films')."""
    for c in categories:
        ct = (c.get("title") or "").lower()
        if "film" in ct:
            return True
    return False


def _film_confidence(
    title: str,
    categories: list[dict[str, Any]],
    snippet: str,
) -> tuple[float, list[str]]:
    """
    Compute film confidence 0.0–1.0 and reasons for poster-source policy.
    Boost: (film), (YYYY film), snippet mentions "film", film category.
    Penalize: disambiguation, non-film types (novel, book, game, album, soundtrack).
    """
    score = 0.0
    reasons: list[str] = []
    t = (title or "").lower()
    s = (snippet or "").lower()
    # Strip HTML for snippet checks
    s_plain = re.sub(r"<[^>]+>", " ", s)
    combined = f"{t} {s_plain}"

    # Penalize non-film content (strong)
    if "(novel" in t or "novel series" in t or "(book" in t or "book series" in t:
        score -= 0.6
        reasons.append("title suggests non-film (novel/book)")
    if "(tv series)" in t or "(television series)" in t or "(video game)" in t:
        score -= 0.5
        reasons.append("title suggests TV/game")
    if "(play)" in t or "(musical)" in t:
        score -= 0.3
        reasons.append("title suggests play/musical")
    if "disambiguation" in combined or "disambiguation page" in s_plain:
        score -= 0.5
        reasons.append("disambiguation page")
    if "soundtrack" in combined or "album)" in t:
        score -= 0.3
        reasons.append("snippet/title suggests soundtrack/album")
    # Demote franchise/topic pages so the specific film page wins (e.g. "How to Train Your Dragon (2010 film)" over "(franchise)")
    if "(franchise)" in t or " (franchise)" in t:
        score -= 0.25
        reasons.append("title suggests franchise/topic page")

    # Boost film signals
    if "(film)" in t or "(movie)" in t:
        score += 0.45
        reasons.append("title has (film) or (movie)")
    if re.search(r"\(\d{4}\s+(?:film|movie)\)", title or ""):
        score += 0.35
        reasons.append("title has (YYYY film)")
    if "film" in s_plain or "movie" in s_plain:
        score += 0.2
        reasons.append("snippet mentions film/movie")
    if _has_film_category(categories):
        score += 0.2
        reasons.append("page has film category")

    confidence = max(0.0, min(1.0, score))
    if not reasons:
        reasons.append("neutral confidence")
    return (round(confidence, 2), reasons)


def _search_wikipedia(
    session: requests.Session,
    query: str,
    cache: Optional["WikipediaCache"] = None,
) -> list[dict[str, Any]]:
    """Return list of search result items with 'title' and optional 'snippet'."""
    if cache:
        cached = cache.get_search(query)
        if cached is not None:
            return cached
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": SEARCH_LIMIT,
        "srprop": "snippet",
        "format": "json",
        "origin": "*",
    }
    try:
        r = session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        results = data.get("query", {}).get("search") or []
        if cache:
            cache.set_search(query, results)
        return results
    except requests.RequestException as e:
        logger.warning("Wikipedia search request failed: %s", e)
        raise
    except (ValueError, KeyError) as e:
        logger.warning("Wikipedia search response parse error: %s", e)
        raise


def _get_categories_batch(
    session: requests.Session,
    titles: list[str],
    cache: Optional["WikipediaCache"] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Get categories for up to CATEGORY_BATCH_SIZE titles. Returns map title -> list of category dicts."""
    if not titles:
        return {}
    titles = titles[:CATEGORY_BATCH_SIZE]
    if cache:
        cached = cache.get_categories(titles)
        if cached is not None:
            return cached
    params = {
        "action": "query",
        "prop": "categories",
        "titles": "|".join(titles),
        "cllimit": 15,
        "format": "json",
        "origin": "*",
    }
    try:
        r = session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages") or {}
        out: dict[str, list[dict[str, Any]]] = {}
        for _pid, p in pages.items():
            title = p.get("title", "")
            out[title] = p.get("categories") or []
        if cache:
            cache.set_categories(titles, out)
        return out
    except requests.RequestException as e:
        logger.warning("Wikipedia categories request failed: %s", e)
        return {t: [] for t in titles}


def _page_title_to_display(title: str) -> str:
    """Convert wiki page title to display form (underscores -> spaces)."""
    return title.replace("_", " ")


def _extract_year_from_title(title: str) -> Optional[int]:
    """Extract year from title suffix, e.g. 'Dune (2021 film)' -> 2021, 'Inception (2010)' -> 2010."""
    # Match (YYYY) or (YYYY film) or (YYYY movie) - year can be inside parens with optional suffix
    m = re.search(r"\((\d{4})(?:\s+(?:film|movie))?\)\s*$", title, re.I) or re.search(r"\((\d{4})\)\s*$", title)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def _build_page_url(page_title: str) -> str:
    """Build Wikipedia page URL from canonical title (underscores)."""
    encoded = quote(page_title.replace(" ", "_"), safe="/")
    return f"https://en.wikipedia.org/wiki/{encoded}"


class WikipediaEntityResolver:
    """
    Resolves raw user text to a Wikipedia movie page or a disambiguation candidate list.
    Wikipedia APIs only; no UI logic.
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: int = REQUEST_TIMEOUT,
        cache: Optional["WikipediaCache"] = None,
    ):
        self._session = session or requests.Session()
        self._session.headers["User-Agent"] = WIKIPEDIA_USER_AGENT
        self._timeout = timeout
        self._cache = cache

    def resolve(self, raw_user_text: str) -> ResolverResult:
        """
        Resolve raw user input to either a single movie page or a candidate list.

        Args:
            raw_user_text: Raw user input (e.g. "The Matrix", "Inception").

        Returns:
            ResolverResult with status resolved | ambiguous | not_found | error,
            and resolvedEntity or candidates when applicable.
        """
        query = _normalize_query(raw_user_text)
        if not query:
            return ResolverResult(
                status="not_found",
                error_message="Empty query",
            )

        try:
            search_results = _search_wikipedia(self._session, query, self._cache)
        except Exception as e:
            logger.exception("Wikipedia unavailable during search")
            return ResolverResult(
                status="error",
                error_message="Wikipedia unavailable",
            )

        if not search_results:
            return ResolverResult(status="not_found")

        titles = [item["title"] for item in search_results]
        snippet_map: dict[str, str] = {}
        for item in search_results:
            tit = item.get("title", "")
            if tit:
                snippet_map[tit] = (item.get("snippet") or "").strip()

        categories_map = _get_categories_batch(self._session, titles, self._cache)

        movie_scores: list[tuple[str, int]] = []
        for title in titles:
            cats = categories_map.get(title, [])
            score = _movie_score(title, cats)
            movie_scores.append((title, score))

        # Build ranked candidates: include all with non-negative score, then sort by rank so best film wins
        scored = [(t, s) for t, s in movie_scores if s >= 0]
        if not scored:
            scored = [(t, 0) for t in titles[:MAX_CANDIDATES]]

        candidates_list = []
        for t, score in scored:
            display = _page_title_to_display(t)
            year = _extract_year_from_title(t)
            cats = categories_map.get(t, [])
            snippet = snippet_map.get(t, "")
            film_conf, film_reasons = _film_confidence(t, cats, snippet)
            candidates_list.append({
                "pageTitle": t,
                "displayTitle": display,
                "year": year,
                "page_url": _build_page_url(t),
                "score": score,
                "film_confidence": film_conf,
                "film_confidence_reasons": film_reasons,
            })

        # Rank: score desc, then film_confidence desc, then year desc, then title asc (so "X (2009 film)" beats "X (franchise)")
        def _rank_key(c: dict) -> tuple:
            return (-c["score"], -(c.get("film_confidence") or 0), -(c["year"] or 0), c["displayTitle"])

        candidates_list.sort(key=_rank_key)
        candidates_list = candidates_list[:MAX_CANDIDATES]

        top = candidates_list[0]
        top_film_conf = top.get("film_confidence") or 0.0

        # Only auto-pick when top candidate is confidently a film page (else did_you_mean + TMDB fallback)
        if top_film_conf < FILM_CONFIDENCE_THRESHOLD:
            return ResolverResult(
                status="ambiguous",
                candidates=candidates_list,
                film_confidence=top_film_conf,
                film_confidence_reasons=top.get("film_confidence_reasons") or [],
            )

        # Single candidate with high film_confidence → resolved
        if len(candidates_list) == 1:
            c = top
            return ResolverResult(
                status="resolved",
                resolved_entity=ResolvedEntity(
                    page_title=c["pageTitle"],
                    display_title=c["displayTitle"],
                ),
                candidates=candidates_list,
                film_confidence=top_film_conf,
                film_confidence_reasons=c.get("film_confidence_reasons") or [],
            )

        # Multiple candidates: do not auto-pick when top two are close in score (did_you_mean preferred)
        if len(candidates_list) >= 2:
            top_score = top.get("score") or 0
            second_score = candidates_list[1].get("score") or 0
            if top_score - second_score <= FILM_CONFIDENCE_SCORE_GAP:
                return ResolverResult(
                    status="ambiguous",
                    candidates=candidates_list,
                    film_confidence=top_film_conf,
                    film_confidence_reasons=top.get("film_confidence_reasons") or [],
                )

        # Clear winner: resolve to first
        c = top
        return ResolverResult(
            status="resolved",
            resolved_entity=ResolvedEntity(
                page_title=c["pageTitle"],
                display_title=c["displayTitle"],
            ),
            candidates=candidates_list[:1],
            film_confidence=top_film_conf,
            film_confidence_reasons=c.get("film_confidence_reasons") or [],
        )
