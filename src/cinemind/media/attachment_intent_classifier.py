"""
Deterministic Attachment Intent Classifier (no AI).

Selects attachment intent from the parsed response first; user question and
resolver ambiguity are secondary. Outputs intent, titles[] for enrichment, and
a rationale string for logging.

Precedence (first match wins):
  1. Ambiguity (resolver or explicit) → did_you_mean
  2. 2+ distinct movies → movie_list (guardrail: never choose scenes for multi-movie)
  3. 1 distinct movie AND deep-dive/scene signals AND sufficient confidence → scenes
  4. 1 distinct movie → primary_movie
  5. Else → none

Guardrail (multi-movie):
  - If 2+ distinct movie titles are detected → always choose movie_list, never scenes.
  - This prevents false positives when a recommendation list mentions "iconic scenes"
    or similar in a blurb; scene detection is applied only when exactly one distinct
    title is present with sufficient confidence.
  - did_you_mean is unchanged (ambiguity takes precedence over movie count).

List-like: has_bullets | has_numbered_list | has_bold_titles | has_title_year_pattern.
Deep-dive signals: presence of deep_dive_indicators or scene_indicators in parsed response.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..extraction.response_movie_extractor import ResponseParseResult

logger = logging.getLogger(__name__)

__all__ = [
    "classify_attachment_intent",
    "AttachmentIntentResult",
    "INTENT_PRIMARY_MOVIE",
    "INTENT_MOVIE_LIST",
    "INTENT_SCENES",
    "INTENT_DID_YOU_MEAN",
    "INTENT_NONE",
]

# Intent values (align with attachment section types where applicable)
INTENT_PRIMARY_MOVIE = "primary_movie"
INTENT_MOVIE_LIST = "movie_list"
INTENT_SCENES = "scenes"
INTENT_DID_YOU_MEAN = "did_you_mean"
INTENT_NONE = "none"


@dataclass
class AttachmentIntentResult:
    """
    Output of the attachment intent classifier.
    - intent: primary_movie | movie_list | scenes | did_you_mean | none
    - titles: ordered list of title strings to use for enrichment (one or many)
    - rationale: debug string for logs only; not user-facing
    """

    intent: str
    titles: list[str]
    rationale: str

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "titles": list(self.titles),
            "rationale": self.rationale,
        }


def _is_list_like(parsed: ResponseParseResult) -> bool:
    """True if response structure suggests a list (bullets, numbered, bold, title-year)."""
    s = parsed.structure
    return bool(
        s.has_bullets
        or s.has_numbered_list
        or s.has_bold_titles
        or s.has_title_year_pattern
    )


# Threshold for "the film" / "the movie" references to trigger scenes (single-movie deep-dive).
_SCENES_FILM_MOVIE_REF_THRESHOLD = 2
# Minimum confidence for the single extracted movie to allow scenes intent (avoid weak extractions).
_SCENES_MIN_SINGLE_MOVIE_CONFIDENCE = 0.6


def _should_trigger_scenes(parsed: ResponseParseResult) -> bool:
    """
    True when response is effectively about scenes/key moments (user need not say "scenes").
    Threshold policy (deterministic):
    - Any scene phrase (key moments, climax, set pieces, etc.), or
    - Any deep-dive phrase (overview, summary, key points, etc.), or
    - Structural: multiple bullet/numbered items that look like scene descriptions, or
    - Single-movie language: "the film" / "the movie" mentioned at least _SCENES_FILM_MOVIE_REF_THRESHOLD times.
    """
    s = parsed.signals
    if s.scene_indicators or s.deep_dive_indicators:
        return True
    if s.scene_like_enumeration:
        return True
    if s.the_film_movie_references >= _SCENES_FILM_MOVIE_REF_THRESHOLD:
        return True
    return False


def classify_attachment_intent(
    parsed_response: ResponseParseResult,
    *,
    user_query_title: Optional[str] = None,
    resolver_ambiguous: Optional[bool] = None,
) -> AttachmentIntentResult:
    """
    Deterministic attachment intent from parsed response; user query and
    resolver ambiguity are secondary.

    Args:
        parsed_response: Output from response_movie_extractor.parse_response(response_text).
        user_query_title: Optional title candidate from the user query (e.g. from title_extraction).
        resolver_ambiguous: Optional; True if resolver reported ambiguity (e.g. multiple candidates).

    Returns:
        AttachmentIntentResult with intent, titles (for enrichment), and rationale (logs only).
    """
    movies = list(parsed_response.movies)
    n = len(movies)
    list_like = _is_list_like(parsed_response)
    trigger_scenes = _should_trigger_scenes(parsed_response)

    # Normalize optional user title for fallback
    query_title = (user_query_title or "").strip()
    if query_title and len(query_title) < 2:
        query_title = ""

    # --- Precedence 1: Ambiguity → did_you_mean ---
    if resolver_ambiguous is True:
        titles = [m.title for m in movies] if movies else ([query_title] if query_title else [])
        rationale = "resolver_ambiguous=True → did_you_mean"
        logger.debug("Attachment intent: did_you_mean (resolver ambiguous), titles=%s", titles)
        return AttachmentIntentResult(
            intent=INTENT_DID_YOU_MEAN,
            titles=titles,
            rationale=rationale,
        )

    # --- Precedence 2: Guardrail — 2+ distinct movies → always movie_list (never scenes) ---
    if n >= 2:
        titles = [m.title for m in movies]
        rationale = f"guardrail: {n} distinct movies → movie_list (never scenes)"
        logger.info(
            "Attachment intent guardrail: multi-movie → movie_list (n=%d, list_like=%s, titles=%s)",
            n,
            list_like,
            titles,
        )
        return AttachmentIntentResult(
            intent=INTENT_MOVIE_LIST,
            titles=titles,
            rationale=rationale,
        )

    # --- Precedence 3: 1 movie AND scene-like signals AND sufficient confidence → scenes ---
    if n == 1 and trigger_scenes:
        single = movies[0]
        if single.confidence >= _SCENES_MIN_SINGLE_MOVIE_CONFIDENCE:
            titles = [single.title]
            rationale = "1 movie and scene/deep-dive signals or structure → scenes"
            logger.debug("Attachment intent: scenes, titles=%s", titles)
            return AttachmentIntentResult(
                intent=INTENT_SCENES,
                titles=titles,
                rationale=rationale,
            )
        # Single movie but low confidence: do not choose scenes (avoid false positives).
        logger.info(
            "Attachment intent guardrail: skipping scenes (single movie confidence %.2f < %.2f), title=%s",
            single.confidence,
            _SCENES_MIN_SINGLE_MOVIE_CONFIDENCE,
            single.title,
        )

    # --- Precedence 4: 1 movie → primary_movie ---
    if n == 1:
        titles = [movies[0].title]
        rationale = "1 movie in response → primary_movie"
        logger.debug("Attachment intent: primary_movie, titles=%s", titles)
        return AttachmentIntentResult(
            intent=INTENT_PRIMARY_MOVIE,
            titles=titles,
            rationale=rationale,
        )

    # --- Precedence 5: No movies (or zero) → none; optional fallback to user query ---
    if query_title:
        # Single title from user query only: treat as primary_movie for enrichment
        rationale = "no movies in response; using user_query_title → primary_movie"
        logger.debug("Attachment intent: primary_movie (from query), titles=%s", [query_title])
        return AttachmentIntentResult(
            intent=INTENT_PRIMARY_MOVIE,
            titles=[query_title],
            rationale=rationale,
        )

    rationale = "no movies in response and no query title → none"
    logger.debug("Attachment intent: none")
    return AttachmentIntentResult(
        intent=INTENT_NONE,
        titles=[],
        rationale=rationale,
    )
