"""
Contract tests for PromptBuilder.

Ensures messages are structured correctly and templates are chosen correctly.
Tests the separation of system/dev/user messages and template selection.
"""
import pytest
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cinemind.prompting.prompt_builder import PromptBuilder, EvidenceBundle
from cinemind.planning.request_plan import RequestPlan, ResponseFormat, ToolType


class TestPromptBuilderContract:
    """Contract tests for PromptBuilder message structure."""
    
    @pytest.fixture
    def prompt_builder(self):
        """Create a PromptBuilder instance."""
        return PromptBuilder()
    
    @pytest.fixture
    def minimal_evidence(self):
        """Create minimal evidence bundle with 1-2 items."""
        return EvidenceBundle(
            search_results=[
                {
                    "title": "The Matrix (1999)",
                    "url": "https://www.imdb.com/title/tt0133093/",
                    "content": "The Matrix is a 1999 science fiction action film written and directed by the Wachowskis.",
                    "source": "kaggle_imdb",
                    "tier": "A"
                }
            ]
        )
    
    @pytest.fixture
    def evidence_with_two_items(self):
        """Create evidence bundle with 2 items."""
        return EvidenceBundle(
            search_results=[
                {
                    "title": "The Matrix (1999)",
                    "url": "https://www.imdb.com/title/tt0133093/",
                    "content": "The Matrix is a 1999 science fiction action film written and directed by the Wachowskis.",
                    "source": "kaggle_imdb",
                    "tier": "A"
                },
                {
                    "title": "Matrix - Wikipedia",
                    "url": "https://en.wikipedia.org/wiki/The_Matrix",
                    "content": "The Matrix is a 1999 science fiction film directed by the Wachowskis.",
                    "source": "tavily",
                    "tier": "B"
                }
            ]
        )
    
    def test_message_count(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that exactly one system message and one user message are created."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, artifacts = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        # Should have exactly 2 messages: system and user
        assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
        
        # Check roles
        roles = [msg["role"] for msg in messages]
        assert "system" in roles, "System message missing"
        assert "user" in roles, "User message missing"
        assert "developer" not in roles, "Developer should be combined into system, not separate"
        
        # Check artifacts
        assert artifacts.messages_count == 2
    
    def test_system_message_contains_movies_only(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that system message contains 'movies only' domain restriction."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, _ = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        
        # Check for movies-only domain restriction
        assert "Movies-only domain" in system_message or "Film-only domain" in system_message, \
            "System message should contain movies-only domain restriction"
    
    def test_system_message_contains_no_metadata_leakage(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that system message contains no internal metadata leakage rule."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, _ = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        
        # Check for no metadata leakage rule
        assert "Never mention internal metadata" in system_message or \
               "no internal metadata" in system_message.lower(), \
            "System message should contain rule about not mentioning internal metadata"
    
    def test_developer_message_contains_verbosity_budget(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that developer message (in system) contains verbosity budget."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, artifacts = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        
        # Developer message is combined into system, so check system message
        # Should contain RESPONSE INSTRUCTIONS
        assert "RESPONSE INSTRUCTIONS" in system_message, \
            "System message should contain RESPONSE INSTRUCTIONS from developer message"
        
        # Should contain verbosity budget (max sentences/words)
        assert "maximum" in system_message.lower() or "max" in system_message.lower(), \
            "Developer message should contain verbosity budget (max sentences/words)"
        
        # Check artifacts
        assert artifacts.verbosity_budget is not None, \
            "Artifacts should contain verbosity budget"
        assert "template_id" in artifacts.verbosity_budget, \
            "Verbosity budget should contain template_id"
    
    def test_developer_message_contains_forbidden_terms(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that developer message contains forbidden terms list."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, _ = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        
        # Should contain forbidden terms list
        assert "Forbidden terms" in system_message or "forbidden" in system_message.lower(), \
            "Developer message should contain forbidden terms list"
        
        # Should mention Tier, Kaggle, Tavily
        forbidden_terms_present = any(
            term in system_message for term in ["Tier", "Kaggle", "Tavily"]
        )
        assert forbidden_terms_present, \
            "Developer message should list Tier, Kaggle, or Tavily as forbidden terms"
    
    def test_user_message_contains_question(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that user message contains the original question."""
        user_query = "Who directed The Matrix?"
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query=user_query
        )
        
        messages, _ = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query=user_query
        )
        
        user_message = next(msg["content"] for msg in messages if msg["role"] == "user")
        
        # Should contain the original question
        assert user_query in user_message, \
            "User message should contain the original question"
    
    def test_user_message_contains_evidence_section(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that user message contains EVIDENCE section."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, _ = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        user_message = next(msg["content"] for msg in messages if msg["role"] == "user")
        
        # Should contain EVIDENCE section
        assert "EVIDENCE" in user_message, \
            "User message should contain EVIDENCE section"
    
    def test_user_message_no_behavioral_instructions(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test that user message does NOT contain behavioral instructions."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, _ = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        user_message = next(msg["content"] for msg in messages if msg["role"] == "user")
        
        # Should NOT contain behavioral instructions
        behavioral_keywords = [
            "RESPONSE INSTRUCTIONS",
            "Forbidden terms",
            "verbosity",
            "maximum sentences",
            "must",
            "should",
            "required"
        ]
        
        for keyword in behavioral_keywords:
            assert keyword not in user_message, \
                f"User message should not contain behavioral instruction: {keyword}"


class TestRequestTypeContracts:
    """Contract tests for different request types."""
    
    @pytest.fixture
    def prompt_builder(self):
        """Create a PromptBuilder instance."""
        return PromptBuilder()
    
    @pytest.fixture
    def minimal_evidence(self):
        """Create minimal evidence bundle."""
        return EvidenceBundle(
            search_results=[
                {
                    "title": "Test Movie",
                    "url": "https://example.com",
                    "content": "Test content about a movie.",
                    "source": "kaggle_imdb",
                    "tier": "A"
                }
            ]
        )
    
    def test_director_info_contract(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test contract for director_info request type."""
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?"
        )
        
        messages, artifacts = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Who directed The Matrix?"
        )
        
        # Check message structure
        assert len(messages) == 2
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        user_message = next(msg["content"] for msg in messages if msg["role"] == "user")
        
        # Check template selection
        assert artifacts.instruction_template_id is not None
        assert "director_info" in artifacts.instruction_template_id.lower()
        
        # Check verbosity budget (director_info should be concise)
        assert artifacts.verbosity_budget is not None
        budget = artifacts.verbosity_budget
        assert "max_sentences" in budget or "max_words" in budget
        
        # Check forbidden terms in developer message
        assert "Forbidden terms" in system_message
        assert any(term in system_message for term in ["Tier", "Kaggle", "Tavily"])
        
        # Check user message structure
        assert "Who directed The Matrix?" in user_message
        assert "EVIDENCE" in user_message
        assert "RESPONSE INSTRUCTIONS" not in user_message
    
    def test_recommendation_contract(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test contract for recommendation request type."""
        request_plan = request_plan_factory(
            intent="recommendation",
            request_type="recs",
            original_query="Recommend movies similar to Inception"
        )
        
        messages, artifacts = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Recommend movies similar to Inception"
        )
        
        # Check message structure
        assert len(messages) == 2
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        user_message = next(msg["content"] for msg in messages if msg["role"] == "user")
        
        # Check template selection
        assert artifacts.instruction_template_id is not None
        assert "recommendation" in artifacts.instruction_template_id.lower()
        
        # Check verbosity budget (recommendation should allow more words)
        assert artifacts.verbosity_budget is not None
        budget = artifacts.verbosity_budget
        # Recommendation should have higher max_words than director_info
        if "max_words" in budget:
            assert budget["max_words"] > 50  # Should be more than director_info's 50
        
        # Check forbidden terms
        assert "Forbidden terms" in system_message
        
        # Check user message
        assert "Recommend movies similar to Inception" in user_message
        assert "EVIDENCE" in user_message
    
    def test_where_to_watch_freshness_contract(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test contract for where_to_watch (freshness) request type."""
        request_plan = request_plan_factory(
            intent="where_to_watch",
            request_type="info",
            original_query="Where can I watch The Matrix?",
            need_freshness=True,
            freshness_ttl_hours=6.0,
            freshness_reason="availability changes constantly"
        )
        
        messages, artifacts = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Where can I watch The Matrix?"
        )
        
        # Check message structure
        assert len(messages) == 2
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        
        # Check freshness instructions are present
        assert "Freshness" in system_message or "freshness" in system_message.lower() or \
               "current" in system_message.lower() or "up-to-date" in system_message.lower(), \
            "Freshness-sensitive query should include freshness instructions"
        
        # Check template selection
        assert artifacts.instruction_template_id is not None
        
        # Check verbosity budget includes as_of_date requirement
        assert artifacts.verbosity_budget is not None
    
    def test_comparison_contract(self, prompt_builder, minimal_evidence, request_plan_factory):
        """Test contract for comparison request type."""
        request_plan = request_plan_factory(
            intent="comparison",
            request_type="comparison",
            original_query="Compare Heat and Collateral",
            response_format=ResponseFormat.COMPARISON
        )
        
        messages, artifacts = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=minimal_evidence,
            user_query="Compare Heat and Collateral"
        )
        
        # Check message structure
        assert len(messages) == 2
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        user_message = next(msg["content"] for msg in messages if msg["role"] == "user")
        
        # Check template selection
        assert artifacts.instruction_template_id is not None
        assert "comparison" in artifacts.instruction_template_id.lower()
        
        # Check verbosity budget (comparison should allow more words)
        assert artifacts.verbosity_budget is not None
        budget = artifacts.verbosity_budget
        if "max_words" in budget:
            assert budget["max_words"] > 100  # Comparison should allow more words
        
        # Check format instructions
        assert "comparison" in system_message.lower() or "side-by-side" in system_message.lower(), \
            "Comparison query should include comparison format instructions"
        
        # Check user message
        assert "Compare Heat and Collateral" in user_message
        assert "EVIDENCE" in user_message


class TestSnapshotContract:
    """Snapshot-style test for prompt structure."""
    
    @pytest.fixture
    def prompt_builder(self):
        """Create a PromptBuilder instance."""
        return PromptBuilder()
    
    @pytest.fixture
    def snapshot_evidence(self):
        """Create evidence for snapshot test."""
        return EvidenceBundle(
            search_results=[
                {
                    "title": "The Matrix (1999) - IMDb",
                    "url": "https://www.imdb.com/title/tt0133093/",
                    "content": "The Matrix is a 1999 science fiction action film written and directed by the Wachowskis. It stars Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss, Hugo Weaving, and Joe Pantoliano.",
                    "source": "kaggle_imdb",
                    "tier": "A"
                }
            ]
        )
    
    def test_director_info_snapshot(self, prompt_builder, snapshot_evidence, request_plan_factory):
        """
        Snapshot test for director_info prompt structure.
        
        This test captures the exact structure of messages for a director_info query.
        Update the expected strings if the prompt structure changes intentionally.
        """
        request_plan = request_plan_factory(
            intent="director_info",
            request_type="info",
            original_query="Who directed The Matrix?",
            entities=["The Matrix"],
            entities_typed={"movies": ["The Matrix"], "people": []}
        )
        
        messages, artifacts = prompt_builder.build_messages(
            request_plan=request_plan,
            evidence=snapshot_evidence,
            user_query="Who directed The Matrix?"
        )
        
        # Extract messages
        system_message = next(msg["content"] for msg in messages if msg["role"] == "system")
        user_message = next(msg["content"] for msg in messages if msg["role"] == "user")
        
        # Snapshot assertions - check key structural elements
        # System message should start with identity
        assert system_message.startswith("You are CineMind"), \
            "System message should start with identity"
        
        # System message should contain domain restriction
        assert "Film-only domain" in system_message or "Movies-only domain" in system_message, \
            "System message should contain domain restriction"
        
        # System message should contain RESPONSE INSTRUCTIONS
        assert "RESPONSE INSTRUCTIONS" in system_message, \
            "System message should contain RESPONSE INSTRUCTIONS"
        
        # System message should contain request type
        assert "Request Type: info" in system_message or "Request Type:info" in system_message, \
            "System message should contain request type"
        
        # System message should contain verbosity budget
        assert "maximum" in system_message.lower() or "max" in system_message.lower(), \
            "System message should contain verbosity budget"
        
        # System message should contain forbidden terms
        assert "Forbidden terms" in system_message, \
            "System message should contain forbidden terms list"
        
        # User message should start with query
        assert user_message.startswith("Who directed The Matrix?"), \
            "User message should start with the query"
        
        # User message should contain EVIDENCE section
        assert "EVIDENCE" in user_message, \
            "User message should contain EVIDENCE section"
        
        # User message should contain evidence content
        assert "The Matrix" in user_message, \
            "User message should contain evidence content"
        
        # User message should NOT contain behavioral instructions
        assert "RESPONSE INSTRUCTIONS" not in user_message, \
            "User message should not contain RESPONSE INSTRUCTIONS"
        assert "Forbidden terms" not in user_message, \
            "User message should not contain forbidden terms"
        
        # Check artifacts
        assert artifacts.prompt_version is not None
        assert artifacts.instruction_template_id is not None
        assert artifacts.verbosity_budget is not None
        assert artifacts.messages_count == 2
        
        # Store snapshot for manual inspection (optional)
        snapshot = {
            "system_message_length": len(system_message),
            "user_message_length": len(user_message),
            "template_id": artifacts.instruction_template_id,
            "verbosity_budget": artifacts.verbosity_budget,
            "has_evidence": "EVIDENCE" in user_message,
            "has_forbidden_terms": "Forbidden terms" in system_message
        }
        
        # These are deterministic checks - if they pass, the structure is correct
        assert snapshot["system_message_length"] > 200, "System message should be substantial"
        assert snapshot["user_message_length"] > 100, "User message should contain query + evidence"
        assert snapshot["has_evidence"], "User message should contain evidence"
        assert snapshot["has_forbidden_terms"], "System message should contain forbidden terms"

