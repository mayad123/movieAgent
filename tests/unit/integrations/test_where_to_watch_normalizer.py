"""
Unit tests for Where to Watch response normalizer.
Run with: PYTHONPATH=src pytest tests/unit/test_where_to_watch_normalizer.py -v
"""
import sys
from pathlib import Path

import pytest

_src = Path(__file__).resolve().parent.parent.parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from integrations.watchmode.normalizer import normalize_where_to_watch_response


def test_empty_groups_returns_title_region_offers():
    out = normalize_where_to_watch_response(
        {"region": "US", "groups": []},
        title_id="603",
        title_name="The Matrix",
        year=1999,
        media_type="movie",
    )
    assert out["title"]["id"] == "603"
    assert out["title"]["name"] == "The Matrix"
    assert out["title"]["year"] == 1999
    assert out["title"]["mediaType"] == "movie"
    assert out["region"] == "US"
    assert out["offers"] == []
    assert "lastUpdated" in out


def test_groups_normalized_to_flat_offers_sorted_by_access_type_then_provider():
    data = {
        "region": "US",
        "groups": [
            {"accessType": "buy", "label": "Buy", "offers": [{"providerName": "Apple TV", "providerId": "2", "webUrl": "https://apple.com/1"}]},
            {"accessType": "subscription", "label": "Subscription", "offers": [
                {"providerName": "Netflix", "providerId": "1", "webUrl": "https://netflix.com/1"},
                {"providerName": "Amazon", "providerId": "3", "webUrl": "https://amazon.com/1"},
            ]},
        ],
    }
    out = normalize_where_to_watch_response(data, title_id="603", title_name="Matrix", media_type="movie")
    assert out["title"]["name"] == "Matrix"
    assert out["region"] == "US"
    # Order: subscription (Amazon, Netflix), then buy (Apple TV)
    assert len(out["offers"]) == 3
    assert out["offers"][0]["accessType"] == "subscription"
    assert out["offers"][0]["provider"]["name"] == "Amazon"
    assert out["offers"][1]["accessType"] == "subscription"
    assert out["offers"][1]["provider"]["name"] == "Netflix"
    assert out["offers"][2]["accessType"] == "buy"
    assert out["offers"][2]["provider"]["name"] == "Apple TV"
    for o in out["offers"]:
        assert "provider" in o and "id" in o["provider"] and "name" in o["provider"]
        assert o["accessType"] in ("subscription", "free", "rent", "buy", "tve", "unknown")
        assert "lastUpdated" in o


def test_dedupe_same_provider_url_access_type():
    data = {
        "region": "GB",
        "groups": [
            {"accessType": "subscription", "label": "Sub", "offers": [
                {"providerName": "Netflix", "providerId": "1", "webUrl": "https://netflix.com/same"},
                {"providerName": "Netflix", "providerId": "1", "webUrl": "https://netflix.com/same"},
            ]},
        ],
    }
    out = normalize_where_to_watch_response(data, title_id="1", title_name="X", media_type="tv")
    assert len(out["offers"]) == 1
    assert out["offers"][0]["provider"]["name"] == "Netflix"


def test_prefer_deeplink_keep_web_fallback():
    data = {
        "region": "US",
        "groups": [
            {"accessType": "subscription", "label": "Sub", "offers": [
                {"providerName": "Netflix", "providerId": "1", "webUrl": "https://netflix.com/title/1", "deeplink": "netflix://title/1"},
            ]},
        ],
    }
    out = normalize_where_to_watch_response(data, title_id="1", title_name="X", media_type="movie")
    assert len(out["offers"]) == 1
    o = out["offers"][0]
    assert o["webUrl"] == "https://netflix.com/title/1"
    assert o["iosUrl"] == "netflix://title/1"
    assert o["androidUrl"] == "netflix://title/1"


def test_rental_purchase_mapped_to_rent_buy():
    data = {
        "region": "US",
        "groups": [
            {"accessType": "rental", "label": "Rent", "offers": [{"providerName": "Vudu", "providerId": "5", "webUrl": "https://vudu.com/1"}]},
            {"accessType": "purchase", "label": "Buy", "offers": [{"providerName": "Google", "providerId": "6", "webUrl": "https://play.google.com/1"}]},
        ],
    }
    out = normalize_where_to_watch_response(data, title_id="1", title_name="Y", media_type="movie")
    assert out["offers"][0]["accessType"] == "rent"
    assert out["offers"][1]["accessType"] == "buy"


def test_price_and_quality_passthrough():
    data = {
        "region": "US",
        "groups": [
            {"accessType": "subscription", "label": "Sub", "offers": [
                {"providerName": "Netflix", "providerId": "1", "webUrl": "https://n.com", "price": {"amount": 15.99, "currency": "USD"}, "quality": "4K"},
            ]},
        ],
    }
    out = normalize_where_to_watch_response(data, title_id="1", title_name="Z", media_type="movie")
    assert out["offers"][0]["price"] == {"amount": 15.99, "currency": "USD"}
    assert out["offers"][0]["quality"] == "4K"


def test_no_groups_uses_movie_from_data():
    out = normalize_where_to_watch_response(
        {"region": "DE", "movie": {"title": "Inception", "year": 2010}, "groups": []},
        title_id="27205",
        media_type="movie",
    )
    assert out["title"]["id"] == "27205"
    assert out["region"] == "DE"
    # title name/year can come from data.movie when not passed
    out2 = normalize_where_to_watch_response(
        {"region": "DE", "movie": {"title": "Inception", "year": 2010}, "groups": []},
        media_type="movie",
    )
    assert out2["title"]["name"] == "Inception"
    assert out2["title"]["year"] == 2010
