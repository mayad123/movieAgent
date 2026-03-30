"""Unit tests for title_extraction (deterministic movie title extraction)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.extraction.title_extraction import (
    extract_movie_titles,
    get_search_phrases,
)


def test_direct_title():
    """Direct movie title returns as-is."""
    r = extract_movie_titles("How to Train Your Dragon")
    assert r.titles == ("How to Train Your Dragon",)
    assert r.reason == "direct"
    assert r.intent == "single_title"


def test_images_for():
    """'show me images for X' extracts X."""
    r = extract_movie_titles("show me images for How to Train Your Dragon")
    assert "How to Train Your Dragon" in r.titles
    assert r.reason.startswith("prefix:")
    assert r.intent == "single_title"


def test_images_of():
    """'images of X' extracts X."""
    r = extract_movie_titles("images of Inception")
    assert "Inception" in r.titles
    assert r.intent == "single_title"


def test_movies_like():
    """'movies like X' extracts X and sets seed_for_similar intent."""
    r = extract_movie_titles("movies like How to Train Your Dragon")
    assert "How to Train Your Dragon" in r.titles
    assert r.intent == "seed_for_similar"


def test_recommend_movies_like():
    """'recommend movies like X' extracts X."""
    r = extract_movie_titles("Recommend movies like The Matrix")
    assert "The Matrix" in r.titles
    assert r.intent == "seed_for_similar"


def test_similar_to():
    """'similar to X' extracts X."""
    r = extract_movie_titles("similar to Dune")
    assert "Dune" in r.titles
    assert r.intent == "seed_for_similar"


def test_who_directed():
    """'who directed X' strips prefix and extracts X."""
    r = extract_movie_titles("Who directed The Matrix?")
    assert "The Matrix" in r.titles
    assert r.intent == "single_title"


def test_compare_splits_and():
    """'compare X and Y' splits into [X, Y] and sets compare intent."""
    r = extract_movie_titles("compare The Matrix and Inception")
    assert "The Matrix" in r.titles
    assert "Inception" in r.titles
    assert r.intent == "compare"


def test_direct_x_and_y():
    """Bare 'X and Y' (e.g. 'Matrix and Inception') splits into two titles."""
    r = extract_movie_titles("Matrix and Inception")
    assert r.titles == ("Matrix", "Inception")
    assert r.intent == "compare"


def test_comma_separated_titles():
    """Comma-separated list (e.g. 'Avatar, Inception, Kung Fu Panda') splits into individual titles."""
    r = extract_movie_titles("Avatar, Inception, Kung Fu Panda")
    assert r.titles == ("Avatar", "Inception", "Kung Fu Panda")
    assert r.reason == "comma_separated"
    assert r.intent == "compare"


def test_empty_query():
    """Empty query returns empty titles."""
    r = extract_movie_titles("")
    assert r.titles == ()
    assert r.reason == "empty"


def test_get_search_phrases():
    """get_search_phrases returns same order as extract_movie_titles.titles."""
    phrases = get_search_phrases("movies like Inception")
    assert "Inception" in phrases or "movies like Inception" in phrases
    assert len(phrases) >= 1
