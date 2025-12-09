"""
Modular test case organization for CineMind.
Import all test cases from category modules.
"""
from .base import TestCase, contains_all_substrings, contains_any_substring, \
    contains_spoiler_warning, min_length, contains_at_least_n_items, \
    mentions_director, mentions_movie

# Import test cases from category modules
from .simple_facts import SIMPLE_FACT_TESTS
from .multi_hop import MULTI_HOP_TESTS
from .recommendations import RECOMMENDATION_TESTS
from .comparisons import COMPARISON_TESTS
from .spoilers import SPOILER_TESTS
from .fact_checking import FACT_CHECK_TESTS

# Combine all test cases
TEST_CASES = (
    SIMPLE_FACT_TESTS +
    MULTI_HOP_TESTS +
    RECOMMENDATION_TESTS +
    COMPARISON_TESTS +
    SPOILER_TESTS +
    FACT_CHECK_TESTS
)

# Test Suite Organization
TEST_SUITES = {
    "all": TEST_CASES,
    "simple": SIMPLE_FACT_TESTS,
    "multi_hop": MULTI_HOP_TESTS,
    "recommendations": RECOMMENDATION_TESTS,
    "comparisons": COMPARISON_TESTS,
    "spoilers": SPOILER_TESTS,
    "fact_check": FACT_CHECK_TESTS,
}

__all__ = [
    'TestCase',
    'TEST_CASES',
    'TEST_SUITES',
    'contains_all_substrings',
    'contains_any_substring',
    'contains_spoiler_warning',
    'min_length',
    'contains_at_least_n_items',
    'mentions_director',
    'mentions_movie',
]

