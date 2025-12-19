"""Simple fact query test cases."""
from .base import TestCase, contains_all_substrings, min_length

SIMPLE_FACT_TESTS = [
    TestCase(
        name="simple_fact_shining_director",
        prompt="Who directed the 1980 horror film The Shining?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("stanley kubrick", "kubrick"),
            min_length(40)
        ]
    ),
    TestCase(
        name="simple_fact_joker_1989",
        prompt="Who played the Joker in the 1989 Batman movie directed by Tim Burton?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("jack nicholson", "nicholson"),
            min_length(40)
        ]
    ),
    TestCase(
        name="simple_fact_goodfellas_director",
        prompt="Which director is responsible for the 1990 gangster film Goodfellas?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("martin scorsese", "scorsese"),
            min_length(40)
        ]
    ),
    TestCase(
        name="simple_fact_neo_actor",
        prompt="Which actor played the character Neo in the 1999 film The Matrix?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("keanu reeves", "reeves"),
            min_length(40)
        ]
    ),
    TestCase(
        name="simple_fact_best_picture_2000",
        prompt="Which movie won the Academy Award for Best Picture in 2000?",
        expected_type="info",
        # Note: 'American Beauty' won in March 2000; 'Gladiator' won in 2001 for a 2000 release.
        # This tests the model's ability to handle the "Award Year" vs "Release Year" nuance.
        acceptance_criteria=[
            contains_all_substrings("american beauty", "gladiator"),
            min_length(50)
        ]
    ),
]

