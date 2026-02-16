"""
Deterministic Response Movie Extractor (no AI).

Parses agent response text to extract:
- movies[]: ordered distinct movies (title, optional year, optional confidence)
- structure: list/paragraph indicators (bullets, numbered, bold, Title (Year), dash-blurb)
- signals: deepDiveIndicators[], sceneIndicators[] for intent/classifier use.

All rules are deterministic (regex and string patterns). Use parse_response(text)
and pass result.to_dict() or the dataclasses to the intent classifier or
media enrichment pipeline.

List patterns: bullet lines (-, *, •, –), numbered (1. 2. or 1) 2)), Markdown
bold (**Title**), and "Title (Year) – blurb" or "Title (Year):" or standalone
"Title (Year)".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "normalize_title",
    "parse_response",
    "ResponseParseResult",
    "ExtractedMovie",
    "ParseStructure",
    "ParseSignals",
]


# --- Title normalization (deterministic) ---

def normalize_title(s: str) -> str:
    """
    Deterministic normalization for movie title strings.
    - Collapse whitespace to single space, strip
    - Normalize common punctuation (curly quotes → straight)
    - Strip outer quotes (single/double) if they wrap the whole string
    - Remove zero-width and other invisible chars
    """
    if not s or not isinstance(s, str):
        return ""
    t = s.strip()
    # Curly/smart quotes and dashes → ASCII
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    t = t.strip()
    # Strip outer quotes only if they wrap the whole string
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ('"', "'"):
        t = t[1:-1].strip()
    # Remove zero-width and other invisible
    t = re.sub(r"[\u200b-\u200d\ufeff]", "", t)
    return t.strip()


# --- Year extraction ---

_YEAR_PATTERN = re.compile(r"\((\d{4})\)")
_YEAR_AT_END = re.compile(r"\((\d{4})\)\s*[:–\-]\s*")  # (1999): or (1999) – or (1999) -


def _extract_year_from_tail(s: str) -> tuple[str, int | None]:
    """If s ends with (YYYY), return (prefix, year); else (s, None)."""
    m = _YEAR_PATTERN.search(s)
    if not m:
        return (s, None)
    year = int(m.group(1))
    if 1900 <= year <= 2100:
        # Remove the (YYYY) from the end (and any trailing space)
        prefix = s[: m.start()].strip()
        return (prefix, year)
    return (s, None)


# --- List and structure patterns ---

# Bullet: line start with -, *, •, – (en-dash), or ◦
_BULLET_START = re.compile(r"^\s*[\-\*•–◦]\s+", re.MULTILINE)
# Numbered: 1. 2. or 1) 2) or (1) (2) or 1) 2)
_NUMBERED_START = re.compile(r"^\s*(?:\(\s*\d+\s*\)|\d+\s*[.\)])\s+", re.MULTILINE)
# Markdown bold: **text** or *text*
_BOLD_TITLE = re.compile(r"\*\*([^*]+)\*\*|\*([^*]+)\*")
# Title (Year) – blurb or Title (Year): blurb (captures title and year)
_TITLE_YEAR_DASH = re.compile(
    r"([^\n*\-•–◦]+?)\s*\((\d{4})\)\s*[:–\-]\s*",
    re.MULTILINE,
)
# Standalone Title (Year) at word boundary (for extraction)
_TITLE_YEAR_ONLY = re.compile(
    r"(?:^|[\s,])([A-Za-z0-9][^\n*(]{2,60}?)\s*\((\d{4})\)(?:\s|[,.]|$)",
    re.MULTILINE,
)


# --- Deep dive / scene indicators (keywords) ---
# Single vocabulary list for maintainability (no AI; deterministic).

_DEEP_DIVE_PHRASES = (
    "overview", "summary", "in depth", "deep dive", "below we", "details below",
    "breakdown", "in detail", "in summary", "to summarize", "key points",
    "the following", "as follows", "see below", "more below", "full analysis",
)

# Scene-like phrases: trigger scenes intent even when user didn't ask for "scenes".
# Ordered so longer phrases are checked first if we ever do substring precedence.
_SCENE_PHRASES = (
    "key moments", "memorable sequences", "opening scene", "climax", "final scene",
    "key scene", "set pieces", "montage", "standout moments", "best moments",
    "notable scenes", "iconic scene", "iconic moments", "scene", "scenes",
    "shot", "shots", "sequence", "clip", "moment in the film", "in the film",
    "on screen", "visual", "cinematography", "director shot", "filmed",
)

# Structural heuristics: minimum bullet/numbered lines that look like scene descriptions (not titles).
_SCENE_LIKE_ENUMERATION_MIN_ITEMS = 2
# Max length for a list item to count as "scene-like" (descriptions, not full sentences).
_SCENE_LIKE_ITEM_MAX_CHARS = 120
# Minimum "the film" / "the movie" references to treat as single-movie deep-dive language.
_THE_FILM_MOVIE_MIN_REFERENCES = 2


@dataclass
class ExtractedMovie:
    """Single movie extracted from response: title, optional year, optional confidence (0-1)."""
    title: str
    year: int | None = None
    confidence: float = 1.0


@dataclass
class ParseStructure:
    """Structure indicators: list-like vs paragraph-like."""
    has_bullets: bool = False
    has_numbered_list: bool = False
    has_bold_titles: bool = False
    has_title_year_pattern: bool = False
    has_dash_blurb_pattern: bool = False


@dataclass
class ParseSignals:
    """Signals derived from response content for intent/classifier."""
    deep_dive_indicators: list[str] = field(default_factory=list)
    scene_indicators: list[str] = field(default_factory=list)
    # Structural: multiple bullet/numbered items that look like scene descriptions (not Title (Year)).
    scene_like_enumeration: bool = False
    # Count of "the film" + "the movie" in text (single-movie deep-dive language).
    the_film_movie_references: int = 0


@dataclass
class ResponseParseResult:
    """
    Full parse result for the intent classifier and downstream.
    - movies: ordered distinct movies (first-seen order)
    - structure: list/paragraph flags
    - signals: deepDiveIndicators, sceneIndicators
    """
    movies: list[ExtractedMovie] = field(default_factory=list)
    structure: ParseStructure = field(default_factory=ParseStructure)
    signals: ParseSignals = field(default_factory=ParseSignals)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging or API."""
        return {
            "movies": [
                {"title": m.title, "year": m.year, "confidence": m.confidence}
                for m in self.movies
            ],
            "structure": {
                "hasBullets": self.structure.has_bullets,
                "hasNumberedList": self.structure.has_numbered_list,
                "hasBoldTitles": self.structure.has_bold_titles,
                "hasTitleYearPattern": self.structure.has_title_year_pattern,
                "hasDashBlurbPattern": self.structure.has_dash_blurb_pattern,
            },
            "signals": {
                "deepDiveIndicators": list(self.signals.deep_dive_indicators),
                "sceneIndicators": list(self.signals.scene_indicators),
                "sceneLikeEnumeration": self.signals.scene_like_enumeration,
                "theFilmMovieReferences": self.signals.the_film_movie_references,
            },
        }


def _dedupe_movies(seen: list[tuple[str, int | None, float]]) -> list[ExtractedMovie]:
    """Deduplicate by normalized title, preserve first-seen order."""
    by_key: dict[str, ExtractedMovie] = {}
    for title, year, conf in seen:
        key = normalize_title(title).lower()
        if not key or len(key) < 2:
            continue
        if key not in by_key:
            by_key[key] = ExtractedMovie(title=normalize_title(title), year=year, confidence=conf)
    return list(by_key.values())


def _compute_structure(text: str) -> ParseStructure:
    """Set structure flags from response text."""
    s = ParseStructure()
    if not text:
        return s
    s.has_bullets = bool(_BULLET_START.search(text))
    s.has_numbered_list = bool(_NUMBERED_START.search(text))
    s.has_bold_titles = bool(_BOLD_TITLE.search(text))
    s.has_title_year_pattern = bool(_YEAR_PATTERN.search(text))
    # Dash-blurb: (Year) followed by – or : and more text
    s.has_dash_blurb_pattern = bool(_YEAR_AT_END.search(text))
    return s


def _compute_scene_structure(text: str) -> tuple[bool, int]:
    """
    Structural heuristics for scene-like response (no user "scenes" required).
    - scene_like_enumeration: True when >= N bullet/numbered lines look like scene descriptions
      (no (YYYY), reasonable length), not movie titles.
    - the_film_movie_refs: Count of "the film" + "the movie" (single-movie deep-dive language).
    """
    scene_like_count = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        stripped = _BULLET_START.sub("", line, count=1)
        stripped = _NUMBERED_START.sub("", stripped, count=1)
        stripped = stripped.strip()
        if len(stripped) < 5 or len(stripped) > _SCENE_LIKE_ITEM_MAX_CHARS:
            continue
        # Does not look like "Title (Year)" — no trailing (YYYY)
        if _YEAR_PATTERN.search(stripped):
            continue
        scene_like_count += 1
    scene_like_enumeration = scene_like_count >= _SCENE_LIKE_ENUMERATION_MIN_ITEMS

    low = text.lower()
    the_film_movie_refs = low.count("the film") + low.count("the movie")

    return (scene_like_enumeration, the_film_movie_refs)


def _compute_signals(text: str) -> ParseSignals:
    """Compute deepDiveIndicators, sceneIndicators, and structural scene signals."""
    sig = ParseSignals()
    if not text:
        return sig
    low = text.lower()
    for phrase in _DEEP_DIVE_PHRASES:
        if phrase in low:
            sig.deep_dive_indicators.append(phrase)
    for phrase in _SCENE_PHRASES:
        if phrase in low:
            sig.scene_indicators.append(phrase)
    sig.scene_like_enumeration, sig.the_film_movie_references = _compute_scene_structure(text)
    return sig


def _extract_from_bullets_and_numbered(text: str) -> list[tuple[str, int | None, float]]:
    """Extract candidate (title, year, confidence) from bullet/numbered lines."""
    out: list[tuple[str, int | None, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip bullet or numbered prefix
        line = _BULLET_START.sub("", line, count=1)
        line = _NUMBERED_START.sub("", line, count=1)
        line = line.strip()
        if not line or len(line) < 2:
            continue
        # Strip leading bold markers
        if line.startswith("**") and "**" in line[2:]:
            line = line[2:].split("**", 1)[0].strip()
        elif line.startswith("*") and not line.startswith("**") and "*" in line[1:]:
            line = line[1:].split("*", 1)[0].strip()
        # Title (Year) at end?
        title_part, year = _extract_year_from_tail(line)
        if title_part:
            title_part = normalize_title(title_part)
            if len(title_part) >= 2:
                conf = 0.85 if year is not None else 0.7
                out.append((title_part, year, conf))
    return out


def _extract_from_bold(text: str) -> list[tuple[str, int | None, float]]:
    """Extract from **Title** or *Title* (high confidence for short titles)."""
    out: list[tuple[str, int | None, float]] = []
    for m in _BOLD_TITLE.finditer(text):
        g = m.group(1) or m.group(2)
        if not g:
            continue
        t = normalize_title(g)
        if len(t) < 2 or len(t) > 120:
            continue
        title_part, year = _extract_year_from_tail(t)
        if title_part:
            title_part = normalize_title(title_part)
            if len(title_part) >= 2:
                conf = 0.9 if year is not None else 0.85
                out.append((title_part, year, conf))
    return out


def _extract_from_title_year_patterns(text: str) -> list[tuple[str, int | None, float]]:
    """Extract from 'Title (Year) – blurb' or 'Title (Year):' or standalone 'Title (Year)'."""
    out: list[tuple[str, int | None, float]] = []
    seen_keys: set[str] = set()
    # Title (Year) – or :
    for m in _TITLE_YEAR_DASH.finditer(text):
        title_raw, year_s = m.group(1).strip(), m.group(2)
        year = int(year_s) if 1900 <= int(year_s) <= 2100 else None
        title_part = normalize_title(title_raw)
        if len(title_part) >= 2:
            key = title_part.lower()
            if key not in seen_keys:
                seen_keys.add(key)
                out.append((title_part, year, 0.95))
    # Standalone Title (Year)
    for m in _TITLE_YEAR_ONLY.finditer(text):
        title_raw, year_s = m.group(1).strip(), m.group(2)
        year = int(year_s) if 1900 <= int(year_s) <= 2100 else None
        title_part = normalize_title(title_raw)
        if len(title_part) >= 2:
            key = title_part.lower()
            if key not in seen_keys:
                seen_keys.add(key)
                out.append((title_part, year, 0.9))
    return out


def parse_response(response_text: str) -> ResponseParseResult:
    """
    Deterministically parse agent response text.

    Returns:
        ResponseParseResult with:
        - movies: ordered distinct movies (title, optional year, optional confidence)
        - structure: hasBullets, hasNumberedList, hasBoldTitles, hasTitleYearPattern, hasDashBlurbPattern
        - signals: deepDiveIndicators[], sceneIndicators[]
    """
    text = (response_text or "").strip()
    structure = _compute_structure(text)
    signals = _compute_signals(text)

    collected: list[tuple[str, int | None, float]] = []

    # Order of extraction: high-confidence patterns first, then list lines
    collected.extend(_extract_from_title_year_patterns(text))
    collected.extend(_extract_from_bold(text))
    collected.extend(_extract_from_bullets_and_numbered(text))

    movies = _dedupe_movies(collected)

    return ResponseParseResult(movies=movies, structure=structure, signals=signals)
