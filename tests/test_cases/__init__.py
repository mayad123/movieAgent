"""
Modular test case organization for CineMind.
Import all test cases from category modules.
"""
from .base import (
    TestCase,
    contains_all_substrings,
    contains_any_substring,
    contains_at_least_n_items,
    contains_spoiler_warning,
    mentions_director,
    mentions_movie,
    min_length,
)
from .comparisons import COMPARISON_TESTS
from .fact_checking import FACT_CHECK_TESTS
from .multi_hop import MULTI_HOP_TESTS
from .recommendations import RECOMMENDATION_TESTS

# Import test cases from category modules
from .simple_facts import SIMPLE_FACT_TESTS
from .spoilers import SPOILER_TESTS

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
    'TEST_CASES',
    'TEST_SUITES',
    'TestCase',
    'contains_all_substrings',
    'contains_any_substring',
    'contains_at_least_n_items',
    'contains_spoiler_warning',
    'mentions_director',
    'mentions_movie',
    'min_length',
]

