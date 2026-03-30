"""Unit tests for hero vs did_you_mean dedup and attachment invariants."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.media.media_enrichment import (
    _same_movie_as_strip,
    build_attachments_from_media,
    enrich,
)
from integrations.tmdb.resolver import TMDBCandidate, TMDBResolveResult


def test_same_movie_as_strip_by_tmdb_id():
    """_same_movie_as_strip returns True when tmdb_id matches."""
    strip = {"movie_title": "Inception", "tmdb_id": 27205, "year": 2010}
    card = {"movie_title": "Inception (2010)", "tmdb_id": 27205, "year": 2010}
    assert _same_movie_as_strip(card, strip) is True
    card_other = {"movie_title": "Other", "tmdb_id": 999, "year": 2010}
    assert _same_movie_as_strip(card_other, strip) is False


def test_same_movie_as_strip_by_title_year():
    """_same_movie_as_strip falls back to title+year when tmdb_id missing."""
    strip = {"movie_title": "Inception", "year": 2010}
    card = {"movie_title": "Inception", "year": 2010}
    assert _same_movie_as_strip(card, strip) is True
    card_other = {"movie_title": "The Matrix", "year": 1999}
    assert _same_movie_as_strip(card_other, strip) is False


@patch("cinemind.media.media_enrichment.get_default_media_cache")
@patch("cinemind.media.media_enrichment.get_search_phrases", return_value=["Inception"])
@patch("config.is_tmdb_enabled", return_value=True)
@patch("config.get_tmdb_access_token", return_value="token")
@patch("integrations.tmdb.image_config.build_image_url", return_value="https://image.tmdb.org/poster.jpg")
@patch("integrations.tmdb.image_config.get_config", return_value=MagicMock())
@patch("integrations.tmdb.resolver.resolve_movie")
def test_hero_not_in_did_you_mean_when_ambiguous(
    mock_resolve, _mock_config, _mock_build_url, _mock_token, _mock_enabled, _mock_phrases, mock_cache
):
    """When TMDB returns ambiguous with 2+ candidates, media_candidates must not include the hero."""
    c1 = TMDBCandidate(id=27205, title="Inception", year=2010, poster_path="/abc.jpg")
    c2 = TMDBCandidate(id=603, title="The Matrix", year=1999, poster_path="/def.jpg")
    mock_resolve.return_value = TMDBResolveResult(
        status="ambiguous",
        movie_id=None,
        poster_path="/abc.jpg",
        confidence=0.7,
        candidates=[c1, c2],
    )
    mock_cache.return_value.get_tmdb_poster.return_value = (None, False)
    mock_cache.return_value.set_tmdb_poster = MagicMock()
    mock_cache.return_value.get_enrich.return_value = None
    mock_cache.return_value.set_enrich = MagicMock()

    result = enrich("Inception")

    assert result.media_strip.get("movie_title")
    hero_id = result.media_strip.get("tmdb_id")
    hero_title = (result.media_strip.get("movie_title") or "").strip().lower()
    hero_year = result.media_strip.get("year")
    for c in result.media_candidates:
        assert c.get("tmdb_id") != hero_id or hero_id is None
        ct = (c.get("movie_title") or "").strip().lower()
        cy = c.get("year")
        assert not (ct == hero_title and cy == hero_year), "hero must not appear in candidates"


def test_build_attachments_from_media_excludes_hero_from_candidates():
    """build_attachments_from_media filters out any candidate that matches the hero."""
    strip = {"movie_title": "Inception", "year": 2010, "tmdb_id": 27205, "page_url": "https://tmdb.org/movie/27205"}
    # Duplicate hero in candidates (simulates legacy or bug)
    candidates = [
        {"movie_title": "Inception", "year": 2010, "tmdb_id": 27205, "page_url": "https://tmdb.org/movie/27205"},
        {"movie_title": "The Matrix", "year": 1999, "tmdb_id": 603, "page_url": "https://tmdb.org/movie/603"},
    ]
    result = {
        "media_strip": strip,
        "media_candidates": candidates,
        "media_gallery_label": "Did you mean?",
    }
    out = build_attachments_from_media(result)
    assert len(out["sections"]) == 2
    primary_items = out["sections"][0]["items"]
    did_you_mean_items = out["sections"][1]["items"]
    hero_tmdb_id = primary_items[0].get("tmdbId") if primary_items else None
    hero_title = (primary_items[0].get("title") or "").strip().lower() if primary_items else ""
    hero_year = primary_items[0].get("year") if primary_items else None
    for item in did_you_mean_items:
        assert item.get("tmdbId") != hero_tmdb_id or hero_tmdb_id is None
        assert not ((item.get("title") or "").strip().lower() == hero_title and item.get("year") == hero_year)


def test_all_attachment_items_unique_by_tmdb_id_or_title_year():
    """After build_attachments_from_media, all items are unique by tmdbId or (title, year)."""
    result = {
        "media_strip": {"movie_title": "Inception", "year": 2010, "tmdb_id": 27205, "page_url": "#"},
        "media_candidates": [
            {"movie_title": "The Matrix", "year": 1999, "tmdb_id": 603, "page_url": "#"},
        ],
        "media_gallery_label": "Did you mean?",
    }
    out = build_attachments_from_media(result)
    seen = set()
    for section in out["sections"]:
        for item in section.get("items", []):
            key = item.get("tmdbId") or (item.get("title"), item.get("year"))
            assert key not in seen, f"Duplicate attachment: {key}"
            seen.add(key)
