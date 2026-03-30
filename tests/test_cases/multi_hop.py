"""Multi-hop reasoning test cases."""

from .base import TestCase, contains_all_substrings, contains_at_least_n_items, min_length

MULTI_HOP_TESTS = [
    TestCase(
        name="multi_hop_actors",
        prompt="Name three movies with both Robert De Niro and Al Pacino, ordered by release year.",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("robert de niro", "al pacino", "pacino", "de niro"),
            contains_at_least_n_items(3, "movie"),
            min_length(100),
        ],
    ),
]
