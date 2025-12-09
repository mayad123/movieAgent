"""Spoiler handling test cases."""
from .base import TestCase, contains_all_substrings, contains_spoiler_warning, min_length

SPOILER_TESTS = [
    TestCase(
        name="spoiler_request",
        prompt="Explain the ending of Shutter Island (spoilers OK).",
        expected_type="spoiler",
        acceptance_criteria=[
            contains_all_substrings("shutter island", "ending"),
            contains_spoiler_warning(),
            min_length(100)
        ]
    ),
]

