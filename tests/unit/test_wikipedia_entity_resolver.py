"""
Unit tests for WikipediaEntityResolver (Wikipedia-only entity resolution).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import requests
from unittest.mock import patch

from cinemind.wikipedia_entity_resolver import (
    WikipediaEntityResolver,
    ResolverResult,
    ResolvedEntity,
    _normalize_query,
    _title_looks_like_movie,
    _has_film_category,
    _page_title_to_display,
    _extract_year_from_title,
    _build_page_url,
)


def test_normalize_query():
    assert _normalize_query("  The   Matrix  ") == "The Matrix"
    assert _normalize_query("") == ""
    assert _normalize_query("Inception") == "Inception"


def test_title_looks_like_movie():
    assert _title_looks_like_movie("The Matrix (film)") is True
    assert _title_looks_like_movie("Something (movie)") is True
    assert _title_looks_like_movie("Dune (2021)") is True
    assert _title_looks_like_movie("The Matrix") is False
    assert _title_looks_like_movie("Matrix (band)") is False


def test_has_film_category():
    assert _has_film_category([{"title": "Category:American films"}]) is True
    assert _has_film_category([{"title": "Category:Films"}]) is True
    assert _has_film_category([{"title": "Category:Actors"}]) is False
    assert _has_film_category([]) is False


def test_page_title_to_display():
    assert _page_title_to_display("The_Matrix_(film)") == "The Matrix (film)"


def test_extract_year_from_title():
    assert _extract_year_from_title("Dune (2021 film)") == 2021
    assert _extract_year_from_title("Inception (2010)") == 2010
    assert _extract_year_from_title("The Matrix (film)") is None
    assert _extract_year_from_title("Something") is None


def test_build_page_url():
    # URL encodes parens
    url = _build_page_url("Inception_(film)")
    assert url.startswith("https://en.wikipedia.org/wiki/")
    assert "Inception" in url
    assert "Dune" in _build_page_url("Dune (2021 film)")


def test_resolve_empty_query():
    resolver = WikipediaEntityResolver()
    out = resolver.resolve("")
    assert out.status == "not_found"
    assert out.resolved_entity is None
    assert out.candidates == []


def test_resolve_whitespace_only():
    resolver = WikipediaEntityResolver()
    out = resolver.resolve("   ")
    assert out.status == "not_found"


@patch("cinemind.wikipedia_entity_resolver._search_wikipedia")
def test_resolve_single_result_resolved(mock_search):
    mock_search.return_value = [{"title": "The Matrix (film)"}]
    with patch("cinemind.wikipedia_entity_resolver._get_categories_batch") as mock_cat:
        mock_cat.return_value = {"The Matrix (film)": [{"title": "Category:American films"}]}
        resolver = WikipediaEntityResolver()
        out = resolver.resolve("The Matrix")
    assert out.status == "resolved"
    assert out.resolved_entity is not None
    assert out.resolved_entity.page_title == "The Matrix (film)"
    assert out.resolved_entity.display_title == "The Matrix (film)"
    assert out.candidates == []


@patch("cinemind.wikipedia_entity_resolver._search_wikipedia")
def test_resolve_multiple_results_ambiguous(mock_search):
    mock_search.return_value = [
        {"title": "Inception (film)"},
        {"title": "Inception (soundtrack)"},
        {"title": "Inception (2010 film)"},
    ]
    with patch("cinemind.wikipedia_entity_resolver._get_categories_batch") as mock_cat:
        mock_cat.return_value = {
            "Inception (film)": [{"title": "Category:Films"}],
            "Inception (soundtrack)": [],
            "Inception (2010 film)": [{"title": "Category:American films"}],
        }
        resolver = WikipediaEntityResolver()
        out = resolver.resolve("Inception")
    assert out.status == "ambiguous"
    assert out.resolved_entity is None
    assert len(out.candidates) >= 2
    assert all("pageTitle" in c and "displayTitle" in c for c in out.candidates)
    assert all("page_url" in c and "year" in c and "score" in c for c in out.candidates)
    assert len(out.candidates) <= 7


@patch("cinemind.wikipedia_entity_resolver._search_wikipedia")
def test_resolve_no_results_not_found(mock_search):
    mock_search.return_value = []
    resolver = WikipediaEntityResolver()
    out = resolver.resolve("XyZNoSuchMovie99")
    assert out.status == "not_found"
    assert out.resolved_entity is None
    assert out.candidates == []


@patch("cinemind.wikipedia_entity_resolver._search_wikipedia")
def test_resolve_wikipedia_unavailable_error(mock_search):
    mock_search.side_effect = requests.RequestException("Connection error")
    resolver = WikipediaEntityResolver()
    out = resolver.resolve("The Matrix")
    assert out.status == "error"
    assert out.error_message == "Wikipedia unavailable"
    assert out.resolved_entity is None
    assert out.candidates == []


def test_resolver_result_to_dict():
    r = ResolverResult(
        status="resolved",
        resolved_entity=ResolvedEntity(page_title="The_Matrix_(film)", display_title="The Matrix (film)"),
    )
    d = r.to_dict()
    assert d["status"] == "resolved"
    assert d["resolvedEntity"]["pageTitle"] == "The_Matrix_(film)"
    assert d["resolvedEntity"]["displayTitle"] == "The Matrix (film)"

    r2 = ResolverResult(status="ambiguous", candidates=[{"pageTitle": "A", "displayTitle": "A"}])
    d2 = r2.to_dict()
    assert d2["status"] == "ambiguous"
    assert d2["candidates"] == [{"pageTitle": "A", "displayTitle": "A"}]
