"""Fact-checking query test cases."""
from .base import TestCase, contains_all_substrings, contains_any_substring, min_length

FACT_CHECK_TESTS = [
    TestCase(
        name="fact_check_dark_knight_posthumous",
        prompt="Did Heath Ledger win an Oscar for his role as the Joker in The Dark Knight?",
        expected_type="fact-check",
        acceptance_criteria=[
            contains_all_substrings("heath", "ledger", "joker", "dark knight"),
            contains_any_substring("yes", "won", "posthumous", "best supporting actor", "2009")
        ]
    ),
    TestCase(
        name="fact_check_lotr_sweep",
        prompt="How many Oscars did The Lord of the Rings: The Return of the King win at the 2004 Academy Awards?",
        expected_type="fact-check",
        acceptance_criteria=[
            contains_all_substrings("return of the king", "11"),
            contains_any_substring("clean sweep", "won all", "tied the record", "eleven")
        ]
    ),
    TestCase(
        name="fact_check_titanic_release",
        prompt="Was the movie Titanic originally released in 1997?",
        expected_type="fact-check",
        # It was famously a December 1997 release after being delayed from summer
        acceptance_criteria=[
            contains_all_substrings("titanic", "1997"),
            contains_any_substring("yes", "correct", "december")
        ]
    ),
    TestCase(
        name="fact_check_avatar_release",
        prompt="When did the first Avatar movie premiere in theaters?",
        expected_type="release-date",
        acceptance_criteria=[
            contains_all_substrings("avatar", "2009"),
            contains_any_substring("december", "december 18", "james cameron")
        ]
    ),
    TestCase(
        name="fact_check_star_wars_first",
        prompt="What was the original title of the first Star Wars movie released in 1977?",
        expected_type="fact-check",
        # It was just "Star Wars", renamed "A New Hope" later
        acceptance_criteria=[
            contains_all_substrings("star wars"),
            contains_any_substring("new hope", "original title", "episode iv")
        ]
    ),
    TestCase(
        name="fact_check_pulp_fiction_winner",
        prompt="Did Pulp Fiction win the Best Picture Oscar in 1995?",
        expected_type="fact-check",
        # It lost to Forrest Gump, which is a classic fact-check 'trap'
        acceptance_criteria=[
            contains_all_substrings("pulp fiction", "forrest gump"),
            contains_any_substring("no", "lost", "did not win", "best original screenplay")
        ]
    ),
]

