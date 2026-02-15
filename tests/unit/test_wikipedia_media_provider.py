"""
Unit tests for WikipediaMediaProvider (primary image for resolved movie entity).
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.wikipedia_entity_resolver import ResolvedEntity
from cinemind.wikipedia_media_provider import WikipediaMediaProvider, _fetch_page_image


def test_get_media_strip_returns_movie_title_always():
    provider = WikipediaMediaProvider()
    entity = ResolvedEntity(page_title="How_to_Train_Your_Dragon_(film)", display_title="How to Train Your Dragon (film)")
    with patch("cinemind.wikipedia_media_provider._fetch_page_image", return_value=None):
        out = provider.get_media_strip(entity)
    assert out["movie_title"] == "How to Train Your Dragon (film)"
    assert "primary_image_url" not in out or out.get("primary_image_url") is None


def test_get_media_strip_includes_primary_url_when_image_exists():
    provider = WikipediaMediaProvider()
    entity = ResolvedEntity(page_title="The_Matrix_(film)", display_title="The Matrix (film)")
    with patch("cinemind.wikipedia_media_provider._fetch_page_image", return_value="https://upload.wikimedia.org/example.jpg"):
        out = provider.get_media_strip(entity)
    assert out["movie_title"] == "The Matrix (film)"
    assert out["primary_image_url"] == "https://upload.wikimedia.org/example.jpg"


def test_get_media_strip_never_raises_on_fetch_failure():
    provider = WikipediaMediaProvider()
    entity = ResolvedEntity(page_title="Some_Film", display_title="Some Film")
    with patch("cinemind.wikipedia_media_provider._fetch_page_image", side_effect=Exception("network error")):
        out = provider.get_media_strip(entity)
    assert out["movie_title"] == "Some Film"
    assert "primary_image_url" not in out


def test_get_media_strip_fallback_display_title():
    entity = ResolvedEntity(page_title="No_Spaces_Here", display_title="")
    provider = WikipediaMediaProvider()
    with patch("cinemind.wikipedia_media_provider._fetch_page_image", return_value=None):
        out = provider.get_media_strip(entity)
    assert out["movie_title"] == "No Spaces Here"


def test_fetch_page_image_returns_none_on_empty_pages():
    session = MagicMock()
    session.get.return_value = MagicMock()
    session.get.return_value.json.return_value = {"query": {"pages": {}}}
    session.get.return_value.raise_for_status = MagicMock()
    assert _fetch_page_image(session, "Some_Page") is None


def test_fetch_page_image_returns_thumbnail_source():
    session = MagicMock()
    session.get.return_value = MagicMock()
    session.get.return_value.json.return_value = {
        "query": {
            "pages": {
                "123": {
                    "title": "Test",
                    "thumbnail": {"source": "https://example.org/thumb.jpg"},
                }
            }
        }
    }
    session.get.return_value.raise_for_status = MagicMock()
    assert _fetch_page_image(session, "Test") == "https://example.org/thumb.jpg"
