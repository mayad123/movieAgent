"""
Deterministic parsing for the Sub-context Movie Hub.

Goal:
- Parse LLM response text into genre buckets so the backend can return
  `movieHubClusters` with posters-ready movie cards.

Expected (LLM) format (strictly parsed when present):
- Genre: <GenreName>
- 1. Title (Year)
- 2. Title (Year)
- ...

Safety:
- Never raise. On any failure or low signal, fall back to extracting titles
  from the response and put them under a single default genre.
"""

from __future__ import annotations

import re
from typing import Any

from cinemind.extraction.response_movie_extractor import extract_titles_for_enrichment

_GENRE_LINE_RE = re.compile(
    r"^\s*(?:Genre|Genres|Category|Type)\s*[:\-]\s*(.+?)\s*$",
    flags=re.IGNORECASE,
)
_NUMBERED_ITEM_RE = re.compile(
    r"^\s*(?:[-*\u2022\u2013\u25E6]\s*)?(?P<num>\d+)\s*[\.\)]\s*(?P<body>.+?)\s*$",
)
# Bullet item fallback: "- Title (YYYY) ..." or "* Title (YYYY) ..."
_BULLET_ITEM_RE = re.compile(r"^\s*(?:[-*\u2022\u2013\u25E6])\s*(?P<body>.+?)\s*$")
# Title/year can appear at the end ("Title (2014)") or inside a line ("Title (2014) - ...")
_TITLE_YEAR_ANYWHERE_RE = re.compile(r"(?P<title>.+?)\s*\((?P<year>\d{4})\)", flags=re.IGNORECASE)
_TITLE_YEAR_TAIL_RE = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*$")


def _strip_leading_list_markers(s: str) -> str:
    """
    Remove list markers that sometimes leak into extracted titles, e.g.
      - "1. Interstellar (2014)" -> "Interstellar (2014)"
      - "• 1) Interstellar (2014)" -> "Interstellar (2014)"
    """
    t = (s or "").strip()
    if not t:
        return t
    # Remove optional bullet prefix first.
    t = re.sub(r"^\s*[-*\u2022\u2013\u25E6]\s*", "", t).strip()
    # Remove numeric prefix like "1." / "1)" / "(1)." / "(1)"
    t = re.sub(r"^\s*\(?\s*\d+\s*\)?\s*[\.\)]\s*", "", t).strip()
    return t


def _safe_normalize_genre(s: Any) -> str:
    g = (s or "").strip()
    # Avoid empty-ish labels; keep it simple.
    return g if len(g) >= 2 else ""


def _safe_normalize_item_str(s: Any) -> str:
    return (s or "").strip()


def _extract_title_year(item_text: str) -> tuple[str, int | None]:
    """
    Extract (title, year) from `Title (YYYY)` strings.
    If no year tail exists, return (normalized_title, None).
    """
    t = (item_text or "").strip()
    if not t:
        return "", None
    # Sometimes the extracted "body" still contains list numbering like:
    #   "1. Interstellar (2014)"
    # Strip it so we never render "1. " as part of the title.
    t = _strip_leading_list_markers(t)

    m = _TITLE_YEAR_TAIL_RE.match(t)
    if not m:
        m = _TITLE_YEAR_ANYWHERE_RE.search(t)
        if not m:
            return t, None

    title = (m.group("title") or "").strip()
    year_s = m.group("year")
    try:
        year = int(year_s) if year_s is not None else None
    except Exception:
        year = None
    return title, year


def _extract_title_years_anywhere(response_text: str, *, max_items: int) -> list[str]:
    """
    Loose extraction of `Title (YYYY)` anywhere in response text.
    Returns formatted strings so the rest of the enrichment pipeline can use them.
    """
    t = (response_text or "").strip()
    if not t:
        return []

    matches = _TITLE_YEAR_ANYWHERE_RE.finditer(t)
    out: list[str] = []
    seen: set[str] = set()
    for m in matches:
        title = _strip_leading_list_markers((m.group("title") or "").strip())
        year_s = m.group("year")
        if not title or not year_s:
            continue
        formatted = f"{title} ({year_s})"
        key = formatted.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(formatted)
        if len(out) >= max_items:
            break
    return out


def parse_movie_hub_genre_buckets(
    response_text: str,
    *,
    expected_genres: int = 6,
    expected_items_per_genre: int = 5,
    min_total_items: int = 30,
    min_genre_items_signal: int = 5,
) -> list[dict[str, Any]]:
    """
    Parse LLM response into:
      [{ "genre": <str>, "items": [<str>, ...] }, ...]

    - `items` are strings of either `Title (Year)` or plain `Title`.
    - The caller is responsible for enriching `items` into movie cards.
    """
    try:
        text = (response_text or "").strip()
        if not text:
            return []

        lines = text.splitlines()

        buckets: list[dict[str, Any]] = []
        current_bucket: dict[str, Any] | None = None
        seen_items_per_bucket: set[str] = set()

        def start_bucket(genre: str) -> None:
            nonlocal current_bucket, seen_items_per_bucket
            current_bucket = {"genre": genre, "items": []}
            seen_items_per_bucket = set()
            buckets.append(current_bucket)

        for raw_line in lines:
            line = (raw_line or "").strip()
            if not line:
                continue

            gm = _GENRE_LINE_RE.match(raw_line or "")
            if gm:
                genre = _safe_normalize_genre(gm.group(1))
                if not genre:
                    continue
                # If we encounter a new Genre line, start fresh.
                if len(buckets) >= expected_genres:
                    break
                start_bucket(genre)
                continue

            im = _NUMBERED_ITEM_RE.match(raw_line or "")
            if im and current_bucket is not None:
                # Titles are expected to be in `Title (Year)` form, but allow
                # slight deviations like bullet prefixes or trailing descriptions.
                item_text = _safe_normalize_item_str(im.group("body"))
                if not item_text:
                    continue

                # Dedupe items within each genre bucket.
                # If year exists, include it in the dedupe key; otherwise, title-only.
                title_part, year_val = _extract_title_year(item_text)
                key = (title_part or "").strip().lower()
                if year_val is not None:
                    key = key + "|" + str(year_val)
                if not key or key in seen_items_per_bucket:
                    continue
                seen_items_per_bucket.add(key)

                # Normalize item into `Title (Year)` if possible, else keep raw.
                title_part_norm, year_val_norm = _extract_title_year(item_text)
                if title_part_norm and year_val_norm is not None:
                    normalized = f"{title_part_norm} ({year_val_norm})"
                else:
                    normalized = item_text

                current_bucket["items"].append(normalized)
                if len(current_bucket["items"]) >= expected_items_per_genre:
                    # Stop collecting this bucket; allow next Genre: line to create a new one.
                    continue

            # Fallback: allow "- Title (Year) ..." without numbering.
            if current_bucket is not None and len(current_bucket["items"]) < expected_items_per_genre:
                bm = _BULLET_ITEM_RE.match(raw_line or "")
                if bm:
                    item_text = _safe_normalize_item_str(bm.group("body"))
                    if item_text:
                        title_part, year_val = _extract_title_year(item_text)
                        key = (title_part or "").strip().lower()
                        if year_val is not None:
                            key = key + "|" + str(year_val)
                        if key and key not in seen_items_per_bucket:
                            seen_items_per_bucket.add(key)
                            title_part_norm, year_val_norm = _extract_title_year(item_text)
                            if title_part_norm and year_val_norm is not None:
                                normalized = f"{title_part_norm} ({year_val_norm})"
                            else:
                                normalized = item_text
                            current_bucket["items"].append(normalized)
                            if len(current_bucket["items"]) >= expected_items_per_genre:
                                continue

        total_items = sum(len(b.get("items") or []) for b in buckets)
        # Only accept the structured parsing result if we have enough signal.
        if total_items >= min_total_items or total_items >= (expected_genres * min_genre_items_signal):
            # Enforce expected limits for stability.
            out: list[dict[str, Any]] = []
            for b in buckets[:expected_genres]:
                items = (b.get("items") or [])[:expected_items_per_genre]
                if not items:
                    continue
                genre = _safe_normalize_genre(b.get("genre"))
                if not genre:
                    continue
                out.append({"genre": genre, "items": items})
            return out

        # Fallback: extract titles, but restrict to list-like lines so we don't
        # accidentally pull movie titles from narrative prose.
        list_like_lines: list[str] = []
        for ln in text.splitlines():
            line = (ln or "").strip()
            if not line:
                continue
            has_year = bool(re.search(r"\(\s*\d{4}\s*\)", line))
            if not has_year:
                continue
            looks_listed = bool(
                re.match(r"^\s*(?:[-*\u2022\u2013\u25E6]\s+)", line)
                or re.match(r"^\s*\(?\s*\d+\s*\)?\s*[\.\)]\s+", line)
                or re.match(r"^\s*\d+\s*[\.\)]\s+", line)
            )
            if looks_listed:
                list_like_lines.append(line)

        fallback_source = "\n".join(list_like_lines) if list_like_lines else text
        title_years = _extract_title_years_anywhere(fallback_source, max_items=min_total_items)
        if title_years:
            titles = title_years[:min_total_items]
        else:
            # Last resort: use the shared extractor, but if we found list-like
            # lines, only run it on those lines.
            enrich_source = "\n".join(list_like_lines) if list_like_lines else text
            titles = extract_titles_for_enrichment(enrich_source)
            titles = [t for t in titles if (t or "").strip()][:min_total_items]
        if not titles:
            return []
        return [{"genre": "Similar by genre", "items": titles}]
    except Exception:
        # Never raise — safe empty so hub rendering can degrade gracefully.
        return []
