"""
Unit tests for ToolPlanner.

Tests freshness determination and browsing policies.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cinemind.tool_plan import ToolPlanner, ToolPlan


class TestDirectorInfoFreshness:
    """Tests for director_info intent (stable metadata)."""
    
    @pytest.fixture
    def planner(self):
        """Create ToolPlanner with current year 2024."""
        return ToolPlanner(current_year=2024)
    
    def test_director_info_no_freshness_needed(self, planner):
        """Test that director_info has need_freshness=false, ttl long."""
        intent = "director_info"
        freshness_signal = False
        entities = {"movies": ["The Matrix"], "people": []}
        
        need_freshness, ttl_hours, reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities,
            candidate_year=1999
        )
        
        assert need_freshness is False, \
            f"director_info should not need freshness, got: {need_freshness}"
        assert ttl_hours == 720.0, \
            f"director_info should have long TTL (720h), got: {ttl_hours}"
        assert reason is not None and len(reason) > 0, \
            f"Reason should be set, got: {reason}"
        assert "stable" in reason.lower() or "metadata" in reason.lower(), \
            f"Reason should mention stable metadata, got: {reason}"
    
    def test_director_info_skip_tavily_by_default(self, planner):
        """Test that director_info skips Tavily by default (no disambiguation)."""
        intent = "director_info"
        need_freshness = False
        freshness_reason = "stable metadata"
        entities = {"movies": ["The Matrix"], "people": []}
        requires_disambiguation = False
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=requires_disambiguation
        )
        
        assert tool_plan.use_tavily is False, \
            f"director_info should skip Tavily by default, got: {tool_plan.use_tavily}"
        assert tool_plan.tool_plan_skip_tavily is True, \
            f"tool_plan_skip_tavily should be True, got: {tool_plan.tool_plan_skip_tavily}"
        assert tool_plan.use_imdb_lookup is True, \
            "Should use IMDb lookup for structured sources"
        assert tool_plan.use_cache is True, \
            "Should use cache for stable metadata"
        assert tool_plan.use_structured_db is True, \
            "Should use structured DB for stable metadata"
    
    def test_director_info_reason_consistency(self, planner):
        """Test that freshness_reason and skip_reason are set and consistent."""
        intent = "director_info"
        need_freshness = False
        freshness_reason = "stable intent 'director_info' - metadata doesn't change"
        entities = {"movies": ["The Matrix"], "people": []}
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan.freshness_reason is not None, \
            "freshness_reason should be set"
        assert tool_plan.skip_reason is not None, \
            "skip_reason should be set"
        assert "stable" in tool_plan.freshness_reason.lower() or \
               "metadata" in tool_plan.freshness_reason.lower(), \
            f"freshness_reason should mention stable metadata, got: {tool_plan.freshness_reason}"
        assert "skip" in tool_plan.skip_reason.lower() or \
               "cache" in tool_plan.skip_reason.lower() or \
               "structured" in tool_plan.skip_reason.lower(), \
            f"skip_reason should explain why Tavily is skipped, got: {tool_plan.skip_reason}"


class TestWhereToWatchFreshness:
    """Tests for where_to_watch intent (volatile, needs freshness)."""
    
    @pytest.fixture
    def planner(self):
        """Create ToolPlanner with current year 2024."""
        return ToolPlanner(current_year=2024)
    
    def test_where_to_watch_needs_freshness(self, planner):
        """Test that where_to_watch has need_freshness=true, ttl short."""
        intent = "where_to_watch"
        freshness_signal = True  # "today" triggers signal
        entities = {"movies": ["The Matrix"], "people": []}
        
        need_freshness, ttl_hours, reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities
        )
        
        assert need_freshness is True, \
            f"where_to_watch should need freshness, got: {need_freshness}"
        assert ttl_hours == 6.0, \
            f"where_to_watch should have short TTL (6h), got: {ttl_hours}"
        assert reason is not None and len(reason) > 0, \
            f"Reason should be set, got: {reason}"
        assert "volatile" in reason.lower() or "fresh" in reason.lower(), \
            f"Reason should mention volatile/fresh, got: {reason}"
    
    def test_where_to_watch_does_not_skip_tavily(self, planner):
        """Test that where_to_watch does not skip Tavily."""
        intent = "where_to_watch"
        need_freshness = True
        freshness_reason = "volatile intent 'where_to_watch' requires fresh data"
        entities = {"movies": ["The Matrix"], "people": []}
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan.use_tavily is True, \
            f"where_to_watch should allow Tavily, got: {tool_plan.use_tavily}"
        assert tool_plan.tool_plan_skip_tavily is False, \
            f"tool_plan_skip_tavily should be False, got: {tool_plan.tool_plan_skip_tavily}"
        assert tool_plan.use_structured_db is False, \
            "Should skip structured DB for volatile data"
        assert tool_plan.use_cache is True, \
            "Should still check cache (may be stale)"
    
    def test_where_to_watch_reason_consistency(self, planner):
        """Test that freshness_reason is set for where_to_watch."""
        intent = "where_to_watch"
        need_freshness = True
        freshness_reason = "volatile intent 'where_to_watch' requires fresh data"
        entities = {"movies": ["The Matrix"], "people": []}
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan.freshness_reason is not None, \
            "freshness_reason should be set"
        assert "volatile" in tool_plan.freshness_reason.lower() or \
               "fresh" in tool_plan.freshness_reason.lower(), \
            f"freshness_reason should mention volatile/fresh, got: {tool_plan.freshness_reason}"
        assert tool_plan.skip_reason is None, \
            "skip_reason should be None when Tavily is allowed"


class TestDisambiguationBrowsing:
    """Tests for disambiguation queries (browsing permitted even if stable)."""
    
    @pytest.fixture
    def planner(self):
        """Create ToolPlanner with current year 2024."""
        return ToolPlanner(current_year=2024)
    
    def test_disambiguation_allows_tavily_even_if_stable(self, planner):
        """Test that disambiguation query allows Tavily even if intent is stable."""
        intent = "director_info"  # Stable intent
        need_freshness = False
        freshness_reason = "stable metadata"
        entities = {"movies": ["Crash"], "people": []}  # Ambiguous title
        requires_disambiguation = True  # Key: disambiguation needed
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=requires_disambiguation
        )
        
        assert tool_plan.use_tavily is True, \
            f"Disambiguation should allow Tavily even for stable intent, got: {tool_plan.use_tavily}"
        assert tool_plan.tool_plan_skip_tavily is False, \
            f"tool_plan_skip_tavily should be False for disambiguation, got: {tool_plan.tool_plan_skip_tavily}"
    
    def test_disambiguation_reason_consistency(self, planner):
        """Test that disambiguation has consistent reasons."""
        intent = "director_info"
        need_freshness = False
        freshness_reason = "stable metadata"
        entities = {"movies": ["Crash"], "people": []}
        requires_disambiguation = True
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=requires_disambiguation
        )
        
        assert tool_plan.freshness_reason is not None, \
            "freshness_reason should be set"
        assert tool_plan.skip_reason is not None, \
            "skip_reason should be set for disambiguation"
        assert "disambiguation" in tool_plan.skip_reason.lower(), \
            f"skip_reason should mention disambiguation, got: {tool_plan.skip_reason}"


class TestFreshnessDetermination:
    """Tests for freshness determination logic."""
    
    @pytest.fixture
    def planner(self):
        """Create ToolPlanner with current year 2024."""
        return ToolPlanner(current_year=2024)
    
    def test_stable_intent_with_old_movie(self, planner):
        """Test that stable intent with old movie doesn't need freshness."""
        intent = "cast_info"  # Stable intent
        freshness_signal = True  # Signal says fresh, but should be overridden
        entities = {"movies": ["The Matrix"], "people": []}
        
        need_freshness, ttl_hours, reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities,
            candidate_year=1999  # Old movie
        )
        
        assert need_freshness is False, \
            f"Old movie with stable intent should not need freshness, got: {need_freshness}"
        assert ttl_hours == 720.0, \
            f"Should have long TTL for old movie, got: {ttl_hours}"
        assert "old movie" in reason.lower() or "age" in reason.lower(), \
            f"Reason should mention old movie/age, got: {reason}"
    
    def test_stable_intent_with_freshness_signal(self, planner):
        """Test that stable intent with freshness signal needs freshness."""
        intent = "director_info"  # Stable intent
        freshness_signal = True  # "today" or "currently" in query
        entities = {"movies": ["The Matrix"], "people": []}
        
        need_freshness, ttl_hours, reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities
        )
        
        assert need_freshness is True, \
            f"Stable intent with freshness signal should need freshness, got: {need_freshness}"
        assert ttl_hours == 6.0, \
            f"Should have short TTL when freshness signal is True, got: {ttl_hours}"
        assert "freshness_signal" in reason.lower() or "today" in reason.lower() or "currently" in reason.lower(), \
            f"Reason should mention freshness signal, got: {reason}"
    
    def test_release_date_recent_movie(self, planner):
        """Test that release_date for recent movie needs freshness."""
        intent = "release_date"
        freshness_signal = False
        entities = {"movies": ["Gladiator II"], "people": []}
        
        need_freshness, ttl_hours, reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities,
            candidate_year=2024  # Recent/upcoming
        )
        
        assert need_freshness is True, \
            f"Release date for recent movie should need freshness, got: {need_freshness}"
        assert ttl_hours == 6.0, \
            f"Should have short TTL for recent release date, got: {ttl_hours}"
    
    def test_release_date_old_movie(self, planner):
        """Test that release_date for old movie doesn't need freshness."""
        intent = "release_date"
        freshness_signal = False
        entities = {"movies": ["The Matrix"], "people": []}
        
        need_freshness, ttl_hours, reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities,
            candidate_year=1999  # Old movie
        )
        
        assert need_freshness is False, \
            f"Release date for old movie should not need freshness, got: {need_freshness}"
        assert ttl_hours == 720.0, \
            f"Should have long TTL for old release date, got: {ttl_hours}"


class TestShouldSkipTavily:
    """Tests for should_skip_tavily final decision logic."""
    
    @pytest.fixture
    def planner(self):
        """Create ToolPlanner with current year 2024."""
        return ToolPlanner(current_year=2024)
    
    def test_skip_tavily_with_cache_hit_and_no_freshness(self, planner):
        """Test that Tavily is skipped when cache hit and no freshness needed."""
        tool_plan = ToolPlan(
            use_tavily=False,
            use_imdb_lookup=True,
            freshness_reason="stable metadata",
            skip_reason="no freshness needed"
        )
        
        should_skip, reason = planner.should_skip_tavily(
            tool_plan=tool_plan,
            cache_hit=True,
            need_freshness=False
        )
        
        assert should_skip is True, \
            f"Should skip Tavily with cache hit and no freshness, got: {should_skip}"
        assert "cache" in reason.lower(), \
            f"Reason should mention cache, got: {reason}"
    
    def test_allow_tavily_with_freshness_needed(self, planner):
        """Test that Tavily is allowed when freshness is needed."""
        tool_plan = ToolPlan(
            use_tavily=True,
            use_imdb_lookup=True,
            freshness_reason="volatile intent",
            skip_reason=None
        )
        
        should_skip, reason = planner.should_skip_tavily(
            tool_plan=tool_plan,
            cache_hit=False,
            need_freshness=True
        )
        
        assert should_skip is False, \
            f"Should allow Tavily when freshness needed, got: {should_skip}"
        assert tool_plan.tool_plan_skip_tavily is False, \
            "tool_plan_skip_tavily should be False"
    
    def test_skip_tavily_follows_tool_plan(self, planner):
        """Test that should_skip_tavily follows tool plan when no cache hit."""
        tool_plan = ToolPlan(
            use_tavily=False,
            use_imdb_lookup=True,
            freshness_reason="stable metadata",
            skip_reason="no freshness needed, using cache/structured sources"
        )
        
        should_skip, reason = planner.should_skip_tavily(
            tool_plan=tool_plan,
            cache_hit=False,
            need_freshness=False
        )
        
        assert should_skip is True, \
            f"Should follow tool plan (skip Tavily), got: {should_skip}"
        assert tool_plan.skip_reason in reason or "stable" in reason.lower(), \
            f"Reason should reflect tool plan, got: {reason}"


class TestReasonConsistency:
    """Tests for reason consistency across methods."""
    
    @pytest.fixture
    def planner(self):
        """Create ToolPlanner with current year 2024."""
        return ToolPlanner(current_year=2024)
    
    def test_freshness_reason_passed_to_tool_plan(self, planner):
        """Test that freshness_reason from determine_freshness is passed to plan_tools."""
        intent = "director_info"
        freshness_signal = False
        entities = {"movies": ["The Matrix"], "people": []}
        
        need_freshness, ttl_hours, freshness_reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities,
            candidate_year=1999
        )
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan.freshness_reason == freshness_reason, \
            f"freshness_reason should match, got: {tool_plan.freshness_reason} vs {freshness_reason}"
    
    def test_skip_reason_explains_tavily_decision(self, planner):
        """Test that skip_reason explains why Tavily is skipped or allowed."""
        # Test case 1: Stable intent, no disambiguation
        intent = "director_info"
        need_freshness = False
        freshness_reason = "stable metadata"
        entities = {"movies": ["The Matrix"], "people": []}
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan.skip_reason is not None, \
            "skip_reason should be set when Tavily is skipped"
        assert tool_plan.use_tavily is False, \
            "Tavily should be skipped"
        
        # Test case 2: Volatile intent
        intent = "where_to_watch"
        need_freshness = True
        freshness_reason = "volatile intent"
        entities = {"movies": ["The Matrix"], "people": []}
        
        tool_plan2 = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan2.skip_reason is None, \
            "skip_reason should be None when Tavily is allowed"
        assert tool_plan2.use_tavily is True, \
            "Tavily should be allowed"
    
    def test_reason_consistency_for_disambiguation(self, planner):
        """Test that reasons are consistent for disambiguation queries."""
        intent = "director_info"
        need_freshness = False
        freshness_reason = "stable metadata"
        entities = {"movies": ["Crash"], "people": []}
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            entities=entities,
            requires_disambiguation=True
        )
        
        assert tool_plan.freshness_reason is not None, \
            "freshness_reason should be set"
        assert tool_plan.skip_reason is not None, \
            "skip_reason should be set even when Tavily is allowed for disambiguation"
        assert "disambiguation" in tool_plan.skip_reason.lower(), \
            f"skip_reason should mention disambiguation, got: {tool_plan.skip_reason}"


class TestToolPlanEdgeCases:
    """Tests for edge cases in tool planning."""
    
    @pytest.fixture
    def planner(self):
        """Create ToolPlanner with current year 2024."""
        return ToolPlanner(current_year=2024)
    
    def test_volatile_intent_always_needs_freshness(self, planner):
        """Test that volatile intents always need freshness regardless of signal."""
        volatile_intents = ["release_status", "where_to_watch", "awards_current_year"]
        
        for intent in volatile_intents:
            need_freshness, ttl_hours, reason = planner.determine_freshness(
                intent=intent,
                freshness_signal=False,  # Even with False signal
                entities={"movies": [], "people": []}
            )
            
            assert need_freshness is True, \
                f"Volatile intent '{intent}' should always need freshness, got: {need_freshness}"
            assert ttl_hours == 6.0, \
                f"Volatile intent should have short TTL, got: {ttl_hours}"
            assert "volatile" in reason.lower(), \
                f"Reason should mention volatile, got: {reason}"
    
    def test_stable_intent_no_movie_year(self, planner):
        """Test that stable intent without movie year respects freshness signal."""
        intent = "director_info"
        freshness_signal = True
        entities = {"movies": ["Unknown Movie"], "people": []}
        
        need_freshness, ttl_hours, reason = planner.determine_freshness(
            intent=intent,
            freshness_signal=freshness_signal,
            entities=entities
        )
        
        # Without movie year, should respect freshness signal
        assert need_freshness is True, \
            f"Should respect freshness signal when no movie year, got: {need_freshness}"
        assert ttl_hours == 6.0, \
            f"Should have short TTL when freshness signal is True, got: {ttl_hours}"
    
    def test_tool_plan_structured_db_for_stable(self, planner):
        """Test that stable intents use structured DB."""
        intent = "director_info"
        need_freshness = False
        entities = {"movies": ["The Matrix"], "people": []}
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason="stable metadata",
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan.use_structured_db is True, \
            "Stable intent should use structured DB"
    
    def test_tool_plan_no_structured_db_for_volatile(self, planner):
        """Test that volatile intents skip structured DB."""
        intent = "where_to_watch"
        need_freshness = True
        entities = {"movies": ["The Matrix"], "people": []}
        
        tool_plan = planner.plan_tools(
            intent=intent,
            need_freshness=need_freshness,
            freshness_reason="volatile intent",
            entities=entities,
            requires_disambiguation=False
        )
        
        assert tool_plan.use_structured_db is False, \
            "Volatile intent should skip structured DB"

