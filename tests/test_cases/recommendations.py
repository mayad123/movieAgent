"""Recommendation query test cases."""
from .base import TestCase, contains_all_substrings, contains_at_least_n_items, min_length, contains_any_substring

RECOMMENDATION_TESTS = [
    TestCase(
        name="recommendations_similar_movies",
        prompt="I liked Arrival and Annihilation, recommend 5 movies and explain why.",
        expected_type="recs",
        acceptance_criteria=[
            contains_all_substrings("arrival", "annihilation"),
            contains_at_least_n_items(5, "movie"),
            min_length(200),
            # Should explain the connection
            contains_any_substring("sci-fi", "science fiction", "similar", "because", "like")
        ]
    ),
]

