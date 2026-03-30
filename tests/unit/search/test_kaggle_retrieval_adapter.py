"""
Unit tests for Kaggle retrieval adapter.

Tests:
- Kaggle hit (successful retrieval)
- Kaggle miss fallback (no results, continues with FakeLLM)
- Kaggle disabled mode
- Kaggle timeout fallback
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest

from cinemind.search.kaggle_retrieval_adapter import (
    KaggleEvidenceItem,
    KaggleRetrievalAdapter,
    KaggleRetrievalResult,
    get_kaggle_adapter,
)


@pytest.fixture
def adapter_enabled():
    """Create an enabled Kaggle adapter."""
    return KaggleRetrievalAdapter(enabled=True, timeout_seconds=5.0)


@pytest.fixture
def adapter_disabled():
    """Create a disabled Kaggle adapter."""
    return KaggleRetrievalAdapter(enabled=False, timeout_seconds=5.0)


class TestRelevanceGate:
    """Test relevance gate logic."""

    def test_relevant_intent_recommendation(self, adapter_enabled):
        """Test that recommendation intent is relevant."""
        prompt = "Recommend movies like The Matrix"
        is_relevant, score = adapter_enabled._is_relevant_for_kaggle(
            prompt, "recommendation", {"movies": ["The Matrix"], "people": []}
        )
        assert is_relevant
        assert score >= 0.4

    def test_relevant_intent_comparison(self, adapter_enabled):
        """Test that comparison intent is relevant."""
        prompt = "Compare The Matrix and Inception"
        is_relevant, score = adapter_enabled._is_relevant_for_kaggle(
            prompt, "comparison", {"movies": ["The Matrix", "Inception"], "people": []}
        )
        assert is_relevant
        assert score >= 0.4

    def test_relevant_keyword_rankings(self, adapter_enabled):
        """Test that queries with ranking keywords are relevant."""
        prompt = "Top 10 movies of all time"
        is_relevant, score = adapter_enabled._is_relevant_for_kaggle(
            prompt, "general_info", {"movies": [], "people": []}
        )
        assert is_relevant
        assert score >= 0.4

    def test_not_relevant_director_info(self, adapter_enabled):
        """Test that simple director info queries are not relevant."""
        prompt = "Who directed The Matrix"
        is_relevant, score = adapter_enabled._is_relevant_for_kaggle(
            prompt, "director_info", {"movies": ["The Matrix"], "people": []}
        )
        # Simple fact queries typically not relevant for Kaggle
        assert not is_relevant or score < 0.4

    def test_relevant_keyword_list(self, adapter_enabled):
        """Test that queries with 'list' keyword are relevant."""
        prompt = "List all action movies"
        is_relevant, score = adapter_enabled._is_relevant_for_kaggle(
            prompt, "general_info", {"movies": [], "people": []}
        )
        assert is_relevant
        assert score >= 0.4


class TestKaggleHit:
    """Test successful Kaggle retrieval (hit)."""

    @pytest.mark.asyncio
    async def test_kaggle_hit_success(self, adapter_enabled):
        """Test successful Kaggle retrieval."""
        # Mock the Kaggle searcher
        mock_results = [
            {
                "title": "The Matrix",
                "url": "",
                "content": "Director: Wachowskis, Year: 1999, Genre: Sci-Fi",
                "correlation": 0.85,
                "match_score": 0.9,
                "match_reason": "exact_title"
            }
        ]

        with patch.object(adapter_enabled, '_get_kaggle_searcher') as mock_searcher:
            mock_searcher_instance = Mock()
            mock_searcher_instance.search = Mock(return_value=(mock_results, 0.85))
            mock_searcher.return_value = mock_searcher_instance

            result = await adapter_enabled.retrieve_evidence(
                prompt="Rank the best sci-fi movies",
                intent="recommendation",
                entities={"movies": [], "people": []},
                max_results=5
            )

            assert result.success
            assert len(result.evidence_items) == 1
            assert result.evidence_items[0].title == "The Matrix"
            assert result.relevance_score >= 0.4

    @pytest.mark.asyncio
    async def test_kaggle_hit_normalizes_results(self, adapter_enabled):
        """Test that Kaggle results are properly normalized."""
        mock_results = [
            {
                "title": "The Matrix",
                "url": "",
                "content": "Director: Wachowskis" * 100,  # Very long content
                "correlation": 0.85,
                "match_score": 0.9,
                "match_reason": "exact_title"
            }
        ]

        with patch.object(adapter_enabled, '_get_kaggle_searcher') as mock_searcher:
            mock_searcher_instance = Mock()
            mock_searcher_instance.search = Mock(return_value=(mock_results, 0.85))
            mock_searcher.return_value = mock_searcher_instance

            result = await adapter_enabled.retrieve_evidence(
                prompt="Best movies",
                intent="recommendation",
                entities={"movies": [], "people": []},
                max_results=5
            )

            assert result.success
            # Content should be truncated
            assert len(result.evidence_items[0].content) <= 803  # 800 + "..."


class TestKaggleMissFallback:
    """Test Kaggle miss scenarios with clean fallback."""

    @pytest.mark.asyncio
    async def test_kaggle_miss_low_correlation(self, adapter_enabled):
        """Test Kaggle miss due to low correlation (below threshold)."""
        mock_results = [
            {
                "title": "Some Movie",
                "url": "",
                "content": "Unrelated content",
                "correlation": 0.3,  # Below threshold (0.6)
                "match_score": 0.4,
                "match_reason": "fuzzy_match"
            }
        ]

        with patch.object(adapter_enabled, '_get_kaggle_searcher') as mock_searcher:
            mock_searcher_instance = Mock()
            mock_searcher_instance.search = Mock(return_value=(mock_results, 0.3))
            mock_searcher.return_value = mock_searcher_instance

            result = await adapter_enabled.retrieve_evidence(
                prompt="Best movies",
                intent="recommendation",
                entities={"movies": [], "people": []},
                max_results=5
            )

            assert not result.success
            assert len(result.evidence_items) == 0
            assert "below threshold" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_kaggle_miss_no_results(self, adapter_enabled):
        """Test Kaggle miss with no results returned."""
        with patch.object(adapter_enabled, '_get_kaggle_searcher') as mock_searcher:
            mock_searcher_instance = Mock()
            mock_searcher_instance.search = Mock(return_value=([], 0.0))
            mock_searcher.return_value = mock_searcher_instance

            result = await adapter_enabled.retrieve_evidence(
                prompt="Best movies",
                intent="recommendation",
                entities={"movies": [], "people": []},
                max_results=5
            )

            assert not result.success
            assert len(result.evidence_items) == 0

    @pytest.mark.asyncio
    async def test_kaggle_miss_searcher_error(self, adapter_enabled):
        """Test Kaggle miss due to searcher error (clean fallback)."""
        with patch.object(adapter_enabled, '_get_kaggle_searcher') as mock_searcher:
            mock_searcher_instance = Mock()
            mock_searcher_instance.search = Mock(side_effect=Exception("Dataset not found"))
            mock_searcher.return_value = mock_searcher_instance

            result = await adapter_enabled.retrieve_evidence(
                prompt="Best movies",
                intent="recommendation",
                entities={"movies": [], "people": []},
                max_results=5
            )

            assert not result.success
            assert len(result.evidence_items) == 0
            assert result.error_message is not None
            # Should not raise exception, should fall back gracefully


class TestKaggleDisabledMode:
    """Test Kaggle disabled mode."""

    @pytest.mark.asyncio
    async def test_disabled_mode_returns_no_results(self, adapter_disabled):
        """Test that disabled adapter returns no results."""
        result = await adapter_disabled.retrieve_evidence(
            prompt="Best movies",
            intent="recommendation",
            entities={"movies": [], "people": []},
            max_results=5
        )

        assert not result.success
        assert len(result.evidence_items) == 0
        assert "disabled" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_disabled_mode_not_relevant(self, adapter_disabled):
        """Test that disabled adapter doesn't check relevance."""
        # Even with relevant query, disabled adapter should skip
        result = await adapter_disabled.retrieve_evidence(
            prompt="Top 10 movies",
            intent="recommendation",
            entities={"movies": [], "people": []},
            max_results=5
        )

        assert not result.success
        assert result.relevance_score == 0.0


class TestKaggleTimeoutFallback:
    """Test Kaggle timeout scenarios."""

    @pytest.mark.asyncio
    async def test_kaggle_timeout_short_timeout(self):
        """Test Kaggle timeout with very short timeout."""
        adapter = KaggleRetrievalAdapter(enabled=True, timeout_seconds=0.1)

        # Mock searcher that takes longer than timeout
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(1.0)  # Longer than 0.1s timeout
            return ([], 0.0)

        with patch.object(adapter, '_get_kaggle_searcher') as mock_searcher:
            mock_searcher_instance = Mock()
            # Use run_in_executor to simulate blocking call
            def blocking_search(*args, **kwargs):
                import time
                time.sleep(1.0)  # Block for 1 second
                return ([], 0.0)

            mock_searcher_instance.search = blocking_search
            mock_searcher.return_value = mock_searcher_instance

            result = await adapter.retrieve_evidence(
                prompt="Best movies",
                intent="recommendation",
                entities={"movies": [], "people": []},
                max_results=5
            )

            assert not result.success
            assert result.timeout
            assert result.error_message is not None
            assert "timeout" in result.error_message.lower() or "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_kaggle_timeout_clean_fallback(self):
        """Test that timeout results in clean fallback (no exceptions)."""
        adapter = KaggleRetrievalAdapter(enabled=True, timeout_seconds=0.1)

        with patch.object(adapter, '_get_kaggle_searcher') as mock_searcher:
            mock_searcher_instance = Mock()
            def blocking_search(*args, **kwargs):
                import time
                time.sleep(1.0)
                return ([], 0.0)

            mock_searcher_instance.search = blocking_search
            mock_searcher.return_value = mock_searcher_instance

            # Should not raise exception
            result = await adapter.retrieve_evidence(
                prompt="Best movies",
                intent="recommendation",
                entities={"movies": [], "people": []},
                max_results=5
            )

            assert not result.success
            assert result.timeout


class TestEvidenceBundleConversion:
    """Test conversion to EvidenceBundle format."""

    def test_convert_to_evidence_bundle_success(self, adapter_enabled):
        """Test successful conversion to EvidenceBundle format."""
        result = KaggleRetrievalResult(
            success=True,
            evidence_items=[
                KaggleEvidenceItem(
                    title="The Matrix",
                    url="https://kaggle.com/dataset",
                    content="Director: Wachowskis",
                    source="kaggle_imdb",
                    metadata={"correlation_score": 0.85}
                )
            ],
            relevance_score=0.8
        )

        bundle = adapter_enabled.convert_to_evidence_bundle(result)

        assert bundle is not None
        assert "search_results" in bundle
        assert len(bundle["search_results"]) == 1
        assert bundle["search_results"][0]["title"] == "The Matrix"
        assert bundle["search_results"][0]["source"] == "kaggle_imdb"

    def test_convert_to_evidence_bundle_none_on_failure(self, adapter_enabled):
        """Test that failed results return None."""
        result = KaggleRetrievalResult(
            success=False,
            evidence_items=[],
            relevance_score=0.3,
            error_message="Not relevant"
        )

        bundle = adapter_enabled.convert_to_evidence_bundle(result)

        assert bundle is None


class TestSingletonPattern:
    """Test singleton pattern for adapter."""

    def test_get_kaggle_adapter_singleton(self):
        """Test that get_kaggle_adapter returns singleton."""
        adapter1 = get_kaggle_adapter(enabled=True, timeout_seconds=5.0)
        adapter2 = get_kaggle_adapter(enabled=True, timeout_seconds=5.0)

        # Should be same instance if parameters match
        assert adapter1 is adapter2

    def test_get_kaggle_adapter_different_params(self):
        """Test that different parameters create different instances."""
        adapter1 = get_kaggle_adapter(enabled=True, timeout_seconds=5.0)
        adapter2 = get_kaggle_adapter(enabled=False, timeout_seconds=5.0)

        # Should be different instances
        assert adapter1 is not adapter2
        assert adapter1.enabled != adapter2.enabled


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

