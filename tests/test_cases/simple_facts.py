"""Simple fact query test cases."""
from .base import TestCase, contains_all_substrings, min_length

SIMPLE_FACT_TESTS = [
    TestCase(
        name="simple_fact_Inside_Out_director",
        prompt="Who directed Inside Out?",
        expected_type="info",
        # This tests for the specific director often used as a benchmark in IMDb datasets.
        acceptance_criteria=[
            contains_all_substrings("pete docter", "docter"),
            min_length(40)
        ]
    ),
]

