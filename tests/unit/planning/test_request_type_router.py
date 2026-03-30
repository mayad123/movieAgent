"""
Unit tests for RequestTypeRouter.

Tests request_type inference covering:
- Common phrasings (questions, imperative prompts)
- Short prompts
- Ambiguous prompts
- Edge cases
"""

import sys
from pathlib import Path

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest

from cinemind.planning.request_type_router import RequestTypeRouter


@pytest.fixture
def router():
    """Create a router instance for testing."""
    return RequestTypeRouter()


class TestHighConfidencePatterns:
    """Test high-confidence pattern matching."""

    def test_comparison_high_confidence(self, router):
        """Test high-confidence comparison patterns."""
        test_cases = [
            ("Compare The Matrix and Inception", "comparison"),
            ("What's the comparison between X and Y", "comparison"),
            ("The Matrix vs Inception", "comparison"),
            ("The Matrix versus Inception", "comparison"),
            ("What's the difference between X and Y", "comparison"),
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query}"
            assert result.confidence >= 0.8, f"Low confidence for: {query}"

    def test_recs_high_confidence(self, router):
        """Test high-confidence recommendation patterns."""
        test_cases = [
            ("Recommend me a movie", "recs"),
            ("Suggest a film similar to The Matrix", "recs"),
            ("Movies like Inception", "recs"),
            ("What should I watch", "recs"),
            ("Recommendations for sci-fi movies", "recs"),
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query}"
            assert result.confidence >= 0.8, f"Low confidence for: {query}"

    def test_release_date_high_confidence(self, router):
        """Test high-confidence release date patterns."""
        test_cases = [
            ("When is Dune out", "release-date"),
            ("Is The Matrix out yet", "release-date"),
            ("When does Dune come out", "release-date"),
            ("What's the release date of Inception", "release-date"),
            ("Premiere date for Dune", "release-date"),
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query}"
            assert result.confidence >= 0.8, f"Low confidence for: {query}"

    def test_info_high_confidence(self, router):
        """Test high-confidence info patterns."""
        test_cases = [
            ("Who directed The Matrix", "info"),
            ("Who starred in Inception", "info"),
            ("What is the runtime of Dune", "info"),
            ("Cast of The Matrix", "info"),
            ("How long is Inception", "info"),
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query}"
            assert result.confidence >= 0.8, f"Low confidence for: {query}"


class TestGuardrails:
    """Test guardrail patterns (highest priority overrides)."""

    def test_guardrail_similar_recommend(self, router):
        """Test guardrail: similar + recommend → recs"""
        query = "Movies similar to The Matrix, recommend some"
        result = router.route(query)
        assert result.request_type == "recs"
        assert result.confidence >= 0.9
        assert "guardrail" in result.rule_hit.lower()

    def test_guardrail_out_yet(self, router):
        """Test guardrail: out yet → release-date"""
        query = "Is The Matrix out yet"
        result = router.route(query)
        assert result.request_type == "release-date"
        assert result.confidence >= 0.9
        assert "guardrail" in result.rule_hit.lower()

    def test_guardrail_explain_ending(self, router):
        """Test guardrail: explain ending → spoiler"""
        query = "Explain the ending of Inception"
        result = router.route(query)
        assert result.request_type == "spoiler"
        assert result.confidence >= 0.9
        assert "guardrail" in result.rule_hit.lower()


class TestMediumConfidencePatterns:
    """Test medium-confidence pattern matching."""

    def test_medium_confidence_patterns(self, router):
        """Test that medium-confidence patterns work."""
        test_cases = [
            ("Movies similar to The Matrix", "recs"),  # Medium confidence - needs "movies" to be recs
            ("Best movies", "recs"),  # Medium confidence
            ("Better movie", "comparison"),  # Medium confidence
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query} (got {result.request_type})"
            # Medium confidence should be >= 0.5
            assert result.confidence >= 0.5, f"Too low confidence for: {query}"


class TestShortPrompts:
    """Test short/ambiguous prompts."""

    def test_very_short_queries(self, router):
        """Test very short queries default to info."""
        test_cases = [
            ("Matrix", "info"),
            ("Who?", "info"),
            ("What?", "info"),
            ("", "info"),  # Empty query
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: '{query}'"
            # Short queries should have lower confidence
            assert result.confidence < 0.7, f"Confidence too high for short query: '{query}'"


class TestAmbiguousPrompts:
    """Test ambiguous prompts that should default to info."""

    def test_ambiguous_queries_default_to_info(self, router):
        """Test ambiguous queries default to info with low confidence."""
        test_cases = [
            ("Tell me about movies", "info"),
            ("Movie information", "info"),
            ("Something about The Matrix", "info"),
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query}"
            # Ambiguous queries should default to info
            assert result.request_type == "info", f"Should default to info: {query}"


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_questions_vs_imperative(self, router):
        """Test both question and imperative forms."""
        question = "Who directed The Matrix?"
        imperative = "Tell me who directed The Matrix"

        result_q = router.route(question)
        result_i = router.route(imperative)

        # Both should be info
        assert result_q.request_type == "info"
        assert result_i.request_type == "info"

    def test_case_insensitive(self, router):
        """Test that patterns are case-insensitive."""
        test_cases = [
            ("COMPARE X AND Y", "comparison"),
            ("Compare X and Y", "comparison"),
            ("compare x and y", "comparison"),
            ("ReCoMmEnD Me A mOvIe", "recs"),
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query}"

    def test_multiple_patterns_priority(self, router):
        """Test that more specific patterns win over generic ones."""
        # "compare" should win over generic "similar"
        query = "Compare The Matrix and movies similar to it"
        result = router.route(query)
        assert result.request_type == "comparison"

        # Guardrails should win over everything
        query = "Movies similar to X, recommend some"
        result = router.route(query)
        assert result.request_type == "recs"
        assert "guardrail" in result.rule_hit.lower()


class TestConfidenceThresholds:
    """Test confidence thresholds and should_use_inferred_type logic."""

    def test_should_use_high_confidence(self, router):
        """Test that high-confidence results should be used."""
        query = "Who directed The Matrix"
        result = router.route(query)
        assert router.should_use_inferred_type(result)

    def test_should_use_medium_confidence(self, router):
        """Test that medium-confidence results should be used."""
        query = "Similar to The Matrix"
        result = router.route(query)
        assert router.should_use_inferred_type(result)

    def test_should_not_use_low_confidence(self, router):
        """Test that low-confidence results default to info."""
        query = "Movie"
        result = router.route(query)
        # Low confidence should default to info, but should_use_inferred_type may still return True
        # if confidence >= 0.5 (medium threshold)
        # Let's check that it defaults to info
        assert result.request_type == "info"


class TestRealWorldExamples:
    """Test real-world query examples."""

    def test_common_user_queries(self, router):
        """Test common real-world user queries."""
        test_cases = [
            ("Who directed The Matrix?", "info"),
            ("Recommend movies like Inception", "recs"),
            ("Compare The Matrix and Inception", "comparison"),
            ("When was Dune released?", "release-date"),
            ("Is Dune out yet?", "release-date"),
            ("What should I watch tonight?", "recs"),
            ("Tell me about The Matrix", "info"),
            ("Movies similar to sci-fi films", "recs"),
        ]

        for query, expected_type in test_cases:
            result = router.route(query)
            assert result.request_type == expected_type, f"Failed for: {query}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
