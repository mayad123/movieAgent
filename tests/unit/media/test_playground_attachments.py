"""Unit tests for playground-only attachment behavior (single → poster+scenes, multi → posters only)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.media.media_enrichment import SECTION_MOVIE_LIST, SECTION_PRIMARY_MOVIE, SECTION_SCENES
from cinemind.media.playground_attachments import (
    ATTACHMENT_DEBUG_KEY,
    apply_playground_attachment_behavior,
)


def test_attachment_debug_key_set():
    """Playground takes user_query as the response: pass mimicked response as first arg."""
    result = {}
    with patch("cinemind.media.playground_attachments.enrich_batch") as mock_batch:
        mock_batch.return_value = [
            {"movie_title": "Inception", "year": 2010, "page_url": "https://en.wikipedia.org/wiki/Inception"},
            {"movie_title": "Dune", "year": 2021, "page_url": "https://en.wikipedia.org/wiki/Dune"},
        ]
        apply_playground_attachment_behavior("Here are two films: Inception (2010) and Dune (2021).", result)
    assert ATTACHMENT_DEBUG_KEY in result
    debug = result[ATTACHMENT_DEBUG_KEY]
    assert debug["detected_movie_count"] >= 2
    assert debug["attachment_intent"] == "movie_list"
    assert "rationale" in debug


def test_multi_movie_sections_movie_list_only():
    """Playground: user query as response → multi-movie text yields [movie_list] only."""
    result = {}
    with patch("cinemind.media.playground_attachments.enrich_batch") as mock_batch:
        mock_batch.return_value = [
            {"movie_title": "Inception", "year": 2010, "page_url": "#"},
            {"movie_title": "Dune", "year": 2021, "page_url": "#"},
        ]
        apply_playground_attachment_behavior("Try these: Inception (2010), Dune (2021), The Matrix (1999).", result)
    sections = result["attachments"]["sections"]
    assert len(sections) == 1
    assert sections[0]["type"] == SECTION_MOVIE_LIST
    assert len(sections[0]["items"]) >= 1


def test_avatar_and_inception_two_movies():
    """Query 'Avatar and Inception' must yield 2 titles and movie_list (both posters), not single + did_you_mean."""
    result = {"query": "Avatar and Inception", "response": "Inception information is available."}
    with patch("cinemind.media.playground_attachments.enrich_batch") as mock_batch:
        mock_batch.return_value = [
            {"movie_title": "Avatar (2009 film)", "year": 2009, "page_url": "#", "primary_image_url": "https://example.com/avatar.jpg"},
            {"movie_title": "Inception (2010 film)", "year": 2010, "page_url": "#", "primary_image_url": "https://example.com/inception.jpg"},
        ]
        apply_playground_attachment_behavior("Avatar and Inception", result)
    assert result[ATTACHMENT_DEBUG_KEY]["detected_movie_count"] == 2
    assert result[ATTACHMENT_DEBUG_KEY]["attachment_intent"] == "movie_list"
    sections = result["attachments"]["sections"]
    assert len(sections) == 1
    assert sections[0]["type"] == SECTION_MOVIE_LIST
    assert len(sections[0]["items"]) == 2
    mock_batch.assert_called_once()
    call_titles = mock_batch.call_args[0][0]
    assert call_titles == ["Avatar", "Inception"]


def test_single_movie_sections_primary_and_scenes_slot():
    """Playground: user query as response → single-movie text yields primary_movie (+ scenes if any)."""
    result = {}
    with patch("cinemind.media.playground_attachments.enrich") as mock_enrich:
        mock_enrich.return_value = type("R", (), {"media_strip": {"movie_title": "Inception", "year": 2010, "page_url": "#"}, "media_candidates": []})()
        apply_playground_attachment_behavior("Inception (2010) is a sci-fi film. Key moments include the dream layers.", result)
    sections = result["attachments"]["sections"]
    assert len(sections) >= 1
    assert sections[0]["type"] == SECTION_PRIMARY_MOVIE
    assert result[ATTACHMENT_DEBUG_KEY]["detected_movie_count"] == 1
    # Scenes stub returns [] so we don't add scenes section; poster still present
    assert any(s["type"] == SECTION_PRIMARY_MOVIE for s in sections)


def test_user_query_title_only_fallback():
    """When user only typed a title (e.g. 'Avatar'), query fallback drives single-movie path."""
    result = {"response": "Avatar is a 2009 film."}
    with patch("cinemind.media.playground_attachments.enrich") as mock_enrich:
        mock_enrich.return_value = type("R", (), {"media_strip": {"movie_title": "Avatar", "year": 2009, "page_url": "#"}, "media_candidates": []})()
        apply_playground_attachment_behavior("Avatar", result)
    assert result["attachments"]["sections"]
    assert result[ATTACHMENT_DEBUG_KEY]["detected_movie_count"] == 1


def test_single_title_multi_movie_intent_no_scenes():
    """Intent-based: 'movies similar to Inception' → 1 title but multi_movie focus → poster only, no scenes section."""
    result = {}
    with patch("cinemind.media.playground_attachments.enrich") as mock_enrich:
        mock_enrich.return_value = type("R", (), {"media_strip": {"movie_title": "Inception", "year": 2010, "page_url": "#"}, "media_candidates": []})()
        apply_playground_attachment_behavior("movies similar to Inception", result)
    sections = result["attachments"]["sections"]
    assert result[ATTACHMENT_DEBUG_KEY]["detected_movie_count"] == 1
    assert result[ATTACHMENT_DEBUG_KEY]["media_focus"] == "multi_movie"
    assert any(s["type"] == SECTION_PRIMARY_MOVIE for s in sections)
    assert not any(s["type"] == SECTION_SCENES for s in sections)
