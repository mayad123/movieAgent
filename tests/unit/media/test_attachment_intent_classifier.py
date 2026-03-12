"""Unit tests for attachment_intent_classifier (deterministic precedence rules)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.response_movie_extractor import (
    parse_response,
    ResponseParseResult,
    ExtractedMovie,
    ParseStructure,
    ParseSignals,
)
from cinemind.attachment_intent_classifier import (
    classify_attachment_intent,
    AttachmentIntentResult,
    INTENT_PRIMARY_MOVIE,
    INTENT_MOVIE_LIST,
    INTENT_SCENES,
    INTENT_DID_YOU_MEAN,
    INTENT_NONE,
)


def _parsed(
    movies: list[tuple[str, int | None]],
    has_bullets: bool = False,
    has_numbered: bool = False,
    deep_dive: bool = False,
    scene_indicators: bool = False,
    scene_like_enumeration: bool = False,
    the_film_movie_references: int = 0,
    movie_confidence: float | None = None,
) -> ResponseParseResult:
    """Build a ResponseParseResult for tests."""
    conf = movie_confidence if movie_confidence is not None else 0.9
    return ResponseParseResult(
        movies=[ExtractedMovie(title=t, year=y, confidence=conf) for t, y in movies],
        structure=ParseStructure(
            has_bullets=has_bullets,
            has_numbered_list=has_numbered,
            has_bold_titles=False,
            has_title_year_pattern=bool(movies),
            has_dash_blurb_pattern=False,
        ),
        signals=ParseSignals(
            deep_dive_indicators=["overview"] if deep_dive else [],
            scene_indicators=["scene"] if scene_indicators else [],
            scene_like_enumeration=scene_like_enumeration,
            the_film_movie_references=the_film_movie_references,
        ),
    )


class TestPrecedenceAmbiguity:
    """Precedence 1: resolver_ambiguous → did_you_mean."""

    def test_ambiguous_did_you_mean(self):
        parsed = _parsed([("Inception", 2010), ("Dune", 2021)], has_bullets=True)
        r = classify_attachment_intent(parsed, resolver_ambiguous=True)
        assert r.intent == INTENT_DID_YOU_MEAN
        assert "ambiguous" in r.rationale.lower() or "did_you_mean" in r.rationale
        assert len(r.titles) >= 1

    def test_ambiguous_uses_response_movies(self):
        parsed = _parsed([("A", None), ("B", None)])
        r = classify_attachment_intent(parsed, resolver_ambiguous=True)
        assert r.intent == INTENT_DID_YOU_MEAN
        assert set(r.titles) >= {"A", "B"}

    def test_ambiguous_fallback_to_query_title(self):
        parsed = _parsed([])  # no movies
        r = classify_attachment_intent(parsed, user_query_title="The Matrix", resolver_ambiguous=True)
        assert r.intent == INTENT_DID_YOU_MEAN
        assert r.titles == ["The Matrix"]


class TestPrecedenceMovieList:
    """Precedence 2: Guardrail — 2+ distinct movies → always movie_list (never scenes)."""

    def test_two_movies_list_like(self):
        parsed = _parsed([("Inception", 2010), ("Dune", 2021)], has_bullets=True)
        r = classify_attachment_intent(parsed, resolver_ambiguous=False)
        assert r.intent == INTENT_MOVIE_LIST
        assert len(r.titles) == 2
        assert "movie_list" in r.rationale
        assert "guardrail" in r.rationale

    def test_two_movies_numbered_list(self):
        parsed = _parsed([("A", None), ("B", None)], has_numbered=True)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_MOVIE_LIST
        assert len(r.titles) == 2

    def test_two_movies_not_list_like_still_movie_list_guardrail(self):
        # Guardrail: 2+ distinct movies → always movie_list (even without list-like structure).
        parsed = ResponseParseResult(
            movies=[ExtractedMovie(title="Inception", year=2010), ExtractedMovie(title="Dune", year=2021)],
            structure=ParseStructure(has_bullets=False, has_numbered_list=False, has_bold_titles=False, has_title_year_pattern=False, has_dash_blurb_pattern=False),
            signals=ParseSignals(deep_dive_indicators=[], scene_indicators=[]),
        )
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_MOVIE_LIST
        assert len(r.titles) == 2
        assert "guardrail" in r.rationale

    def test_multi_movie_with_scene_words_in_blurb_guardrail(self):
        """Recommendation list with 'iconic scenes' in blurb must yield movie_list, not scenes."""
        parsed = _parsed(
            [("Inception", 2010), ("Dune", 2021)],
            has_bullets=True,
            scene_indicators=True,  # e.g. "iconic scenes" in one of the blurbs
        )
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_MOVIE_LIST
        assert len(r.titles) == 2
        assert "guardrail" in r.rationale


class TestPrecedenceScenes:
    """Precedence 3: 1 movie AND scene-like signals (no user 'scenes' required)."""

    def test_one_movie_with_deep_dive(self):
        parsed = _parsed([("Inception", 2010)], deep_dive=True)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_SCENES
        assert r.titles == ["Inception"]
        assert "scene" in r.rationale.lower() or "deep" in r.rationale.lower()

    def test_one_movie_with_scene_indicators(self):
        parsed = _parsed([("Dune", 2021)], scene_indicators=True)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_SCENES
        assert r.titles == ["Dune"]

    def test_one_movie_with_scene_like_enumeration(self):
        """Structural: multiple bullet items that look like scene descriptions → scenes."""
        parsed = _parsed([("Inception", 2010)], scene_like_enumeration=True)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_SCENES
        assert r.titles == ["Inception"]

    def test_one_movie_with_the_film_movie_references(self):
        """Single-movie deep-dive language: 'the film'/'the movie' >= 2 → scenes."""
        parsed = _parsed([("Dune", 2021)], the_film_movie_references=2)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_SCENES
        assert r.titles == ["Dune"]

    def test_one_movie_no_signals_stays_primary_movie(self):
        parsed = _parsed([("Inception", 2010)], scene_like_enumeration=False, the_film_movie_references=1)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_PRIMARY_MOVIE

    def test_one_movie_scene_signals_low_confidence_primary_movie(self):
        """Single movie with scene-like signals but low confidence → primary_movie (guardrail)."""
        parsed = _parsed(
            [("Inception", 2010)],
            scene_indicators=True,
            movie_confidence=0.5,
        )
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_PRIMARY_MOVIE
        assert r.titles == ["Inception"]


class TestPrecedencePrimaryMovie:
    """Precedence 4: 1 movie → primary_movie."""

    def test_one_movie_no_signals(self):
        parsed = _parsed([("Inception", 2010)])
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_PRIMARY_MOVIE
        assert r.titles == ["Inception"]

    def test_one_movie_query_fallback(self):
        parsed = _parsed([])
        r = classify_attachment_intent(parsed, user_query_title="The Matrix")
        assert r.intent == INTENT_PRIMARY_MOVIE
        assert r.titles == ["The Matrix"]


class TestPrecedenceNone:
    """Precedence 5: no movies and no query title → none."""

    def test_no_movies_no_query(self):
        parsed = _parsed([])
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_NONE
        assert r.titles == []
        assert "none" in r.rationale.lower()


class TestDeterminism:
    """Same inputs → same output."""

    def test_deterministic_same_inputs(self):
        parsed = _parsed([("Inception", 2010)], has_bullets=True)
        r1 = classify_attachment_intent(parsed, user_query_title="Inception")
        r2 = classify_attachment_intent(parsed, user_query_title="Inception")
        assert r1.intent == r2.intent
        assert r1.titles == r2.titles
        assert r1.rationale == r2.rationale

    def test_to_dict_shape(self):
        parsed = _parsed([("Dune", 2021)])
        r = classify_attachment_intent(parsed)
        d = r.to_dict()
        assert d["intent"] == INTENT_PRIMARY_MOVIE
        assert d["titles"] == ["Dune"]
        assert "rationale" in d


class TestIntegrationWithParseResponse:
    """Classifier with real parse_response output."""

    def test_from_parsed_bullet_list(self):
        text = "Recommendations:\n- Inception (2010)\n- Dune (2021)\n- The Matrix (1999)"
        parsed = parse_response(text)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_MOVIE_LIST
        assert len(r.titles) >= 2

    def test_from_parsed_single_movie(self):
        text = "**Inception** (2010) is a sci-fi film."
        parsed = parse_response(text)
        r = classify_attachment_intent(parsed)
        assert r.intent == INTENT_PRIMARY_MOVIE
        assert len(r.titles) >= 1
