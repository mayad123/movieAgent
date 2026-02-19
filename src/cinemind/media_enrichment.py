"""
Shared media enrichment: movie title → poster + metadata.

Uses TMDB only for resolution and poster images. No Wikipedia API calls.
Cache: enrich results by query; TMDB poster URLs by (title, year).
Deterministic; never blocks or raises.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Optional

from .media_cache import MediaCache, get_default_media_cache
from .title_extraction import get_search_phrases, extract_movie_titles

logger = logging.getLogger(__name__)

# Attachments section types (see docs/ATTACHMENTS_SCHEMA.md)
SECTION_PRIMARY_MOVIE = "primary_movie"
SECTION_MOVIE_LIST = "movie_list"
SECTION_DID_YOU_MEAN = "did_you_mean"
SECTION_SCENES = "scenes"

MAX_GALLERY_CANDIDATES = 5

# Poster debug keys (attachment_debug)
POSTER_DEBUG_TMDB_ATTEMPTED = "tmdb_attempted"
POSTER_DEBUG_PROVIDER = "poster_provider"  # "tmdb" | null


def _normalize_enrich_key(user_query: str) -> str:
    q = (user_query or "").strip().lower()
    return " ".join(q.split())


def _tmdb_movie_url(movie_id: int) -> str:
    return f"https://www.themoviedb.org/movie/{movie_id}"


def _build_strip_from_tmdb(
    tr: Any,
    search_text: str,
    token: str,
    cache: Optional[MediaCache] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Build media_strip and poster_debug from TMDBResolveResult.
    Uses cache for poster URL when provided. Returns (media_strip, poster_debug).
    """
    strip: dict[str, Any] = {
        "movie_title": search_text,
        "page_url": "#",
    }
    debug: dict[str, Any] = {POSTER_DEBUG_TMDB_ATTEMPTED: False, POSTER_DEBUG_PROVIDER: None}
    try:
        from config import get_tmdb_access_token
        if not token or not (get_tmdb_access_token() or "").strip():
            return strip, debug
    except Exception:
        return strip, debug

    debug[POSTER_DEBUG_TMDB_ATTEMPTED] = True
    title = (tr.candidates[0].title if tr.candidates else search_text) or search_text
    year = tr.candidates[0].year if tr.candidates else None
    strip["movie_title"] = title
    if year is not None:
        strip["year"] = year

    movie_id = tr.movie_id if tr.movie_id is not None else (tr.candidates[0].id if tr.candidates else None)
    if movie_id is not None:
        strip["tmdb_id"] = movie_id
        strip["page_url"] = _tmdb_movie_url(movie_id)

    # Poster: from cache or from tr.poster_path
    poster_url: Optional[str] = None
    if cache is not None:
        cached_url, hit = cache.get_tmdb_poster(title, year)
        if hit and cached_url:
            poster_url = cached_url
    if not poster_url and (tr.poster_path or "").strip():
        from .tmdb_image_config import get_config, build_image_url, SIZE_POSTER_GALLERY
        cfg = get_config(token)
        poster_url = build_image_url((tr.poster_path or "").strip(), SIZE_POSTER_GALLERY, cfg)
        if cache is not None and poster_url:
            cache.set_tmdb_poster(title, year, poster_url)
    if not poster_url and cache is not None:
        cache.set_tmdb_poster(title, year, None)

    if poster_url:
        strip["primary_image_url"] = poster_url
        debug[POSTER_DEBUG_PROVIDER] = "tmdb"
    return strip, debug


def _build_candidate_from_tmdb(c: Any, token: str = "") -> dict[str, Any]:
    """Build UI-ready candidate from TMDBCandidate (id, title, year, optional poster_path)."""
    out: dict[str, Any] = {
        "movie_title": (c.title or "").strip() or "Unknown",
        "page_url": _tmdb_movie_url(c.id) if c.id else "#",
    }
    if c.year is not None:
        out["year"] = c.year
    poster_path = getattr(c, "poster_path", None) or (c.get("poster_path") if isinstance(c, dict) else None)
    if (poster_path or "").strip() and token:
        try:
            from .tmdb_image_config import get_config, build_image_url, SIZE_POSTER_GALLERY
            cfg = get_config(token)
            url = build_image_url((poster_path or "").strip(), SIZE_POSTER_GALLERY, cfg)
            if url:
                out["primary_image_url"] = url
        except Exception:
            pass
    return out


def _should_show_gallery_tmdb(tr: Any) -> bool:
    """Show did_you_mean when TMDB returned ambiguous with multiple candidates."""
    return tr.status == "ambiguous" and len(tr.candidates or []) > 1


@dataclass
class MediaEnrichmentResult:
    """
    Response payload for UI consumption.
    - media_strip: single result (movie_title, optional primary_image_url, page_url, year, tmdb_id)
    - media_candidates: optional gallery for "Did you mean?"
    - poster_debug: poster-source debug (tmdb_attempted, poster_provider)
    """

    media_strip: dict[str, Any] = field(default_factory=dict)
    media_candidates: list[dict[str, Any]] = field(default_factory=list)
    poster_debug: dict[str, Any] = field(default_factory=dict)
    wiki_poster_policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"media_strip": self.media_strip}
        if self.media_candidates:
            out["media_candidates"] = self.media_candidates
        if self.poster_debug:
            out["poster_debug"] = self.poster_debug
        return out


# Batch concurrency
BATCH_MAX_CONCURRENT = 2
BATCH_MAX_TITLES = 8


def _enrich_one_title_tmdb(
    title: str,
    token: str,
    cache: Optional[MediaCache] = None,
) -> dict[str, Any]:
    """Enrich a single title using TMDB only. Returns UI-ready card dict."""
    title = (title or "").strip()
    if not title:
        return {}
    try:
        from .tmdb_resolver import resolve_movie
        tr = resolve_movie(title, year=None, access_token=token)
        if tr.status == "not_found":
            return {"movie_title": title, "page_url": "#"}
        strip, _ = _build_strip_from_tmdb(tr, title, token, cache=cache)
        return strip
    except Exception as e:
        logger.debug("Batch enrich single title failed for %r: %s", title, e)
        return {"movie_title": title, "page_url": "#"}


def enrich(
    user_query: str,
    fallback_title: Optional[str] = None,
    fallback_from_result: Optional[dict[str, Any]] = None,
    *,
    cache: Optional[MediaCache] = None,
    use_enrich_cache: bool = True,
) -> MediaEnrichmentResult:
    """
    TMDB-only media enrichment: resolve movie from query, get poster from TMDB.

    Never calls Wikipedia. On TMDB disabled or failure, returns placeholder.
    """

    def _fallback_title_value() -> str:
        if fallback_title and (fallback_title or "").strip():
            return (fallback_title or "").strip()
        if fallback_from_result:
            title = (fallback_from_result.get("query") or "").strip()
            if title:
                return title
            sources = fallback_from_result.get("sources") or []
            if sources and isinstance(sources[0], dict):
                t = (sources[0].get("title") or "").strip()
                if t:
                    return t
        return (user_query or "").strip()

    media_cache = cache or get_default_media_cache()
    query_key = _normalize_enrich_key(user_query)

    if use_enrich_cache and query_key and not fallback_from_result and not fallback_title:
        cached = media_cache.get_enrich(query_key)
        if cached is not None:
            return cached

    token = ""
    try:
        from config import is_tmdb_enabled, get_tmdb_access_token
        if is_tmdb_enabled():
            token = (get_tmdb_access_token() or "").strip()
    except Exception:
        pass

    if not token:
        title = _fallback_title_value()
        if title:
            return MediaEnrichmentResult(
                media_strip={"movie_title": title, "page_url": "#"},
                poster_debug={POSTER_DEBUG_TMDB_ATTEMPTED: False, POSTER_DEBUG_PROVIDER: None},
            )
        return MediaEnrichmentResult(media_strip={}, poster_debug={})

    try:
        from .tmdb_resolver import resolve_movie
        for search_text in get_search_phrases(user_query):
            if not (search_text or "").strip():
                continue
            tr = resolve_movie(search_text, year=None, access_token=token)
            if tr.status == "not_found":
                continue
            media_strip, poster_debug = _build_strip_from_tmdb(tr, search_text, token, cache=media_cache)
            if not media_strip.get("movie_title"):
                continue
            payloads = [_build_candidate_from_tmdb(c, token) for c in (tr.candidates or [])[:MAX_GALLERY_CANDIDATES]]
            if not payloads:
                payloads = [dict(media_strip)]
            show_gallery = _should_show_gallery_tmdb(tr) and len(payloads) > 1
            result = MediaEnrichmentResult(
                media_strip=media_strip,
                media_candidates=payloads if show_gallery else [],
                poster_debug=poster_debug,
            )
            if use_enrich_cache and query_key:
                media_cache.set_enrich(query_key, result)
            return result
    except Exception as e:
        logger.debug("Media enrichment failed: %s", e)

    title = _fallback_title_value()
    if title:
        fallback_strip: dict[str, Any] = {"movie_title": title, "page_url": "#"}
        try:
            from .tmdb_resolver import resolve_movie
            tr = resolve_movie(title, year=None, access_token=token)
            if tr.status != "not_found":
                fallback_strip, poster_debug = _build_strip_from_tmdb(tr, title, token, cache=media_cache)
                return MediaEnrichmentResult(media_strip=fallback_strip, poster_debug=poster_debug)
        except Exception:
            pass
        return MediaEnrichmentResult(
            media_strip=fallback_strip,
            poster_debug={POSTER_DEBUG_TMDB_ATTEMPTED: True, POSTER_DEBUG_PROVIDER: None},
        )
    return MediaEnrichmentResult(media_strip={}, poster_debug={})


def enrich_batch(
    titles: list[str],
    *,
    max_concurrent: int = BATCH_MAX_CONCURRENT,
    max_titles: int = BATCH_MAX_TITLES,
    cache: Optional[MediaCache] = None,
) -> list[dict[str, Any]]:
    """
    Enrich multiple titles using TMDB only. Returns list of UI-ready cards.
    """
    media_cache = cache or get_default_media_cache()
    token = ""
    try:
        from config import is_tmdb_enabled, get_tmdb_access_token
        if is_tmdb_enabled():
            token = (get_tmdb_access_token() or "").strip()
    except Exception:
        pass
    if not token:
        return [{"movie_title": (t or "").strip(), "page_url": "#"} for t in (titles or [])[:max_titles] if (t or "").strip()]

    seen: set[str] = set()
    unique: list[str] = []
    for t in (titles or [])[:max_titles]:
        n = (t or "").strip().lower()
        if n and n not in seen:
            seen.add(n)
            unique.append(t.strip())

    if not unique:
        return []

    cards: list[Optional[dict[str, Any]]] = [None] * len(unique)

    def _task(i: int, title: str) -> tuple[int, dict[str, Any]]:
        return (i, _enrich_one_title_tmdb(title, token, cache=media_cache))

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {executor.submit(_task, i, t): i for i, t in enumerate(unique)}
        for future in as_completed(futures):
            try:
                idx, card = future.result()
                if card and card.get("movie_title"):
                    cards[idx] = card
            except Exception as e:
                logger.debug("Batch enrich future failed: %s", e)

    return [c for c in cards if c is not None and c.get("movie_title")]


def _movie_card_item(card: dict[str, Any]) -> dict[str, Any]:
    """Build stable movie-card item for attachments."""
    title = (card.get("movie_title") or card.get("displayTitle") or "").strip()
    item: dict[str, Any] = {"title": title or "Untitled"}
    if card.get("year") is not None:
        item["year"] = card["year"]
    if (card.get("primary_image_url") or "").strip():
        item["imageUrl"] = (card.get("primary_image_url") or "").strip()
    if (card.get("page_url") or "").strip():
        url = (card.get("page_url") or "").strip()
        item["sourceUrl"] = url
        item["id"] = url
    if card.get("tmdb_id") is not None:
        item["tmdbId"] = str(card["tmdb_id"])
    elif (card.get("tmdbId") or "").strip():
        item["tmdbId"] = (card.get("tmdbId") or "").strip()
    return item


def build_attachments_from_media(result: dict[str, Any]) -> dict[str, Any]:
    """Build attachments.sections from media_strip and media_candidates."""
    sections: list[dict[str, Any]] = []
    strip = result.get("media_strip") or {}
    candidates = result.get("media_candidates") or []
    gallery_label = (result.get("media_gallery_label") or "").strip()

    if strip and (strip.get("movie_title") or "").strip():
        sections.append({
            "type": SECTION_PRIMARY_MOVIE,
            "title": "This movie",
            "items": [_movie_card_item(strip)],
        })

    if candidates:
        if gallery_label.lower().startswith("did you mean") or gallery_label == "":
            section_type = SECTION_DID_YOU_MEAN
            title = gallery_label or "Did you mean?"
        else:
            section_type = SECTION_MOVIE_LIST
            title = gallery_label or "Similar movies"
        sections.append({
            "type": section_type,
            "title": title,
            "items": [_movie_card_item(c) for c in candidates if (c.get("movie_title") or c.get("displayTitle") or "").strip()],
        })

    return {"sections": sections}


def attach_media_to_result(
    user_query: str,
    result: dict[str, Any],
    *,
    titles: Optional[list[str]] = None,
    gallery_label: Optional[str] = None,
    cache: Optional[MediaCache] = None,
) -> None:
    """
    Attach media_strip (and optional media_candidates) to result using TMDB only.
    """
    batch_titles = titles if titles is not None else result.get("recommended_movies")
    from_extraction = False
    if not batch_titles or len(batch_titles) <= 1:
        extracted = extract_movie_titles(user_query)
        if extracted.intent == "compare" and len(extracted.titles) >= 2:
            batch_titles = list(extracted.titles)
            from_extraction = True
    if batch_titles and len(batch_titles) > 1:
        cards = enrich_batch(batch_titles, cache=cache)
        if cards:
            result["media_strip"] = cards[0]
            if len(cards) > 1:
                result["media_candidates"] = cards[1:]
            if gallery_label is not None:
                result["media_gallery_label"] = gallery_label
            elif not from_extraction:
                result["media_gallery_label"] = "Similar movies"
            else:
                result["media_gallery_label"] = "Movies"
        result["attachments"] = build_attachments_from_media(result)
        return

    enrichment = enrich(
        user_query,
        fallback_from_result=result,
        cache=cache,
    )
    if enrichment.media_strip.get("movie_title"):
        result["media_strip"] = enrichment.media_strip
        if enrichment.media_candidates:
            result["media_candidates"] = enrichment.media_candidates
    result["attachments"] = build_attachments_from_media(result)
