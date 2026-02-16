"""Unit tests for Wikipedia cache (TTL, key normalization, enrich cache)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.wikipedia_cache import WikipediaCache, TTLCache


def test_search_cache_hit():
    cache = WikipediaCache()
    cache.set_search("inception", [{"title": "Inception (film)"}])
    assert cache.get_search("inception") == [{"title": "Inception (film)"}]
    assert cache.get_search("  INCEPTION  ") == [{"title": "Inception (film)"}]


def test_search_cache_miss():
    cache = WikipediaCache()
    assert cache.get_search("nonexistent") is None


def test_categories_cache():
    cache = WikipediaCache()
    cache.set_categories(["A", "B"], {"A": [], "B": []})
    assert cache.get_categories(["B", "A"]) == {"A": [], "B": []}


def test_pageimage_cache_hit():
    cache = WikipediaCache()
    cache.set_pageimage("Inception_(film)", "https://example.org/img.jpg")
    url, hit = cache.get_pageimage("Inception_(film)")
    assert hit is True
    assert url == "https://example.org/img.jpg"


def test_pageimage_cache_no_image():
    cache = WikipediaCache()
    cache.set_pageimage("No_Image_Page", None)
    url, hit = cache.get_pageimage("No_Image_Page")
    assert hit is True
    assert url is None


def test_pageimage_cache_miss():
    cache = WikipediaCache()
    url, hit = cache.get_pageimage("Unknown_Page")
    assert hit is False
    assert url is None


def test_ttl_cache_eviction():
    cache = TTLCache(max_entries=2)
    cache.set("a", 1, 3600)
    cache.set("b", 2, 3600)
    cache.get("a")  # a becomes most recently used
    cache.set("c", 3, 3600)  # evict b (least recently used)
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3
