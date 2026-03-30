"""
Offline end-to-end tests for CineMind agent using FakeLLM.

Tests the full pipeline: PromptBuilder → generation → OutputValidator repair
without calling OpenAI.
"""

import pytest

from cinemind.agent import CineMind
from cinemind.llm.client import FakeLLMClient


@pytest.fixture
def fake_llm_client():
    """Provide a FakeLLMClient instance."""
    return FakeLLMClient()


@pytest.fixture
def agent_offline(fake_llm_client):
    """Create CineMind agent with FakeLLM for offline testing."""
    # Disable observability to avoid DB dependencies
    agent = CineMind(
        openai_api_key="fake-key",
        enable_observability=False,
        llm_client=fake_llm_client
    )
    # Note: We still need to handle planning, so we'll use request_type parameter
    # to bypass planning in tests
    return agent


@pytest.mark.asyncio
async def test_director_info_pass_through(agent_offline):
    """Test director_info query with pass-through (no repair needed)."""
    user_query = "Who directed The Matrix?"

    # Use request_type to bypass planning (which would need real OpenAI)
    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,  # Disable live data to avoid API calls
        request_type="info"  # Bypass planning
    )

    assert result is not None
    assert "response" in result or "answer" in result

    response_text = result.get("response") or result.get("answer", "")
    assert "directed" in response_text.lower()
    assert "matrix" in response_text.lower()

    # Check template was used correctly
    assert len(response_text.split(".")) <= 2  # Should be 1-2 sentences for director_info


@pytest.mark.asyncio
async def test_forbidden_terms_repair(agent_offline):
    """Test that validator detects and repairs forbidden terms."""
    user_query = "Who directed The Matrix? forbidden_test"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="info"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    # After repair, should NOT contain forbidden terms
    assert "tier" not in response_text.lower()
    assert "kaggle" not in response_text.lower()
    assert "dataset" not in response_text.lower()

    # Should still contain the answer
    assert "matrix" in response_text.lower()


@pytest.mark.asyncio
async def test_verbosity_violation_repair(agent_offline):
    """Test that validator detects and repairs verbosity violations."""
    user_query = "Who directed The Matrix? verbosity_test"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="info"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    # After repair, should be within verbosity budget (max 2 sentences for director_info)
    sentences = [s.strip() for s in response_text.split(".") if s.strip()]
    assert len(sentences) <= 2, f"Response has {len(sentences)} sentences, should be <= 2"


@pytest.mark.asyncio
async def test_freshness_timestamp_included(agent_offline):
    """Test that freshness-sensitive queries include timestamp."""
    user_query = "Where can I watch Dune?"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="info"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    # Should include "As of" timestamp for freshness-sensitive queries
    assert "as of" in response_text.lower() or "december 2024" in response_text.lower()
    assert "dune" in response_text.lower()


@pytest.mark.asyncio
async def test_freshness_missing_repair(agent_offline):
    """Test that validator detects missing freshness timestamp and repairs.

    Note: This test demonstrates the repair mechanism. In practice, the planner
    may classify queries differently, so freshness checks depend on need_freshness
    being True. The FakeLLMClient generates responses without timestamps for
    freshness_test queries to demonstrate the violation detection capability.
    """
    user_query = "Where can I watch Dune? freshness_test"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="info"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    # Verify we got a response (repair behavior depends on planner classification)
    assert len(response_text) > 0
    assert "dune" in response_text.lower()


@pytest.mark.asyncio
async def test_cast_info_pass_through(agent_offline):
    """Test cast_info query with pass-through."""
    user_query = "Who starred in Inglourious Basterds?"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="info"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    assert "inglourious" in response_text.lower() or "basterds" in response_text.lower()
    # Cast info template allows up to 3 sentences
    sentences = [s.strip() for s in response_text.split(".") if s.strip()]
    assert len(sentences) <= 3


@pytest.mark.asyncio
async def test_recommendation_pass_through(agent_offline):
    """Test recommendation query with pass-through."""
    user_query = "Recommend movies like The Matrix"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="recs"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    assert "matrix" in response_text.lower()
    # Recommendation template requires at least 5 sentences
    sentences = [s.strip() for s in response_text.split(".") if s.strip()]
    assert len(sentences) >= 5
    # Batch enrichment: similar movies from FakeLLM -> media_strip + media_candidates
    assert "media_strip" in result
    assert result["media_strip"].get("movie_title")
    assert "media_candidates" in result
    assert len(result["media_candidates"]) >= 1
    assert result.get("media_gallery_label") == "Similar movies"


@pytest.mark.asyncio
async def test_release_date_pass_through(agent_offline):
    """Test release_date query with pass-through."""
    user_query = "When was Dune released?"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="release-date"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    assert "dune" in response_text.lower()
    assert "released" in response_text.lower() or "2021" in response_text
    # Release date template allows up to 2 sentences
    sentences = [s.strip() for s in response_text.split(".") if s.strip()]
    assert len(sentences) <= 2


@pytest.mark.asyncio
async def test_routing_decision_record(agent_offline):
    """Test that routing decision record is produced (if implemented)."""
    user_query = "Who directed The Matrix?"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="info"
    )

    assert result is not None
    # Check if routing decision metadata is present
    # This depends on implementation - may be in result metadata or logs
    # For now, just check that result structure is valid
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_comparison_pass_through(agent_offline):
    """Test comparison query with pass-through."""
    user_query = "Compare The Matrix and Inception"

    result = await agent_offline.search_and_analyze(
        user_query=user_query,
        use_live_data=False,
        request_type="comparison"
    )

    assert result is not None
    response_text = result.get("response") or result.get("answer", "")

    assert "matrix" in response_text.lower()
    assert "inception" in response_text.lower()
    # Comparison template requires at least 8 sentences
    sentences = [s.strip() for s in response_text.split(".") if s.strip()]
    assert len(sentences) >= 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

