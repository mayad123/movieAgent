"""
Wikipedia media provider: primary image for a resolved movie entity.

Returns a normalized media_strip payload (movie_title, optional primary_image_url).
Never blocks message rendering; on failure returns movie_title only (UI shows placeholder).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Optional

import requests

from .wikipedia_entity_resolver import ResolvedEntity, WIKIPEDIA_USER_AGENT

if TYPE_CHECKING:
    from .wikipedia_cache import WikipediaCache

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
REQUEST_TIMEOUT = 5
PITHUMB_SIZE = 400


def _extract_url_from_page(p: dict) -> Optional[str]:
    """Extract image URL from pageimages API page dict."""
    thumb = p.get("thumbnail")
    if thumb and isinstance(thumb, dict):
        src = thumb.get("source")
        if src and isinstance(src, str) and src.strip():
            return src.strip()
    original = p.get("original")
    if original and isinstance(original, dict):
        src = original.get("source")
        if src and isinstance(src, str) and src.strip():
            return src.strip()
    return None


def _fetch_page_image(
    session: requests.Session,
    page_title: str,
    cache: Optional["WikipediaCache"] = None,
) -> Optional[str]:
    """
    Fetch primary image URL for a Wikipedia page using pageimages API.
    PageImages often returns no image for titles like "X (film)"; fallback to base "X".
    Returns None on any failure or if no image. Never raises.
    """
    titles_to_try = [page_title]
    # Fallback: "Inception (film)" often has no pageimage; "Inception" does
    m = re.match(r"^(.+?)\s+\((?:film|movie|franchise|film series|animated film)\)\s*$", page_title, re.I)
    if m:
        base = m.group(1).strip()
        if base and base not in titles_to_try:
            titles_to_try.append(base)

    for title in titles_to_try:
        if cache:
            url, hit = cache.get_pageimage(title)
            if hit:
                return url
        try:
            params = {
                "action": "query",
                "prop": "pageimages",
                "titles": title,
                "pithumbsize": PITHUMB_SIZE,
                "pilicense": "any",
                "format": "json",
                "origin": "*",
            }
            r = session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages") or {}
            for _pid, p in pages.items():
                url = _extract_url_from_page(p)
                if url:
                    if cache:
                        cache.set_pageimage(title, url)
                    return url
            if cache:
                cache.set_pageimage(title, None)
        except Exception as e:
            logger.debug("Wikipedia pageimage request failed for %s: %s", title, e)
            # Don't cache failures; allow retry on next request
    return None


class WikipediaMediaProvider:
    """
    Provides a single primary image for a resolved movie entity.
    Normalizes output to the existing meta.media_strip contract.
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

    def get_media_strip(self, entity: ResolvedEntity) -> dict[str, Any]:
        """
        Build media_strip payload for the UI contract.

        Args:
            entity: Resolved movie entity (page_title, display_title).

        Returns:
            Dict with movie_title (required) and primary_image_url (optional).
            If image fetch fails or no image exists, only movie_title is set;
            UI will render the placeholder card. Never raises.
        """
        movie_title = (entity.display_title or "").strip() or entity.page_title.replace("_", " ")
        out: dict[str, Any] = {"movie_title": movie_title}

        try:
            url = _fetch_page_image(self._session, entity.page_title, self._cache)
            if url:
                out["primary_image_url"] = url
        except Exception as e:
            logger.warning("WikipediaMediaProvider get_media_strip failed: %s", e)

        return out
