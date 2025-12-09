"""Fact-checking query test cases."""
from .base import TestCase, contains_all_substrings, contains_any_substring, min_length

FACT_CHECK_TESTS = [
    TestCase(
        name="fact_check",
        prompt="Did Leonardo DiCaprio win an Oscar for The Revenant?",
        expected_type="fact-check",
        acceptance_criteria=[
            contains_all_substrings("revenant", "oscar", "leonardo", "dicaprio"),
            contains_any_substring("yes", "won", "award", "2016", "best actor")
        ]
    ),
    
    TestCase(
        name="release_date_future",
        prompt="Is Gladiator II already out? If not, when is it scheduled to release?",
        expected_type="release-date",
        acceptance_criteria=[
            contains_any_substring("gladiator", "2024", "2025", "release", "scheduled", "premiere"),
            min_length(50)
        ]
    ),
]

