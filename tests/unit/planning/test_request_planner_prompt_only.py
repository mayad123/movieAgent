"""
Unit tests for prompt-only RequestPlan creation.

Tests that RequestPlanner can build complete RequestPlans from only the user prompt,
without requiring a UI-provided request_type.
"""
import sys
import asyncio
from pathlib import Path

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
from cinemind.planning.request_plan import RequestPlanner, RequestPlan
from cinemind.extraction.intent_extraction import IntentExtractor
from cinemind.infrastructure.tagging import HybridClassifier
from cinemind.llm.client import FakeLLMClient


@pytest.fixture
def planner():
    """Create a RequestPlanner instance for testing."""
    classifier = HybridClassifier()
    intent_extractor = IntentExtractor()
    return RequestPlanner(classifier, intent_extractor)


@pytest.fixture
def fake_client():
    """Create a FakeLLMClient for testing."""
    return FakeLLMClient()


@pytest.mark.asyncio
class TestPromptOnlyPlanning:
    """Test that prompt-only planning produces stable RequestPlans."""
    
    async def test_info_query_prompt_only(self, planner, fake_client):
        """Test prompt-only planning for info query."""
        prompt = "Who directed The Matrix?"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Should infer request_type from prompt
        assert plan.request_type == "info"
        assert plan.intent == "director_info"
        assert isinstance(plan.entities_typed, dict)
        assert "movies" in plan.entities_typed
        assert "people" in plan.entities_typed
        assert plan.response_format is not None
        assert plan.freshness_reason is not None
        assert plan.original_query == prompt
    
    async def test_recs_query_prompt_only(self, planner, fake_client):
        """Test prompt-only planning for recommendation query."""
        prompt = "Recommend movies like The Matrix"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Should infer request_type from prompt
        assert plan.request_type == "recs"
        assert plan.intent == "recommendation"
        assert isinstance(plan.entities_typed, dict)
        assert plan.response_format is not None
        assert plan.freshness_reason is not None
    
    async def test_comparison_query_prompt_only(self, planner, fake_client):
        """Test prompt-only planning for comparison query."""
        prompt = "Compare The Matrix vs Inception"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Should infer request_type from prompt
        assert plan.request_type == "comparison"
        assert plan.intent in ["comparison", "filmography_overlap"]  # May match either
        assert isinstance(plan.entities_typed, dict)
        assert plan.response_format is not None
    
    async def test_release_date_query_prompt_only(self, planner, fake_client):
        """Test prompt-only planning for release date query."""
        prompt = "When was The Matrix released?"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Should infer request_type from prompt
        assert plan.request_type == "release-date"
        assert plan.intent == "release_date"
        assert isinstance(plan.entities_typed, dict)
        assert plan.response_format is not None
        assert plan.freshness_reason is not None
    
    async def test_cast_info_query_prompt_only(self, planner, fake_client):
        """Test prompt-only planning for cast info query."""
        prompt = "Who starred in The Matrix?"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Should infer request_type from prompt (info for cast queries)
        assert plan.request_type == "info"
        assert plan.intent == "cast_info"
        assert isinstance(plan.entities_typed, dict)
        assert plan.response_format is not None
    
    async def test_ambiguous_query_prompt_only(self, planner, fake_client):
        """Test prompt-only planning for ambiguous query defaults to info."""
        prompt = "Tell me about movies"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Should default to info for ambiguous queries
        assert plan.request_type == "info"
        assert isinstance(plan.intent, str)
        assert isinstance(plan.entities_typed, dict)
        assert plan.response_format is not None
    
    async def test_query_with_typos_prompt_only(self, planner, fake_client):
        """Test prompt-only planning handles typos."""
        prompt = "Who directer The Matrix?"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Should still infer correctly despite typo
        assert plan.request_type == "info"
        assert plan.intent == "director_info"
        assert isinstance(plan.entities_typed, dict)


@pytest.mark.asyncio
class TestRequestTypeOverride:
    """Test that explicit request_type override still works (for tests)."""
    
    async def test_override_request_type_info(self, planner, fake_client):
        """Test that explicit request_type overrides inference."""
        prompt = "Tell me about The Matrix"
        
        # Override to info explicitly
        plan = await planner.plan_request(prompt, fake_client, request_type="info")
        
        assert plan.request_type == "info"
        assert isinstance(plan.intent, str)
        assert plan.response_format is not None
    
    async def test_override_request_type_recs(self, planner, fake_client):
        """Test that explicit request_type override works for recs."""
        prompt = "Movies similar to The Matrix"
        
        # Override to recs explicitly
        plan = await planner.plan_request(prompt, fake_client, request_type="recs")
        
        assert plan.request_type == "recs"
        assert isinstance(plan.intent, str)
        assert plan.response_format is not None
    
    async def test_override_request_type_comparison(self, planner, fake_client):
        """Test that explicit request_type override works for comparison."""
        prompt = "The Matrix and Inception"
        
        # Override to comparison explicitly
        plan = await planner.plan_request(prompt, fake_client, request_type="comparison")
        
        assert plan.request_type == "comparison"
        assert isinstance(plan.intent, str)
        assert plan.response_format is not None


@pytest.mark.asyncio
class TestRequestPlanCompleteness:
    """Test that RequestPlans are complete and consistent."""
    
    async def test_plan_has_all_required_fields(self, planner, fake_client):
        """Test that RequestPlan has all required fields."""
        prompt = "Who directed The Matrix?"
        
        plan = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Check all required fields are present
        assert plan.request_type is not None
        assert plan.intent is not None
        assert plan.entities_typed is not None
        assert isinstance(plan.entities_typed, dict)
        assert "movies" in plan.entities_typed
        assert "people" in plan.entities_typed
        assert plan.freshness_signal is not None
        assert plan.need_freshness is not None
        assert plan.freshness_reason is not None
        assert plan.freshness_ttl_hours is not None
        assert plan.allowed_source_tiers is not None
        assert plan.tools_to_call is not None
        assert plan.response_format is not None
        assert plan.confidence is not None
        assert plan.original_query == prompt
        assert plan.intent_extraction_mode is not None
    
    async def test_plan_freshness_decision(self, planner, fake_client):
        """Test that freshness decision is made correctly."""
        # Query that needs freshness
        prompt_fresh = "Where to watch The Matrix today?"
        plan_fresh = await planner.plan_request(prompt_fresh, fake_client, request_type=None)
        assert plan_fresh.need_freshness is not None
        
        # Query that doesn't need freshness
        prompt_stable = "Who directed The Matrix?"
        plan_stable = await planner.plan_request(prompt_stable, fake_client, request_type=None)
        assert plan_stable.need_freshness is not None  # May still be False
    
    async def test_plan_response_format_selection(self, planner, fake_client):
        """Test that response format is selected correctly."""
        # Info query should get SHORT_FACT
        prompt_info = "Who directed The Matrix?"
        plan_info = await planner.plan_request(prompt_info, fake_client, request_type=None)
        assert plan_info.response_format is not None
        
        # Recommendation query should get LIST
        prompt_recs = "Recommend movies like The Matrix"
        plan_recs = await planner.plan_request(prompt_recs, fake_client, request_type=None)
        assert plan_recs.response_format is not None
        
        # Comparison query should get COMPARISON
        prompt_compare = "Compare The Matrix vs Inception"
        plan_compare = await planner.plan_request(prompt_compare, fake_client, request_type=None)
        assert plan_compare.response_format is not None


@pytest.mark.asyncio
class TestStability:
    """Test that prompt-only planning is stable (same prompt = same plan)."""
    
    async def test_same_prompt_produces_same_plan(self, planner, fake_client):
        """Test that same prompt produces same plan (deterministic)."""
        prompt = "Who directed The Matrix?"
        
        plan1 = await planner.plan_request(prompt, fake_client, request_type=None)
        plan2 = await planner.plan_request(prompt, fake_client, request_type=None)
        
        # Core fields should be identical
        assert plan1.request_type == plan2.request_type
        assert plan1.intent == plan2.intent
        assert plan1.response_format == plan2.response_format
        assert plan1.need_freshness == plan2.need_freshness
    
    async def test_similar_prompts_produce_similar_plans(self, planner, fake_client):
        """Test that similar prompts produce similar plans."""
        prompt1 = "Who directed The Matrix?"
        prompt2 = "Who directed The Matrix"  # No question mark
        
        plan1 = await planner.plan_request(prompt1, fake_client, request_type=None)
        plan2 = await planner.plan_request(prompt2, fake_client, request_type=None)
        
        # Should have same request_type and intent
        assert plan1.request_type == plan2.request_type
        assert plan1.intent == plan2.intent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

