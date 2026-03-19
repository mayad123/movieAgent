from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


def _build_llm_genre_response(*, genres: list[str], items_per_genre: int = 5, start_year: int = 2000) -> str:
    """
    Deterministic LLM output matching `parse_movie_hub_genre_buckets()` expectations:
      Genre: <GenreName>
      1. Title (Year)
      2. Title (Year)
    """
    lines: list[str] = []
    idx = 1
    for g in genres:
        lines.append(f"Genre: {g}")
        for i in range(items_per_genre):
            year = start_year + idx % 10
            lines.append(f"{i + 1}. Movie {idx} ({year})")
            idx += 1
        lines.append("")
    return "\n".join(lines).strip()


def test_movie_hub_dedup_blanks_duplicate_posters(monkeypatch: pytest.MonkeyPatch):
    """
    If different LLM entries resolve to the same TMDB id, we should not show the
    exact same poster image repeatedly.

    Contract:
      - total movies still equals 20
      - for each repeated tmdbId, at most one item keeps `primary_image_url`
    """
    from src.api import main as api_main

    genres = ["Action", "Comedy", "Drama", "Horror", "Romance", "Sci-Fi"]
    llm_response = _build_llm_genre_response(genres=genres, items_per_genre=5, start_year=1990)

    async def fake_run_playground(user_query: str, request_type: str | None):
        # Marker handling extracts the marker and then strips it; we only need a response text.
        return {"response": llm_response}

    # Make sure we enrich all titles we request so dedupe behavior is visible in the output.
    monkeypatch.setenv("HUB_ENRICH_POSTERS_LIMIT", "20")

    monkeypatch.setattr(api_main, "run_playground", fake_run_playground)

    def fake_enrich_batch(titles: list[str], *, max_titles: int = 30, **_kwargs: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, t in enumerate(titles[:max_titles]):
            # Force duplicates: tmdb_id repeats every 2 titles.
            tmdb_id = (i // 2) + 100
            year = 2000 + (i % 10)
            out.append(
                {
                    "movie_title": (t or "").strip(),
                    "year": year,
                    "primary_image_url": f"https://example.com/poster/{tmdb_id}.jpg",
                    "page_url": f"/movie/{tmdb_id}",
                    "tmdb_id": tmdb_id,
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
    clusters = data.get("movieHubClusters") or []
    genre_clusters = [c for c in clusters if c.get("kind") == "genre"]
    assert len(genre_clusters) == 4

    all_movies: list[dict[str, Any]] = []
    for c in genre_clusters:
        all_movies.extend(c.get("movies") or [])

    assert len(all_movies) == 20

    # For each tmdbId, only the first occurrence should keep the image URL.
    by_tmdb: dict[int, list[dict[str, Any]]] = {}
    for m in all_movies:
        tmdb_id = m.get("tmdbId")
        assert tmdb_id is not None
        by_tmdb.setdefault(int(tmdb_id), []).append(m)

    for tmdb_id, items in by_tmdb.items():
        kept = [it for it in items if it.get("primary_image_url")]
        assert len(kept) <= 1, f"tmdbId={tmdb_id} kept {len(kept)} images"


def test_movie_hub_rebucketing_single_fallback_bucket_to_four_genres(monkeypatch: pytest.MonkeyPatch):
    """
    If `parse_movie_hub_genre_buckets(...)` falls back to a single bucket like
    {"genre":"Similar by genre","items":[...up to 20...]} we must still return
    4 genre clusters x 5 items each.

    Otherwise downstream truncation (`items = items[:5]`) collapses the UI to
    only ~5 movies.
    """
    from src.api import main as api_main

    async def fake_run_playground(user_query: str, request_type: str | None):
        # We don't rely on this text because we monkeypatch the parsing stage.
        return {"response": "irrelevant"}

    monkeypatch.setattr(api_main, "run_playground", fake_run_playground)

    # Force the parser to return a single fallback bucket with 20 titles.
    def fake_parse_movie_hub_genre_buckets(*_args: Any, **_kwargs: Any):
        items = [f"Movie {i} ({2000 + i % 10})" for i in range(20)]
        return [{"genre": "Similar by genre", "items": items}]

    monkeypatch.setattr(api_main, "parse_movie_hub_genre_buckets", fake_parse_movie_hub_genre_buckets)

    # Provide deterministic enrichments for all requested titles.
    def fake_enrich_batch(titles: list[str], *, max_titles: int = 30, **_kwargs: Any):
        out: list[dict[str, Any]] = []
        for i, t in enumerate(titles[:max_titles]):
            out.append(
                {
                    "movie_title": (t or "").strip(),
                    "year": 2000 + (i % 10),
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
            "user_query": f"{marker} Show similar movies grouped by genre.",
            "requestedAgentMode": "PLAYGROUND",
        },
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()
    clusters = data.get("movieHubClusters") or []
    genre_clusters = [c for c in clusters if c.get("kind") == "genre"]
    assert len(genre_clusters) == 4

    all_movies: list[dict[str, Any]] = []
    for c in genre_clusters:
        all_movies.extend(c.get("movies") or [])
    assert len(all_movies) == 20

