"""Comparison query test cases."""
from .base import TestCase, contains_all_substrings, min_length

COMPARISON_TESTS = [
    TestCase(
        name="comparison_directors",
        prompt="Compare the directing styles of Christopher Nolan and Denis Villeneuve.",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("nolan", "villeneuve", "compare", "comparison", "style"),
            min_length(150)
        ]
    ),
]

