"""Unit tests for media_enrichment (shared Wikipedia-only enrichment)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.media_enrichment import (
    MediaEnrichmentResult,
    enrich,
    enrich_batch,
    attach_media_to_result,
)
from cinemind.wikipedia_entity_resolver import WikipediaEntityResolver, ResolverResult, ResolvedEntity
from cinemind.wikipedia_media_provider import WikipediaMediaProvider


def test_enrich_returns_media_strip_with_movie_title():
    """enrich() returns MediaEnrichmentResult with media_strip (at least movie_title)."""
    result = enrich("The Matrix")
    assert isinstance(result, MediaEnrichmentResult)
    assert "media_strip" in result.to_dict()
    assert result.media_strip.get("movie_title")


def test_enrich_strips_prefixes():
    """enrich() strips common prefixes like 'who directed'."""
    result = enrich("Who directed The Matrix?")
    assert result.media_strip.get("movie_title")


def test_enrich_fallback_from_user_query():
    """When Wikipedia fails, fallback uses user query as movie_title."""
    # Use a query that won't resolve (empty is handled)
    result = enrich("xyz nonexistent movie 12345", fallback_title="Custom Fallback")
    assert result.media_strip.get("movie_title") == "Custom Fallback"


def test_enrich_fallback_from_result():
    """When Wikipedia fails, fallback uses result.query or first source title."""
    # Use a query that won't resolve to any Wikipedia page
    result = enrich(
        "xyznonexistentmovie123",
        fallback_from_result={"query": "Inception", "sources": []},
    )
    assert result.media_strip.get("movie_title") == "Inception"


def test_attach_media_to_result_mutates_in_place():
    """attach_media_to_result mutates result dict in place."""
    result = {"response": "test", "query": "The Matrix"}
    attach_media_to_result("The Matrix", result)
    assert "media_strip" in result
    assert result["media_strip"].get("movie_title")


def test_enrich_never_raises():
    """enrich() never raises even on bad input."""
    enrich("")
    enrich("", fallback_from_result={})


def test_enrich_candidate_payload_has_page_url_and_year():
    """When ambiguous, candidates include page_url and year when available."""
    result = enrich("Dune")  # Ambiguous: Dune 1984, Dune 2021, etc.
    # May be single or gallery depending on resolver; if we get candidates, check shape
    if result.media_candidates:
        for c in result.media_candidates:
            assert "movie_title" in c
            assert "page_url" in c
            assert c["page_url"].startswith("https://en.wikipedia.org/wiki/")
            # year is optional
            if "year" in c:
                assert isinstance(c["year"], int)
                assert 1900 <= c["year"] <= 2100


def test_enrich_media_strip_includes_page_url():
    """media_strip includes page_url when we have a resolved entity."""
    result = enrich("Inception")
    assert result.media_strip.get("movie_title")
    assert "page_url" in result.media_strip


def test_enrich_images_for_phrasing():
    """'show me images for X' resolves X and returns media_strip (title extraction)."""
    result = enrich("show me images for Inception")
    assert result.media_strip.get("movie_title")
    # Should resolve to Inception (film)
    assert "Inception" in (result.media_strip.get("movie_title") or "")


def test_enrich_movies_like_phrasing():
    """'movies like X' resolves seed title X and returns media_strip (similar-movies intent)."""
    result = enrich("movies like The Matrix")
    assert result.media_strip.get("movie_title")
    assert "Matrix" in (result.media_strip.get("movie_title") or "")


def test_enrich_batch_returns_cards():
    """enrich_batch returns list of card dicts with movie_title and page_url."""
    cards = enrich_batch(["Inception", "The Matrix"])
    assert len(cards) >= 1
    for c in cards:
        assert "movie_title" in c
        assert "page_url" in c
        assert c["page_url"].startswith("https://") or c["page_url"] == "#"


def test_attach_media_x_and_y_uses_batch():
    """'Matrix and Inception' produces media_strip + media_candidates (both movies)."""
    result = {"response": "test"}
    attach_media_to_result("Matrix and Inception", result)
    assert "media_strip" in result
    assert result["media_strip"].get("movie_title")
    assert "media_candidates" in result
    assert len(result["media_candidates"]) >= 1
    # Should have 2 cards total (strip + at least 1 candidate)
    total = 1 + len(result["media_candidates"])
    assert total >= 2


def test_enrich_batch_graceful_degradation():
    """One failing title does not fail the batch; returns cards for resolved titles."""
    cards = enrich_batch(["Inception", "xyznonexistent123", "The Matrix"])
    assert len(cards) >= 2  # At least Inception and The Matrix
    titles = [c["movie_title"] for c in cards]
    assert "Inception" in titles or any("Inception" in t for t in titles)
    assert any("Matrix" in t for t in titles)
