"""
Playground-only attachment behavior: single movie → poster + scenes; multi → posters only.

This module is applied only in playground mode (offline runner / playground server).
It runs the movie extraction/classification pipeline on the response (and query fallback),
then sets attachments.sections and debug metadata accordingly.

Playground convention: the USER QUERY is treated as the "response" text for parsing.
So when testing, type the mimicked agent response in the query box to drive attachments.

Switch: Call apply_playground_attachment_behavior() only from the playground request path
(e.g. run_playground_query in playground.py). The single switch to enable/disable this
behavior is PLAYGROUND_ATTACHMENT_RULE_ENABLED in cinemind.playground (and the offline
runner uses the same flag). Do not call from the real agent path so agent mode can tune
behavior separately.

Rules:
  - single movie (1 distinct title) → sections = [primary_movie, scenes]
  - multi movie (2+ distinct titles) → sections = [movie_list] only
  - Scenes retrieval must not block; on failure we still return the poster.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .response_movie_extractor import parse_response
from .attachment_intent_classifier import (
    classify_attachment_intent,
    INTENT_MOVIE_LIST,
    INTENT_DID_YOU_MEAN,
)
from .media_enrichment import (
    enrich,
    enrich_batch,
    SECTION_PRIMARY_MOVIE,
    SECTION_MOVIE_LIST,
    SECTION_SCENES,
    SECTION_DID_YOU_MEAN,
    _movie_card_item,
)
from .title_extraction import get_search_phrases, extract_movie_titles
from .wikipedia_entity_resolver import WikipediaEntityResolver
from .wikipedia_cache import get_default_wikipedia_cache
from .scenes_provider import get_scenes_provider

logger = logging.getLogger(__name__)

# Debug key on result: server logs / response metadata
ATTACHMENT_DEBUG_KEY = "attachment_debug"


def _fetch_scenes_nonblocking(title: str, year: Optional[int] = None) -> list[dict[str, Any]]:
    """
    Fetch scene/backdrop items for a movie via the pluggable scenes provider.

    Uses TMDB when enabled and configured; otherwise fallback (empty or Wikipedia-only).
    Must not raise; returns [] on any failure so poster is still returned.
    """
    try:
        provider = get_scenes_provider()
        items = provider.fetch_scenes(title, year=year)
        return [s.to_attachment_item() for s in items]
    except Exception as e:
        logger.debug("Scenes fetch skipped or failed for %r: %s", title, e)
        return []


def _scenes_section(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a scenes section for attachments schema."""
    return {
        "type": SECTION_SCENES,
        "title": "Scenes",
        "items": items,
    }


def apply_playground_attachment_behavior(user_query: str, result: dict[str, Any]) -> None:
    """
    Playground-only: set attachments by single/multi rule and add debug metadata.

    Playground convention: the USER QUERY is taken as the "response" for parsing.
    So type the mimicked agent response in the query box (e.g. "**Inception** (2010) and
    **The Matrix** (1999)") to drive which movies are detected and shown.

    - Parses user_query as the response text (not result["response"]).
    - Classifies intent; then:
      - 1 title → sections = [primary_movie, scenes] (scenes non-blocking; may be empty).
      - 2+ titles → sections = [movie_list] only.
    - Sets result["attachments"] and result[ATTACHMENT_DEBUG_KEY].
    - Never raises; on any failure leaves or restores sensible attachments.
    """
    try:
        # Use the same query string as in the response (result["query"]) so we match what the client sent.
        user_query_stripped = (user_query or result.get("query") or "").strip()
        # Normalize any whitespace to single space so " and " always matches.
        user_query_normalized = re.sub(r"\s+", " ", user_query_stripped)

        # Robust 2+ title detection: literal " and " / " & " in query (e.g. "Avatar and Inception").
        and_split = re.split(r"\s+and\s+|\s+&\s+", user_query_normalized, flags=re.IGNORECASE)
        and_parts = [p.strip() for p in and_split if (p or "").strip() and len((p or "").strip()) >= 2]
        if len(and_parts) >= 2:
            titles = and_parts
            intent = INTENT_MOVIE_LIST
            detected_movie_count = len(titles)
            intent_result = type("_Intent", (), {"rationale": "user query has 'X and Y' / 'X & Y' → movie_list"})()
            # Go straight to multi/single branch below.
        else:
            # Prioritize: if the user query explicitly lists 2+ titles (e.g. "Avatar and Inception"),
            # use them first so both movies always get posters regardless of response parsing.
            query_extraction = extract_movie_titles(user_query_normalized) if user_query_normalized else None
            if query_extraction and len(query_extraction.titles) >= 2:
                titles = list(query_extraction.titles)
                intent = INTENT_MOVIE_LIST
                detected_movie_count = len(titles)
                intent_result = type("_Intent", (), {"rationale": "user query has 2+ titles (e.g. X and Y) → movie_list"})()
                # Skip response parsing; go straight to multi/single branch below.
            else:
                # Playground: treat user query as the "response" so the user can mimic the agent response when testing.
                response_text = user_query_stripped
                parsed = parse_response(response_text)

                # When nothing was typed (or parsed yielded no movies), fallback to result's response for query_title only.
                query_title = ""
                if not parsed.movies and user_query_stripped:
                    phrases = get_search_phrases(user_query)
                    if len(phrases) == 1:
                        query_title = (phrases[0] or "").strip()
                if not parsed.movies and not query_title:
                    agent_response = (result.get("response") or result.get("answer") or "").strip()
                    if agent_response:
                        phrases = get_search_phrases(agent_response)
                        if len(phrases) == 1:
                            query_title = (phrases[0] or "").strip()

                intent_result = classify_attachment_intent(
                    parsed,
                    user_query_title=query_title if query_title else None,
                )
                titles = list(intent_result.titles) if intent_result.titles else []
                if not titles and query_title:
                    titles = [query_title]
                intent = intent_result.intent
                detected_movie_count = len(titles)

        # did_you_mean: keep default behavior (don't override with single/multi rule here).
        if intent == INTENT_DID_YOU_MEAN:
            debug = {
                "detected_movie_count": detected_movie_count,
                "attachment_intent": intent,
                "rationale": intent_result.rationale,
            }
            result[ATTACHMENT_DEBUG_KEY] = debug
            logger.info(
                "Playground attachment: did_you_mean (count=%s, intent=%s)",
                detected_movie_count,
                intent,
            )
            return

        if detected_movie_count >= 2:
            # Multi: posters only → sections = [movie_list]
            cards = enrich_batch(titles)
            if not cards:
                result["attachments"] = {"sections": []}
            else:
                result["media_strip"] = cards[0]
                result["media_candidates"] = cards[1:]
                result["media_gallery_label"] = "Similar movies"
                sections = [{
                    "type": SECTION_MOVIE_LIST,
                    "title": result.get("media_gallery_label") or "Similar movies",
                    "items": [_movie_card_item(c) for c in cards if (c.get("movie_title") or c.get("displayTitle") or "").strip()],
                }]
                result["attachments"] = {"sections": sections}
            debug = {
                "detected_movie_count": detected_movie_count,
                "attachment_intent": intent,
                "rationale": intent_result.rationale,
            }
            result[ATTACHMENT_DEBUG_KEY] = debug
            logger.info(
                "Playground attachment: multi → movie_list only (count=%s, titles=%s)",
                detected_movie_count,
                titles,
            )
            return

        # Single: poster + scenes
        single_title = titles[0] if titles else query_title
        if not single_title:
            debug = {
                "detected_movie_count": 0,
                "attachment_intent": intent,
                "rationale": intent_result.rationale,
            }
            result[ATTACHMENT_DEBUG_KEY] = debug
            logger.info("Playground attachment: no titles, skipping override")
            return

        enrichment = enrich(
            user_query,
            fallback_title=single_title,
            fallback_from_result=result,
        )
        sections: list[dict[str, Any]] = []
        strip = enrichment.media_strip if enrichment.media_strip.get("movie_title") else {"movie_title": single_title, "page_url": "#"}
        result["media_strip"] = strip
        result["media_candidates"] = list(enrichment.media_candidates) if enrichment.media_candidates else []
        if result["media_candidates"]:
            result["media_gallery_label"] = "Did you mean?"
        sections.append({
            "type": SECTION_PRIMARY_MOVIE,
            "title": "This movie",
            "items": [_movie_card_item(strip)],
        })
        if result["media_candidates"]:
            sections.append({
                "type": SECTION_DID_YOU_MEAN,
                "title": result.get("media_gallery_label") or "Did you mean?",
                "items": [_movie_card_item(c) for c in result["media_candidates"] if (c.get("movie_title") or c.get("displayTitle") or "").strip()],
            })

        single_year = strip.get("year") if isinstance(strip.get("year"), int) else None
        scenes_items = _fetch_scenes_nonblocking(single_title, year=single_year)
        if scenes_items:
            sections.append(_scenes_section(scenes_items))
        # If scenes fetch failed or returned empty, we still have poster (primary_movie).

        result["attachments"] = {"sections": sections}
        from config import ENABLE_TMDB_SCENES
        debug = {
            "detected_movie_count": 1,
            "attachment_intent": intent,
            "rationale": intent_result.rationale,
            "scenes_count": len(scenes_items),
            "tmdb_scenes_enabled": ENABLE_TMDB_SCENES,
        }
        pd = getattr(enrichment, "poster_debug", None) or {}
        debug.update(pd)
        debug.setdefault("poster_provider", None)
        debug.setdefault("tmdb_fallback_ran", False)
        tmdb_attempted = debug.get("tmdb_attempted", False)
        logger.info("request poster_debug tmdb_attempted=%s", tmdb_attempted)
        try:
            resolver = WikipediaEntityResolver(cache=get_default_wikipedia_cache())
            resolve_result = resolver.resolve(single_title)
            debug["resolver_status"] = getattr(resolve_result, "status", None)
            debug["resolver_candidate_count"] = len(getattr(resolve_result, "candidates", []) or [])
        except Exception as e:
            logger.debug("Resolver debug skipped: %s", e)
        result[ATTACHMENT_DEBUG_KEY] = debug
        logger.info(
            "Playground attachment: single → primary_movie + scenes (title=%s, scenes_count=%s)",
            single_title,
            len(scenes_items),
        )
    except Exception as e:
        logger.warning("Playground attachment behavior failed: %s", e)
        if ATTACHMENT_DEBUG_KEY not in result:
            result[ATTACHMENT_DEBUG_KEY] = {
                "error": str(e),
                "attachment_intent": "error",
            }
