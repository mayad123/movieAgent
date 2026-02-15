"""
Wikipedia media provider: primary image for a resolved movie entity.

Returns a normalized media_strip payload (movie_title, optional primary_image_url).
Never blocks message rendering; on failure returns movie_title only (UI shows placeholder).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from .wikipedia_entity_resolver import ResolvedEntity

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
REQUEST_TIMEOUT = 5
PITHUMB_SIZE = 400


def _fetch_page_image(session: requests.Session, page_title: str) -> Optional[str]:
    """
    Fetch primary image URL for a Wikipedia page using pageimages API.
    Returns None on any failure or if no image.
    """
    params = {
        "action": "query",
        "prop": "pageimages",
        "titles": page_title,
        "pithumbsize": PITHUMB_SIZE,
        "format": "json",
        "origin": "*",
    }
    try:
        r = session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages") or {}
        for _pid, p in pages.items():
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
    except Exception as e:
        logger.debug("Wikipedia pageimage request failed for %s: %s", page_title, e)
        return None


class WikipediaMediaProvider:
    """
    Provides a single primary image for a resolved movie entity.
    Normalizes output to the existing meta.media_strip contract.
    """

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = REQUEST_TIMEOUT):
        self._session = session or requests.Session()
        self._timeout = timeout

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
            url = _fetch_page_image(self._session, entity.page_title)
            if url:
                out["primary_image_url"] = url
        except Exception as e:
            logger.warning("WikipediaMediaProvider get_media_strip failed: %s", e)

        return out
