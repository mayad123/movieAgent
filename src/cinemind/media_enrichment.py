"""
Shared Wikipedia-only media enrichment: type movie title → show image.

Deterministic enrichment step that runs regardless of Tavily/OpenAI availability.
Reuses WikipediaEntityResolver + WikipediaMediaProvider. Never blocks or raises.
Used by both playground_server and agent for consistent media_strip payloads.

Ambiguity handling: returns either a single best match (hero) or a small gallery
of candidates for "Did you mean...?" when the query is ambiguous (remakes, sequels).

Batch enrichment: enrich_batch(titles) for multi-movie responses (e.g. similar movies)
with bounded concurrency to avoid spiking Wikipedia.
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
)
from .wikipedia_media_provider import WikipediaMediaProvider
from .wikipedia_cache import (
    WikipediaCache,
    get_default_wikipedia_cache,
    CACHE_TTL_ENRICH,
)

logger = logging.getLogger(__name__)

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


@dataclass
class MediaEnrichmentResult:
    """
    Stable response payload for UI consumption.
    - media_strip: single result (movie_title, optional primary_image_url, page_url, year)
      — always present when a title is available; used as hero in single mode
    - media_candidates: optional gallery for "Did you mean...?" when ambiguous
      — each item: movie_title, year?, page_url, primary_image_url?
    """

    media_strip: dict[str, Any] = field(default_factory=dict)
    media_candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"media_strip": self.media_strip}
        if self.media_candidates:
            out["media_candidates"] = self.media_candidates
        return out


def _normalize_enrich_key(user_query: str) -> str:
    """Normalize user query for enrich-level cache key."""
    q = (user_query or "").strip().lower()
    return " ".join(q.split())


def _enrich_one_title_to_card(
    title: str,
    *,
    resolver: WikipediaEntityResolver,
    provider: WikipediaMediaProvider,
) -> dict[str, Any]:
    """
    Enrich a single title to a UI-ready card. Never raises; on failure returns placeholder.
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

    Each item degrades gracefully: one failure does not fail the batch.
    Returns list of cards (same shape as media_candidates items) in input order.

    Args:
        titles: List of movie title strings to enrich.
        max_concurrent: Max concurrent Wikipedia requests (default 2).
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
        return (i, _enrich_one_title_to_card(title, resolver=resolver, provider=provider))

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
            return cached

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
            if first.get("year") is not None:
                media_strip["year"] = first["year"]

            show_gallery = _should_show_gallery(all_candidates) and len(payloads) > 1

            result = MediaEnrichmentResult(
                media_strip=media_strip,
                media_candidates=payloads if show_gallery else [],
            )
            if use_enrich_cache and query_key:
                wiki_cache.set_enrich(query_key, result)
            return result
    except Exception as e:
        logger.debug("Media enrichment failed: %s", e)

    # Fallback: Wikipedia failed or no candidates
    title = _fallback_title_value()
    if title:
        return MediaEnrichmentResult(media_strip={"movie_title": title})
    return MediaEnrichmentResult(media_strip={})


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
