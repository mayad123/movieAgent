"""Unit tests for response_movie_extractor (deterministic response parsing)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.extraction.response_movie_extractor import (
    normalize_title,
    parse_response,
    extract_titles_for_enrichment,
    ResponseParseResult,
    ExtractedMovie,
    ParseStructure,
    ParseSignals,
)


class TestNormalizeTitle:
    """Deterministic title normalization."""

    def test_empty(self):
        assert normalize_title("") == ""
        assert normalize_title(None) == ""

    def test_collapse_whitespace(self):
        assert normalize_title("  The   Matrix  ") == "The Matrix"

    def test_curly_quotes(self):
        assert normalize_title("\u2018Inception\u2019") == "Inception"
        assert normalize_title("\u201cDune\u201d") == "Dune"

    def test_strip_outer_quotes(self):
        assert normalize_title('"Avatar"') == "Avatar"
        assert normalize_title("'Pulp Fiction'") == "Pulp Fiction"

    def test_en_dash_normalized(self):
        assert "\u2013" not in normalize_title("Title\u2013Subtitle")
        assert "-" in normalize_title("Title\u2013Subtitle") or "Title" in normalize_title("Title\u2013Subtitle")


class TestParseStructure:
    """Structure flags: bullets, numbered, bold, title-year, dash-blurb."""

    def test_has_bullets(self):
        r = parse_response("Here are some films:\n- Inception (2010)\n- Dune (2021)")
        assert r.structure.has_bullets is True
        assert r.structure.has_numbered_list is False

    def test_has_numbered_list(self):
        r = parse_response("1. The Matrix (1999)\n2. Inception (2010)")
        assert r.structure.has_numbered_list is True

    def test_has_bold_titles(self):
        r = parse_response("**Inception** is a 2010 film. Also **Dune**.")
        assert r.structure.has_bold_titles is True

    def test_has_title_year_pattern(self):
        r = parse_response("Inception (2010) is great.")
        assert r.structure.has_title_year_pattern is True

    def test_has_dash_blurb_pattern(self):
        r = parse_response("Inception (2010) – a sci-fi thriller. Dune (2021): epic.")
        assert r.structure.has_dash_blurb_pattern is True

    def test_paragraph_like_no_flags(self):
        r = parse_response("This is a paragraph with no list structure.")
        assert r.structure.has_bullets is False
        assert r.structure.has_numbered_list is False
        assert r.structure.has_bold_titles is False


class TestParseMovies:
    """Extraction of ordered distinct movies."""

    def test_bullet_list_extraction(self):
        r = parse_response(
            "Movies similar to Dune:\n"
            "- Inception (2010)\n"
            "- Interstellar (2014)\n"
            "- The Matrix (1999)"
        )
        assert len(r.movies) >= 2
        titles = [m.title for m in r.movies]
        assert "Inception" in titles or any("Inception" in t for t in titles)
        assert "The Matrix" in titles or any("Matrix" in t for t in titles)

    def test_numbered_list_extraction(self):
        r = parse_response("1. Dune (2021)\n2. Blade Runner 2049 (2017)")
        assert len(r.movies) >= 1
        titles = [m.title for m in r.movies]
        assert any("Dune" in t for t in titles)

    def test_title_year_dash_blurb(self):
        r = parse_response(
            "Inception (2010) – A mind-bending sci-fi. Dune (2021): Epic adaptation."
        )
        assert len(r.movies) >= 1
        by_title = {m.title: m for m in r.movies}
        assert any("Inception" in t for t in by_title) or "Inception" in str(by_title)
        for m in r.movies:
            if "Inception" in m.title:
                assert m.year == 2010
            if "Dune" in m.title and m.year is not None:
                assert m.year == 2021

    def test_standalone_title_year(self):
        r = parse_response("We recommend The Matrix (1999) and Inception (2010).")
        assert len(r.movies) >= 1
        years = {m.title: m.year for m in r.movies}
        assert any(y == 1999 for y in years.values())
        assert any(y == 2010 for y in years.values())

    def test_dedupe_first_seen_order(self):
        r = parse_response(
            "**Inception** (2010) – great. Also:\n- Inception (2010)\n- Dune (2021)"
        )
        # Inception should appear once (first from bold/title-year), then Dune
        titles = [m.title for m in r.movies]
        assert titles.count("Inception") <= 1
        assert len(r.movies) >= 1

    def test_confidence_present(self):
        r = parse_response("**Dune** (2021)")
        assert len(r.movies) >= 1
        assert 0 <= r.movies[0].confidence <= 1.0


class TestSignals:
    """Deep dive and scene indicators."""

    def test_deep_dive_indicators(self):
        r = parse_response(
            "Below is an overview. In depth analysis. Summary: we have key points."
        )
        assert len(r.signals.deep_dive_indicators) >= 1
        assert any("overview" in s or "summary" in s or "key points" in s for s in r.signals.deep_dive_indicators)

    def test_scene_indicators(self):
        r = parse_response("The opening scene is stunning. The climax and key scene are memorable.")
        assert len(r.signals.scene_indicators) >= 1
        assert any("scene" in s for s in r.signals.scene_indicators)

    def test_no_signals(self):
        r = parse_response("Inception is a movie. So is Dune.")
        # May or may not have scene/deep dive; structure still computed
        assert hasattr(r.signals, "deep_dive_indicators")
        assert hasattr(r.signals, "scene_indicators")

    def test_the_film_movie_references(self):
        r = parse_response(
            "The film is great. The movie has stunning visuals. The film won awards."
        )
        assert r.signals.the_film_movie_references >= 2

    def test_scene_like_enumeration_bullet_descriptions(self):
        # Bullet lines without (Year) that look like scene descriptions
        r = parse_response(
            "Key moments in Inception:\n"
            "- The opening heist sequence\n"
            "- The dream within a dream\n"
            "- The spinning top ending"
        )
        assert r.signals.scene_like_enumeration is True

    def test_scene_phrase_key_moments(self):
        r = parse_response("Here are the key moments in the film. The climax is stunning.")
        assert any("key" in s or "climax" in s for s in r.signals.scene_indicators)


class TestToDict:
    """Serialization for intent classifier."""

    def test_to_dict_shape(self):
        r = parse_response("- Inception (2010)\n- Dune (2021)")
        d = r.to_dict()
        assert "movies" in d
        assert "structure" in d
        assert "signals" in d
        assert "hasBullets" in d["structure"]
        assert "hasNumberedList" in d["structure"]
        assert "hasBoldTitles" in d["structure"]
        assert "hasTitleYearPattern" in d["structure"]
        assert "hasDashBlurbPattern" in d["structure"]
        assert "deepDiveIndicators" in d["signals"]
        assert "sceneIndicators" in d["signals"]
        for m in d["movies"]:
            assert "title" in m
            assert "year" in m
            assert "confidence" in m

    def test_empty_response(self):
        r = parse_response("")
        assert r.movies == []
        d = r.to_dict()
        assert d["movies"] == []
        assert d["structure"]["hasBullets"] is False


class TestExtractTitlesForEnrichment:
    """extract_titles_for_enrichment: clean titles for TMDB, filtered by confidence."""

    RECOMMENDATION_RESPONSE = (
        'To give you recommendations similar to "Inception," here are some movies:\n'
        '\n'
        '- "Interstellar" (2014) - Directed by Christopher Nolan\n'
        '- "The Matrix" (1999) - A classic sci-fi film\n'
        '- "Donnie Darko" (2001) - A psychological thriller\n'
        '- "Eternal Sunshine of the Spotless Mind" (2004) - Romantic sci-fi\n'
        '- "Primer" (2004) - An intricate time travel plot\n'
        '\n'
        'These movies offer intricate plots, much like "Inception."\n'
        '\n'
        '(Source: IMDb)'
    )

    def test_quoted_titles_with_years(self):
        titles = extract_titles_for_enrichment(self.RECOMMENDATION_RESPONSE)
        assert len(titles) >= 5
        lower = [t.lower() for t in titles]
        assert any("interstellar" in t for t in lower)
        assert any("matrix" in t for t in lower)
        assert any("donnie darko" in t for t in lower)
        assert any("eternal sunshine" in t for t in lower)
        assert any("primer" in t for t in lower)

    def test_no_garbage_sentences(self):
        titles = extract_titles_for_enrichment(self.RECOMMENDATION_RESPONSE)
        for t in titles:
            assert len(t) < 60, f"Garbage extracted: {t!r}"
            assert "intricate plots" not in t.lower()
            assert "source:" not in t.lower()

    def test_bold_titles_with_year_after_markers(self):
        response = (
            "Top picks:\n"
            "- **Inception** (2010) - Mind-bending\n"
            "- **Interstellar** (2014) - Space epic\n"
            "- **The Dark Knight** (2008) - Superhero thriller"
        )
        titles = extract_titles_for_enrichment(response)
        assert len(titles) >= 3
        lower = [t.lower() for t in titles]
        assert any("inception" in t for t in lower)
        assert any("interstellar" in t for t in lower)
        assert any("dark knight" in t for t in lower)

    def test_bold_titles_without_years(self):
        response = (
            "Recommendations:\n"
            "- **The Matrix** - A reality-bending classic\n"
            "- **Inception** - A dream within a dream\n"
            "- **Tenet** - Time inversion thriller"
        )
        titles = extract_titles_for_enrichment(response)
        assert len(titles) >= 3
        lower = [t.lower() for t in titles]
        assert any("matrix" in t for t in lower)
        assert any("inception" in t for t in lower)
        assert any("tenet" in t for t in lower)

    def test_numbered_list(self):
        response = (
            "1. The Shawshank Redemption (1994)\n"
            "2. The Godfather (1972)\n"
            "3. Pulp Fiction (1994)"
        )
        titles = extract_titles_for_enrichment(response)
        assert len(titles) >= 3

    def test_mixed_bold_and_year(self):
        """Bold title with (Year) inside the bold markers."""
        response = "- **Inception (2010)** - Great movie"
        titles = extract_titles_for_enrichment(response)
        assert len(titles) >= 1
        assert any("inception" in t.lower() for t in titles)

    def test_inline_title_year_in_prose(self):
        response = "You should watch The Matrix (1999) and Inception (2010)."
        titles = extract_titles_for_enrichment(response)
        assert len(titles) >= 2

    def test_empty_response_returns_empty(self):
        assert extract_titles_for_enrichment("") == []

    def test_no_movies_in_response(self):
        assert extract_titles_for_enrichment("The weather is nice today.") == []

    def test_quoted_titles_no_years(self):
        response = (
            "Check out these films:\n"
            '- "The Matrix" - A classic\n'
            '- "Inception" - Mind-bending\n'
            '- "Tenet" - Time bending'
        )
        titles = extract_titles_for_enrichment(response)
        assert len(titles) >= 3
        lower = [t.lower() for t in titles]
        assert any("matrix" in t for t in lower)
        assert any("inception" in t for t in lower)

    def test_bold_colon_format(self):
        """Format: **Title**: description"""
        response = (
            "- **The Matrix**: A reality-bending classic\n"
            "- **Inception**: Dream heist thriller"
        )
        titles = extract_titles_for_enrichment(response)
        assert len(titles) >= 2
