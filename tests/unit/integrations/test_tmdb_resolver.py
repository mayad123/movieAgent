"""Unit tests for TMDB Search → ID → Details resolver."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from integrations.tmdb.resolver import (
    MIN_CONFIDENCE_AUTO_SELECT,
    TMDBCandidate,
    TMDBResolveResult,
    _extract_year,
    _normalize_title,
    _score_candidate,
    clear_resolve_cache,
    resolve_movie,
)


@pytest.fixture(autouse=True)
def _clear_resolver_cache():
    clear_resolve_cache()
    yield
    clear_resolve_cache()


class TestNormalizeAndExtract:
    def test_normalize_title(self):
        assert _normalize_title("  Inception  ") == "inception"
        assert _normalize_title("The Matrix") == "the matrix"
        assert _normalize_title("") == ""

    def test_extract_year(self):
        assert _extract_year("2010-07-16") == 2010
        assert _extract_year("1999") == 1999
        assert _extract_year("") is None
        assert _extract_year(None) is None


class TestScoreCandidate:
    def test_exact_title_match_bonus(self):
        r = {"title": "Inception", "release_date": "2010-07-16", "popularity": 50, "vote_count": 10000}
        s = _score_candidate(r, "Inception", 2010)
        assert s >= 1.0

    def test_year_exact_match_bonus(self):
        r = {"title": "Dune", "release_date": "2021-09-15", "popularity": 10, "vote_count": 1000}
        s = _score_candidate(r, "Dune", 2021)
        assert s > _score_candidate(r, "Dune", None)
        s2 = _score_candidate(r, "Dune", 2020)
        assert s2 < s

    def test_tie_breaker_popularity_vote_count(self):
        r1 = {"title": "A", "release_date": None, "popularity": 100, "vote_count": 5000}
        r2 = {"title": "A", "release_date": None, "popularity": 10, "vote_count": 100}
        assert _score_candidate(r1, "A", None) > _score_candidate(r2, "A", None)


class TestResolveMovie:
    def test_not_found_empty_query(self):
        result = resolve_movie("", access_token="token")
        assert result.status == "not_found"
        assert result.movie_id is None
        assert result.confidence == 0.0

    def test_not_found_empty_token(self):
        result = resolve_movie("Inception", access_token="")
        assert result.status == "not_found"

    def test_not_found_no_results(self):
        with patch("integrations.tmdb.resolver.tmdb_request_json") as m:
            m.return_value = {"results": []}
            result = resolve_movie("Nonexistent Movie XYZ", access_token="t")
        assert result.status == "not_found"
        assert result.movie_id is None

    def test_resolved_single_clear_match(self):
        payload = {
            "results": [
                {"id": 27205, "title": "Inception", "release_date": "2010-07-16", "popularity": 50, "vote_count": 10000}
            ]
        }
        with patch("integrations.tmdb.resolver.tmdb_request_json") as m:
            m.return_value = payload
            result = resolve_movie("Inception", year=2010, access_token="t")
        assert result.status == "resolved"
        assert result.movie_id == 27205
        assert result.confidence >= MIN_CONFIDENCE_AUTO_SELECT
        assert len(result.candidates) >= 1

    def test_ambiguous_when_top_two_close(self):
        payload = {
            "results": [
                {"id": 1, "title": "Dune", "release_date": "2021-01-01", "popularity": 80, "vote_count": 8000},
                {"id": 2, "title": "Dune", "release_date": "1984-01-01", "popularity": 75, "vote_count": 7500},
            ]
        }
        with patch("integrations.tmdb.resolver.tmdb_request_json") as m:
            m.return_value = payload
            result = resolve_movie("Dune", access_token="t")
        assert result.status in ("resolved", "ambiguous")
        assert len(result.candidates) >= 2
        ids = [c.id for c in result.candidates]
        assert 1 in ids and 2 in ids

    def test_candidates_have_id_title_year(self):
        payload = {
            "results": [
                {"id": 123, "title": "Test Movie", "release_date": "1999-05-01", "popularity": 1, "vote_count": 10}
            ]
        }
        with patch("integrations.tmdb.resolver.tmdb_request_json") as m:
            m.return_value = payload
            result = resolve_movie("Test Movie", access_token="t")
        assert result.candidates
        c = result.candidates[0]
        assert c.id == 123
        assert c.title == "Test Movie"
        assert c.year == 1999
        d = c.to_dict()
        assert d["id"] == 123 and d["title"] == "Test Movie" and d.get("year") == 1999

    def test_second_call_uses_cache(self):
        payload = {
            "results": [{"id": 1, "title": "Cached", "release_date": "2000-01-01", "popularity": 10, "vote_count": 100}]
        }
        with patch("integrations.tmdb.resolver.tmdb_request_json") as m:
            m.return_value = payload
            r1 = resolve_movie("Cached", access_token="t")
            r2 = resolve_movie("Cached", access_token="t")
        assert r1.movie_id == r2.movie_id
        assert m.call_count == 1


class TestTMDBResolveResultToDict:
    def test_to_dict_resolved(self):
        r = TMDBResolveResult(status="resolved", movie_id=42, confidence=0.9, candidates=[TMDBCandidate(42, "X", 2000)])
        d = r.to_dict()
        assert d["status"] == "resolved"
        assert d["movie_id"] == 42
        assert d["confidence"] == 0.9
        assert len(d["candidates"]) == 1

    def test_to_dict_ambiguous(self):
        r = TMDBResolveResult(
            status="ambiguous", confidence=0.5, candidates=[TMDBCandidate(1, "A", None), TMDBCandidate(2, "B", None)]
        )
        d = r.to_dict()
        assert d["status"] == "ambiguous"
        assert "movie_id" not in d or d.get("movie_id") is None
        assert len(d["candidates"]) == 2
