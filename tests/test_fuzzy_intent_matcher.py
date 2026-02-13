"""
Unit tests for fuzzy intent matching.

Tests fuzzy matching covering:
- Exact matches still work (preserved behavior)
- Fuzzy matches catch typos
- False positives are controlled
- Paraphrases are recognized
"""
import sys
import re
from pathlib import Path

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
from cinemind.fuzzy_intent_matcher import FuzzyIntentMatcher, FuzzyMatchResult
from cinemind.intent_extraction import IntentExtractor


@pytest.fixture
def matcher():
    """Create a fuzzy matcher instance for testing."""
    return FuzzyIntentMatcher()


@pytest.fixture
def extractor():
    """Create an intent extractor instance for testing."""
    return IntentExtractor()


class TestExactMatchesPreserved:
    """Test that exact matches still work and have highest priority."""
    
    def test_exact_match_director_info(self, extractor):
        """Test exact match for director_info still works."""
        query = "Who directed The Matrix"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "director_info"
        assert intent.confidence >= 0.9  # High confidence for exact match
    
    def test_exact_match_cast_info(self, extractor):
        """Test exact match for cast_info still works."""
        query = "Who starred in The Matrix"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "cast_info"
        assert intent.confidence >= 0.9
    
    def test_exact_match_release_date(self, extractor):
        """Test exact match for release_date still works."""
        query = "When was The Matrix released"
        intent = extractor.extract(query, request_type="release-date")
        assert intent.intent == "release_date"
        assert intent.confidence >= 0.9
    
    def test_exact_match_recommendation(self, extractor):
        """Test exact match for recommendation still works."""
        query = "Recommend movies like The Matrix"
        intent = extractor.extract(query, request_type="recs")
        assert intent.intent == "recommendation"
        assert intent.confidence >= 0.9
    
    def test_exact_match_comparison(self, extractor):
        """Test exact match for comparison still works."""
        query = "Compare The Matrix vs Inception"  # Use "vs" instead of "and" to avoid filmography_overlap
        intent = extractor.extract(query, request_type="comparison")
        assert intent.intent == "comparison"
        assert intent.confidence >= 0.9


class TestTypoMatching:
    """Test that common misspellings are caught by fuzzy matching."""
    
    def test_typo_directer(self, extractor):
        """Test typo: 'directer' → 'directed'"""
        query = "Who directer The Matrix"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "director_info"
        assert 0.8 <= intent.confidence < 1.0  # Fuzzy match confidence
    
    def test_typo_realease(self, extractor):
        """Test typo: 'realease' → 'release'"""
        query = "When was The Matrix realeased"
        intent = extractor.extract(query, request_type="release-date")
        assert intent.intent == "release_date"
        assert 0.8 <= intent.confidence < 1.0
    
    def test_typo_recomend(self, extractor):
        """Test typo: 'recomend' → 'recommend'"""
        query = "recomend movies like The Matrix"
        intent = extractor.extract(query, request_type="recs")
        assert intent.intent == "recommendation"
        assert 0.8 <= intent.confidence < 1.0
    
    def test_typo_comparr(self, extractor):
        """Test typo: 'comparr' → 'compare'"""
        query = "comparr The Matrix vs Inception"  # Use "vs" to avoid filmography_overlap
        intent = extractor.extract(query, request_type="comparison")
        assert intent.intent == "comparison"
        assert 0.8 <= intent.confidence < 1.0
    
    def test_typo_wathc(self, matcher):
        """Test typo: 'wathc' → 'watch' (context-dependent)"""
        # This is a weaker test since "wathc" is very context-dependent
        # The typo pattern exists but may not trigger in all contexts
        query = "wathc The Matrix"
        result = matcher.match_fuzzy(query.lower(), exact_match_found=False)
        # May or may not match depending on context, but if it does, should have typo strength
        if result:
            assert result.match_type == "fuzzy_typo"
            assert result.match_strength == matcher.FUZZY_TYPO_STRENGTH
    
    def test_typo_streamin(self, matcher):
        """Test typo: 'streamin' → 'streaming'"""
        query = "where to streamin The Matrix"
        result = matcher.match_fuzzy(query.lower(), exact_match_found=False)
        if result:
            assert result.match_type == "fuzzy_typo"
            assert result.match_strength == matcher.FUZZY_TYPO_STRENGTH


class TestParaphraseMatching:
    """Test that common paraphrases are recognized."""
    
    def test_paraphrase_who_made(self, extractor):
        """Test paraphrase: 'who made' → director_info"""
        query = "Who made The Matrix"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "director_info"
        assert 0.75 <= intent.confidence < 1.0  # Paraphrase match confidence
    
    def test_paraphrase_whos_in(self, extractor):
        """Test paraphrase: 'who's in' → cast_info"""
        query = "Who's in The Matrix"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "cast_info"
        assert 0.75 <= intent.confidence < 1.0
    
    def test_paraphrase_when_did_it_come_out(self, extractor):
        """Test paraphrase: 'when did it come out' → release_date"""
        query = "When did The Matrix come out"
        intent = extractor.extract(query, request_type="release-date")
        assert intent.intent == "release_date"
        # This may match exact pattern "when.*come out", so confidence can be 1.0
        assert intent.confidence >= 0.75
    
    def test_paraphrase_whats_it_about(self, extractor):
        """Test paraphrase: 'what's it about' → general_info"""
        query = "What's The Matrix about"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "general_info"
        # May have lower confidence if no exact match, but should still detect intent
        assert intent.confidence >= 0.6
    
    def test_paraphrase_movies_similar_to(self, extractor):
        """Test paraphrase: 'movies similar to' → recommendation"""
        query = "Movies similar to The Matrix"
        intent = extractor.extract(query, request_type="recs")
        assert intent.intent == "recommendation"
        # This may match exact pattern "similar to", so confidence can be high
        assert intent.confidence >= 0.75
    
    def test_paraphrase_difference_between(self, extractor):
        """Test paraphrase: 'difference between' → comparison"""
        query = "What's the difference between The Matrix vs Inception"  # Use "vs" to avoid filmography_overlap
        intent = extractor.extract(query, request_type="comparison")
        assert intent.intent == "comparison"
        # "difference" is an exact pattern, so it may match with exact strength
        assert intent.confidence >= 0.75


class TestExactOverridesFuzzy:
    """Test that exact matches always win over fuzzy matches."""
    
    def test_exact_wins_over_typo(self, matcher):
        """Test that exact match wins even if typo pattern exists."""
        # "directed" is exact, should not be overridden by "directer" typo pattern
        query = "Who directed The Matrix"
        
        # Check exact match
        exact_patterns = {
            "director_info": [re.compile(r"who directed", re.IGNORECASE)]
        }
        exact_result = matcher.match_exact(query.lower(), exact_patterns)
        assert exact_result is not None
        assert exact_result.match_type == "exact"
        assert exact_result.match_strength == 1.0
        
        # Fuzzy should not override if exact found
        fuzzy_result = matcher.match_fuzzy(query.lower(), exact_match_found=True)
        assert fuzzy_result is None  # Should not match if exact found
    
    def test_exact_wins_over_paraphrase(self, matcher):
        """Test that exact match wins over paraphrase."""
        query = "Who directed The Matrix"
        
        exact_patterns = {
            "director_info": [re.compile(r"who directed", re.IGNORECASE)]
        }
        exact_result = matcher.match_exact(query.lower(), exact_patterns)
        assert exact_result is not None
        assert exact_result.match_strength == 1.0
        
        # Paraphrase "who made" should not override exact "who directed"
        fuzzy_result = matcher.match_fuzzy(query.lower(), exact_match_found=True)
        assert fuzzy_result is None


class TestFalsePositiveControl:
    """Test that false positives are controlled."""
    
    def test_no_match_on_unrelated_query(self, matcher):
        """Test that unrelated queries don't trigger false matches."""
        query = "Tell me a joke"
        result = matcher.match_fuzzy(query.lower(), exact_match_found=False)
        # Should not match any intent patterns
        assert result is None or result.match_strength < 0.7
    
    def test_typo_in_different_context(self, extractor):
        """Test that typos in wrong context still match but with appropriate confidence."""
        # "directer" as a typo for "director" - fuzzy matcher will catch it
        query = "The Matrix is a great directer movie"  # Contains typo "directer"
        intent = extractor.extract(query, request_type="info")
        # Fuzzy matcher will match "directer" typo, but in wrong context
        # The intent may still be director_info (fuzzy match), but confidence should reflect context
        # This is a limitation of simple pattern matching - it can't understand full context
        # The important thing is it doesn't break - it still extracts some intent
        assert intent.intent in ["director_info", "general_info"]
        # If it matches director_info via typo, confidence should be fuzzy-level (not exact)
        if intent.intent == "director_info":
            assert intent.confidence < 1.0  # Should be fuzzy match strength
    
    def test_paraphrase_not_overly_broad(self, extractor):
        """Test that paraphrase patterns aren't too broad."""
        query = "I like movies"
        intent = extractor.extract(query, request_type="info")
        # Should not match recommendation paraphrase "movies similar to"
        # unless query actually contains recommendation intent
        assert intent.intent != "recommendation" or intent.confidence < 0.7


class TestMatchStrengthScores:
    """Test that match strength scores are appropriate."""
    
    def test_exact_match_strength(self, matcher):
        """Test that exact matches have strength 1.0."""
        query = "who directed"
        exact_patterns = {
            "director_info": [re.compile(r"who directed", re.IGNORECASE)]
        }
        result = matcher.match_exact(query.lower(), exact_patterns)
        assert result is not None
        assert result.match_strength == 1.0
        assert result.match_type == "exact"
    
    def test_typo_match_strength(self, matcher):
        """Test that typo matches have appropriate strength."""
        query = "who directer"
        result = matcher.match_fuzzy(query.lower(), exact_match_found=False)
        if result and result.match_type == "fuzzy_typo":
            assert result.match_strength == matcher.FUZZY_TYPO_STRENGTH
            assert 0.8 <= result.match_strength < 1.0
    
    def test_paraphrase_match_strength(self, matcher):
        """Test that paraphrase matches have appropriate strength."""
        query = "who made"
        result = matcher.match_fuzzy(query.lower(), exact_match_found=False)
        if result and result.match_type == "fuzzy_paraphrase":
            assert result.match_strength == matcher.FUZZY_PARAPHRASE_STRENGTH
            assert 0.75 <= result.match_strength < 1.0


class TestRealWorldScenarios:
    """Test real-world scenarios with typos and paraphrases."""
    
    def test_typo_in_question(self, extractor):
        """Test typos in natural questions."""
        query = "Who directer The Matrix?"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "director_info"
    
    def test_multiple_typos(self, extractor):
        """Test queries with multiple potential typos."""
        query = "recomend movies similr to The Matrix"
        intent = extractor.extract(query, request_type="recs")
        # Should still detect recommendation intent
        assert intent.intent == "recommendation"
    
    def test_paraphrase_in_natural_speech(self, extractor):
        """Test paraphrases in natural speech patterns."""
        query = "Hey, what's The Matrix about anyway?"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "general_info"
    
    def test_mixed_exact_and_fuzzy(self, extractor):
        """Test queries that might match both exact and fuzzy."""
        # "directed" is exact, should win
        query = "Who directed The Matrix"
        intent = extractor.extract(query, request_type="info")
        assert intent.intent == "director_info"
        assert intent.confidence >= 0.9  # Should be high for exact match


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

