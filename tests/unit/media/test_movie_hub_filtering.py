from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient


def _clusters_with_movies() -> list[dict[str, Any]]:
    return [
        {
            "kind": "genre",
            "label": "Similar by genre to Anchor",
            "movies": [
                {
                    "title": "Movie A",
                    "year": 2000,
                    "primary_image_url": None,
                    "page_url": None,
                    "tmdbId": 1,
                    "mediaType": "movie",
                },
                {
                    "title": "Movie B",
                    "year": 2001,
                    "primary_image_url": None,
                    "page_url": None,
                    "tmdbId": 2,
                    "mediaType": "movie",
                },
                {
                    "title": "Movie C",
                    "year": 2002,
                    "primary_image_url": None,
                    "page_url": None,
                    "tmdbId": 3,
                    "mediaType": "movie",
                },
            ],
        },
        {"kind": "tone", "label": "Similar by tone or theme to Anchor", "movies": []},
        {"kind": "cast", "label": "Similar by cast or crew to Anchor", "movies": []},
    ]


def test_filter_by_actor_star_constraint(monkeypatch: pytest.MonkeyPatch):
    """Star questions should deterministically narrow hub candidates."""
    from src.cinemind.media import movie_hub_filtering as m

    monkeypatch.setattr(m, "is_tmdb_enabled", lambda: True)
    monkeypatch.setattr(m, "get_tmdb_access_token", lambda: "token")

    def fake_cast(tmdb_id: int, _token: str, *, max_names: int = 80) -> list[str]:
        return ["Keanu Reeves"] if tmdb_id in (1, 3) else ["Someone Else"]

    monkeypatch.setattr(m, "fetch_movie_cast_names", fake_cast)
    monkeypatch.setattr(m, "fetch_movie_genre_names", lambda _tmdb_id, _token: [])
    monkeypatch.setattr(m, "fetch_movie_keyword_names", lambda _tmdb_id, _token: [])

    clusters = _clusters_with_movies()
    out = m.filter_movie_hub_clusters_by_question(clusters, "Which movies star Keanu Reeves?")

    genre_cluster = next(c for c in out if c["kind"] == "genre")
    assert [mv["tmdbId"] for mv in genre_cluster["movies"]] == [1, 3]


def test_filter_by_not_scary_constraint(monkeypatch: pytest.MonkeyPatch):
    """Not-scary questions should exclude horror candidates."""
    from src.cinemind.media import movie_hub_filtering as m

    monkeypatch.setattr(m, "is_tmdb_enabled", lambda: True)
    monkeypatch.setattr(m, "get_tmdb_access_token", lambda: "token")
    monkeypatch.setattr(m, "fetch_movie_cast_names", lambda _tmdb_id, _token: [])

    def fake_genres(tmdb_id: int, _token: str) -> list[str]:
        if tmdb_id == 2:
            return ["Horror"]
        return ["Drama"]

    def fake_keywords(tmdb_id: int, _token: str) -> list[str]:
        if tmdb_id == 3:
            return ["scary"]
        return []

    monkeypatch.setattr(m, "fetch_movie_genre_names", fake_genres)
    monkeypatch.setattr(m, "fetch_movie_keyword_names", fake_keywords)

    clusters = _clusters_with_movies()
    out = m.filter_movie_hub_clusters_by_question(clusters, "Are there movies that aren't scary?")

    genre_cluster = next(c for c in out if c["kind"] == "genre")
    assert [mv["tmdbId"] for mv in genre_cluster["movies"]] == [1]


def test_filter_no_recognized_constraints_returns_unchanged(monkeypatch: pytest.MonkeyPatch):
    """If no supported constraints exist, return clusters unchanged."""
    from src.cinemind.media import movie_hub_filtering as m

    monkeypatch.setattr(m, "is_tmdb_enabled", lambda: True)
    monkeypatch.setattr(m, "get_tmdb_access_token", lambda: "token")

    clusters = _clusters_with_movies()
    out = m.filter_movie_hub_clusters_by_question(clusters, "Tell me about the plot of the movie.")
    assert out == clusters


def test_query_returns_movieHubClusters_when_marker_present(monkeypatch: pytest.MonkeyPatch):
    """Integration: /query should return `movieHubClusters` when context marker is included."""
    # Import after monkeypatch to avoid side effects ordering surprises.
    from src.api import main as api_main

    async def fake_run_playground(user_query: str, request_type: str | None):
        # Provide deterministic, genre-grouped output compatible with parse_movie_hub_genre_buckets().
        genres = ["Action", "Comedy", "Drama", "Horror", "Romance", "Sci-Fi"]
        lines: list[str] = []
        idx = 1
        for g in genres:
            lines.append(f"Genre: {g}")
            for i in range(5):
                lines.append(f"{i + 1}. Movie {idx} ({2000 + idx % 10})")
                idx += 1
            lines.append("")
        return {"response": "\n".join(lines).strip()}

    monkeypatch.setattr(api_main, "run_playground", fake_run_playground)

    def fake_enrich_batch(titles: list[str], *, max_titles: int = 30, **_kwargs: Any) -> list[dict[str, Any]]:
        # Return stable, posters-ready-like cards without any TMDB calls.
        out: list[dict[str, Any]] = []
        for i, t in enumerate(titles[:max_titles]):
            out.append(
                {
                    "movie_title": (t or "").strip(),
                    "year": 2000 + i % 10,
                    "primary_image_url": None,
                    "page_url": f"/movie/{i}",
                    "tmdb_id": i + 1,
                }
            )
        return out

    monkeypatch.setattr(api_main, "enrich_batch", fake_enrich_batch)

    client = TestClient(api_main.app)
    marker = '[[CINEMIND_HUB_CONTEXT]]{"title":"Anchor","year":1999,"tmdbId":10}[[/CINEMIND_HUB_CONTEXT]]'
    resp = client.post(
        "/query",
        json={
            "user_query": f"{marker} Which movies star Keanu Reeves?",
            "requestedAgentMode": "PLAYGROUND",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "movieHubClusters" in data
    genre_clusters = [c for c in data["movieHubClusters"] if c["kind"] == "genre"]
    assert len(genre_clusters) == 4

    total_movies = sum(len(c.get("movies") or []) for c in genre_clusters)
    assert total_movies == 20

    movies: list[dict[str, Any]] = []
    for c in genre_clusters:
        movies.extend(c.get("movies") or [])

    required_keys = {"title", "year", "primary_image_url", "page_url", "tmdbId", "mediaType"}
    assert movies, "expected at least one enriched movie"
    assert all(required_keys.issubset(m.keys()) for m in movies)


def test_query_returns_movieHubClusters_when_only_partial_genres_parsed(monkeypatch: pytest.MonkeyPatch):
    """Backend should still return movieHubClusters when it extracts >= 20 genre movies."""
    from src.api import main as api_main

    async def fake_run_playground(user_query: str, request_type: str | None):
        # 4 genres x 5 titles = 20 total.
        genres = ["Action", "Comedy", "Drama", "Horror"]
        lines: list[str] = []
        idx = 1
        for g in genres:
            lines.append(f"Genre: {g}")
            for i in range(5):
                lines.append(f"{i + 1}. Movie {idx} ({2000 + idx % 10})")
                idx += 1
            lines.append("")
        return {"response": "\n".join(lines).strip()}

    monkeypatch.setattr(api_main, "run_playground", fake_run_playground)

    def fake_enrich_batch(titles: list[str], *, max_titles: int = 30, **_kwargs: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, t in enumerate(titles[:max_titles]):
            out.append(
                {
                    "movie_title": (t or "").strip(),
                    "year": 2000 + i % 10,
                    "primary_image_url": "https://example.com/poster/" + str(i) + ".jpg",
                    "page_url": "/movie/" + str(i),
                    "tmdb_id": i + 1,
                }
            )
        return out

    monkeypatch.setattr(api_main, "enrich_batch", fake_enrich_batch)

    client = TestClient(api_main.app)
    marker = '[[CINEMIND_HUB_CONTEXT]]{"title":"Anchor","year":1999,"tmdbId":10}[[/CINEMIND_HUB_CONTEXT]]'
    resp = client.post(
        "/query",
        json={
            "user_query": f"{marker} Show similar movies grouped by genre.",
            "requestedAgentMode": "PLAYGROUND",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "movieHubClusters" in data

    genre_clusters = [c for c in data["movieHubClusters"] if c["kind"] == "genre"]
    assert len(genre_clusters) == 4
    total_movies = sum(len(c.get("movies") or []) for c in genre_clusters)
    assert total_movies == 20

    movies: list[dict[str, Any]] = []
    for c in genre_clusters:
        movies.extend(c.get("movies") or [])

    required_keys = {"title", "year", "primary_image_url", "page_url", "tmdbId", "mediaType"}
    assert movies
    assert all(required_keys.issubset(m.keys()) for m in movies)


def test_candidate_titles_injected_into_prompt(monkeypatch: pytest.MonkeyPatch):
    """When `candidateTitles` is in the hub marker, backend injects them into the agent prompt."""
    from src.api import main as api_main

    captured = {"user_query": None}

    async def fake_run_playground(user_query: str, request_type: str | None):
        captured["user_query"] = user_query
        # Provide deterministic genre-grouped output compatible with parse_movie_hub_genre_buckets().
        genres = ["Action", "Comedy", "Drama", "Horror"]
        lines: list[str] = []
        idx = 1
        for g in genres:
            lines.append(f"Genre: {g}")
            for _ in range(5):
                lines.append(f"{idx}. Movie {idx} (2000)")
                idx += 1
            lines.append("")
        return {"response": "\n".join(lines).strip()}

    monkeypatch.setattr(api_main, "run_playground", fake_run_playground)

    def fake_enrich_batch(titles: list[str], *, max_titles: int = 30, **_kwargs: Any) -> list[dict[str, Any]]:
        # Posters-ready-like cards; no real TMDB calls.
        out: list[dict[str, Any]] = []
        for i, _t in enumerate(titles[:max_titles]):
            out.append(
                {
                    "movie_title": "Movie",
                    "year": 2000 + i % 10,
                    "primary_image_url": None,
                    "page_url": f"/movie/{i}",
                    "tmdb_id": i + 1,
                }
            )
        return out

    monkeypatch.setattr(api_main, "enrich_batch", fake_enrich_batch)

    client = TestClient(api_main.app)

    candidate_titles = [
        "Scary Movie (2000)",
        "Horror Nights (2001)",
        "Fear Street (2002)",
    ]
    marker_payload = {
        "title": "Anchor",
        "year": 1999,
        "tmdbId": 10,
        "candidateTitles": candidate_titles,
    }
    marker = (
        "[[CINEMIND_HUB_CONTEXT]]"
        + json.dumps(marker_payload)
        + "[[/CINEMIND_HUB_CONTEXT]]"
    )

    resp = client.post(
        "/query",
        json={
            "user_query": f"{marker} Which movies are scary?",
            "requestedAgentMode": "PLAYGROUND",
        },
    )
    assert resp.status_code == 200, resp.text
    assert "movieHubClusters" in resp.json()

    q = captured["user_query"] or ""
    # Candidate title injection.
    for t in candidate_titles:
        assert t in q
    # Output format contract for the UI parsing contract.
    assert "Return exactly 4 genre blocks." in q
    assert "Genre: <GenreName>" in q
    assert "1. Title (Year)" in q

