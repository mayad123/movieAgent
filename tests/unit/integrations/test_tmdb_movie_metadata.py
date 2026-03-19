"""Contract tests for TMDB movie metadata helper functions.

These helpers must:
- Not raise on any failure (bad token, network, malformed JSON)
- Return [] on failure so downstream hub filtering degrades gracefully
- Parse TMDB JSON into deterministic lists
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

_src = Path(__file__).resolve().parent.parent.parent.parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from integrations.tmdb.movie_metadata import (  # noqa: E402
    fetch_movie_cast_names,
    fetch_movie_genre_names,
    fetch_movie_keyword_names,
)


class DummyResponse:
    def __init__(self, payload_bytes: bytes):
        self._payload_bytes = payload_bytes

    def read(self) -> bytes:
        return self._payload_bytes

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_fetch_movie_cast_names_empty_when_token_missing():
    assert fetch_movie_cast_names(movie_id=123, token="") == []


def test_fetch_movie_cast_names_parses_names_and_truncates():
    payload: dict[str, Any] = {
        "cast": [
            {"name": "Keanu Reeves"},
            {"name": "Keanu Reeves (2nd)"},
            {"name": "Someone Else"},
        ]
    }
    with patch("urllib.request.urlopen") as m:
        m.return_value.__enter__.return_value = DummyResponse(
            payload_bytes=(
                __import__("json").dumps(payload).encode("utf-8")
            )
        )
        # Truncate to 2 names.
        out = fetch_movie_cast_names(movie_id=1, token="token", max_names=2)

    assert out == ["Keanu Reeves", "Keanu Reeves (2nd)"]


def test_fetch_movie_genre_names_parses_genre_names():
    payload = {"genres": [{"name": "Horror"}, {"name": "Drama"}]}
    with patch("urllib.request.urlopen") as m:
        m.return_value.__enter__.return_value = DummyResponse(
            payload_bytes=(
                __import__("json").dumps(payload).encode("utf-8")
            )
        )
        out = fetch_movie_genre_names(movie_id=10, token="token")

    assert out == ["Horror", "Drama"]


def test_fetch_movie_keyword_names_parses_keyword_names():
    payload = {"keywords": [{"name": "scary"}, {"name": "fear"}]}
    with patch("urllib.request.urlopen") as m:
        m.return_value.__enter__.return_value = DummyResponse(
            payload_bytes=(
                __import__("json").dumps(payload).encode("utf-8")
            )
        )
        out = fetch_movie_keyword_names(movie_id=10, token="token")

    assert out == ["scary", "fear"]


def test_fetch_movie_metadata_returns_empty_on_malformed_json():
    with patch("urllib.request.urlopen") as m:
        m.return_value.__enter__.return_value = DummyResponse(payload_bytes=b"not-json")

        assert fetch_movie_cast_names(movie_id=1, token="token") == []
        assert fetch_movie_genre_names(movie_id=1, token="token") == []
        assert fetch_movie_keyword_names(movie_id=1, token="token") == []

