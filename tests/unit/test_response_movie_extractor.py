"""Unit tests for response_movie_extractor (deterministic response parsing)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.response_movie_extractor import (
    normalize_title,
    parse_response,
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
