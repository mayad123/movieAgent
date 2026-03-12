"""
Tests for GET /api/watch/where-to-watch: happy path, not found, rate limit, missing key.
Run with: PYTHONPATH=src pytest tests/unit/test_where_to_watch_api.py -v
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_src = Path(__file__).resolve().parent.parent.parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def test_where_to_watch_missing_key_returns_500(client):
    """When WATCHMODE_API_KEY is not set, returns 500 with structured error."""
    with patch("api.main.is_watchmode_configured", return_value=False):
        r = client.get("/api/watch/where-to-watch", params={"tmdbId": "603", "mediaType": "movie", "country": "US"})
    assert r.status_code == 500
    data = r.json()
    assert data.get("error") == "missing_key"
    assert "WATCHMODE_API_KEY" in (data.get("message") or "")


def test_where_to_watch_not_found_returns_404(client):
    """When title is not found in Watchmode, returns 404 with not_found error."""
    mock_client = AsyncMock()
    mock_client.get_availability = AsyncMock(return_value=("Title not found for the given TMDB id and type.", None))
    with patch("api.main.is_watchmode_configured", return_value=True):
        with patch("integrations.watchmode.get_watchmode_client", return_value=mock_client):
            r = client.get("/api/watch/where-to-watch", params={"tmdbId": "99999999", "mediaType": "movie", "country": "US"})
    assert r.status_code == 404
    data = r.json()
    assert data.get("error") == "not_found"
    assert "not found" in (data.get("message") or "").lower()


def test_where_to_watch_rate_limit_returns_429(client):
    """When Watchmode returns rate limit, returns 429 with rate_limit_exceeded."""
    mock_client = AsyncMock()
    mock_client.get_availability = AsyncMock(return_value=("Rate limit exceeded. Try again later.", None))
    with patch("api.main.is_watchmode_configured", return_value=True):
        with patch("integrations.watchmode.get_watchmode_client", return_value=mock_client):
            r = client.get("/api/watch/where-to-watch", params={"tmdbId": "603", "mediaType": "movie", "country": "US"})
    assert r.status_code == 429
    data = r.json()
    assert data.get("error") == "rate_limit_exceeded"
    assert "rate limit" in (data.get("message") or "").lower()


def test_where_to_watch_happy_path_returns_200_and_normalized_shape(client):
    """When Watchmode returns data, returns 200 with title, region, offers (normalized)."""
    mock_payload = {
        "movie": {"title": "The Matrix", "year": 1999},
        "region": "US",
        "groups": [
            {"accessType": "subscription", "label": "Subscription", "offers": [{"providerName": "Netflix", "providerId": "1", "price": None, "webUrl": "https://netflix.com/title/123", "deeplink": None}]},
        ],
    }
    mock_client = AsyncMock()
    mock_client.get_availability = AsyncMock(return_value=(None, mock_payload))
    with patch("api.main.is_watchmode_configured", return_value=True):
        with patch("integrations.watchmode.get_watchmode_client", return_value=mock_client):
            r = client.get("/api/watch/where-to-watch", params={"tmdbId": "603", "mediaType": "movie", "country": "US"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("region") == "US"
    assert "title" in data
    assert data["title"].get("id") == "603"
    assert data["title"].get("mediaType") == "movie"
    assert "offers" in data
    assert isinstance(data["offers"], list)
    assert len(data["offers"]) >= 1
    assert data["offers"][0].get("accessType") == "subscription"
    assert data["offers"][0].get("provider", {}).get("name") == "Netflix"
    assert "lastUpdated" in data


def test_where_to_watch_missing_tmdb_id_and_title_returns_400(client):
    """When both tmdbId and title are missing, returns 400."""
    with patch("api.main.is_watchmode_configured", return_value=True):
        r = client.get("/api/watch/where-to-watch", params={"mediaType": "movie", "country": "US"})
    assert r.status_code == 400
    data = r.json()
    assert data.get("error") == "missing_params"


def test_where_to_watch_invalid_media_type_returns_400(client):
    """When mediaType is not movie or tv, returns 400."""
    with patch("api.main.is_watchmode_configured", return_value=True):
        r = client.get("/api/watch/where-to-watch", params={"tmdbId": "603", "mediaType": "other", "country": "US"})
    assert r.status_code == 400
    data = r.json()
    assert data.get("error") == "invalid_media_type"


def test_where_to_watch_empty_groups_returns_200(client):
    """When Watchmode returns no sources, returns 200 with title, region, empty offers."""
    mock_payload = {"movie": {}, "region": "US", "groups": []}
    mock_client = AsyncMock()
    mock_client.get_availability = AsyncMock(return_value=(None, mock_payload))
    with patch("api.main.is_watchmode_configured", return_value=True):
        with patch("integrations.watchmode.get_watchmode_client", return_value=mock_client):
            r = client.get("/api/watch/where-to-watch", params={"tmdbId": "603", "mediaType": "movie", "country": "US"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("offers") == []
    assert data.get("region") == "US"
    assert "title" in data
    assert data["title"].get("id") == "603"
