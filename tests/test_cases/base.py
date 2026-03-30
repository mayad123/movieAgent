"""
Base test case definitions and acceptance criteria functions.
"""
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class TestCase:
    """Single test case definition."""
    name: str
    prompt: str
    reference_answer: str | None = None
    acceptance_criteria: list[Callable] = field(default_factory=list)
    expected_type: str | None = None
    expected_outcome: str = "success"
    metadata: dict = field(default_factory=dict)


# Acceptance Criteria Functions
def contains_all_substrings(*substrings: str) -> Callable:
    """Check if response contains all specified substrings."""
    def check(response: str) -> tuple[bool, str]:
        missing = [s for s in substrings if s.lower() not in response.lower()]
        if missing:
            return False, f"Missing: {', '.join(missing)}"
        return True, "All required substrings found"
    return check


def contains_any_substring(*substrings: str) -> Callable:
    """Check if response contains at least one substring."""
    def check(response: str) -> tuple[bool, str]:
        found = [s for s in substrings if s.lower() in response.lower()]
        if found:
            return True, f"Found: {', '.join(found)}"
        return False, f"None found. Required one of: {', '.join(substrings)}"
    return check


def contains_spoiler_warning() -> Callable:
    """Check if response contains spoiler warning."""
    spoiler_keywords = ["spoiler", "spoilers", "warning", "reveal"]
    def check(response: str) -> tuple[bool, str]:
        if any(kw in response.lower() for kw in spoiler_keywords):
            return True, "Spoiler warning present"
        return False, "No spoiler warning found"
    return check


def min_length(min_chars: int) -> Callable:
    """Check minimum response length."""
    def check(response: str) -> tuple[bool, str]:
        if len(response) >= min_chars:
            return True, f"Length {len(response)} >= {min_chars}"
        return False, f"Length {len(response)} < {min_chars}"
    return check


def contains_at_least_n_items(min_count: int, item_keyword: str) -> Callable:
    """Check if response contains at least N items (e.g., movies, titles)."""
    def check(response: str) -> tuple[bool, str]:
        # Simple heuristic: count occurrences of numbered lists or bullet points
        import re
        patterns = [
            r'\d+\.',  # Numbered lists
            r'•',      # Bullet points
            r'[-*]',   # Dashes/asterisks
        ]
        count = sum(len(re.findall(pattern, response)) for pattern in patterns)
        if count >= min_count:
            return True, f"Found {count} items (>= {min_count})"
        return False, f"Found {count} items (< {min_count})"
    return check


def mentions_director(director_name: str) -> Callable:
    """Check if response mentions specific director."""
    return contains_all_substrings(director_name)


def mentions_movie(movie_title: str) -> Callable:
    """Check if response mentions specific movie."""
    return contains_any_substring(movie_title)

