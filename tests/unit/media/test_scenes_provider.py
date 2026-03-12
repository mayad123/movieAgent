"""Unit tests for pluggable scenes provider (TMDB + empty fallback)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from integrations.tmdb.scenes import (
    SceneItem,
    ScenesProviderEmpty,
    ScenesProviderTMDB,
    get_scenes_provider,
)


class TestSceneItem:
    def test_to_attachment_item(self):
        item = SceneItem(image_url="https://img.example/a.jpg", caption="Backdrop", source_url="https://tmdb.org/movie/1")
        out = item.to_attachment_item()
        assert out["imageUrl"] == "https://img.example/a.jpg"
        assert out["caption"] == "Backdrop"
        assert out["sourceUrl"] == "https://tmdb.org/movie/1"

    def test_to_attachment_item_minimal(self):
        item = SceneItem(image_url="https://x.y/z.jpg")
        out = item.to_attachment_item()
        assert out == {"imageUrl": "https://x.y/z.jpg"}


class TestScenesProviderEmpty:
    def test_returns_empty_list(self):
        p = ScenesProviderEmpty()
        assert p.fetch_scenes("Inception") == []
        assert p.fetch_scenes("Inception", year=2010) == []


class TestScenesProviderTMDB:
    def test_empty_token_returns_empty(self):
        p = ScenesProviderTMDB(access_token="")
        assert p.fetch_scenes("Inception") == []

    def test_search_failure_returns_empty(self):
        p = ScenesProviderTMDB(access_token="test-token")
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            assert p.fetch_scenes("Inception") == []

    def test_returns_normalized_items_on_mock_response(self):
        from integrations.tmdb.image_config import TMDBImageConfig, get_config, clear_config_cache
        clear_config_cache()
        p = ScenesProviderTMDB(access_token="token", max_backdrops=2)
        search_response = b'{"results":[{"id":27205,"title":"Inception","release_date":"2010-07-16"}]}'
        images_response = b'{"backdrops":[{"file_path":"/abc.jpg","vote_average":7.5,"vote_count":10},{"file_path":"/def.jpg","vote_average":6,"vote_count":2}]}'
        fixed_config = TMDBImageConfig(
            secure_base_url="https://image.tmdb.org/t/p/",
            backdrop_sizes=["w300", "w780", "w1280", "original"],
            poster_sizes=["w92", "w185", "w500", "original"],
        )
        with patch("integrations.tmdb.image_config.get_config", return_value=fixed_config):
            with patch("urllib.request.urlopen") as m:
                m.return_value.__enter__.return_value.read.side_effect = [search_response, images_response]
                items = p.fetch_scenes("Inception")
        assert len(items) == 2
        assert items[0].image_url == "https://image.tmdb.org/t/p/w780/abc.jpg"
        assert items[0].source_url == "https://www.themoviedb.org/movie/27205"
        assert items[0].source == "TMDB"
        assert items[0].source_label == "The Movie Database"
        assert items[1].image_url == "https://image.tmdb.org/t/p/w780/def.jpg"
        # Attachment item includes attribution for UI
        d = items[0].to_attachment_item()
        assert d.get("source") == "TMDB" and d.get("sourceLabel") == "The Movie Database"

    def test_low_resolution_backdrops_filtered_out(self):
        """Backdrops below MIN_BACKDROP_WIDTH/MIN_BACKDROP_HEIGHT are excluded."""
        from integrations.tmdb.image_config import TMDBImageConfig, get_config, clear_config_cache
        clear_config_cache()
        p = ScenesProviderTMDB(access_token="token", max_backdrops=5)
        search_response = b'{"results":[{"id":1,"title":"X","release_date":"2020-01-01"}]}'
        # One valid (w780), one too narrow (width 200), one too short (height 100)
        images_response = b'{"backdrops":[' \
            b'{"file_path":"/good.jpg","vote_average":8,"vote_count":100,"width":780,"height":439},' \
            b'{"file_path":"/narrow.jpg","vote_average":7,"vote_count":50,"width":200,"height":112},' \
            b'{"file_path":"/short.jpg","vote_average":6,"vote_count":25,"width":400,"height":100}' \
            b']}'
        fixed_config = TMDBImageConfig(
            secure_base_url="https://image.tmdb.org/t/p/",
            backdrop_sizes=["w780"],
            poster_sizes=["w185"],
        )
        with patch("integrations.tmdb.image_config.get_config", return_value=fixed_config):
            with patch("urllib.request.urlopen") as m:
                m.return_value.__enter__.return_value.read.side_effect = [search_response, images_response]
                items = p.fetch_scenes("X")
        # Only the first (good) backdrop passes the filter
        assert len(items) == 1
        assert "good.jpg" in items[0].image_url

    def test_uses_bearer_header_not_api_key_in_url(self):
        """TMDB requests use Authorization: Bearer and no token in query string."""
        from integrations.tmdb.scenes import _bearer_headers
        h = _bearer_headers("secret-token")
        assert h["Authorization"] == "Bearer secret-token"
        assert "Accept" in h
        # Ensure no key named api_key would be sent
        assert "api_key" not in h


class TestGetScenesProvider:
    def test_fallback_when_tmdb_disabled(self):
        with patch("config.ENABLE_TMDB_SCENES", False):
            with patch("config.TMDB_READ_ACCESS_TOKEN", "token"):
                p = get_scenes_provider()
        assert isinstance(p, ScenesProviderEmpty)

    def test_fallback_when_tmdb_token_empty(self):
        with patch("config.ENABLE_TMDB_SCENES", True):
            with patch("config.TMDB_READ_ACCESS_TOKEN", ""):
                p = get_scenes_provider()
        assert isinstance(p, ScenesProviderEmpty)

    def test_tmdb_provider_when_enabled_and_configured(self):
        with patch("config.ENABLE_TMDB_SCENES", True):
            with patch("config.TMDB_READ_ACCESS_TOKEN", "secret-token"):
                p = get_scenes_provider()
        assert isinstance(p, ScenesProviderTMDB)
