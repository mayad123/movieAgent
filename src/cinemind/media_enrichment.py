"""
Shared media enrichment: movie title → poster + metadata.

Resolution: Wikipedia (correct page/site). Poster source policy: prefer Wikipedia when
the resolved page is confidently a film and has a usable image; else TMDB fallback.
Cache layering: base cache stores Wikipedia enrichment only; on cache hit we copy the
result, apply poster policy (and optional TMDB poster URL cache) in-memory, and return
the copy so the stored entry is never mutated. TMDB poster URLs can be cached by
(title, year) to avoid repeated TMDB calls. Deterministic; never blocks or raises.

Ambiguity: single best match (hero) or did_you_mean gallery when top candidates are close.
Batch: enrich_batch(titles) with same poster policy per card.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Optional

from .wikipedia_entity_resolver import (
    WikipediaEntityResolver,
    ResolvedEntity,
    ResolverResult,
    _build_page_url,
    FILM_CONFIDENCE_THRESHOLD,
)
from .wikipedia_media_provider import WikipediaMediaProvider
from .wikipedia_cache import (
    WikipediaCache,
    get_default_wikipedia_cache,
    CACHE_TTL_ENRICH,
)

logger = logging.getLogger(__name__)

# Attachments section types (see docs/ATTACHMENTS_SCHEMA.md)
SECTION_PRIMARY_MOVIE = "primary_movie"
SECTION_MOVIE_LIST = "movie_list"
SECTION_DID_YOU_MEAN = "did_you_mean"
SECTION_SCENES = "scenes"

# Score gap above which we treat the top candidate as a clear winner (single, not gallery)
CLEAR_WIN_SCORE_GAP = 2
MAX_GALLERY_CANDIDATES = 5

# Batch enrichment: max concurrent Wikipedia requests, max titles per batch
BATCH_MAX_CONCURRENT = 2
BATCH_MAX_TITLES = 8

from .title_extraction import get_search_phrases, extract_movie_titles


def _build_candidate_payload(
    c: dict[str, Any],
    strip: dict[str, Any],
) -> dict[str, Any]:
    """Build UI-ready candidate: movie_title, year, page_url, primary_image_url."""
    out: dict[str, Any] = {
        "movie_title": strip.get("movie_title") or c.get("displayTitle", ""),
        "page_url": c.get("page_url", ""),
    }
    if c.get("year") is not None:
        out["year"] = c["year"]
    if strip.get("primary_image_url"):
        out["primary_image_url"] = strip["primary_image_url"]
    return out


def _should_show_gallery(candidates: list[dict[str, Any]]) -> bool:
    """
    Decision: single best match vs small gallery.
    Gallery when 2+ candidates with close scores (score gap < CLEAR_WIN_SCORE_GAP).
    """
    if len(candidates) <= 1:
        return False
    top_score = candidates[0].get("score", 0)
    second_score = candidates[1].get("score", 0) if len(candidates) > 1 else 0
    if top_score - second_score >= CLEAR_WIN_SCORE_GAP:
        return False  # Clear winner → single
    return True  # Close race → gallery


# Poster source policy debug keys (attachment_debug / logging)
POSTER_DEBUG_WIKIPEDIA_PAGE_TITLE = "wikipedia_page_title"
POSTER_DEBUG_WIKIPEDIA_PAGE_URL = "wikipedia_page_url"
POSTER_DEBUG_FILM_CONFIDENCE = "film_confidence"
POSTER_DEBUG_FILM_CONFIDENCE_REASONS = "film_confidence_reasons"
POSTER_DEBUG_WIKIPEDIA_HAD_POSTER = "wikipedia_had_poster"
POSTER_DEBUG_TMDB_FALLBACK_RAN = "tmdb_fallback_ran"
POSTER_DEBUG_TMDB_FALLBACK_SUCCEEDED = "tmdb_fallback_succeeded"
POSTER_DEBUG_PROVIDER = "poster_provider"  # "wikipedia" | "tmdb" | null
POSTER_DEBUG_TMDB_ATTEMPTED = "tmdb_attempted"  # Runtime verification: true if TMDB was actually attempted this request
# Legacy aliases for backward compatibility
POSTER_DEBUG_OVERRIDE_RAN = "tmdb_poster_override_ran"
POSTER_DEBUG_OVERRIDE_SUCCEEDED = "tmdb_poster_override_succeeded"


@dataclass
class MediaEnrichmentResult:
    """
    Stable response payload for UI consumption.
    - media_strip: single result (movie_title, optional primary_image_url, page_url, year)
    - media_candidates: optional gallery for "Did you mean...?" when ambiguous
    - poster_debug: poster-source policy debug (film_confidence, provider, etc.)
    - wiki_poster_policy: stored for cache-hit re-run (film_confidence, reasons, wiki_page_title, wiki_page_url)
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
        if self.wiki_poster_policy:
            out["wiki_poster_policy"] = self.wiki_poster_policy
        return out


def _normalize_enrich_key(user_query: str) -> str:
    """Normalize user query for enrich-level cache key."""
    q = (user_query or "").strip().lower()
    return " ".join(q.split())


def _apply_tmdb_poster(
    media_strip: dict[str, Any],
    title: str,
    year: Optional[int],
    wiki_film_confidence: float,
    *,
    tmdb_poster_cache: Optional[WikipediaCache] = None,
) -> dict[str, Any]:
    """
    Attempt TMDB poster lookup and set media_strip["primary_image_url"] only when policy says fallback is needed.
    Policy: favor Wikipedia when it is confidently a film AND has an image; otherwise fall back to TMDB.

    - Runs only when tmdb_enabled (config.is_tmdb_enabled()).
    - If wiki_film_confidence >= threshold and media_strip already has primary_image_url → no-op (keep Wikipedia).
    - Else: resolve_movie(title, year), build URL via tmdb_image_config.build_image_url; set primary_image_url when found.
    Uses tmdb_poster_cache when provided to avoid repeated TMDB calls.

    Returns a small result dict: applied (bool), provider ("tmdb"|"wikipedia"|None) for debug.
    Does not log secrets.
    """
    had_wikipedia = bool((media_strip.get("primary_image_url") or "").strip())
    result: dict[str, Any] = {"applied": False, "provider": "wikipedia" if had_wikipedia else None, "tmdb_attempted": False}

    try:
        from .config import is_tmdb_enabled, get_tmdb_access_token
        if not is_tmdb_enabled():
            logger.info("tmdb_attempted=false reason=tmdb_not_enabled (backend config)")
            return result
        # Policy: keep Wikipedia when confident film page and it has a poster
        if wiki_film_confidence >= FILM_CONFIDENCE_THRESHOLD and had_wikipedia:
            logger.info("tmdb_attempted=false reason=policy_keep_wikipedia confidence=%.2f", wiki_film_confidence)
            return result
        token = get_tmdb_access_token()
        if not token:
            logger.info("tmdb_attempted=false reason=token_empty")
            return result

        result["tmdb_attempted"] = True
        logger.info("tmdb_attempted=true title=%r year=%s", (title or "")[:60], year)

        url: Optional[str] = None
        if tmdb_poster_cache is not None:
            cached_url, cache_hit = tmdb_poster_cache.get_tmdb_poster(title, year)
            if cache_hit:
                if cached_url:
                    media_strip["primary_image_url"] = cached_url
                    result["applied"] = True
                    result["provider"] = "tmdb"
                return result

        from .tmdb_resolver import resolve_movie
        from .tmdb_image_config import get_config, build_image_url, SIZE_POSTER_GALLERY
        tr = resolve_movie(title, year=year, access_token=token)
        path = (tr.poster_path or "").strip()
        if path:
            cfg = get_config(token)
            url = build_image_url(path, SIZE_POSTER_GALLERY, cfg)
            if url:
                media_strip["primary_image_url"] = url
                if tmdb_poster_cache is not None:
                    tmdb_poster_cache.set_tmdb_poster(title, year, url)
                result["applied"] = True
                result["provider"] = "tmdb"
        else:
            if tmdb_poster_cache is not None:
                tmdb_poster_cache.set_tmdb_poster(title, year, None)
        if not result["applied"]:
            result["provider"] = "wikipedia" if had_wikipedia else None
    except Exception as e:
        logger.debug("_apply_tmdb_poster failed for title=%r: %s", (title or "")[:60], e)
        result["provider"] = "wikipedia" if had_wikipedia else None
    return result


def _apply_poster_source_policy(
    media_strip: dict[str, Any],
    film_confidence: float,
    film_confidence_reasons: list[str],
    wiki_page_title: str,
    wiki_page_url: str,
    title: str,
    year: Optional[int],
    tmdb_poster_cache: Optional[WikipediaCache] = None,
) -> dict[str, Any]:
    """
    Centralized poster-source policy: prefer Wikipedia when it is clearly the film and has an image;
    otherwise use TMDB fallback. Does not force override; mutates media_strip only when policy chooses TMDB.
    When tmdb_poster_cache is provided, TMDB poster URLs are cached by (title, year) to reduce repeated calls.
    Does not log secrets.

    Returns debug dict: wikipedia_page_title, wikipedia_page_url, film_confidence, film_confidence_reasons,
    wikipedia_had_poster, tmdb_fallback_ran, tmdb_fallback_succeeded, poster_provider.
    """
    wiki_url = (wiki_page_url or "").strip()
    wiki_title = (wiki_page_title or "").strip().replace("_", " ")
    had_wikipedia = bool((media_strip.get("primary_image_url") or "").strip())
    debug: dict[str, Any] = {
        POSTER_DEBUG_WIKIPEDIA_PAGE_TITLE: wiki_title or None,
        POSTER_DEBUG_WIKIPEDIA_PAGE_URL: wiki_url or None,
        POSTER_DEBUG_FILM_CONFIDENCE: round(film_confidence, 2),
        POSTER_DEBUG_FILM_CONFIDENCE_REASONS: film_confidence_reasons or [],
        POSTER_DEBUG_WIKIPEDIA_HAD_POSTER: had_wikipedia,
        POSTER_DEBUG_TMDB_FALLBACK_RAN: False,
        POSTER_DEBUG_TMDB_FALLBACK_SUCCEEDED: False,
        POSTER_DEBUG_PROVIDER: "wikipedia" if had_wikipedia else None,
        POSTER_DEBUG_TMDB_ATTEMPTED: False,
        # Legacy
        POSTER_DEBUG_OVERRIDE_RAN: False,
        POSTER_DEBUG_OVERRIDE_SUCCEEDED: False,
    }

    # Policy: favor Wikipedia when confidently film AND has image; else fall back to TMDB
    if film_confidence >= FILM_CONFIDENCE_THRESHOLD and had_wikipedia:
        logger.info("tmdb_attempted=false reason=policy_keep_wikipedia confidence=%.2f", film_confidence)
        logger.debug(
            "Poster source policy: using Wikipedia (confidence=%.2f, page=%r)",
            film_confidence,
            (wiki_title or "")[:50],
        )
        return debug

    # Fallback: call _apply_tmdb_poster (only when policy says so; no forced override)
    tmdb_result = _apply_tmdb_poster(
        media_strip,
        title,
        year,
        film_confidence,
        tmdb_poster_cache=tmdb_poster_cache,
    )
    debug[POSTER_DEBUG_TMDB_FALLBACK_RAN] = True
    debug[POSTER_DEBUG_OVERRIDE_RAN] = True
    debug[POSTER_DEBUG_TMDB_FALLBACK_SUCCEEDED] = tmdb_result.get("applied", False)
    debug[POSTER_DEBUG_OVERRIDE_SUCCEEDED] = tmdb_result.get("applied", False)
    debug[POSTER_DEBUG_PROVIDER] = tmdb_result.get("provider")
    debug[POSTER_DEBUG_TMDB_ATTEMPTED] = tmdb_result.get("tmdb_attempted", False)
    if tmdb_result.get("applied"):
        logger.info(
            "Poster source policy: TMDB fallback succeeded for title=%r (wiki_confidence=%.2f)",
            (title or "")[:60],
            film_confidence,
        )
    else:
        logger.debug(
            "Poster source policy: TMDB fallback ran but no poster; provider=%s",
            debug[POSTER_DEBUG_PROVIDER],
        )
    return debug


def _enrich_one_title_to_card(
    title: str,
    *,
    resolver: WikipediaEntityResolver,
    provider: WikipediaMediaProvider,
    tmdb_poster_cache: Optional[WikipediaCache] = None,
) -> dict[str, Any]:
    """
    Enrich a single title to a UI-ready card. Applies the same poster-source policy as
    single-movie (Wikipedia when confident + has image, else TMDB fallback). Never raises;
    on failure returns placeholder. Partial failure in poster policy does not break the card.
    """
    title = (title or "").strip()
    if not title:
        return {}
    try:
        resolve_result = resolver.resolve(title)
        entity = _entity_from_resolve_result(resolve_result)
        if entity is None:
            return {"movie_title": title, "page_url": "#"}
        strip = provider.get_media_strip(entity)
        if not strip.get("movie_title"):
            return {"movie_title": title, "page_url": "#"}
        out: dict[str, Any] = {
            "movie_title": strip.get("movie_title") or title,
            "page_url": _build_page_url(entity.page_title),
        }
        if strip.get("primary_image_url"):
            out["primary_image_url"] = strip["primary_image_url"]
        year = None
        if resolve_result.candidates:
            year = resolve_result.candidates[0].get("year")
        if year is None:
            from .wikipedia_entity_resolver import _extract_year_from_title
            year = _extract_year_from_title(entity.page_title)
        if year is not None:
            out["year"] = year
        # Batch per-card: run _apply_tmdb_poster via policy (same as normal/cache-hit). tmdb_poster_cache optional.
        try:
            film_confidence = getattr(resolve_result, "film_confidence", 0.0) or 0.0
            film_reasons = getattr(resolve_result, "film_confidence_reasons", None) or []
            if resolve_result.candidates:
                first_c = resolve_result.candidates[0]
                film_confidence = first_c.get("film_confidence", film_confidence)
                film_reasons = first_c.get("film_confidence_reasons", film_reasons)
            poster_debug = _apply_poster_source_policy(
                out,
                film_confidence,
                film_reasons,
                entity.page_title,
                _build_page_url(entity.page_title),
                title,
                year,
                tmdb_poster_cache=tmdb_poster_cache,
            )
            if poster_debug.get(POSTER_DEBUG_PROVIDER):
                out[POSTER_DEBUG_PROVIDER] = poster_debug[POSTER_DEBUG_PROVIDER]
            logger.debug(
                "Poster source policy (batch): title=%r confidence=%.2f provider=%s tmdb_fallback_ran=%s",
                (title or "")[:50],
                film_confidence,
                poster_debug.get(POSTER_DEBUG_PROVIDER),
                poster_debug.get(POSTER_DEBUG_TMDB_FALLBACK_RAN),
            )
        except Exception as e:
            logger.debug("Poster source policy in batch enrich skipped for %r: %s", title, e)
        return out
    except Exception as e:
        logger.debug("Batch enrich single title failed for %r: %s", title, e)
        return {"movie_title": title, "page_url": "#"}


def enrich_batch(
    titles: list[str],
    *,
    max_concurrent: int = BATCH_MAX_CONCURRENT,
    max_titles: int = BATCH_MAX_TITLES,
    resolver: Optional[WikipediaEntityResolver] = None,
    provider: Optional[WikipediaMediaProvider] = None,
    cache: Optional[WikipediaCache] = None,
) -> list[dict[str, Any]]:
    """
    Enrich multiple titles to UI-ready cards with bounded concurrency.

    Applies the same poster-source policy per card as single-movie: prefer Wikipedia when
    confident film + has image, else TMDB fallback. Concurrency is capped (max_concurrent)
    to avoid rate limits. Ordering is preserved. Partial failure safe: one TMDB or Wikipedia
    failure for a card does not break the batch; that card gets a placeholder or Wikipedia-only result.

    Args:
        titles: List of movie title strings to enrich.
        max_concurrent: Max concurrent workers (default 2).
        max_titles: Max titles to process (default 8).
        resolver, provider, cache: Optional DI (uses defaults if not provided).

    Returns:
        List of card dicts: movie_title, page_url, optional year, primary_image_url.
        Placeholder card (movie_title + page_url="#") on resolution failure.
    """
    wiki_cache = cache or get_default_wikipedia_cache()
    resolver = resolver or WikipediaEntityResolver(cache=wiki_cache)
    provider = provider or WikipediaMediaProvider(cache=wiki_cache)

    # Dedupe by normalized title, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for t in (titles or [])[:max_titles]:
        n = (t or "").strip().lower()
        if n and n not in seen:
            seen.add(n)
            unique.append(t.strip())

    if not unique:
        return []

    cards: list[Optional[dict[str, Any]]] = [None] * len(unique)  # preserve order

    def _task(i: int, title: str) -> tuple[int, dict[str, Any]]:
        return (i, _enrich_one_title_to_card(title, resolver=resolver, provider=provider, tmdb_poster_cache=wiki_cache))

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


def _entity_from_resolve_result(resolve_result: ResolverResult) -> Optional[ResolvedEntity]:
    """Get ResolvedEntity from resolver output: either resolved_entity or first candidate."""
    if resolve_result.resolved_entity is not None:
        return resolve_result.resolved_entity
    if resolve_result.candidates:
        c = resolve_result.candidates[0]
        return ResolvedEntity(
            page_title=c.get("pageTitle", ""),
            display_title=c.get("displayTitle", c.get("pageTitle", "").replace("_", " ")),
        )
    return None


def enrich(
    user_query: str,
    fallback_title: Optional[str] = None,
    fallback_from_result: Optional[dict[str, Any]] = None,
    *,
    resolver: Optional[WikipediaEntityResolver] = None,
    provider: Optional[WikipediaMediaProvider] = None,
    cache: Optional[WikipediaCache] = None,
    use_enrich_cache: bool = True,
) -> MediaEnrichmentResult:
    """
    Deterministic Wikipedia-only media enrichment: resolve movie from query, fetch image.

    Args:
        user_query: Raw user input (e.g. "Who directed The Matrix?", "Inception").
        fallback_title: Optional title to use when Wikipedia resolution fails.
        fallback_from_result: Optional result dict; used to derive fallback from result.query
            or first source title when fallback_title is not provided.
        resolver: Optional WikipediaEntityResolver instance (for testing/di).
        provider: Optional WikipediaMediaProvider instance (for testing/di).
        cache: Optional WikipediaCache; uses default if not provided.
        use_enrich_cache: If True, cache full result by normalized query (default True).

    Returns:
        MediaEnrichmentResult with media_strip (always) and optional media_candidates.
        On any failure, returns placeholder media_strip with movie_title only.
        Never raises.
    """
    wiki_cache = cache or get_default_wikipedia_cache()
    resolver = resolver or WikipediaEntityResolver(cache=wiki_cache)
    provider = provider or WikipediaMediaProvider(cache=wiki_cache)

    # Enrich-level cache: instant response for repeated identical queries
    query_key = _normalize_enrich_key(user_query)
    if use_enrich_cache and query_key and not fallback_from_result and not fallback_title:
        cached = wiki_cache.get_enrich(query_key)
        if cached is not None:
            # Cache layering: return in-memory upgraded response; do not rewrite the cache entry.
            # Copy base enrichment (Wikipedia-derived + film-confidence metadata) so we never mutate stored cache.
            copy_strip = dict(cached.media_strip)
            result_copy = MediaEnrichmentResult(
                media_strip=copy_strip,
                media_candidates=list(cached.media_candidates),
                poster_debug={},
                wiki_poster_policy=dict(cached.wiki_poster_policy),
            )
            policy = getattr(cached, "wiki_poster_policy", None) or {}
            film_confidence = policy.get("film_confidence", 0.0)
            film_reasons = policy.get("film_confidence_reasons") or []
            wiki_title = policy.get("wikipedia_page_title") or (copy_strip.get("movie_title") or query_key)
            wiki_url = policy.get("wikipedia_page_url") or (copy_strip.get("page_url") or "#")
            year_cached = copy_strip.get("year") if isinstance(copy_strip.get("year"), int) else None
            # Run _apply_tmdb_poster via policy on cache-hit (same behavior as normal path). Per-title TMDB poster
            # cache (tmdb_poster_cache=wiki_cache) avoids calling TMDB on every cache hit.
            poster_debug = _apply_poster_source_policy(
                result_copy.media_strip,
                film_confidence,
                film_reasons,
                wiki_title,
                wiki_url,
                query_key,
                year_cached,
                tmdb_poster_cache=wiki_cache,
            )
            result_copy.poster_debug = poster_debug
            logger.debug(
                "Poster source policy on cache hit (in-memory upgrade): confidence=%.2f, provider=%s, tmdb_fallback_ran=%s",
                film_confidence,
                poster_debug.get(POSTER_DEBUG_PROVIDER),
                poster_debug.get(POSTER_DEBUG_TMDB_FALLBACK_RAN),
            )
            return result_copy

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

    try:
        for search_text in get_search_phrases(user_query):
            resolve_result = resolver.resolve(search_text)
            entity = _entity_from_resolve_result(resolve_result)
            if entity is None:
                continue

            best_strip = provider.get_media_strip(entity)
            if not best_strip.get("movie_title"):
                continue

            # Build UI-ready candidate payloads for all candidates
            all_candidates = resolve_result.candidates or []
            payloads: list[dict[str, Any]] = []
            for c in all_candidates[:MAX_GALLERY_CANDIDATES]:
                e = ResolvedEntity(
                    page_title=c.get("pageTitle", ""),
                    display_title=c.get("displayTitle", c.get("pageTitle", "").replace("_", " ")),
                )
                strip = provider.get_media_strip(e)
                if strip.get("movie_title"):
                    payloads.append(_build_candidate_payload(c, strip))

            if not payloads:
                c = {
                    "pageTitle": entity.page_title,
                    "displayTitle": entity.display_title,
                    "year": None,
                    "page_url": _build_page_url(entity.page_title),
                    "score": 0,
                }
                payloads = [_build_candidate_payload(c, best_strip)]

            # Add page_url/year to media_strip
            media_strip = dict(best_strip)
            first = all_candidates[0] if all_candidates else payloads[0]
            media_strip["page_url"] = first.get("page_url") or _build_page_url(entity.page_title)
            year = first.get("year")
            if year is not None:
                media_strip["year"] = year
            if year is None:
                from .wikipedia_entity_resolver import _extract_year_from_title
                year = _extract_year_from_title(entity.page_title)

            # Normal enrich path: run _apply_tmdb_poster via policy (prefer Wikipedia when confident + has image,
            # else TMDB fallback). tmdb_poster_cache reduces repeated TMDB calls for same title/year.
            film_confidence = getattr(resolve_result, "film_confidence", 0.0) or 0.0
            film_reasons = getattr(resolve_result, "film_confidence_reasons", None) or []
            wiki_url = _build_page_url(entity.page_title)
            poster_debug = _apply_poster_source_policy(
                media_strip,
                film_confidence,
                film_reasons,
                entity.page_title,
                wiki_url,
                search_text,
                year,
                tmdb_poster_cache=wiki_cache,
            )
            wiki_poster_policy = {
                "film_confidence": film_confidence,
                "film_confidence_reasons": film_reasons,
                "wikipedia_page_title": entity.page_title,
                "wikipedia_page_url": wiki_url,
            }

            # Show did_you_mean when resolver said ambiguous (e.g. low film_confidence) or when top two are close
            show_gallery = (
                getattr(resolve_result, "status", "") == "ambiguous"
                or (_should_show_gallery(all_candidates) and len(payloads) > 1)
            )

            result = MediaEnrichmentResult(
                media_strip=media_strip,
                media_candidates=payloads if show_gallery else [],
                poster_debug=poster_debug,
                wiki_poster_policy=wiki_poster_policy,
            )
            if use_enrich_cache and query_key:
                wiki_cache.set_enrich(query_key, result)
            return result
    except Exception as e:
        logger.debug("Media enrichment failed: %s", e)

    # Fallback: Wikipedia failed or no candidates — still try TMDB for a poster and set poster_debug
    title = _fallback_title_value()
    if title:
        fallback_strip: dict[str, Any] = {"movie_title": title, "page_url": "#"}
        poster_debug = _apply_poster_source_policy(
            fallback_strip,
            0.0,
            [],
            "",
            "#",
            title,
            None,
            tmdb_poster_cache=wiki_cache,
        )
        return MediaEnrichmentResult(media_strip=fallback_strip, poster_debug=poster_debug)
    return MediaEnrichmentResult(media_strip={}, poster_debug={})


def _movie_card_item(card: dict[str, Any]) -> dict[str, Any]:
    """Build stable movie-card item for attachments (title, year?, imageUrl?, sourceUrl?, id?)."""
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
    return item


def build_attachments_from_media(result: dict[str, Any]) -> dict[str, Any]:
    """
    Build attachments.sections from media_strip and media_candidates (and media_gallery_label).

    Section types: primary_movie (hero), movie_list | did_you_mean (candidates).
    Keeps backward compatibility: does not remove or alter media_strip/media_candidates.
    See docs/ATTACHMENTS_SCHEMA.md.
    """
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
        # did_you_mean for disambiguation (no label or "Did you mean?"); else movie_list
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
    resolver: Optional[WikipediaEntityResolver] = None,
    provider: Optional[WikipediaMediaProvider] = None,
) -> None:
    """
    Attach media_strip (and optional media_candidates) to a result dict in-place.

    When titles is provided and len > 1: runs batch enrichment, sets media_candidates
    with gallery_label (e.g. "Similar movies"). First card is hero (media_strip).
    When titles is None or len <= 1: uses enrich() with user_query and fallback.

    Never raises; on failure, attaches placeholder media_strip with movie_title only.
    """
    # Batch path: multiple titles from recommended_movies, explicit titles, or "X and Y" extraction
    batch_titles = titles if titles is not None else result.get("recommended_movies")
    from_extraction = False
    if not batch_titles or len(batch_titles) <= 1:
        extracted = extract_movie_titles(user_query)
        if extracted.intent == "compare" and len(extracted.titles) >= 2:
            batch_titles = list(extracted.titles)
            from_extraction = True
    if batch_titles and len(batch_titles) > 1:
        cards = enrich_batch(batch_titles, resolver=resolver, provider=provider)
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

    # Single-title path
    enrichment = enrich(
        user_query,
        fallback_from_result=result,
        resolver=resolver,
        provider=provider,
    )
    if enrichment.media_strip.get("movie_title"):
        result["media_strip"] = enrichment.media_strip
        if enrichment.media_candidates:
            result["media_candidates"] = enrichment.media_candidates
    result["attachments"] = build_attachments_from_media(result)
