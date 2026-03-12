"""Unit tests for playground attachment invariants (hero not in did_you_mean, query-only seed)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.media.playground_attachments import apply_playground_attachment_behavior, ATTACHMENT_DEBUG_KEY


def test_playground_single_movie_hero_not_in_did_you_mean():
    """When enrich returns hero in media_candidates, sections must exclude hero from did_you_mean."""
    hero_card = {
        "movie_title": "Inception",
        "year": 2010,
        "tmdb_id": 27205,
        "page_url": "https://tmdb.org/movie/27205",
        "primary_image_url": "https://example.com/inception.jpg",
    }
    other_card = {
        "movie_title": "The Matrix",
        "year": 1999,
        "tmdb_id": 603,
        "page_url": "https://tmdb.org/movie/603",
    }
    enrichment_result = MagicMock()
    enrichment_result.media_strip = hero_card
    enrichment_result.media_candidates = [hero_card, other_card]
    enrichment_result.poster_debug = {}
    result = {"response": "Inception (2010).", "request_type": "info"}

    intent_result = MagicMock(intent="primary_movie", titles=["Inception"], rationale="1 movie")
    parsed = MagicMock(movies=[MagicMock(title="Inception", confidence=0.9)])

    with patch("cinemind.media.playground_attachments.enrich", return_value=enrichment_result):
        with patch("cinemind.media.playground_attachments._fetch_scenes_nonblocking", return_value=[]):
            with patch("cinemind.media.playground_attachments.get_media_focus", return_value="single_movie"):
                with patch("cinemind.media.playground_attachments.parse_response", return_value=parsed):
                    with patch("cinemind.media.playground_attachments.classify_attachment_intent", return_value=intent_result):
                        apply_playground_attachment_behavior("Inception (2010)", result)

    sections = result.get("attachments", {}).get("sections", [])
    primary_section = next((s for s in sections if s.get("type") == "primary_movie"), None)
    did_you_mean_section = next((s for s in sections if s.get("type") == "did_you_mean"), None)
    assert primary_section is not None and len(primary_section.get("items", [])) >= 1
    hero_item = primary_section["items"][0]
    hero_tmdb_id = hero_item.get("tmdbId")
    hero_title = (hero_item.get("title") or "").strip().lower()
    hero_year = hero_item.get("year")
    if did_you_mean_section and did_you_mean_section.get("items"):
        for item in did_you_mean_section["items"]:
            assert item.get("tmdbId") != hero_tmdb_id or hero_tmdb_id is None
            item_title = (item.get("title") or "").strip().lower()
            assert not (item_title == hero_title and item.get("year") == hero_year), "hero must not appear in did_you_mean"


def test_playground_no_attachments_when_no_titles():
    """When no titles are detected, attachment override does not set primary_movie with empty items."""
    result = {"response": "Some text with no movie titles."}
    parsed = MagicMock(movies=[], structure=MagicMock(), signals=MagicMock())
    intent_result = MagicMock(intent="none", titles=[], rationale="none")
    with patch("cinemind.media.playground_attachments.parse_response", return_value=parsed):
        with patch("cinemind.media.playground_attachments.get_search_phrases", return_value=[]):
            with patch("cinemind.media.playground_attachments.classify_attachment_intent", return_value=intent_result):
                apply_playground_attachment_behavior("Some text with no movie titles.", result)
    assert ATTACHMENT_DEBUG_KEY in result
    assert result[ATTACHMENT_DEBUG_KEY].get("detected_movie_count", 0) == 0
