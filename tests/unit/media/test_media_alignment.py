"""Media alignment tests: posters/media should match resolved movies or be omitted."""

from __future__ import annotations

import types
from typing import Any

from cinemind.media.media_enrichment import (
    MediaEnrichmentResult,
    attach_media_to_result,
    build_similar_movie_clusters,
    enrich,
)


class DummyTMDBCandidate:
    def __init__(
        self, title: str, year: int | None = None, movie_id: int | None = None, poster_path: str | None = None
    ):
        self.title = title
        self.year = year
        self.id = movie_id
        self.poster_path = poster_path


class DummyTMDBResolveResult:
    def __init__(
        self,
        status: str,
        candidates: list[DummyTMDBCandidate] | None = None,
        movie_id: int | None = None,
        poster_path: str | None = None,
    ):
        self.status = status
        self.candidates = candidates or []
        self.movie_id = movie_id
        self.poster_path = poster_path


def test_enrich_returns_empty_when_tmdb_disabled(monkeypatch):
    """When TMDB is disabled, enrich() should return no media (no placeholder from query)."""

    def fake_is_tmdb_enabled() -> bool:
        return False

    monkeypatch.setattr(
        "cinemind.media.media_enrichment.get_default_media_cache",
        lambda: types.SimpleNamespace(get_enrich=lambda _k: None, set_enrich=lambda *_a, **_k: None),
        raising=False,
    )
    monkeypatch.setattr("cinemind.media.media_enrichment.is_tmdb_enabled", fake_is_tmdb_enabled, raising=False)

    result: MediaEnrichmentResult = enrich("Tell me more about Inception")
    assert result.media_strip == {} or not result.media_strip.get("movie_title")


def test_attach_media_uses_resolved_title_not_query(monkeypatch):
    """attach_media_to_result should align media_strip title with resolved movie, not raw query."""

    def fake_is_tmdb_enabled() -> bool:
        return True

    def fake_get_tmdb_access_token() -> str:
        return "token"

    def fake_resolve_movie(title: str, year: int | None = None, access_token: str | None = None) -> Any:
        # Simulate resolving to Inception (2010) regardless of query phrasing.
        candidate = DummyTMDBCandidate("Inception", 2010, movie_id=123, poster_path="/inception.jpg")
        return DummyTMDBResolveResult(status="ok", candidates=[candidate], movie_id=123, poster_path="/inception.jpg")

    # Patch config + resolver
    monkeypatch.setattr("cinemind.media.media_enrichment.is_tmdb_enabled", fake_is_tmdb_enabled, raising=False)
    monkeypatch.setattr(
        "cinemind.media.media_enrichment.get_tmdb_access_token", fake_get_tmdb_access_token, raising=False
    )
    # Production code reads enabled/token directly from `config` inside enrich().
    monkeypatch.setattr("config.is_tmdb_enabled", fake_is_tmdb_enabled, raising=False)
    # Production code paths also read the token from `config` inside TMDB strip building.
    monkeypatch.setattr("config.get_tmdb_access_token", fake_get_tmdb_access_token, raising=False)
    # `enrich()` imports resolve_movie from `integrations.tmdb.resolver` internally.
    monkeypatch.setattr("integrations.tmdb.resolver.resolve_movie", fake_resolve_movie, raising=False)

    # Patch image config builder to avoid network
    def fake_get_config(_token: str) -> dict[str, Any]:
        return {}

    def fake_build_image_url(path: str, _size: str, _cfg: dict[str, Any]) -> str:
        return f"https://image.tmdb.org{path}"

    monkeypatch.setattr("cinemind.media.media_enrichment.get_config", fake_get_config, raising=False)
    monkeypatch.setattr("cinemind.media.media_enrichment.build_image_url", fake_build_image_url, raising=False)

    result_dict: dict[str, Any] = {
        "query": "Tell me more about Inception",
        "response": "Inception is a 2010 science fiction film directed by Christopher Nolan.",
    }

    attach_media_to_result("Tell me more about Inception", result_dict)
    strip = result_dict.get("media_strip") or {}
    attachments = result_dict.get("attachments") or {}

    assert strip.get("movie_title") == "Inception"
    assert strip.get("year") == 2010
    assert strip.get("tmdb_id") == 123
    assert "primary_image_url" in strip

    sections = attachments.get("sections") or []
    assert sections, "Expected at least one attachment section"
    primary = sections[0]
    assert primary.get("type") == "primary_movie"
    first_item = (primary.get("items") or [])[0]
    assert first_item.get("title") == "Inception"


def test_build_similar_movie_clusters_uses_tmdb_results(monkeypatch):
    """build_similar_movie_clusters should surface multiple TMDB similar titles."""

    # Enable TMDB + provide fake token so the helper does not early-exit.
    monkeypatch.setattr(
        "cinemind.media.media_enrichment.is_tmdb_enabled",
        lambda: True,
        raising=False,
    )
    monkeypatch.setattr(
        "cinemind.media.media_enrichment.get_tmdb_access_token",
        lambda: "token",
        raising=False,
    )

    # Stub resolver at the source module used by media_enrichment.
    from integrations.tmdb import resolver as tmdb_resolver

    class DummyResolveResult:
        def __init__(self, movie_id: int):
            self.status = "resolved"
            self.movie_id = movie_id

    monkeypatch.setattr(
        tmdb_resolver,
        "resolve_movie",
        lambda title, year=None, access_token=None: DummyResolveResult(278),
        raising=False,
    )

    # Stub image URL builder in the TMDB image_config module to avoid config/network.
    from integrations.tmdb import image_config as tmdb_image_config

    monkeypatch.setattr(
        tmdb_image_config,
        "build_image_url",
        lambda path, size_key, config=None: f"https://images.example.com/{size_key}{path}",
        raising=False,
    )

    similar_payload = {
        "results": [
            {
                "id": 1,
                "title": "Similar One",
                "poster_path": "/one.jpg",
                "release_date": "2010-01-01",
            },
            {
                "id": 2,
                "title": "Similar Two",
                "poster_path": "/two.jpg",
                "release_date": "2011-02-02",
            },
            {
                "id": 3,
                "title": "Similar Three",
                "poster_path": "/three.jpg",
                "release_date": "2012-03-03",
            },
        ]
    }

    def fake_tmdb_json(url: str, token: str, **_kwargs: Any):
        if "similar" in url:
            return similar_payload
        return None

    monkeypatch.setattr("integrations.tmdb.http_client.tmdb_request_json", fake_tmdb_json, raising=False)

    clusters = build_similar_movie_clusters(
        title="Inception",
        year=2010,
        tmdb_id=None,
        media_type="movie",
    )["clusters"]

    # We always expect three clusters: genre/tone/cast
    assert len(clusters) == 3
    genre_cluster = next(c for c in clusters if c["kind"] == "genre")
    movies = genre_cluster["movies"]
    assert len(movies) == 3
    titles = {m["title"] for m in movies}
    assert titles == {"Similar One", "Similar Two", "Similar Three"}


def test_build_similar_movie_clusters_returns_empty_movies_when_token_missing(monkeypatch):
    """TMDB similar-cluster builder should keep stable clusters but with empty movie lists."""

    # build_similar_movie_clusters imports `is_tmdb_enabled` and `get_tmdb_access_token`
    # from the top-level `config` module inside the function, so we must patch those.
    monkeypatch.setattr("config.is_tmdb_enabled", lambda: True, raising=False)
    monkeypatch.setattr("config.get_tmdb_access_token", lambda: "", raising=False)

    clusters = build_similar_movie_clusters(
        title="Inception",
        year=2010,
        tmdb_id=278,
        media_type="movie",
        max_results=30,
    )["clusters"]

    assert [c["kind"] for c in clusters] == ["genre", "tone", "cast"]
    assert all(isinstance(c.get("movies"), list) for c in clusters)
    assert all(c["movies"] == [] for c in clusters)
    assert clusters[0]["label"].startswith("Similar by genre to Inception")


def test_similar_movies_endpoint_shapes_clusters(monkeypatch):
    """API layer should expose clusters from build_similar_movie_clusters unchanged."""

    # Provide deterministic clusters from the helper
    fake_clusters = [
        {
            "kind": "genre",
            "label": "Similar by genre to Inception",
            "movies": [
                {
                    "title": "Foo",
                    "year": 2010,
                    "primary_image_url": None,
                    "page_url": None,
                    "tmdbId": 1,
                    "mediaType": "movie",
                },
                {
                    "title": "Bar",
                    "year": 2011,
                    "primary_image_url": None,
                    "page_url": None,
                    "tmdbId": 2,
                    "mediaType": "movie",
                },
            ],
        }
    ]

    monkeypatch.setattr(
        "src.api.main.build_similar_movie_clusters",
        lambda title, year=None, tmdb_id=None, media_type=None, max_results=None, **_kwargs: {
            "clusters": fake_clusters
        },
        raising=False,
    )

    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)
    resp = client.get("/api/movies/278/similar?title=Inception&year=2010&mediaType=movie")
    assert resp.status_code == 200
    data = resp.json()
    assert "clusters" in data
    assert len(data["clusters"]) == 1
    cluster = data["clusters"][0]
    assert cluster["kind"] == "genre"
    assert len(cluster["movies"]) == 2


def test_similar_movies_non_numeric_path_passes_title_for_resolve(monkeypatch):
    """Hub fallback may use a non-numeric path segment when TMDB id is unknown; title/year must reach build_similar_movie_clusters."""
    captured: dict = {}

    def fake_build(title, year=None, tmdb_id=None, media_type=None, max_results=None, **_kwargs):
        captured["title"] = title
        captured["year"] = year
        captured["tmdb_id"] = tmdb_id
        captured["media_type"] = media_type
        return {
            "clusters": [
                {
                    "kind": "genre",
                    "label": "Similar by genre to Test",
                    "movies": [],
                }
            ]
        }

    monkeypatch.setattr(
        "src.api.main.build_similar_movie_clusters",
        fake_build,
        raising=False,
    )

    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)
    resp = client.get("/api/movies/_/similar?title=Interstellar&year=2014&mediaType=movie")
    assert resp.status_code == 200
    assert captured.get("title") == "Interstellar"
    assert captured.get("year") == 2014
    assert captured.get("tmdb_id") is None
    assert captured.get("media_type") == "movie"
