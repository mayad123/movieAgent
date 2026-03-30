"""
Integration tests for SearchEngine/Agent routing using mocked APIs.

Tests routing decisions between Kaggle and Tavily with mocked results.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cinemind.agent import CineMind
from cinemind.planning.request_plan import RequestPlan
from cinemind.search.search_engine import SearchEngine, TavilyOverrideReason


class TestKaggleHighCorrelationNoTavily:
    """Tests that high Kaggle correlation prevents Tavily call."""

    @pytest.fixture
    def mock_kaggle_high_correlation(self):
        """Mock Kaggle searcher returning high correlation."""
        mock_searcher = Mock()
        mock_searcher.is_highly_correlated = Mock(
            return_value=(
                True,  # is_highly_correlated
                [  # kaggle_results
                    {
                        "title": "Inglourious Basterds (2009)",
                        "url": "",
                        "content": "Director: Quentin Tarantino",
                        "source": "kaggle_imdb",
                        "tier": "A",
                        "score": 0.95,
                    }
                ],
                0.95,  # max_correlation
            )
        )
        mock_searcher.correlation_threshold = 0.7
        return mock_searcher

    @pytest.fixture
    def search_engine(self, mock_kaggle_high_correlation):
        """Create SearchEngine with mocked Kaggle."""
        engine = SearchEngine(tavily_api_key="test_key", enable_kaggle=True)
        engine.kaggle_searcher = mock_kaggle_high_correlation
        return engine

    @pytest.mark.asyncio
    async def test_kaggle_high_correlation_skips_tavily(self, search_engine):
        """Test that high Kaggle correlation prevents Tavily call."""
        # Mock Tavily to track if it's called
        tavily_called = []

        async def mock_tavily_search(query, max_results):
            tavily_called.append((query, max_results))
            return []

        search_engine._search_tavily = mock_tavily_search

        query = "Inglourious Basterds"
        results, decision = await search_engine.search(
            query=query,
            max_results=5,
            skip_tavily=False,  # Even if allowed, should skip due to Kaggle
            override_reason=None,
        )

        # Should have results from Kaggle
        assert len(results) > 0, f"Should have Kaggle results, got: {len(results)}"
        assert all(r.get("source") == "kaggle_imdb" for r in results), (
            f"All results should be from Kaggle, got: {[r.get('source') for r in results]}"
        )

        # Tavily should NOT be called
        assert len(tavily_called) == 0, (
            f"Tavily should not be called when Kaggle has high correlation, got {len(tavily_called)} calls"
        )

        # Decision metadata
        assert decision.tavily_used is False, f"tavily_used should be False, got: {decision.tavily_used}"
        assert decision.override_used is False, f"override_used should be False, got: {decision.override_used}"
        assert decision.kaggle_max_score >= 0.7, f"kaggle_max_score should be high, got: {decision.kaggle_max_score}"


class TestKaggleEmptyWithOverride:
    """Tests that empty Kaggle with valid override calls Tavily once."""

    @pytest.fixture
    def mock_kaggle_empty(self):
        """Mock Kaggle searcher returning empty/unusable results."""
        mock_searcher = Mock()
        mock_searcher.is_highly_correlated = Mock(
            return_value=(
                False,  # is_highly_correlated
                [],  # kaggle_results (empty)
                0.3,  # max_correlation (low)
            )
        )
        mock_searcher.correlation_threshold = 0.7
        return mock_searcher

    @pytest.fixture
    def search_engine(self, mock_kaggle_empty):
        """Create SearchEngine with mocked Kaggle."""
        engine = SearchEngine(tavily_api_key="test_key", enable_kaggle=True)
        engine.kaggle_searcher = mock_kaggle_empty
        return engine

    @pytest.mark.asyncio
    async def test_kaggle_empty_with_override_calls_tavily_once(self, search_engine):
        """Test that empty Kaggle with valid override_reason calls Tavily once."""
        # Mock Tavily to track calls
        tavily_calls = []

        async def mock_tavily_search(query, max_results):
            tavily_calls.append((query, max_results))
            return [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Test content",
                    "source": "tavily",
                    "score": 0.8,
                }
            ]

        search_engine._search_tavily = mock_tavily_search

        query = "Unknown Movie"
        override_reason = TavilyOverrideReason.STRUCTURED_LOOKUP_EMPTY.value

        results, decision = await search_engine.search(
            query=query,
            max_results=5,
            skip_tavily=True,  # Tool plan says skip
            override_reason=override_reason,  # But override is provided
        )

        # Tavily should be called exactly once
        assert len(tavily_calls) == 1, f"Tavily should be called exactly once, got: {len(tavily_calls)}"
        assert tavily_calls[0][0] == query, f"Tavily should be called with correct query, got: {tavily_calls[0]}"

        # Should have results from Tavily
        assert len(results) > 0, f"Should have Tavily results, got: {len(results)}"
        assert any(r.get("source") == "tavily" for r in results), (
            f"Should have Tavily results, got: {[r.get('source') for r in results]}"
        )

        # Decision metadata
        assert decision.tavily_used is True, f"tavily_used should be True, got: {decision.tavily_used}"
        assert decision.override_used is True, f"override_used should be True, got: {decision.override_used}"
        assert decision.override_reason == override_reason, (
            f"override_reason should match, got: {decision.override_reason}"
        )

    @pytest.mark.asyncio
    async def test_kaggle_empty_without_override_skips_tavily(self, search_engine):
        """Test that empty Kaggle without override does NOT call Tavily."""
        tavily_calls = []

        async def mock_tavily_search(query, max_results):
            tavily_calls.append((query, max_results))
            return []

        search_engine._search_tavily = mock_tavily_search

        query = "Unknown Movie"

        results, decision = await search_engine.search(
            query=query,
            max_results=5,
            skip_tavily=True,  # Tool plan says skip
            override_reason=None,  # No override
        )

        # Tavily should NOT be called
        assert len(tavily_calls) == 0, f"Tavily should not be called without override, got: {len(tavily_calls)}"

        # Should have no results
        assert len(results) == 0, f"Should have no results, got: {len(results)}"

        # Decision metadata
        assert decision.tavily_used is False, f"tavily_used should be False, got: {decision.tavily_used}"
        assert decision.override_used is False, f"override_used should be False, got: {decision.override_used}"


class TestRequireTierAOverride:
    """Tests that require_tier_a=true with no Tier A evidence overrides to Tavily."""

    @pytest.fixture
    def mock_kaggle_low_correlation(self):
        """Mock Kaggle searcher returning low correlation."""
        mock_searcher = Mock()
        mock_searcher.is_highly_correlated = Mock(
            return_value=(
                False,  # is_highly_correlated
                [],  # kaggle_results (empty)
                0.3,  # max_correlation (low)
            )
        )
        mock_searcher.correlation_threshold = 0.7
        return mock_searcher

    @pytest.fixture
    def search_engine(self, mock_kaggle_low_correlation):
        """Create SearchEngine with mocked Kaggle."""
        engine = SearchEngine(tavily_api_key="test_key", enable_kaggle=True)
        engine.kaggle_searcher = mock_kaggle_low_correlation
        return engine

    @pytest.mark.asyncio
    async def test_require_tier_a_override_to_tavily(self, search_engine):
        """Test that require_tier_a=true with no Tier A evidence overrides to Tavily."""

        # Mock Tavily to return Tier B/C results (no Tier A)
        async def mock_tavily_search(query, max_results):
            return [
                {
                    "title": "Test Result B",
                    "url": "https://variety.com/test",
                    "content": "Test content from Variety",
                    "source": "tavily",
                    "tier": "B",
                    "score": 0.8,
                },
                {
                    "title": "Test Result C",
                    "url": "https://reddit.com/test",
                    "content": "Test content from Reddit",
                    "source": "tavily",
                    "tier": "C",
                    "score": 0.7,
                },
            ]

        search_engine._search_tavily = mock_tavily_search

        query = "Test Movie"
        override_reason = TavilyOverrideReason.TIER_A_MISSING.value

        results, decision = await search_engine.search(
            query=query,
            max_results=5,
            skip_tavily=True,  # Tool plan says skip
            override_reason=override_reason,  # But override for Tier A missing
        )

        # Tavily should be called
        assert decision.tavily_used is True, (
            f"tavily_used should be True when override for Tier A missing, got: {decision.tavily_used}"
        )
        assert decision.override_used is True, f"override_used should be True, got: {decision.override_used}"
        assert decision.override_reason == override_reason, (
            f"override_reason should be tier_a_missing, got: {decision.override_reason}"
        )

        # Should have results
        assert len(results) > 0, f"Should have results from Tavily, got: {len(results)}"


class TestRoutingMetadata:
    """Tests for routing decision metadata assertions."""

    @pytest.fixture
    def mock_kaggle_high_correlation(self):
        """Mock Kaggle searcher returning high correlation."""
        mock_searcher = Mock()
        mock_searcher.is_highly_correlated = Mock(
            return_value=(
                True,
                [
                    {
                        "title": "The Matrix (1999)",
                        "url": "",
                        "content": "Director: Wachowskis",
                        "source": "kaggle_imdb",
                        "tier": "A",
                        "score": 0.95,
                    }
                ],
                0.95,
            )
        )
        mock_searcher.correlation_threshold = 0.7
        return mock_searcher

    @pytest.fixture
    def mock_kaggle_empty(self):
        """Mock Kaggle searcher returning empty."""
        mock_searcher = Mock()
        mock_searcher.is_highly_correlated = Mock(return_value=(False, [], 0.3))
        mock_searcher.correlation_threshold = 0.7
        return mock_searcher

    @pytest.fixture
    def search_engine_with_kaggle(self, mock_kaggle_high_correlation):
        """Create SearchEngine with mocked Kaggle."""
        engine = SearchEngine(tavily_api_key="test_key", enable_kaggle=True)
        engine.kaggle_searcher = mock_kaggle_high_correlation
        return engine

    @pytest.fixture
    def search_engine_no_kaggle(self, mock_kaggle_empty):
        """Create SearchEngine with empty Kaggle."""
        engine = SearchEngine(tavily_api_key="test_key", enable_kaggle=True)
        engine.kaggle_searcher = mock_kaggle_empty
        return engine

    @pytest.mark.asyncio
    async def test_routing_metadata_kaggle_high_correlation(self, search_engine_with_kaggle):
        """Test routing metadata when Kaggle has high correlation."""
        query = "The Matrix"
        results, decision = await search_engine_with_kaggle.search(query=query, max_results=5, skip_tavily=False)

        # Assert routing metadata
        assert decision.tavily_used is False, f"tavily_used should be False, got: {decision.tavily_used}"
        assert decision.override_used is False, f"override_used should be False, got: {decision.override_used}"
        assert decision.override_reason is None, f"override_reason should be None, got: {decision.override_reason}"
        assert decision.kaggle_query_string is not None, (
            f"kaggle_query_string should be set, got: {decision.kaggle_query_string}"
        )
        assert decision.kaggle_max_score >= 0.7, f"kaggle_max_score should be high, got: {decision.kaggle_max_score}"
        assert decision.kaggle_stage_a_candidates >= 0, (
            f"kaggle_stage_a_candidates should be set, got: {decision.kaggle_stage_a_candidates}"
        )

        # Evidence count
        evidence_used_count = len(results)
        assert evidence_used_count > 0, f"evidence_used_count should be > 0, got: {evidence_used_count}"

    @pytest.mark.asyncio
    async def test_routing_metadata_tavily_override(self, search_engine_no_kaggle):
        """Test routing metadata when Tavily is called with override."""
        tavily_calls = []

        async def mock_tavily_search(query, max_results):
            tavily_calls.append((query, max_results))
            return [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Test content",
                    "source": "tavily",
                    "score": 0.8,
                }
            ]

        search_engine_no_kaggle._search_tavily = mock_tavily_search

        query = "Unknown Movie"
        override_reason = TavilyOverrideReason.STRUCTURED_LOOKUP_EMPTY.value

        results, decision = await search_engine_no_kaggle.search(
            query=query, max_results=5, skip_tavily=True, override_reason=override_reason
        )

        # Assert routing metadata
        assert decision.tavily_used is True, f"tavily_used should be True, got: {decision.tavily_used}"
        assert decision.override_used is True, f"override_used should be True, got: {decision.override_used}"
        assert decision.override_reason == override_reason, (
            f"override_reason should match, got: {decision.override_reason}"
        )

        # Evidence count
        evidence_used_count = len(results)
        assert evidence_used_count > 0, f"evidence_used_count should be > 0, got: {evidence_used_count}"

    @pytest.mark.asyncio
    async def test_routing_metadata_no_results(self, search_engine_no_kaggle):
        """Test routing metadata when no results are found."""

        async def mock_tavily_search(query, max_results):
            return []  # Empty results

        search_engine_no_kaggle._search_tavily = mock_tavily_search

        query = "Unknown Movie"

        results, decision = await search_engine_no_kaggle.search(
            query=query, max_results=5, skip_tavily=True, override_reason=None
        )

        # Assert routing metadata
        assert decision.tavily_used is False, f"tavily_used should be False, got: {decision.tavily_used}"
        assert decision.override_used is False, f"override_used should be False, got: {decision.override_used}"

        # Evidence count should be 0
        evidence_used_count = len(results)
        assert evidence_used_count == 0, f"evidence_used_count should be 0, got: {evidence_used_count}"


class TestAgentRoutingIntegration:
    """Integration tests for Agent-level routing."""

    @pytest.fixture
    def mock_kaggle_high_correlation(self):
        """Mock Kaggle searcher returning high correlation."""
        mock_searcher = Mock()
        mock_searcher.is_highly_correlated = Mock(
            return_value=(
                True,
                [
                    {
                        "title": "Inglourious Basterds (2009)",
                        "url": "",
                        "content": "Director: Quentin Tarantino",
                        "source": "kaggle_imdb",
                        "tier": "A",
                        "score": 0.95,
                    }
                ],
                0.95,
            )
        )
        mock_searcher.correlation_threshold = 0.7
        return mock_searcher

    @pytest.mark.asyncio
    async def test_agent_routing_kaggle_high_correlation(self):
        """Test agent-level routing when Kaggle adapter returns Tier A evidence (skip Tavily)."""
        from cinemind.llm.client import FakeLLMClient
        from cinemind.search.kaggle_retrieval_adapter import KaggleEvidenceItem, KaggleRetrievalResult

        tavily_calls = []

        async def mock_tavily_search(query, max_results):
            tavily_calls.append((query, max_results))
            return []

        mock_bundle = {
            "search_results": [
                {
                    "title": "Inglourious Basterds (2009)",
                    "url": "",
                    "content": "Director: Quentin Tarantino",
                    "source": "kaggle_imdb",
                    "tier": "A",
                    "score": 0.95,
                }
            ]
        }
        mock_adapter = Mock()
        mock_adapter.retrieve_evidence = AsyncMock(
            return_value=KaggleRetrievalResult(
                success=True,
                evidence_items=[
                    KaggleEvidenceItem(
                        title="Inglourious Basterds (2009)",
                        url="",
                        content="Director: Quentin Tarantino",
                        source="kaggle_imdb",
                    )
                ],
                relevance_score=0.95,
            )
        )
        mock_adapter.convert_to_evidence_bundle = Mock(return_value=mock_bundle)

        agent = CineMind(tavily_api_key="test_key", enable_observability=False, llm_client=FakeLLMClient())
        agent.search_engine._search_tavily = mock_tavily_search

        request_plan = RequestPlan(
            intent="director_info",
            request_type="info",
            original_query="Who directed Inglourious Basterds?",
            need_freshness=False,
            entities=["Inglourious Basterds"],
            entities_typed={"movies": ["Inglourious Basterds"], "people": []},
        )
        agent.planner.plan_request = AsyncMock(return_value=request_plan)

        with patch("cinemind.search.kaggle_retrieval_adapter.get_kaggle_adapter", return_value=mock_adapter):
            result = await agent.search_and_analyze(
                "Who directed Inglourious Basterds?",
                use_live_data=True,
            )

        mock_adapter.retrieve_evidence.assert_awaited()
        assert result.get("tavily_used") is False, (
            f"tavily_used should be False in result, got: {result.get('tavily_used')}"
        )
        assert "Quentin Tarantino" in (result.get("response") or "") or result.get("sources"), (
            "Expected Kaggle-backed evidence to contribute to the answer or sources"
        )

        await agent.close()

    @pytest.mark.asyncio
    async def test_agent_routing_override_to_tavily(self):
        """Test agent-level routing with override to Tavily."""
        from cinemind.llm.client import FakeLLMClient

        mock_kaggle_empty = Mock()
        mock_kaggle_empty.is_highly_correlated = Mock(return_value=(False, [], 0.3))
        mock_kaggle_empty.correlation_threshold = 0.7

        tavily_calls = []

        async def mock_tavily_search(query, max_results):
            tavily_calls.append((query, max_results))
            return [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Test content",
                    "source": "tavily",
                    "tier": "B",
                    "score": 0.8,
                }
            ]

        agent = CineMind(tavily_api_key="test_key", enable_observability=False, llm_client=FakeLLMClient())
        agent.search_engine._search_tavily = mock_tavily_search
        agent.search_engine.kaggle_searcher = mock_kaggle_empty

        request_plan = RequestPlan(
            intent="director_info",
            request_type="info",
            original_query="Who directed Unknown Movie?",
            need_freshness=False,
            entities=["Unknown Movie"],
            require_tier_a=True,
            reject_tier_c=True,
        )

        agent.planner.plan_request = AsyncMock(return_value=request_plan)

        from cinemind.extraction.intent_extraction import StructuredIntent

        structured_intent = StructuredIntent(
            intent="director_info",
            entities={"movies": ["Unknown Movie"], "people": []},
            constraints={},
            original_query="Who directed Unknown Movie?",
        )
        agent.intent_extractor.extract_smart = AsyncMock(return_value=(structured_intent, "rules", 0.9))

        await agent.search_and_analyze(
            "Who directed Unknown Movie?",
            use_live_data=True,
        )

        await agent.close()


class TestOverrideReasonValidation:
    """Tests for override reason validation."""

    @pytest.fixture
    def mock_kaggle_empty(self):
        """Mock Kaggle searcher returning empty."""
        mock_searcher = Mock()
        mock_searcher.is_highly_correlated = Mock(return_value=(False, [], 0.3))
        mock_searcher.correlation_threshold = 0.7
        return mock_searcher

    @pytest.fixture
    def search_engine(self, mock_kaggle_empty):
        """Create SearchEngine with mocked Kaggle."""
        engine = SearchEngine(tavily_api_key="test_key", enable_kaggle=True)
        engine.kaggle_searcher = mock_kaggle_empty
        return engine

    @pytest.mark.asyncio
    async def test_valid_override_reasons(self, search_engine):
        """Test that valid override reasons are accepted."""
        tavily_calls = []

        async def mock_tavily_search(query, max_results):
            tavily_calls.append((query, max_results))
            return []

        search_engine._search_tavily = mock_tavily_search

        valid_reasons = [
            TavilyOverrideReason.DISAMBIGUATION_NEEDED.value,
            TavilyOverrideReason.STRUCTURED_LOOKUP_EMPTY.value,
            TavilyOverrideReason.TIER_A_MISSING.value,
        ]

        for override_reason in valid_reasons:
            tavily_calls.clear()

            _results, decision = await search_engine.search(
                query="Test", max_results=5, skip_tavily=True, override_reason=override_reason
            )

            # Should accept valid override reason
            assert decision.override_used is True, (
                f"Should accept valid override reason '{override_reason}', got: {decision.override_used}"
            )
            assert decision.override_reason == override_reason, (
                f"override_reason should match, got: {decision.override_reason}"
            )
            assert len(tavily_calls) > 0, f"Tavily should be called with valid override reason '{override_reason}'"

    @pytest.mark.asyncio
    async def test_invalid_override_reason_rejected(self, search_engine):
        """Test that invalid override reasons are rejected."""
        tavily_calls = []

        async def mock_tavily_search(query, max_results):
            tavily_calls.append((query, max_results))
            return []

        search_engine._search_tavily = mock_tavily_search

        invalid_reason = "invalid_reason"

        _results, decision = await search_engine.search(
            query="Test", max_results=5, skip_tavily=True, override_reason=invalid_reason
        )

        # Should reject invalid override reason
        assert decision.override_used is False, f"Should reject invalid override reason, got: {decision.override_used}"
        assert len(tavily_calls) == 0, (
            f"Tavily should not be called with invalid override reason, got: {len(tavily_calls)}"
        )
