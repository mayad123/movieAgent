"""Simple fact query test cases."""
from .base import TestCase, contains_all_substrings, min_length

SIMPLE_FACT_TESTS = [
    TestCase(
        name="simple_fact_director",
        prompt="Who directed Prisoners?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("denis villeneuve", "villeneuve"),
            min_length(50)
        ]
    ),
    
    TestCase(
        name="simple_fact_release_date",
        prompt="When was The Matrix released?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("1999", "matrix"),
            min_length(50)
        ]
    ),
]

