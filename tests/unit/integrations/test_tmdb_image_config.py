"""Unit tests for TMDB image configuration and URL building."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from integrations.tmdb.image_config import (
    FALLBACK_BACKDROP_SIZE,
    FALLBACK_SECURE_BASE,
    SIZE_BACKDROP_GALLERY,
    SIZE_POSTER_GALLERY,
    SIZE_POSTER_THUMBNAIL,
    TMDBImageConfig,
    build_image_url,
    clear_config_cache,
    fetch_config,
    get_config,
)


class TestBuildImageUrl:
    def test_builds_url_with_config(self):
        config = TMDBImageConfig(
            secure_base_url="https://image.tmdb.org/t/p/",
            backdrop_sizes=["w300", "w780", "w1280", "original"],
            poster_sizes=["w92", "w185", "w500", "original"],
        )
        url = build_image_url("/abc.jpg", SIZE_BACKDROP_GALLERY, config)
        assert url == "https://image.tmdb.org/t/p/w780/abc.jpg"
        assert "w780" in url

    def test_builds_url_without_config_uses_fallback(self):
        url = build_image_url("/path/to.jpg", SIZE_BACKDROP_GALLERY, None)
        assert url.startswith(FALLBACK_SECURE_BASE)
        assert FALLBACK_BACKDROP_SIZE in url
        assert url.endswith("/path/to.jpg")

    def test_strips_and_adds_leading_slash_to_path(self):
        config = TMDBImageConfig(secure_base_url="https://x/t/p/", backdrop_sizes=["w780"], poster_sizes=["w185"])
        url = build_image_url("abc.jpg", SIZE_BACKDROP_GALLERY, config)
        assert url == "https://x/t/p/w780/abc.jpg"

    def test_returns_empty_for_empty_path(self):
        assert build_image_url("", SIZE_BACKDROP_GALLERY, None) == ""

    def test_returns_unchanged_for_http_path(self):
        assert build_image_url("https://other.com/x.jpg", SIZE_BACKDROP_GALLERY, None) == "https://other.com/x.jpg"


class TestTMDBImageConfigSizeSelection:
    def test_backdrop_gallery_prefers_w780(self):
        config = TMDBImageConfig(backdrop_sizes=["w300", "w780", "w1280", "original"])
        assert config.get_size(SIZE_BACKDROP_GALLERY) == "w780"

    def test_poster_thumbnail_prefers_w185(self):
        config = TMDBImageConfig(poster_sizes=["w92", "w154", "w185", "w342", "w500"])
        assert config.get_size(SIZE_POSTER_THUMBNAIL) == "w185"

    def test_poster_gallery_prefers_w500(self):
        config = TMDBImageConfig(poster_sizes=["w92", "w185", "w342", "w500", "original"])
        assert config.get_size(SIZE_POSTER_GALLERY) == "w500"

    def test_fallback_when_preferred_missing(self):
        config = TMDBImageConfig(backdrop_sizes=["w300", "original"])
        assert config.get_size(SIZE_BACKDROP_GALLERY) == "w300"


class TestFetchConfig:
    def test_returns_default_when_token_empty(self):
        config = fetch_config("")
        assert config.secure_base_url == FALLBACK_SECURE_BASE
        assert config.backdrop_sizes

    def test_parses_valid_response(self):
        payload_dict = {
            "images": {
                "secure_base_url": "https://cdn.tmdb.org/t/p/",
                "backdrop_sizes": ["w300", "w780"],
                "poster_sizes": ["w92", "w185"],
            }
        }
        with patch("integrations.tmdb.image_config.tmdb_request_json") as m:
            m.return_value = payload_dict
            config = fetch_config("token")
        assert config.secure_base_url == "https://cdn.tmdb.org/t/p/"
        assert "w780" in config.backdrop_sizes
        assert "w185" in config.poster_sizes


class TestGetConfigCache:
    def test_cache_cleared(self):
        clear_config_cache()
        with patch("integrations.tmdb.image_config.fetch_config") as mock_fetch:
            mock_fetch.return_value = TMDBImageConfig()
            get_config("t")
            get_config("t")
            # Second call should use cache (fetch_config called once)
            mock_fetch.assert_called_once()
