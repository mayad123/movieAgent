"""Contract tests for TMDB movie metadata helper functions.

These helpers must:
- Not raise on any failure (bad token, network, malformed JSON)
- Return [] on failure so downstream hub filtering degrades gracefully
- Parse TMDB JSON into deterministic lists
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from integrations.tmdb.movie_metadata import (
    clear_movie_metadata_bundle_cache,
    fetch_movie_cast_names,
    fetch_movie_genre_names,
    fetch_movie_keyword_names,
)


@pytest.fixture(autouse=True)
def _clear_bundle_cache():
    clear_movie_metadata_bundle_cache()
    yield
    clear_movie_metadata_bundle_cache()


def test_fetch_movie_cast_names_empty_when_token_missing():
    assert fetch_movie_cast_names(movie_id=123, token="") == []


def test_fetch_movie_cast_names_parses_names_and_truncates():
    payload = {
        "genres": [],
        "credits": {
            "cast": [
                {"name": "Keanu Reeves"},
                {"name": "Keanu Reeves (2nd)"},
                {"name": "Someone Else"},
            ]
        },
        "keywords": {"keywords": []},
    }
    with patch("integrations.tmdb.movie_metadata.tmdb_request_json") as m:
        m.return_value = payload
        out = fetch_movie_cast_names(movie_id=1, token="token", max_names=2)

    assert out == ["Keanu Reeves", "Keanu Reeves (2nd)"]


def test_fetch_movie_genre_names_parses_genre_names():
    payload = {
        "genres": [{"name": "Horror"}, {"name": "Drama"}],
        "credits": {"cast": []},
        "keywords": {"keywords": []},
    }
    with patch("integrations.tmdb.movie_metadata.tmdb_request_json") as m:
        m.return_value = payload
        out = fetch_movie_genre_names(movie_id=10, token="token")

    assert out == ["Horror", "Drama"]


def test_fetch_movie_keyword_names_parses_keyword_names():
    payload = {
        "genres": [],
        "credits": {"cast": []},
        "keywords": {"keywords": [{"name": "scary"}, {"name": "fear"}]},
    }
    with patch("integrations.tmdb.movie_metadata.tmdb_request_json") as m:
        m.return_value = payload
        out = fetch_movie_keyword_names(movie_id=10, token="token")

    assert out == ["scary", "fear"]


def test_fetch_movie_metadata_returns_empty_on_malformed_json():
    with patch("integrations.tmdb.movie_metadata.tmdb_request_json") as m:
        m.return_value = None

        assert fetch_movie_cast_names(movie_id=1, token="token") == []
        assert fetch_movie_genre_names(movie_id=1, token="token") == []
        assert fetch_movie_keyword_names(movie_id=1, token="token") == []
