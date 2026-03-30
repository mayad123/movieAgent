from __future__ import annotations

import pytest


def _build_genre_response(*, genres: list[str], items_per_genre: int = 5, start_year: int = 2000) -> str:
    lines: list[str] = []
    year = start_year
    idx = 1
    for g in genres:
        lines.append(f"Genre: {g}")
        for i in range(items_per_genre):
            lines.append(f"{i + 1}. Movie {idx} ({year + (idx % 10)})")
            idx += 1
        lines.append("")
    return "\n".join(lines).strip()


def test_parse_movie_hub_genre_buckets_parses_genre_and_numbered_items():
    from src.cinemind.media.movie_hub_genre_parsing import parse_movie_hub_genre_buckets

    genres = ["Action", "Comedy", "Drama", "Horror", "Romance", "Sci-Fi"]
    response = _build_genre_response(genres=genres, items_per_genre=5)

    buckets = parse_movie_hub_genre_buckets(response)
    assert isinstance(buckets, list)
    assert len(buckets) == 6
    assert all(b.get("genre") in genres for b in buckets)
    assert all(isinstance(b.get("items"), list) for b in buckets)
    assert sum(len(b["items"]) for b in buckets) == 30

    # Spot-check a couple of item strings include years.
    first_bucket_items = buckets[0]["items"]
    assert len(first_bucket_items) == 5
    assert "(" in first_bucket_items[0] and ")" in first_bucket_items[0]


def test_parse_movie_hub_genre_buckets_falls_back_when_structured_signal_too_low(monkeypatch: pytest.MonkeyPatch):

    from src.cinemind.media import movie_hub_genre_parsing as p

    # Force extract_titles_for_enrichment to produce deterministic fallback titles.
    monkeypatch.setattr(p, "extract_titles_for_enrichment", lambda _txt: ["Fallback A", "Fallback B"])

    response = "This is not in the expected format. No genre lines here."
    buckets = p.parse_movie_hub_genre_buckets(response, min_total_items=30)
    assert buckets == [{"genre": "Similar by genre", "items": ["Fallback A", "Fallback B"]}]


def test_parse_movie_hub_genre_buckets_accepts_dash_genre_and_quoted_items():
    from src.cinemind.media.movie_hub_genre_parsing import parse_movie_hub_genre_buckets

    genres = ["Action", "Comedy", "Drama", "Horror", "Romance", "Sci-Fi"]
    lines: list[str] = []
    idx = 1
    start_year = 1990
    for g in genres:
        lines.append(f"Genre - {g}")
        for i in range(5):
            year = start_year + idx % 30
            # Intentionally vary formatting: quotes + trailing description.
            lines.append(f'{i + 1}) "Movie {idx}" ({year}) - some extra text')
            idx += 1
        lines.append("")

    response = "\n".join(lines).strip()
    buckets = parse_movie_hub_genre_buckets(response)
    assert isinstance(buckets, list)
    assert len(buckets) == 6
    assert sum(len(b.get("items") or []) for b in buckets) == 30
    assert all("(" in (b["items"][0] if b.get("items") else "") for b in buckets)


def test_parse_movie_hub_genre_buckets_fallback_extracts_title_year_anywhere():
    from src.cinemind.media.movie_hub_genre_parsing import parse_movie_hub_genre_buckets

    # No Genre lines at all — fallback should still find Title (Year) occurrences.
    pairs: list[str] = []
    for i in range(30):
        year = 2000 + (i % 20)
        pairs.append(f"Movie {i} ({year})")
    response = "Here are picks: " + ", ".join(pairs)

    buckets = parse_movie_hub_genre_buckets(response)
    assert buckets and buckets[0]["genre"] == "Similar by genre"
    assert len(buckets[0]["items"]) >= 30


def test_parse_movie_hub_genre_buckets_accepts_bullet_items_without_numbering():
    from src.cinemind.media.movie_hub_genre_parsing import parse_movie_hub_genre_buckets

    genres = ["Action", "Comedy", "Drama", "Horror", "Romance", "Sci-Fi"]
    lines: list[str] = []
    idx = 1
    start_year = 1995
    for g in genres:
        lines.append(f"Genre: {g}")
        for _ in range(5):
            year = start_year + (idx % 20)
            lines.append(f"- Movie {idx} ({year}) - extra text")
            idx += 1
        lines.append("")

    response = "\n".join(lines).strip()
    buckets = parse_movie_hub_genre_buckets(response)
    assert len(buckets) == 6
    assert sum(len(b.get("items") or []) for b in buckets) == 30


def test_parse_movie_hub_genre_buckets_strips_leading_numbering_from_fallback_titles():
    """Fallback extraction should not treat list numbering as part of the title."""
    from src.cinemind.media.movie_hub_genre_parsing import parse_movie_hub_genre_buckets

    response = "\n".join(
        [
            "1. Movie A (2010)",
            "2. Movie B (2011)",
        ]
    )
    buckets = parse_movie_hub_genre_buckets(response, min_total_items=2)
    assert buckets and buckets[0]["genre"] == "Similar by genre"
    items = buckets[0]["items"]
    assert len(items) == 2
    assert all(not it.strip().startswith(("1.", "2.", "• 1.", "• 2.")) for it in items)
    assert items[0].startswith("Movie A") and items[1].startswith("Movie B")


def test_parse_movie_hub_genre_buckets_accepts_dot_numbering_with_bullet_prefix():
    """Structured parsing should accept bullet-style prefixes like '• 1.'."""
    from src.cinemind.media.movie_hub_genre_parsing import parse_movie_hub_genre_buckets

    response = "\n".join(
        [
            "Genre: Action",
            "• 1. Movie A (2010)",
            "• 2. Movie B (2011)",
            "",
        ]
    ).strip()
    buckets = parse_movie_hub_genre_buckets(response, expected_genres=1, expected_items_per_genre=2, min_total_items=2)
    assert buckets and buckets[0]["genre"] == "Action"
    assert buckets[0]["items"] == ["Movie A (2010)", "Movie B (2011)"]
