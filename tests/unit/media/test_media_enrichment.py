"""Unit tests for media_enrichment (TMDB-only enrichment)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.media.media_enrichment import (
    SECTION_DID_YOU_MEAN,
    SECTION_MOVIE_LIST,
    SECTION_PRIMARY_MOVIE,
    MediaEnrichmentResult,
    attach_media_to_result,
    build_attachments_from_media,
    enrich,
    enrich_batch,
)


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
    """When TMDB fails or is disabled, fallback uses fallback_title."""
    result = enrich("xyz nonexistent movie 12345", fallback_title="Custom Fallback")
    assert result.media_strip.get("movie_title") == "Custom Fallback"


def test_enrich_fallback_from_result():
    """When TMDB fails, fallback uses result.query or first source title."""
    result = enrich(
        "xyznonexistentmovie123",
        fallback_from_result={"query": "Inception", "sources": []},
    )
    assert result.media_strip.get("movie_title") == "Inception"


def test_build_attachments_from_media_primary_only():
    """build_attachments_from_media produces primary_movie section from media_strip."""
    result = {
        "media_strip": {
            "movie_title": "Dune (1984 film)",
            "year": 1984,
            "primary_image_url": "https://example.com/dune.jpg",
            "page_url": "https://www.themoviedb.org/movie/841",
        },
        "media_candidates": [],
    }
    out = build_attachments_from_media(result)
    assert "sections" in out
    assert len(out["sections"]) == 1
    assert out["sections"][0]["type"] == SECTION_PRIMARY_MOVIE
    assert out["sections"][0]["title"] == "This movie"
    assert len(out["sections"][0]["items"]) == 1
    item = out["sections"][0]["items"][0]
    assert item["title"] == "Dune (1984 film)"
    assert item["year"] == 1984
    assert item.get("imageUrl") and "dune" in item["imageUrl"]
    assert item.get("sourceUrl")


def test_build_attachments_from_media_movie_list():
    """build_attachments_from_media produces movie_list section from media_candidates with label."""
    result = {
        "media_strip": {"movie_title": "Dune", "page_url": "https://www.themoviedb.org/movie/438631"},
        "media_candidates": [
            {
                "movie_title": "Inception",
                "year": 2010,
                "page_url": "https://www.themoviedb.org/movie/27205",
                "primary_image_url": "https://ex.inception.jpg",
            },
        ],
        "media_gallery_label": "Similar movies",
    }
    out = build_attachments_from_media(result)
    assert len(out["sections"]) == 2
    assert out["sections"][0]["type"] == SECTION_PRIMARY_MOVIE
    assert out["sections"][1]["type"] == SECTION_MOVIE_LIST
    assert out["sections"][1]["title"] == "Similar movies"
    assert len(out["sections"][1]["items"]) == 1
    assert out["sections"][1]["items"][0]["title"] == "Inception"


def test_build_attachments_from_media_did_you_mean():
    """build_attachments_from_media produces did_you_mean when label starts with Did you mean."""
    result = {
        "media_strip": {},
        "media_candidates": [
            {"movie_title": "Dune (1984 film)", "page_url": "https://www.themoviedb.org/movie/841"},
        ],
        "media_gallery_label": "Did you mean?",
    }
    out = build_attachments_from_media(result)
    assert len(out["sections"]) == 1
    assert out["sections"][0]["type"] == SECTION_DID_YOU_MEAN
    assert "Did you mean" in out["sections"][0]["title"]


def test_attach_media_to_result_mutates_in_place():
    """attach_media_to_result mutates result when result has recommended_movies (non-playground: no user_query seed)."""
    result = {"response": "test", "query": "The Matrix", "recommended_movies": ["The Matrix"]}
    attach_media_to_result("The Matrix", result)
    assert "media_strip" in result
    assert result["media_strip"].get("movie_title")
    assert "attachments" in result
    assert "sections" in result["attachments"]
    assert isinstance(result["attachments"]["sections"], list)


def test_enrich_never_raises():
    """enrich() never raises even on bad input."""
    enrich("")
    enrich("", fallback_from_result={})


def test_enrich_candidate_payload_has_page_url_and_year():
    """When ambiguous, candidates include page_url and year when available."""
    result = enrich("Dune")
    if result.media_candidates:
        for c in result.media_candidates:
            assert "movie_title" in c
            assert "page_url" in c
            assert c["page_url"].startswith("https://") or c["page_url"] == "#"
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
    assert "Inception" in (result.media_strip.get("movie_title") or "")


def test_enrich_movies_like_phrasing():
    """'movies like X' resolves seed title X and returns media_strip."""
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


def test_attach_media_to_result_fallback_from_user_query():
    """Without recommended_movies or response titles, falls back to user_query."""
    result = {"response": "Here is some info.", "query": "Inception"}
    attach_media_to_result("Inception", result)
    assert "media_strip" in result
    assert result["media_strip"].get("movie_title")
    assert "attachments" in result
    assert isinstance(result["attachments"].get("sections"), list)


def test_attach_media_extracts_from_response_bullets_with_year():
    """When response has bullet-listed movies with years, extracts and batch-enriches them."""
    response = (
        "Here are some movies you might enjoy:\n"
        '- "Interstellar" (2014) - A sci-fi film by Christopher Nolan\n'
        '- "The Matrix" (1999) - A classic about reality\n'
        '- "Primer" (2004) - A low-budget time travel film'
    )
    result = {"response": response, "query": "movies like Inception"}
    attach_media_to_result("movies like Inception", result)
    assert "media_strip" in result
    assert result["media_strip"].get("movie_title")
    assert "attachments" in result
    sections = result["attachments"].get("sections", [])
    assert len(sections) >= 1
    all_titles = []
    for s in sections:
        for item in s.get("items", []):
            all_titles.append(item.get("title", ""))
    assert len(all_titles) >= 2, f"Expected >=2 movie posters, got {all_titles}"


def test_attach_media_extracts_from_response_bold_with_year():
    """Bold titles with years after the bold markers are extracted."""
    response = (
        "Top picks:\n"
        "- **Inception** (2010) - A mind-bending thriller\n"
        "- **Interstellar** (2014) - Space exploration epic\n"
        "- **The Dark Knight** (2008) - Superhero drama"
    )
    result = {"response": response}
    attach_media_to_result("recommend Christopher Nolan movies", result)
    assert "media_strip" in result
    strip_title = result["media_strip"].get("movie_title", "")
    assert strip_title, "Expected a movie title in media_strip"
    sections = result["attachments"].get("sections", [])
    all_titles = [item.get("title", "") for s in sections for item in s.get("items", [])]
    assert len(all_titles) >= 2


def test_attach_media_extracts_from_response_numbered_list():
    """Numbered list format is parsed correctly."""
    response = (
        "1. The Shawshank Redemption (1994) - A tale of hope\n"
        "2. The Godfather (1972) - Crime family saga\n"
        "3. Pulp Fiction (1994) - Non-linear storytelling"
    )
    result = {"response": response}
    attach_media_to_result("best movies of all time", result)
    assert "media_strip" in result
    sections = result["attachments"].get("sections", [])
    all_titles = [item.get("title", "") for s in sections for item in s.get("items", [])]
    assert len(all_titles) >= 2


def test_attach_media_response_extraction_not_garbage():
    """Prose sentences in the response are NOT extracted as titles."""
    response = (
        "Here are some great films:\n"
        "- Inception (2010) - A mind-bending thriller\n"
        "- The Matrix (1999) - A classic sci-fi film\n"
        "\n"
        "These movies offer intricate plots and visual spectacles."
    )
    result = {"response": response}
    attach_media_to_result("movie recommendations", result)
    sections = result.get("attachments", {}).get("sections", [])
    all_titles = [item.get("title", "") for s in sections for item in s.get("items", [])]
    for title in all_titles:
        assert len(title) < 60, f"Garbage title extracted: {title!r}"


def test_attach_media_prefers_recommended_movies_over_response():
    """Explicit recommended_movies takes priority over response parsing."""
    response = "- Inception (2010) - A mind-bending thriller\n- The Matrix (1999) - A classic sci-fi film"
    result = {"response": response, "recommended_movies": ["Dune"]}
    attach_media_to_result("movie recs", result)
    assert result["media_strip"].get("movie_title")
    title = result["media_strip"]["movie_title"].lower()
    assert "dune" in title


def test_attach_media_x_and_y_uses_batch():
    """When recommended_movies has 2+ titles, attach_media uses enrich_batch (no user_query seed)."""
    result = {"response": "test", "recommended_movies": ["Matrix", "Inception"]}
    attach_media_to_result("Matrix and Inception", result)
    assert "media_strip" in result
    assert result["media_strip"].get("movie_title")
    assert "media_candidates" in result
    assert len(result["media_candidates"]) >= 1
    total = 1 + len(result["media_candidates"])
    assert total >= 2


def test_enrich_batch_graceful_degradation():
    """One failing title does not fail the batch; returns cards for resolved titles."""
    cards = enrich_batch(["Inception", "xyznonexistent123", "The Matrix"])
    assert len(cards) >= 2
    titles = [c["movie_title"] for c in cards]
    assert "Inception" in titles or any("Inception" in t for t in titles)
    assert any("Matrix" in t for t in titles)
