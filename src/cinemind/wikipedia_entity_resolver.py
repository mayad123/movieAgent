"""
Wikipedia-only entity resolution layer.

Converts raw user input into either a resolved movie page or a candidate list
for disambiguation. No AI or Tavily; Wikipedia APIs only. No UI logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
REQUEST_TIMEOUT = 10
MAX_CANDIDATES = 7
SEARCH_LIMIT = 15
CATEGORY_BATCH_SIZE = 10


@dataclass(frozen=True)
class ResolvedEntity:
    """A single resolved Wikipedia page (movie)."""
    page_title: str   # canonical title as in URL (underscores)
    display_title: str  # human-readable (spaces, etc.)


@dataclass
class ResolverResult:
    """
    Standard return shape for WikipediaEntityResolver.
    """
    status: str  # "resolved" | "ambiguous" | "not_found" | "error"
    resolved_entity: Optional[ResolvedEntity] = None
    candidates: list[dict[str, str]] = field(default_factory=list)  # [{"pageTitle", "displayTitle"}, ...]
    error_message: Optional[str] = None

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


def _has_film_category(categories: list[dict[str, Any]]) -> bool:
    """True if any category title suggests a film (e.g. 'Films', 'American films')."""
    for c in categories:
        ct = (c.get("title") or "").lower()
        if "film" in ct:
            return True
    return False


def _search_wikipedia(session: requests.Session, query: str) -> list[dict[str, Any]]:
    """Return list of search result items with 'title' and optional 'snippet'."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": SEARCH_LIMIT,
        "format": "json",
        "origin": "*",
    }
    try:
        r = session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get("query", {}).get("search") or []
    except requests.RequestException as e:
        logger.warning("Wikipedia search request failed: %s", e)
        raise
    except (ValueError, KeyError) as e:
        logger.warning("Wikipedia search response parse error: %s", e)
        raise


def _get_categories_batch(session: requests.Session, titles: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Get categories for up to CATEGORY_BATCH_SIZE titles. Returns map title -> list of category dicts."""
    if not titles:
        return {}
    titles = titles[:CATEGORY_BATCH_SIZE]
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
        return out
    except requests.RequestException as e:
        logger.warning("Wikipedia categories request failed: %s", e)
        return {t: [] for t in titles}


def _page_title_to_display(title: str) -> str:
    """Convert wiki page title to display form (underscores -> spaces)."""
    return title.replace("_", " ")


class WikipediaEntityResolver:
    """
    Resolves raw user text to a Wikipedia movie page or a disambiguation candidate list.
    Wikipedia APIs only; no UI logic.
    """

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = REQUEST_TIMEOUT):
        self._session = session or requests.Session()
        self._timeout = timeout

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
            search_results = _search_wikipedia(self._session, query)
        except Exception as e:
            logger.exception("Wikipedia unavailable during search")
            return ResolverResult(
                status="error",
                error_message="Wikipedia unavailable",
            )

        if not search_results:
            return ResolverResult(status="not_found")

        titles = [item["title"] for item in search_results]
        categories_map = _get_categories_batch(self._session, titles)

        movie_scores: list[tuple[str, int]] = []
        for title in titles:
            score = 0
            if _title_looks_like_movie(title):
                score += 2
            cats = categories_map.get(title, [])
            if _has_film_category(cats):
                score += 2
            movie_scores.append((title, score))

        movie_titles = [t for t, s in movie_scores if s > 0]
        if not movie_titles:
            movie_titles = titles[:MAX_CANDIDATES]

        candidates_list = [
            {"pageTitle": t, "displayTitle": _page_title_to_display(t)}
            for t in movie_titles[:MAX_CANDIDATES]
        ]

        # Single clear movie match → auto-resolve
        if len(candidates_list) == 1:
            c = candidates_list[0]
            return ResolverResult(
                status="resolved",
                resolved_entity=ResolvedEntity(
                    page_title=c["pageTitle"],
                    display_title=c["displayTitle"],
                ),
            )

        # Multiple plausible matches → disambiguation list
        if len(candidates_list) > 1:
            return ResolverResult(
                status="ambiguous",
                candidates=candidates_list,
            )

        return ResolverResult(status="not_found")
