"""
Shared media enrichment: movie title → poster + metadata.

Uses TMDB only for resolution and poster images. No Wikipedia API calls.
Cache: enrich results by query; TMDB poster URLs by (title, year).
Deterministic; never blocks or raises.
"""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict

from .media_cache import MediaCache, get_default_media_cache
from ..extraction.title_extraction import get_search_phrases, extract_movie_titles

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


def _get_tmdb_token_best_effort() -> str:
    """
    Best-effort TMDB token retrieval that respects test monkeypatching.

    Tests sometimes patch `cinemind.media.media_enrichment.is_tmdb_enabled` /
    `cinemind.media.media_enrichment.get_tmdb_access_token` directly.
    Production code uses `config.is_tmdb_enabled` / `config.get_tmdb_access_token`.
    """
    try:
        local_is_enabled = globals().get("is_tmdb_enabled")
        local_get_token = globals().get("get_tmdb_access_token")
        if callable(local_is_enabled):
            # If tests override `is_tmdb_enabled`, respect it even if
            # `get_tmdb_access_token` wasn't overridden.
            if not bool(local_is_enabled()):
                return ""
            if callable(local_get_token):
                return (local_get_token() or "").strip()
            return ""
    except Exception:
        pass

    try:
        from config import is_tmdb_enabled, get_tmdb_access_token
        if is_tmdb_enabled():
            return (get_tmdb_access_token() or "").strip()
    except Exception:
        pass
    return ""


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
        from integrations.tmdb.image_config import get_config, build_image_url, SIZE_POSTER_GALLERY
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
    if getattr(c, "id", None) is not None:
        out["tmdb_id"] = int(c.id)
    if c.year is not None:
        out["year"] = c.year
    poster_path = getattr(c, "poster_path", None) or (c.get("poster_path") if isinstance(c, dict) else None)
    if (poster_path or "").strip() and token:
        try:
            from integrations.tmdb.image_config import get_config, build_image_url, SIZE_POSTER_GALLERY
            cfg = get_config(token)
            url = build_image_url((poster_path or "").strip(), SIZE_POSTER_GALLERY, cfg)
            if url:
                out["primary_image_url"] = url
        except Exception:
            pass
    return out


def _same_movie_as_strip(card: dict[str, Any], strip: dict[str, Any]) -> bool:
    """True if card is the same movie as strip (by tmdb_id, or by normalized title+year)."""
    sid = strip.get("tmdb_id")
    cid = card.get("tmdb_id")
    if sid is not None and cid is not None:
        return int(sid) == int(cid)
    st = (strip.get("movie_title") or "").strip().lower()
    sy = strip.get("year")
    ct = (card.get("movie_title") or "").strip().lower()
    cy = card.get("year")
    return bool(st and ct and st == ct and sy == cy)


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
        from integrations.tmdb.resolver import resolve_movie

        # Extract an optional "(YYYY)" tail so resolver can apply deterministic year scoring.
        # Many LLM outputs are formatted as "Title (Year)".
        year = None
        cleaned_title = title
        try:
            m = re.search(r"\(\s*(\d{4})\s*\)\s*$", title)
            if m:
                year = int(m.group(1))
                cleaned_title = re.sub(r"\(\s*\d{4}\s*\)\s*$", "", title).strip()
        except Exception:
            year = None
            cleaned_title = title

        tr = resolve_movie(cleaned_title, year=year, access_token=token)
        if tr.status == "not_found":
            # Always return a placeholder so enrich_batch stays usable even
            # when TMDB resolution fails (unit tests + hub UI robustness).
            out: dict[str, Any] = {"movie_title": cleaned_title or title, "page_url": "#"}
            if year is not None:
                out["year"] = year
            return out
        strip, _ = _build_strip_from_tmdb(tr, cleaned_title, token, cache=cache)
        return strip
    except Exception as e:
        logger.debug("Batch enrich single title failed for %r: %s", title, e)
        # Last-resort placeholder.
        out: dict[str, Any] = {"movie_title": title, "page_url": "#"}
        return out


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

    explicit_fallback_provided = bool(fallback_title and (fallback_title or "").strip()) or bool(fallback_from_result)

    media_cache = cache or get_default_media_cache()
    query_key = _normalize_enrich_key(user_query)

    if use_enrich_cache and query_key and not fallback_from_result and not fallback_title:
        cached = media_cache.get_enrich(query_key)
        if cached is not None:
            return cached

    token = _get_tmdb_token_best_effort()

    if not token:
        # No TMDB token → still return a minimal placeholder for `movie_title`
        # so downstream code/tests can render “text-only” cards safely.
        if explicit_fallback_provided:
            title = _fallback_title_value()
        else:
            title = ""
        if (title or "").strip():
            return MediaEnrichmentResult(
                media_strip={"movie_title": title, "page_url": "#"},
                poster_debug={POSTER_DEBUG_TMDB_ATTEMPTED: False, POSTER_DEBUG_PROVIDER: None},
            )
        return MediaEnrichmentResult(
            media_strip={},
            poster_debug={POSTER_DEBUG_TMDB_ATTEMPTED: False, POSTER_DEBUG_PROVIDER: None},
        )

    try:
        from integrations.tmdb.resolver import resolve_movie

        phrases = [p for p in get_search_phrases(user_query) if (p or "").strip()]
        if phrases:

            def _resolve_phrase(search_text: str):
                return resolve_movie(search_text, year=None, access_token=token)

            max_workers = min(2, len(phrases))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                resolved_list = list(pool.map(_resolve_phrase, phrases))

            for search_text, tr in zip(phrases, resolved_list):
                if tr.status == "not_found":
                    continue
                media_strip, poster_debug = _build_strip_from_tmdb(tr, search_text, token, cache=media_cache)
                if not media_strip.get("movie_title"):
                    continue
                payloads = [_build_candidate_from_tmdb(c, token) for c in (tr.candidates or [])[:MAX_GALLERY_CANDIDATES]]
                if not payloads:
                    payloads = [dict(media_strip)]
                # Invariant: hero must not appear in did_you_mean; exclude strip from candidates.
                candidates_no_hero = [p for p in payloads if not _same_movie_as_strip(p, media_strip)]
                show_gallery = _should_show_gallery_tmdb(tr) and len(candidates_no_hero) > 0
                result = MediaEnrichmentResult(
                    media_strip=media_strip,
                    media_candidates=candidates_no_hero if show_gallery else [],
                    poster_debug=poster_debug,
                )
                if use_enrich_cache and query_key:
                    media_cache.set_enrich(query_key, result)
                return result
    except Exception as e:
        logger.debug("Media enrichment failed: %s", e)

    title = _fallback_title_value()
    if title:
        try:
            from integrations.tmdb.resolver import resolve_movie
            tr = resolve_movie(title, year=None, access_token=token)
            if tr.status != "not_found":
                fallback_strip, poster_debug = _build_strip_from_tmdb(tr, title, token, cache=media_cache)
                return MediaEnrichmentResult(media_strip=fallback_strip, poster_debug=poster_debug)
        except Exception:
            logger.debug("Fallback media enrichment failed for %r", title)
        # If even fallback resolution fails, return a minimal placeholder.
        # Here TMDB is enabled (token exists), so we always return `movie_title`
        # to keep enrichment usable even without successful TMDB resolution.
        if (title or "").strip():
            return MediaEnrichmentResult(
                media_strip={"movie_title": title, "page_url": "#"},
                poster_debug={POSTER_DEBUG_TMDB_ATTEMPTED: True, POSTER_DEBUG_PROVIDER: None},
            )
        return MediaEnrichmentResult(
            media_strip={},
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
    t_batch = time.perf_counter()
    media_cache = cache or get_default_media_cache()
    token = _get_tmdb_token_best_effort()
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

    out_cards = [c for c in cards if c is not None and c.get("movie_title")]
    logger.debug(
        "TMDB enrich_batch input_titles=%s unique=%s max_concurrent=%s total_ms=%.1f",
        min(len(titles or []), max_titles),
        len(unique),
        max_concurrent,
        (time.perf_counter() - t_batch) * 1000,
    )
    return out_cards


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
    """Build attachments.sections from media_strip and media_candidates. Excludes hero from candidates."""
    sections: list[dict[str, Any]] = []
    strip = result.get("media_strip") or {}
    raw_candidates = result.get("media_candidates") or []
    gallery_label = (result.get("media_gallery_label") or "").strip()

    if strip and (strip.get("movie_title") or "").strip():
        sections.append({
            "type": SECTION_PRIMARY_MOVIE,
            "title": "This movie",
            "items": [_movie_card_item(strip)],
        })

    # Invariant: hero must not appear in did_you_mean; filter again at build time.
    candidates = [c for c in raw_candidates if not _same_movie_as_strip(c, strip)]
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

    # Surface relatedMovies alongside attachments for Movie Hub and Movie Details.
    # When we have movie_list-style candidates, reuse them as relatedMovies.
    # Preserve any existing relatedMovies set earlier in the pipeline.
    existing_related = result.get("relatedMovies")
    if existing_related is None:
        related: list[dict[str, Any]] = []
        # Hero is always "this movie"; relatedMovies should be "other movies".
        if len(sections) >= 2 and sections[1]["type"] in (SECTION_MOVIE_LIST, SECTION_DID_YOU_MEAN):
            for item in sections[1].get("items", []):
                if not item:
                    continue
                related.append(dict(item))
        if related:
            result["relatedMovies"] = related

    return {"sections": sections}


def _attach_single(
    title: str,
    result: dict[str, Any],
    cache: Optional[MediaCache],
) -> None:
    """Enrich a single title and attach to result."""
    enrichment = enrich(
        title,
        fallback_title=title,
        fallback_from_result=result,
        cache=cache,
    )
    if enrichment.media_strip.get("movie_title"):
        result["media_strip"] = enrichment.media_strip
        if enrichment.media_candidates:
            result["media_candidates"] = enrichment.media_candidates
    result["attachments"] = build_attachments_from_media(result)


def _attach_batch(
    batch_titles: list[str],
    result: dict[str, Any],
    gallery_label: Optional[str],
    cache: Optional[MediaCache],
) -> None:
    """Enrich multiple titles via batch and attach to result."""
    cards = enrich_batch(batch_titles, cache=cache)
    if cards:
        result["media_strip"] = cards[0]
        if len(cards) > 1:
            result["media_candidates"] = cards[1:]
        result["media_gallery_label"] = gallery_label or "Similar movies"
    result["attachments"] = build_attachments_from_media(result)


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

    Title sources (in priority order):
      1. Explicit titles= parameter
      2. result["recommended_movies"] (from LLM metadata)
      3. Parsed from result["response"] via response_movie_extractor
      4. Fallback: user_query
    """
    batch_titles = titles if titles is not None else result.get("recommended_movies")
    if batch_titles:
        batch_titles = [t for t in batch_titles if (t or "").strip()]

    # Priority 1-2: explicit titles or recommended_movies
    if batch_titles and len(batch_titles) > 1:
        _attach_batch(batch_titles, result, gallery_label, cache)
        return
    if batch_titles and len(batch_titles) == 1:
        _attach_single(batch_titles[0], result, cache)
        return

    # Priority 3: parse movie titles from agent response text
    response_text = (result.get("response") or result.get("answer") or "").strip()
    if response_text:
        from ..extraction.response_movie_extractor import extract_titles_for_enrichment
        extracted = extract_titles_for_enrichment(response_text)
        if len(extracted) > 1:
            _attach_batch(extracted, result, gallery_label, cache)
            return
        if len(extracted) == 1:
            _attach_single(extracted[0], result, cache)
            return

    # Priority 4: user query as final fallback
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


def build_similar_movie_clusters(
    title: str,
    year: Optional[int] = None,
    tmdb_id: Optional[int] = None,
    media_type: Optional[str] = None,
    max_results: int = 18,
) -> Dict[str, Any]:
    """
    Build genre/tone/cast clusters for a movie using TMDB "similar" titles.

    Contract:
      - Returns {"clusters": [SimilarCluster, ...]} where each cluster has:
          kind: "genre" | "tone" | "cast"
          label: human‑readable string
          movies: list of movie card dicts compatible with SimilarMovie / Movie Hub.

    Data sourcing strategy:
      1. If TMDB is disabled or we cannot resolve a TMDB id → return empty clusters
         with labels only (frontend will hide strips with no movies).
      2. If tmdb_id is provided (preferred) → call TMDB /movie/{id}/similar.
      3. Else, resolve by title/year via integrations.tmdb.resolver.resolve_movie.

    The "genre" cluster is the primary IMDb‑style "People who liked this also liked..."
    row. "tone" and "cast" are currently placeholders (empty) that can be filled by a
    richer similarity model later (e.g. LLM‑derived tone tags or shared cast credits).
    """
    from config import is_tmdb_enabled, get_tmdb_access_token  # local import to avoid cycles

    # Always build the three clusters so the frontend contract is stable.
    base_label = (title or "").strip() or "This movie"
    clusters: List[Dict[str, Any]] = [
        {
            "kind": "genre",
            "label": f"Similar by genre to {base_label}",
            "movies": [],
        },
        {
            "kind": "tone",
            "label": f"Similar by tone or theme to {base_label}",
            "movies": [],
        },
        {
            "kind": "cast",
            "label": f"Similar by cast or crew to {base_label}",
            "movies": [],
        },
    ]

    # Fast path: TMDB integration disabled or missing token → just return labels.
    token = ""
    try:
        if is_tmdb_enabled():
            token = (get_tmdb_access_token() or "").strip()
    except Exception:
        token = ""
    if not token:
        return {"clusters": clusters}

    # Helper imports kept inside the function to avoid hard dependencies at module import.
    try:
        from integrations.tmdb.http_client import tmdb_request_json  # type: ignore
        from integrations.tmdb.resolver import (  # type: ignore
            BASE_URL,
            _extract_year,
            resolve_movie,
        )
        from integrations.tmdb.image_config import (  # type: ignore
            SIZE_POSTER_GALLERY,
            build_image_url,
        )
    except Exception:
        # If TMDB modules are not available for any reason, keep graceful fallback.
        return {"clusters": clusters}

    # Resolve TMDB id if not provided.
    resolved_id: Optional[int] = tmdb_id
    if resolved_id is None:
        try:
            search_title = (title or "").strip()
            if not search_title:
                return {"clusters": clusters}
            tr = resolve_movie(search_title, year=year, access_token=token)
            if tr.status == "resolved" and tr.movie_id:
                resolved_id = tr.movie_id
        except Exception:
            resolved_id = None
    if resolved_id is None:
        return {"clusters": clusters}

    import urllib.parse

    url = f"{BASE_URL}/movie/{resolved_id}/similar"
    qs: Dict[str, str] = {"page": "1"}
    full_url = f"{url}?{urllib.parse.urlencode(qs)}"
    data = tmdb_request_json(full_url, token, timeout=10.0, log_label="TMDB_similar")
    if not isinstance(data, dict):
        return {"clusters": clusters}

    results = (data or {}).get("results") or []
    if not results:
        return {"clusters": clusters}

    movies: List[Dict[str, Any]] = []
    slice_limit = max(0, int(max_results) if max_results is not None else 0)
    for r in results[:slice_limit]:
        try:
            tmdb_movie_id = int(r.get("id") or 0)
        except Exception:
            tmdb_movie_id = 0
        if tmdb_movie_id <= 0:
            continue

        raw_title = (r.get("title") or r.get("original_title") or "").strip()
        if not raw_title:
            continue

        poster_path = (r.get("poster_path") or "").strip()
        primary_image_url: Optional[str] = None
        if poster_path:
            try:
                primary_image_url = build_image_url(poster_path, SIZE_POSTER_GALLERY)
            except Exception:
                primary_image_url = None

        release_year = _extract_year(r.get("release_date"))

        media_kind = (media_type or "movie").strip() or "movie"
        page_url = f"https://www.themoviedb.org/{'movie' if media_kind == 'movie' else 'tv'}/{tmdb_movie_id}"

        movie_item: Dict[str, Any] = {
            "title": raw_title,
            "year": release_year,
            "primary_image_url": primary_image_url,
            "page_url": page_url,
            "tmdbId": tmdb_movie_id,
            "mediaType": media_kind,
        }
        movies.append(movie_item)

    # Attach all movies to the primary "genre" cluster; tone/cast remain placeholders for now.
    if movies:
        clusters[0]["movies"] = movies

    return {"clusters": clusters}
