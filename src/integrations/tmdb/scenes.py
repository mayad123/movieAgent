"""
Pluggable Scenes/Backdrops provider (server-side only).

Used only when a single movie is detected and scenes are requested (intent=scenes).
Never called from the browser.

Provider selection (see get_scenes_provider()):
  - Playground default: Wikipedia-only scenes (ScenesProviderEmpty returns []).
  - If ENABLE_TMDB_SCENES is true and TMDB_READ_ACCESS_TOKEN is set: ScenesProviderTMDB (Bearer auth).
  - If TMDB is not configured or misconfigured: automatic fallback to empty scenes
    (documented); playground mode is not broken.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

# Attribution for UI display (e.g. "Images from The Movie Database")
TMDB_SOURCE_LABEL = "The Movie Database"
TMDB_SOURCE_VALUE = "TMDB"

# Minimum width/height to include (filter out very low-resolution backdrops); None = no filter
MIN_BACKDROP_WIDTH = 300
MIN_BACKDROP_HEIGHT = 150


# Normalized scene item for attachments schema (imageUrl required; caption/sourceUrl/attribution optional)
@dataclass(frozen=True)
class SceneItem:
    image_url: str
    caption: Optional[str] = None
    source_url: Optional[str] = None
    source: Optional[str] = None  # e.g. "TMDB" for attribution
    source_label: Optional[str] = None  # e.g. "The Movie Database" for UI

    def to_attachment_item(self) -> dict[str, Any]:
        out: dict[str, Any] = {"imageUrl": self.image_url}
        if self.caption is not None:
            out["caption"] = self.caption
        if self.source_url is not None:
            out["sourceUrl"] = self.source_url
        if self.source is not None:
            out["source"] = self.source
        if self.source_label is not None:
            out["sourceLabel"] = self.source_label
        return out


class ScenesProvider(Protocol):
    """Interface for pluggable scenes/backdrops providers. Server-side only."""

    def fetch_scenes(self, title: str, year: Optional[int] = None) -> list[SceneItem]:
        """
        Return a normalized list of scene/backdrop images for the given movie.

        Must not raise; return [] on any failure or when no images are available.
        """
        ...


class ScenesProviderEmpty:
    """Fallback provider: returns no scenes (Wikipedia-only / no external scenes)."""

    def fetch_scenes(self, title: str, year: Optional[int] = None) -> list[SceneItem]:
        return []


def _bearer_headers(token: str) -> dict[str, str]:
    """Build request headers with Bearer auth. Token must not be logged."""
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


class ScenesProviderTMDB:
    """
    TMDB-based scenes/backdrops provider (server-side only).

    Authenticates with TMDB using the API Read Access Token (Bearer header).
    Uses TMDB /configuration for image base URL and sizes (cached); builds image URLs
    via centralized build_image_url (backdrop_gallery). Search → resolve → details by ID.
    """

    BASE_URL = "https://api.themoviedb.org/3"
    MOVIE_PAGE_BASE = "https://www.themoviedb.org/movie"

    def __init__(self, access_token: str, timeout: float = 10.0, max_backdrops: int = 8):
        self._token = (access_token or "").strip()
        self._timeout = max(1.0, timeout)
        self._max_backdrops = max(1, min(20, max_backdrops))

    def fetch_scenes(self, title: str, year: Optional[int] = None) -> list[SceneItem]:
        """
        Fetch backdrops for the movie. Does not raise; returns [] on any failure.

        Uses Search → ID → Details: resolve_movie() selects best candidate deterministically;
        if confidence is low or ambiguous, returns [] (no auto-select; "Did you mean?" candidates
        available from resolver for caller to use).
        """
        if not self._token or not (title or "").strip():
            return []
        try:
            from .resolver import resolve_movie
            result = resolve_movie(
                (title or "").strip(),
                year=year,
                access_token=self._token,
                timeout=self._timeout,
            )
            if result.status != "resolved" or result.movie_id is None:
                if result.status == "ambiguous":
                    logger.debug("TMDB ambiguous for %r: returning no scenes (Did you mean? candidates)", title)
                return []
            return self._fetch_backdrops(result.movie_id, title)
        except Exception as e:
            logger.debug("TMDB scenes fetch failed for %r: %s", title, e)
            return []

    def _fetch_backdrops(self, movie_id: int, title: str) -> list[SceneItem]:
        """
        Fetch backdrops from TMDB movie images endpoint; normalize into scenes gallery items.

        Deterministic: sort by vote_average desc, then vote_count desc (stable across runs).
        Cap at max_backdrops; filter out very low-resolution images (width/height below min).
        Each item includes attribution (source=TMDB, sourceLabel) for UI display.
        """
        try:
            import urllib.request
            url = f"{self.BASE_URL}/movie/{movie_id}/images"
            req = urllib.request.Request(url, headers=_bearer_headers(self._token))
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = self._decode_json(resp.read())
            backdrops = (data or {}).get("backdrops") or []

            # Filter out very low-resolution (deterministic)
            def _accept(b: dict[str, Any]) -> bool:
                w = b.get("width") or 0
                h = b.get("height") or 0
                if MIN_BACKDROP_WIDTH and w > 0 and w < MIN_BACKDROP_WIDTH:
                    return False
                if MIN_BACKDROP_HEIGHT and h > 0 and h < MIN_BACKDROP_HEIGHT:
                    return False
                return True

            backdrops = [b for b in backdrops if _accept(b)]

            # Deterministic sort: vote_average desc, then vote_count desc (consistent across runs)
            backdrops = sorted(
                backdrops,
                key=lambda b: (-(b.get("vote_average") or 0), -(b.get("vote_count") or 0)),
            )

            from .image_config import get_config, build_image_url, SIZE_BACKDROP_GALLERY
            img_config = get_config(self._token, timeout=self._timeout)
            source_url = f"{self.MOVIE_PAGE_BASE}/{movie_id}"
            seen_urls: set[str] = set()
            items: list[SceneItem] = []
            for b in backdrops[: self._max_backdrops]:
                path = (b.get("file_path") or "").strip()
                if not path or path.startswith("http"):
                    continue
                image_url = build_image_url(path, SIZE_BACKDROP_GALLERY, img_config)
                if not image_url or image_url in seen_urls:
                    continue
                seen_urls.add(image_url)
                caption = None
                if b.get("vote_count"):
                    caption = f"Backdrop ({b.get('vote_count')} votes)"
                items.append(
                    SceneItem(
                        image_url=image_url,
                        caption=caption,
                        source_url=source_url,
                        source=TMDB_SOURCE_VALUE,
                        source_label=TMDB_SOURCE_LABEL,
                    )
                )
            return items
        except Exception as e:
            logger.debug("TMDB images fetch failed for movie_id=%s: %s", movie_id, e)
            return []

    @staticmethod
    def _decode_json(payload: bytes) -> Any:
        import json
        return json.loads(payload.decode("utf-8"))


def get_scenes_provider() -> ScenesProvider:
    """
    Return the active scenes provider.

    - If TMDB is enabled and configured (ENABLE_TMDB_SCENES + TMDB_READ_ACCESS_TOKEN): ScenesProviderTMDB (Bearer).
    - Otherwise: ScenesProviderEmpty (Wikipedia-only / no external scenes; playground default).

    Safe fallback when TMDB is disabled or misconfigured: always returns a provider that
    does not raise and returns [] on failure. Playground mode never breaks when TMDB is off.
    """
    from config import ENABLE_TMDB_SCENES, TMDB_READ_ACCESS_TOKEN
    if ENABLE_TMDB_SCENES and TMDB_READ_ACCESS_TOKEN:
        return ScenesProviderTMDB(access_token=TMDB_READ_ACCESS_TOKEN)
    return ScenesProviderEmpty()


__all__ = [
    "SceneItem",
    "ScenesProvider",
    "ScenesProviderEmpty",
    "ScenesProviderTMDB",
    "get_scenes_provider",
]
