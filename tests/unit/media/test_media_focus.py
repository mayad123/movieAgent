"""Unit tests for intent-based media focus (single_movie vs multi_movie)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.media.media_focus import MEDIA_FOCUS_MULTI, MEDIA_FOCUS_SINGLE, get_media_focus


def test_compare_intent_multi():
    """Comparison queries → multi_movie (posters only)."""
    assert get_media_focus("Compare Inception and The Matrix") == MEDIA_FOCUS_MULTI
    assert get_media_focus("Inception vs The Matrix", request_type="comparison") == MEDIA_FOCUS_MULTI


def test_recs_intent_multi():
    """Recommendation/similar → multi_movie."""
    assert get_media_focus("Recommend me a movie like Inception", request_type="recs") == MEDIA_FOCUS_MULTI
    assert get_media_focus("movies similar to Inception") == MEDIA_FOCUS_MULTI


def test_summary_ending_intent_single():
    """Summary, ending, key scenes → single_movie (poster + scenes)."""
    assert get_media_focus("Explain the ending of Inception") == MEDIA_FOCUS_SINGLE
    assert get_media_focus("Summary of The Matrix") == MEDIA_FOCUS_SINGLE
    assert get_media_focus("Key scenes in Inception") == MEDIA_FOCUS_SINGLE


def test_default_single():
    """Single title with no multi patterns → single_movie."""
    assert get_media_focus("Inception") == MEDIA_FOCUS_SINGLE
    assert get_media_focus("Tell me about Dune", request_type="info") == MEDIA_FOCUS_SINGLE
