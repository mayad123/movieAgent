"""
Test cases for CineMind agent evaluation.

Each test case includes:
- prompt: The user query
- reference_answer: Expected answer or key facts that must be present
- acceptance_criteria: Conditions that must be met
- expected_type: Expected request type classification
- metadata: Additional test information
"""
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class TestCase:
    """Single test case definition."""
    name: str
    prompt: str
    reference_answer: Optional[str] = None
    acceptance_criteria: List[Callable] = field(default_factory=list)
    expected_type: Optional[str] = None
    expected_outcome: str = "success"
    metadata: Dict = field(default_factory=dict)
    mock_search_results: Optional[List[Dict]] = None
    mock_response: Optional[str] = None


# Acceptance Criteria Functions
def contains_all_substrings(*substrings: str) -> Callable:
    """Check if response contains all specified substrings."""
    def check(response: str) -> tuple[bool, str]:
        missing = [s for s in substrings if s.lower() not in response.lower()]
        if missing:
            return False, f"Missing: {', '.join(missing)}"
        return True, "All required substrings found"
    return check


def contains_any_substring(*substrings: str) -> Callable:
    """Check if response contains at least one substring."""
    def check(response: str) -> tuple[bool, str]:
        found = [s for s in substrings if s.lower() in response.lower()]
        if found:
            return True, f"Found: {', '.join(found)}"
        return False, f"None found. Required one of: {', '.join(substrings)}"
    return check


def contains_spoiler_warning() -> Callable:
    """Check if response contains spoiler warning."""
    spoiler_keywords = ["spoiler", "spoilers", "warning", "reveal"]
    def check(response: str) -> tuple[bool, str]:
        if any(kw in response.lower() for kw in spoiler_keywords):
            return True, "Spoiler warning present"
        return False, "No spoiler warning found"
    return check


def min_length(min_chars: int) -> Callable:
    """Check minimum response length."""
    def check(response: str) -> tuple[bool, str]:
        if len(response) >= min_chars:
            return True, f"Length {len(response)} >= {min_chars}"
        return False, f"Length {len(response)} < {min_chars}"
    return check


def contains_at_least_n_items(min_count: int, item_keyword: str) -> Callable:
    """Check if response contains at least N items (e.g., movies, titles)."""
    def check(response: str) -> tuple[bool, str]:
        # Simple heuristic: count occurrences of numbered lists or bullet points
        import re
        patterns = [
            r'\d+\.',  # Numbered lists
            r'•',      # Bullet points
            r'[-*]',   # Dashes/asterisks
        ]
        count = sum(len(re.findall(pattern, response)) for pattern in patterns)
        if count >= min_count:
            return True, f"Found {count} items (>= {min_count})"
        return False, f"Found {count} items (< {min_count})"
    return check


def mentions_director(director_name: str) -> Callable:
    """Check if response mentions specific director."""
    return contains_all_substrings(director_name)


def mentions_movie(movie_title: str) -> Callable:
    """Check if response mentions specific movie."""
    return contains_any_substring(movie_title)


# Test Case Definitions
TEST_CASES = [
    # Simple fact queries
    TestCase(
        name="simple_fact_director",
        prompt="Who directed Prisoners?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("denis villeneuve", "villeneuve"),
            min_length(50)
        ],
        mock_response="Denis Villeneuve directed Prisoners (2013). This psychological thriller stars Hugh Jackman and Jake Gyllenhaal.",
        mock_search_results=[
            {
                "title": "Prisoners (2013) - IMDb",
                "url": "https://www.imdb.com/title/tt1392214/",
                "content": "Prisoners is a 2013 American thriller film directed by Denis Villeneuve.",
                "source": "imdb"
            }
        ]
    ),
    
    TestCase(
        name="simple_fact_release_date",
        prompt="When was The Matrix released?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("1999", "matrix"),
            min_length(50)
        ],
        mock_response="The Matrix was released in March 1999. It was directed by the Wachowskis and stars Keanu Reeves.",
        mock_search_results=[
            {
                "title": "The Matrix - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/The_Matrix",
                "content": "The Matrix is a 1999 science fiction action film.",
                "source": "wikipedia"
            }
        ]
    ),
    
    # Multi-hop queries
    TestCase(
        name="multi_hop_actors",
        prompt="Name three movies with both Robert De Niro and Al Pacino, ordered by release year.",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("robert de niro", "al pacino", "pacino", "de niro"),
            contains_at_least_n_items(3, "movie"),
            min_length(100)
        ],
        mock_response="Movies featuring both Robert De Niro and Al Pacino: 1. The Godfather Part II (1974) - De Niro as young Vito, 2. Heat (1995) - both lead roles, 3. Righteous Kill (2008) - both detectives.",
        mock_search_results=[
            {
                "title": "Movies with Robert De Niro and Al Pacino",
                "url": "https://www.imdb.com",
                "content": "Films: The Godfather Part II (1974), Heat (1995), Righteous Kill (2008)",
                "source": "imdb"
            }
        ]
    ),
    
    # Recommendation queries
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
        ],
        mock_response="Based on your enjoyment of Arrival and Annihilation, here are 5 recommendations: 1. Ex Machina (2014) - Similar AI themes, 2. Blade Runner 2049 (2017) - Also directed by Villeneuve, 3. Under the Skin (2013) - Atmospheric sci-fi, 4. Annihilation (2018) - Same director as Arrival, 5. The Arrival (1996) - Similar themes. These films share themes of alien contact, mystery, and atmospheric storytelling.",
        mock_search_results=[
            {
                "title": "Movies like Arrival and Annihilation",
                "url": "https://www.imdb.com",
                "content": "Similar sci-fi films: Ex Machina, Blade Runner 2049, Under the Skin",
                "source": "imdb"
            }
        ]
    ),
    
    # Release date queries
    TestCase(
        name="release_date_future",
        prompt="Is Gladiator II already out? If not, when is it scheduled to release?",
        expected_type="release-date",
        acceptance_criteria=[
            contains_any_substring("gladiator", "2024", "2025", "release", "scheduled", "premiere"),
            min_length(50)
        ],
        mock_response="Gladiator II is scheduled to release in November 2024. It is not yet released as of the current date. The film is a sequel to the 2000 film Gladiator, directed by Ridley Scott.",
        mock_search_results=[
            {
                "title": "Gladiator II Release Date",
                "url": "https://www.imdb.com",
                "content": "Gladiator II scheduled for November 2024 release.",
                "source": "imdb"
            }
        ]
    ),
    
    # Spoiler handling
    TestCase(
        name="spoiler_request",
        prompt="Explain the ending of Shutter Island (spoilers OK).",
        expected_type="spoiler",
        acceptance_criteria=[
            contains_all_substrings("shutter island", "ending"),
            contains_spoiler_warning(),
            min_length(100)
        ],
        mock_response="SPOILER WARNING: The ending of Shutter Island reveals that Leonardo DiCaprio's character, Teddy Daniels, is actually Andrew Laeddis, a patient at the mental institution. He has been living in a delusion, and the entire investigation was part of an experimental therapy to help him confront the truth about his past.",
        mock_search_results=[
            {
                "title": "Shutter Island Ending Explained",
                "url": "https://www.collider.com",
                "content": "The twist ending reveals Teddy is actually a patient at the asylum.",
                "source": "collider"
            }
        ]
    ),
    
    # Comparison queries
    TestCase(
        name="comparison_directors",
        prompt="Compare the directing styles of Christopher Nolan and Denis Villeneuve.",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("nolan", "villeneuve", "compare", "comparison", "style"),
            min_length(150)
        ],
        mock_response="Christopher Nolan and Denis Villeneuve both excel in atmospheric, visually stunning films. Nolan is known for complex time structures and practical effects (Inception, Interstellar), while Villeneuve focuses on slow-burn tension and philosophical themes (Blade Runner 2049, Dune). Both create immersive cinematic experiences.",
        mock_search_results=[
            {
                "title": "Nolan vs Villeneuve",
                "url": "https://www.variety.com",
                "content": "Both directors known for sci-fi epics with distinct styles.",
                "source": "variety"
            }
        ]
    ),
    
    # Fact-check queries
    TestCase(
        name="fact_check",
        prompt="Did Leonardo DiCaprio win an Oscar for The Revenant?",
        expected_type="fact-check",
        acceptance_criteria=[
            contains_all_substrings("revenant", "oscar", "leonardo", "dicaprio"),
            contains_any_substring("yes", "won", "award", "2016", "best actor")
        ],
        mock_response="Yes, Leonardo DiCaprio won the Academy Award for Best Actor for his role in The Revenant (2015). This was his first Oscar win, awarded in 2016 after several nominations.",
        mock_search_results=[
            {
                "title": "Leonardo DiCaprio Oscar Win",
                "url": "https://www.oscars.org",
                "content": "DiCaprio won Best Actor for The Revenant in 2016.",
                "source": "oscars"
            }
        ]
    ),
]

# Test Suite Organization
TEST_SUITES = {
    "all": TEST_CASES,
    "simple": [tc for tc in TEST_CASES if "simple" in tc.name],
    "multi_hop": [tc for tc in TEST_CASES if "multi_hop" in tc.name],
    "recommendations": [tc for tc in TEST_CASES if tc.expected_type == "recs"],
    "spoilers": [tc for tc in TEST_CASES if "spoiler" in tc.name],
    "fact_check": [tc for tc in TEST_CASES if "fact_check" in tc.name],
}

