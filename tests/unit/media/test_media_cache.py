"""Unit tests for media cache (enrich and TMDB poster TTL cache)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cinemind.media.media_cache import MediaCache, TTLCache, get_default_media_cache, set_default_media_cache


def test_enrich_cache_hit():
    cache = MediaCache()
    cache.set_enrich("inception", {"media_strip": {"movie_title": "Inception"}})
    out = cache.get_enrich("inception")
    assert out is not None
    assert out.get("media_strip", {}).get("movie_title") == "Inception"


def test_enrich_cache_miss():
    cache = MediaCache()
    assert cache.get_enrich("nonexistent") is None


def test_tmdb_poster_cache_hit():
    cache = MediaCache()
    cache.set_tmdb_poster("Inception", 2010, "https://image.tmdb.org/t/p/w500/abc.jpg")
    url, hit = cache.get_tmdb_poster("Inception", 2010)
    assert hit is True
    assert url == "https://image.tmdb.org/t/p/w500/abc.jpg"


def test_tmdb_poster_cache_no_poster():
    cache = MediaCache()
    cache.set_tmdb_poster("No Poster", None, None)
    url, hit = cache.get_tmdb_poster("No Poster", None)
    assert hit is True
    assert url is None


def test_tmdb_poster_cache_miss():
    cache = MediaCache()
    url, hit = cache.get_tmdb_poster("Unknown", 2020)
    assert hit is False
    assert url is None


def test_ttl_cache_eviction():
    cache = TTLCache(max_entries=2)
    cache.set("a", 1, 3600)
    cache.set("b", 2, 3600)
    cache.get("a")
    cache.set("c", 3, 3600)
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_get_default_media_cache():
    set_default_media_cache(None)
    c = get_default_media_cache()
    assert c is not None
    assert isinstance(c, MediaCache)
