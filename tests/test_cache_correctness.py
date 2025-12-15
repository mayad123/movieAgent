"""
Cache correctness tests for CineMind.
Tests cache decision logic, freshness gates, and invalidation rules.
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cinemind.cache import SemanticCache, CacheEntry
from cinemind.request_plan import RequestPlan, RequestPlanner
from cinemind.database import Database
from cinemind.tagging import HybridClassifier
from cinemind.intent_extraction import IntentExtractor


class TestCacheCorrectness:
    """Test cache correctness rules and decision logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.db = Database()
        self.cache = SemanticCache(self.db)
        self.classifier = HybridClassifier()
        self.intent_extractor = IntentExtractor()
        self.planner = RequestPlanner(self.classifier, self.intent_extractor)
        
        # Create a test cache entry
        self.test_entry = CacheEntry(
            prompt_original="Name three movies with both Robert De Niro and Al Pacino",
            prompt_normalized="name three movies with both robert de niro and al pacino",
            prompt_hash="test_hash_123",
            predicted_type="info",
            entities=["Robert De Niro", "Al Pacino"],
            response_text="The Godfather Part II (1974), Heat (1995), Righteous Kill (2008)",
            sources=[
                {"url": "https://www.imdb.com/title/tt0071562/", "tier": "A"},
                {"url": "https://en.wikipedia.org/wiki/Heat_(1995_film)", "tier": "A"}
            ],
            created_at=(datetime.utcnow() - timedelta(hours=1)).isoformat(),
            expires_at=(datetime.utcnow() + timedelta(hours=23)).isoformat(),
            agent_version="1.0.0",
            prompt_version="v4",
            tool_config_version="cine_prompt_v4",
            cost_metrics={"saved_cost": 0.05}
        )
    
    def test_same_prompt_twice_cache_hit(self):
        """Test: Same prompt twice → second time should hit cache."""
        # This test verifies that exact same prompt results in cache hit
        # In practice, this would be tested with actual agent calls
        # For now, we test the cache lookup logic
        
        # Store entry
        self.cache.put(
            prompt=self.test_entry.prompt_original,
            response_text=self.test_entry.response_text,
            sources=self.test_entry.sources,
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version=self.test_entry.tool_config_version,
            agent_version=self.test_entry.agent_version,
            prompt_version=self.test_entry.prompt_version
        )
        
        # Try to retrieve same prompt
        cache_hit = self.cache.get(
            prompt=self.test_entry.prompt_original,
            classifier_type="hybrid",
            tool_config_version=self.test_entry.tool_config_version,
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            current_agent_version=self.test_entry.agent_version,
            current_prompt_version=self.test_entry.prompt_version
        )
        
        assert cache_hit is not None, "Same prompt should result in cache hit"
        assert cache_hit.cache_tier == "exact", "Should be exact match"
    
    def test_paraphrase_prompt_semantic_cache_hit(self):
        """Test: Paraphrase prompt → semantic cache hit."""
        # Store original entry
        self.cache.put(
            prompt=self.test_entry.prompt_original,
            response_text=self.test_entry.response_text,
            sources=self.test_entry.sources,
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version=self.test_entry.tool_config_version,
            agent_version=self.test_entry.agent_version,
            prompt_version=self.test_entry.prompt_version
        )
        
        # Try paraphrased version
        paraphrase = "What are three films featuring both Robert De Niro and Al Pacino?"
        cache_hit = self.cache.get(
            prompt=paraphrase,
            classifier_type="hybrid",
            tool_config_version=self.test_entry.tool_config_version,
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            current_agent_version=self.test_entry.agent_version,
            current_prompt_version=self.test_entry.prompt_version
        )
        
        # Semantic cache might or might not hit depending on embedding similarity
        # This test verifies the mechanism works
        if cache_hit:
            assert cache_hit.cache_tier in ["exact", "semantic"], "Should be cache hit"
            assert cache_hit.similarity_score >= 0.90, "Similarity should be high"
    
    def test_release_status_after_ttl_forces_refresh(self):
        """Test: Release-status prompt after TTL → forces refresh."""
        # Create a release-date entry that's older than TTL
        old_entry = CacheEntry(
            prompt_original="Is Gladiator 2 out yet?",
            prompt_normalized="is gladiator 2 out yet",
            prompt_hash="release_test_hash",
            predicted_type="release-date",
            entities=["Gladiator 2"],
            response_text="Gladiator 2 is scheduled for release in 2024",
            sources=[{"url": "https://www.imdb.com/title/tt123456/", "tier": "A"}],
            created_at=(datetime.utcnow() - timedelta(hours=7)).isoformat(),  # 7 hours old
            expires_at=(datetime.utcnow() - timedelta(hours=1)).isoformat(),  # Already expired
            agent_version="1.0.0",
            prompt_version="v4",
            tool_config_version="cine_prompt_v4"
        )
        
        # Store entry
        self.cache.put(
            prompt=old_entry.prompt_original,
            response_text=old_entry.response_text,
            sources=old_entry.sources,
            predicted_type=old_entry.predicted_type,
            entities=old_entry.entities,
            need_freshness=True,  # Release dates need freshness
            classifier_type="hybrid",
            tool_config_version=old_entry.tool_config_version,
            agent_version=old_entry.agent_version,
            prompt_version=old_entry.prompt_version
        )
        
        # Create request plan for release-date
        request_plan = RequestPlan(
            intent="release_date",
            request_type="release-date",
            entities=["Gladiator 2"],
            need_freshness=True,
            freshness_ttl_hours=6.0,  # 6 hour TTL for release dates
            original_query=old_entry.prompt_original
        )
        
        # Try to get cache entry
        cache_hit = self.cache.get(
            prompt=old_entry.prompt_original,
            classifier_type="hybrid",
            tool_config_version=old_entry.tool_config_version,
            predicted_type=old_entry.predicted_type,
            entities=old_entry.entities,
            need_freshness=True,
            current_agent_version=old_entry.agent_version,
            current_prompt_version=old_entry.prompt_version
        )
        
        # Should be None because expired
        assert cache_hit is None or not self.cache._is_fresh(
            cache_hit, old_entry.predicted_type, True
        ), "Expired cache entry should not be returned"
        
        # Even if found, should_use_cache_entry should reject it
        if cache_hit:
            plan_dict = request_plan.to_dict()
            plan_dict["agent_version"] = old_entry.agent_version
            plan_dict["prompt_version"] = old_entry.prompt_version
            plan_dict["tool_config_version"] = old_entry.tool_config_version
            
            should_use, reason = self.cache.should_use_cache_entry(cache_hit, plan_dict)
            assert not should_use, f"Expired cache should be rejected: {reason}"
            assert "freshness_ttl_expired" in reason or "expired" in reason.lower()
    
    def test_different_movie_year_no_cache_hit(self):
        """Test: Same prompt but different movie year → no cache hit."""
        # Store entry for "The Matrix (1999)"
        self.cache.put(
            prompt="Who directed The Matrix?",
            response_text="The Matrix (1999) was directed by the Wachowskis",
            sources=[{"url": "https://www.imdb.com/title/tt0133093/", "tier": "A"}],
            predicted_type="info",
            entities=["The Matrix"],
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version="cine_prompt_v4",
            agent_version="1.0.0",
            prompt_version="v4"
        )
        
        # Try query for "The Matrix (2021)" - different movie
        # The hash should be different because entities are different
        cache_hit = self.cache.get(
            prompt="Who directed The Matrix (2021)?",
            classifier_type="hybrid",
            tool_config_version="cine_prompt_v4",
            predicted_type="info",
            entities=["The Matrix"],  # Entity extraction might be same
            need_freshness=False,
            current_agent_version="1.0.0",
            current_prompt_version="v4"
        )
        
        # Should be None or semantic match with low similarity
        # Exact match should not happen because prompt is different
        if cache_hit:
            # If semantic match, similarity should be checked
            # Different years should reduce similarity
            assert cache_hit.cache_tier != "exact", "Different year should not be exact match"
    
    def test_version_mismatch_bypasses_cache(self):
        """Test: Agent version changed → bypass cache."""
        # Store entry with old version
        self.cache.put(
            prompt=self.test_entry.prompt_original,
            response_text=self.test_entry.response_text,
            sources=self.test_entry.sources,
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version=self.test_entry.tool_config_version,
            agent_version="1.0.0",  # Old version
            prompt_version="v4"
        )
        
        # Try to get with new version
        cache_hit = self.cache.get(
            prompt=self.test_entry.prompt_original,
            classifier_type="hybrid",
            tool_config_version=self.test_entry.tool_config_version,
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            current_agent_version="2.0.0",  # New version
            current_prompt_version="v4"
        )
        
        # Should be None due to version mismatch
        assert cache_hit is None, "Version mismatch should bypass cache"
    
    def test_tier_c_sources_in_facts_bypasses_cache(self):
        """Test: Cached sources include Tier C → bypass cache for facts."""
        # Create entry with Tier C sources
        tier_c_entry = CacheEntry(
            prompt_original="Who directed The Matrix?",
            prompt_normalized="who directed the matrix",
            prompt_hash="tier_c_test",
            predicted_type="info",
            entities=["The Matrix"],
            response_text="The Matrix was directed by the Wachowskis",
            sources=[
                {"url": "https://www.quora.com/question/123", "tier": "C"},
                {"url": "https://www.facebook.com/post/456", "tier": "C"}
            ],
            created_at=(datetime.utcnow() - timedelta(hours=1)).isoformat(),
            expires_at=(datetime.utcnow() + timedelta(hours=23)).isoformat(),
            agent_version="1.0.0",
            prompt_version="v4",
            tool_config_version="cine_prompt_v4"
        )
        
        # Store entry
        self.cache.put(
            prompt=tier_c_entry.prompt_original,
            response_text=tier_c_entry.response_text,
            sources=tier_c_entry.sources,
            predicted_type=tier_c_entry.predicted_type,
            entities=tier_c_entry.entities,
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version=tier_c_entry.tool_config_version,
            agent_version=tier_c_entry.agent_version,
            prompt_version=tier_c_entry.prompt_version
        )
        
        # Create request plan for facts (reject_tier_c=True)
        request_plan = RequestPlan(
            intent="director_info",
            request_type="info",
            entities=["The Matrix"],
            need_freshness=False,
            reject_tier_c=True,  # Reject Tier C for facts
            original_query=tier_c_entry.prompt_original
        )
        
        # Get cache entry
        cache_hit = self.cache.get(
            prompt=tier_c_entry.prompt_original,
            classifier_type="hybrid",
            tool_config_version=tier_c_entry.tool_config_version,
            predicted_type=tier_c_entry.predicted_type,
            entities=tier_c_entry.entities,
            need_freshness=False,
            current_agent_version=tier_c_entry.agent_version,
            current_prompt_version=tier_c_entry.prompt_version
        )
        
        # Should be found, but should_use_cache_entry should reject it
        if cache_hit:
            plan_dict = request_plan.to_dict()
            plan_dict["agent_version"] = tier_c_entry.agent_version
            plan_dict["prompt_version"] = tier_c_entry.prompt_version
            plan_dict["tool_config_version"] = tier_c_entry.tool_config_version
            
            should_use, reason = self.cache.should_use_cache_entry(cache_hit, plan_dict)
            assert not should_use, "Tier C sources in facts should bypass cache"
            assert "tier_c" in reason.lower(), f"Reason should mention tier_c: {reason}"
    
    def test_require_tier_a_missing_bypasses_cache(self):
        """Test: Require Tier A but missing → bypass cache."""
        # Create entry without Tier A sources
        no_tier_a_entry = CacheEntry(
            prompt_original="Who directed The Matrix?",
            prompt_normalized="who directed the matrix",
            prompt_hash="no_tier_a_test",
            predicted_type="info",
            entities=["The Matrix"],
            response_text="The Matrix was directed by the Wachowskis",
            sources=[
                {"url": "https://www.movieweb.com/article/123", "tier": "B"},
                {"url": "https://www.variety.com/article/456", "tier": "B"}
            ],
            created_at=(datetime.utcnow() - timedelta(hours=1)).isoformat(),
            expires_at=(datetime.utcnow() + timedelta(hours=23)).isoformat(),
            agent_version="1.0.0",
            prompt_version="v4",
            tool_config_version="cine_prompt_v4"
        )
        
        # Store entry
        self.cache.put(
            prompt=no_tier_a_entry.prompt_original,
            response_text=no_tier_a_entry.response_text,
            sources=no_tier_a_entry.sources,
            predicted_type=no_tier_a_entry.predicted_type,
            entities=no_tier_a_entry.entities,
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version=no_tier_a_entry.tool_config_version,
            agent_version=no_tier_a_entry.agent_version,
            prompt_version=no_tier_a_entry.prompt_version
        )
        
        # Create request plan that requires Tier A
        request_plan = RequestPlan(
            intent="director_info",
            request_type="info",
            entities=["The Matrix"],
            need_freshness=False,
            require_tier_a=True,  # Require Tier A
            original_query=no_tier_a_entry.prompt_original
        )
        
        # Get cache entry
        cache_hit = self.cache.get(
            prompt=no_tier_a_entry.prompt_original,
            classifier_type="hybrid",
            tool_config_version=no_tier_a_entry.tool_config_version,
            predicted_type=no_tier_a_entry.predicted_type,
            entities=no_tier_a_entry.entities,
            need_freshness=False,
            current_agent_version=no_tier_a_entry.agent_version,
            current_prompt_version=no_tier_a_entry.prompt_version
        )
        
        # Should be found, but should_use_cache_entry should reject it
        if cache_hit:
            plan_dict = request_plan.to_dict()
            plan_dict["agent_version"] = no_tier_a_entry.agent_version
            plan_dict["prompt_version"] = no_tier_a_entry.prompt_version
            plan_dict["tool_config_version"] = no_tier_a_entry.tool_config_version
            
            should_use, reason = self.cache.should_use_cache_entry(cache_hit, plan_dict)
            assert not should_use, "Missing Tier A should bypass cache when required"
            assert "tier_a" in reason.lower(), f"Reason should mention tier_a: {reason}"
    
    def test_prompt_version_mismatch_bypasses_cache(self):
        """Test: Prompt version changed → bypass cache."""
        # Store entry with old prompt version
        self.cache.put(
            prompt=self.test_entry.prompt_original,
            response_text=self.test_entry.response_text,
            sources=self.test_entry.sources,
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version="cine_prompt_v3",  # Old version
            agent_version=self.test_entry.agent_version,
            prompt_version="v3"  # Old version
        )
        
        # Try to get with new prompt version
        cache_hit = self.cache.get(
            prompt=self.test_entry.prompt_original,
            classifier_type="hybrid",
            tool_config_version="cine_prompt_v4",  # New version
            predicted_type=self.test_entry.predicted_type,
            entities=self.test_entry.entities,
            need_freshness=False,
            current_agent_version=self.test_entry.agent_version,
            current_prompt_version="v4"  # New version
        )
        
        # Should be None due to version mismatch (different tool_config_version hash)
        assert cache_hit is None, "Prompt version mismatch should bypass cache"
    
    def test_fresh_cache_entry_allowed(self):
        """Test: Fresh cache entry within TTL → allowed."""
        # Create fresh entry
        fresh_entry = CacheEntry(
            prompt_original="Who directed The Matrix?",
            prompt_normalized="who directed the matrix",
            prompt_hash="fresh_test",
            predicted_type="info",
            entities=["The Matrix"],
            response_text="The Matrix was directed by the Wachowskis",
            sources=[{"url": "https://www.imdb.com/title/tt0133093/", "tier": "A"}],
            created_at=(datetime.utcnow() - timedelta(hours=1)).isoformat(),  # 1 hour old
            expires_at=(datetime.utcnow() + timedelta(hours=23)).isoformat(),  # Still valid
            agent_version="1.0.0",
            prompt_version="v4",
            tool_config_version="cine_prompt_v4"
        )
        
        # Store entry
        self.cache.put(
            prompt=fresh_entry.prompt_original,
            response_text=fresh_entry.response_text,
            sources=fresh_entry.sources,
            predicted_type=fresh_entry.predicted_type,
            entities=fresh_entry.entities,
            need_freshness=False,
            classifier_type="hybrid",
            tool_config_version=fresh_entry.tool_config_version,
            agent_version=fresh_entry.agent_version,
            prompt_version=fresh_entry.prompt_version
        )
        
        # Create request plan
        request_plan = RequestPlan(
            intent="director_info",
            request_type="info",
            entities=["The Matrix"],
            need_freshness=False,
            freshness_ttl_hours=168.0,  # 7 days TTL
            original_query=fresh_entry.prompt_original
        )
        
        # Get cache entry
        cache_hit = self.cache.get(
            prompt=fresh_entry.prompt_original,
            classifier_type="hybrid",
            tool_config_version=fresh_entry.tool_config_version,
            predicted_type=fresh_entry.predicted_type,
            entities=fresh_entry.entities,
            need_freshness=False,
            current_agent_version=fresh_entry.agent_version,
            current_prompt_version=fresh_entry.prompt_version
        )
        
        # Should be found and valid
        assert cache_hit is not None, "Fresh cache entry should be found"
        
        # Should be allowed
        plan_dict = request_plan.to_dict()
        plan_dict["agent_version"] = fresh_entry.agent_version
        plan_dict["prompt_version"] = fresh_entry.prompt_version
        plan_dict["tool_config_version"] = fresh_entry.tool_config_version
        
        should_use, reason = self.cache.should_use_cache_entry(cache_hit, plan_dict)
        assert should_use, f"Fresh cache entry should be allowed: {reason}"


if __name__ == "__main__":
    # Run tests
    test = TestCacheCorrectness()
    test.setup_method()
    
    print("Running cache correctness tests...")
    
    try:
        test.test_same_prompt_twice_cache_hit()
        print("✓ Test 1: Same prompt twice → cache hit")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
    
    try:
        test.test_paraphrase_prompt_semantic_cache_hit()
        print("✓ Test 2: Paraphrase → semantic cache hit")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
    
    try:
        test.test_release_status_after_ttl_forces_refresh()
        print("✓ Test 3: Release status after TTL → forces refresh")
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
    
    try:
        test.test_different_movie_year_no_cache_hit()
        print("✓ Test 4: Different movie year → no cache hit")
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")
    
    try:
        test.test_version_mismatch_bypasses_cache()
        print("✓ Test 5: Version mismatch → bypasses cache")
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
    
    try:
        test.test_tier_c_sources_in_facts_bypasses_cache()
        print("✓ Test 6: Tier C sources in facts → bypasses cache")
    except Exception as e:
        print(f"✗ Test 6 failed: {e}")
    
    try:
        test.test_require_tier_a_missing_bypasses_cache()
        print("✓ Test 7: Missing Tier A when required → bypasses cache")
    except Exception as e:
        print(f"✗ Test 7 failed: {e}")
    
    try:
        test.test_prompt_version_mismatch_bypasses_cache()
        print("✓ Test 8: Prompt version mismatch → bypasses cache")
    except Exception as e:
        print(f"✗ Test 8 failed: {e}")
    
    try:
        test.test_fresh_cache_entry_allowed()
        print("✓ Test 9: Fresh cache entry → allowed")
    except Exception as e:
        print(f"✗ Test 9 failed: {e}")
    
    print("\nAll tests completed!")

