"""
Unit tests for SourcePolicy.

Tests source filtering based on RequestPlan constraints (require_tier_a, reject_tier_c, allowed_tiers).
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cinemind.planning.source_policy import SourceConstraints, SourcePolicy, SourceTier


class TestSourcePolicyFixtures:
    """Helper functions for creating test evidence items."""

    @staticmethod
    def create_evidence_item(
        url: str, tier: str, title: str = "Test Title", content: str = "Test content", source: str = "unknown"
    ) -> dict:
        """
        Create a single evidence item dictionary.

        Args:
            url: Source URL
            tier: Tier value ("A", "B", "C", or "UNKNOWN")
            title: Source title
            content: Source content
            source: Source name (e.g., "kaggle_imdb", "tavily")

        Returns:
            Dictionary representing a search result
        """
        return {"url": url, "title": title, "content": content, "source": source, "tier": tier, "score": 0.8}

    @staticmethod
    def create_tier_a_evidence() -> list:
        """Create list of Tier A evidence items."""
        return [
            TestSourcePolicyFixtures.create_evidence_item(
                url="https://www.imdb.com/title/tt0133093/",
                tier="A",
                title="The Matrix (1999)",
                content="The Matrix is a 1999 science fiction film.",
                source="kaggle_imdb",
            ),
            TestSourcePolicyFixtures.create_evidence_item(
                url="https://en.wikipedia.org/wiki/The_Matrix",
                tier="A",
                title="The Matrix - Wikipedia",
                content="The Matrix is a 1999 science fiction action film.",
                source="tavily",
            ),
        ]

    @staticmethod
    def create_tier_b_evidence() -> list:
        """Create list of Tier B evidence items."""
        return [
            TestSourcePolicyFixtures.create_evidence_item(
                url="https://www.variety.com/movie/the-matrix",
                tier="B",
                title="The Matrix Review",
                content="Review of The Matrix film.",
                source="tavily",
            ),
            TestSourcePolicyFixtures.create_evidence_item(
                url="https://www.rottentomatoes.com/m/the_matrix",
                tier="B",
                title="The Matrix - Rotten Tomatoes",
                content="The Matrix ratings and reviews.",
                source="tavily",
            ),
        ]

    @staticmethod
    def create_tier_c_evidence() -> list:
        """Create list of Tier C evidence items."""
        return [
            TestSourcePolicyFixtures.create_evidence_item(
                url="https://www.reddit.com/r/movies/the-matrix",
                tier="C",
                title="The Matrix Discussion",
                content="Reddit discussion about The Matrix.",
                source="tavily",
            ),
            TestSourcePolicyFixtures.create_evidence_item(
                url="https://www.quora.com/what-is-the-matrix",
                tier="C",
                title="What is The Matrix?",
                content="Quora answer about The Matrix.",
                source="tavily",
            ),
        ]

    @staticmethod
    def create_unknown_tier_evidence() -> list:
        """Create list of UNKNOWN tier evidence items."""
        return [
            TestSourcePolicyFixtures.create_evidence_item(
                url="https://example.com/movie",
                tier="UNKNOWN",
                title="Example Movie Site",
                content="Content from unknown source.",
                source="tavily",
            )
        ]

    @staticmethod
    def create_mixed_tier_evidence() -> list:
        """Create list with mixed tiers (A, B, C, UNKNOWN)."""
        return (
            TestSourcePolicyFixtures.create_tier_a_evidence()
            + TestSourcePolicyFixtures.create_tier_b_evidence()
            + TestSourcePolicyFixtures.create_tier_c_evidence()
            + TestSourcePolicyFixtures.create_unknown_tier_evidence()
        )


class TestRequireTierA:
    """Tests for require_tier_a constraint."""

    @pytest.fixture
    def policy(self):
        """Create SourcePolicy instance."""
        return SourcePolicy()

    def test_require_tier_a_returns_only_tier_a(self, policy):
        """Test that require_tier_a=true returns only Tier A sources."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B", "C"], require_tier_a=True, reject_tier_c=False)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should only have Tier A sources
        assert len(filtered_sources) > 0, "Should have some Tier A sources"
        assert all(s.tier == SourceTier.TIER_A for s in filtered_sources), (
            f"All sources should be Tier A, got: {[s.tier.value for s in filtered_sources]}"
        )

        # Check metadata
        assert metadata["tiers_used_in_evidence"]["A"] == len(filtered_sources), "All used sources should be Tier A"
        assert metadata["tiers_used_in_evidence"]["B"] == 0, "Should not use Tier B sources"
        assert metadata["tiers_used_in_evidence"]["C"] == 0, "Should not use Tier C sources"
        assert metadata["missing_required_tier"] is False, "Should not flag missing required tier when Tier A exists"

    def test_require_tier_a_returns_empty_when_none(self, policy):
        """Test that require_tier_a=true returns empty list when no Tier A sources exist."""
        # Only Tier B and C evidence
        evidence = TestSourcePolicyFixtures.create_tier_b_evidence() + TestSourcePolicyFixtures.create_tier_c_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B", "C"], require_tier_a=True, reject_tier_c=False)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should return empty list
        assert len(filtered_sources) == 0, (
            f"Should return empty list when no Tier A sources, got: {len(filtered_sources)}"
        )

        # Should set missing_required_tier flag
        assert metadata["missing_required_tier"] is True, "Should set missing_required_tier flag when no Tier A sources"

        # Check filtering reasons
        assert any("No Tier A sources found" in reason for reason in metadata["filtering_reasons"]), (
            f"Should mention missing Tier A in reasons, got: {metadata['filtering_reasons']}"
        )

    def test_require_tier_a_with_only_tier_a_evidence(self, policy):
        """Test require_tier_a with only Tier A evidence."""
        evidence = TestSourcePolicyFixtures.create_tier_a_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A"], require_tier_a=True, reject_tier_c=True)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should return all Tier A sources
        assert len(filtered_sources) == len(evidence), f"Should return all Tier A sources, got: {len(filtered_sources)}"
        assert all(s.tier == SourceTier.TIER_A for s in filtered_sources), "All sources should be Tier A"
        assert metadata["missing_required_tier"] is False, "Should not flag missing required tier"


class TestRejectTierC:
    """Tests for reject_tier_c constraint."""

    @pytest.fixture
    def policy(self):
        """Create SourcePolicy instance."""
        return SourcePolicy()

    def test_reject_tier_c_removes_tier_c(self, policy):
        """Test that reject_tier_c=True removes Tier C sources."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B", "C"], require_tier_a=False, reject_tier_c=True)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should not have Tier C sources
        assert all(s.tier != SourceTier.TIER_C for s in filtered_sources), (
            f"Should not have Tier C sources, got: {[s.tier.value for s in filtered_sources]}"
        )

        # Check metadata
        assert metadata["tiers_used_in_evidence"]["C"] == 0, "Should not use Tier C sources"
        assert any(
            "tier C" in reason.lower() or "tier_c_rejected" in reason.lower()
            for reason in metadata["filtering_reasons"]
        ), f"Should mention Tier C rejection in reasons, got: {metadata['filtering_reasons']}"

    def test_reject_tier_c_allows_other_tiers(self, policy):
        """Test that reject_tier_c only removes Tier C, keeps A and B."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B", "C"], require_tier_a=False, reject_tier_c=True)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should have Tier A and B sources
        tier_a_count = sum(1 for s in filtered_sources if s.tier == SourceTier.TIER_A)
        tier_b_count = sum(1 for s in filtered_sources if s.tier == SourceTier.TIER_B)

        assert tier_a_count > 0, "Should have Tier A sources"
        assert tier_b_count > 0, "Should have Tier B sources"
        assert metadata["tiers_used_in_evidence"]["A"] == tier_a_count
        assert metadata["tiers_used_in_evidence"]["B"] == tier_b_count

    def test_reject_tier_c_false_allows_tier_c(self, policy):
        """Test that reject_tier_c=False allows Tier C sources."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B", "C"], require_tier_a=False, reject_tier_c=False)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should have Tier C sources
        tier_c_count = sum(1 for s in filtered_sources if s.tier == SourceTier.TIER_C)
        assert tier_c_count > 0, f"Should have Tier C sources when reject_tier_c=False, got: {tier_c_count}"
        assert metadata["tiers_used_in_evidence"]["C"] == tier_c_count


class TestAllowedTiers:
    """Tests for allowed_source_tiers filtering."""

    @pytest.fixture
    def policy(self):
        """Create SourcePolicy instance."""
        return SourcePolicy()

    def test_allowed_tiers_filters_correctly(self, policy):
        """Test that allowed_source_tiers filters sources correctly."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(
            allowed_source_tiers=["A", "B"],  # Only A and B allowed
            require_tier_a=False,
            reject_tier_c=True,
        )

        filtered_sources, _metadata = policy.rank_and_filter(evidence, constraints)

        # Should only have Tier A and B
        assert all(s.tier in [SourceTier.TIER_A, SourceTier.TIER_B] for s in filtered_sources), (
            f"Should only have Tier A and B, got: {[s.tier.value for s in filtered_sources]}"
        )

        # Should not have Tier C or UNKNOWN
        assert all(s.tier != SourceTier.TIER_C for s in filtered_sources), "Should not have Tier C"
        assert all(s.tier != SourceTier.UNKNOWN for s in filtered_sources), "Should not have UNKNOWN tier"

    def test_allowed_tiers_only_a(self, policy):
        """Test that allowed_source_tiers=["A"] only allows Tier A."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A"], require_tier_a=False, reject_tier_c=True)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should only have Tier A
        assert all(s.tier == SourceTier.TIER_A for s in filtered_sources), (
            f"Should only have Tier A, got: {[s.tier.value for s in filtered_sources]}"
        )
        assert metadata["tiers_used_in_evidence"]["A"] == len(filtered_sources)
        assert metadata["tiers_used_in_evidence"]["B"] == 0
        assert metadata["tiers_used_in_evidence"]["C"] == 0

    def test_allowed_tiers_all_tiers(self, policy):
        """Test that allowed_source_tiers=["A", "B", "C"] allows all tiers."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(
            allowed_source_tiers=["A", "B", "C"],
            require_tier_a=False,
            reject_tier_c=False,  # Don't reject C
        )

        filtered_sources, _metadata = policy.rank_and_filter(evidence, constraints)

        # Should have A, B, and C (but not UNKNOWN)
        tier_a_count = sum(1 for s in filtered_sources if s.tier == SourceTier.TIER_A)
        tier_b_count = sum(1 for s in filtered_sources if s.tier == SourceTier.TIER_B)
        tier_c_count = sum(1 for s in filtered_sources if s.tier == SourceTier.TIER_C)

        assert tier_a_count > 0, "Should have Tier A"
        assert tier_b_count > 0, "Should have Tier B"
        assert tier_c_count > 0, "Should have Tier C"
        assert all(s.tier != SourceTier.UNKNOWN for s in filtered_sources), "Should not have UNKNOWN tier"


class TestUnknownTierRemoval:
    """Tests for UNKNOWN tier removal."""

    @pytest.fixture
    def policy(self):
        """Create SourcePolicy instance."""
        return SourcePolicy()

    def test_unknown_tier_removed_when_not_allowed(self, policy):
        """Test that UNKNOWN tier is removed when not in allowed_source_tiers."""
        evidence = TestSourcePolicyFixtures.create_unknown_tier_evidence()
        constraints = SourceConstraints(
            allowed_source_tiers=["A", "B"],  # UNKNOWN not allowed
            require_tier_a=False,
            reject_tier_c=True,
        )

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should be empty (no allowed tiers)
        assert len(filtered_sources) == 0, f"Should remove UNKNOWN tier when not allowed, got: {len(filtered_sources)}"

        # Check metadata
        assert metadata["tiers_used_in_evidence"]["UNKNOWN"] == 0, "Should not use UNKNOWN tier"
        assert any(
            "tier_not_allowed" in reason.lower() or "UNKNOWN" in reason for reason in metadata["filtering_reasons"]
        ), f"Should mention UNKNOWN removal in reasons, got: {metadata['filtering_reasons']}"

    def test_unknown_tier_not_in_allowed_list(self, policy):
        """Test that UNKNOWN tier is never in allowed_source_tiers by default."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(
            allowed_source_tiers=["A", "B", "C"],  # UNKNOWN not included
            require_tier_a=False,
            reject_tier_c=False,
        )

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should not have UNKNOWN tier
        assert all(s.tier != SourceTier.UNKNOWN for s in filtered_sources), (
            f"Should not have UNKNOWN tier, got: {[s.tier.value for s in filtered_sources]}"
        )
        assert metadata["tiers_used_in_evidence"]["UNKNOWN"] == 0, "Should not use UNKNOWN tier"


class TestCombinedConstraints:
    """Tests for combined constraints."""

    @pytest.fixture
    def policy(self):
        """Create SourcePolicy instance."""
        return SourcePolicy()

    def test_require_tier_a_and_reject_tier_c(self, policy):
        """Test require_tier_a=True with reject_tier_c=True."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B", "C"], require_tier_a=True, reject_tier_c=True)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should only have Tier A (require_tier_a takes precedence)
        assert all(s.tier == SourceTier.TIER_A for s in filtered_sources), (
            "Should only have Tier A when require_tier_a=True"
        )
        assert metadata["tiers_used_in_evidence"]["A"] == len(filtered_sources)
        assert metadata["tiers_used_in_evidence"]["B"] == 0
        assert metadata["tiers_used_in_evidence"]["C"] == 0

    def test_allowed_tiers_and_reject_tier_c(self, policy):
        """Test allowed_source_tiers with reject_tier_c=True."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(
            allowed_source_tiers=["A", "B", "C"],  # C is allowed
            require_tier_a=False,
            reject_tier_c=True,  # But rejected
        )

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should not have Tier C (reject_tier_c overrides allowed_source_tiers)
        assert all(s.tier != SourceTier.TIER_C for s in filtered_sources), (
            "Should not have Tier C when reject_tier_c=True"
        )
        assert metadata["tiers_used_in_evidence"]["C"] == 0


class TestMetadataAndReasons:
    """Tests for metadata and filtering reasons."""

    @pytest.fixture
    def policy(self):
        """Create SourcePolicy instance."""
        return SourcePolicy()

    def test_metadata_tracks_tiers_present(self, policy):
        """Test that metadata tracks tiers present in candidates."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B", "C"], require_tier_a=False, reject_tier_c=False)

        _filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should track tiers present
        assert "tiers_present_in_candidates" in metadata, "Should track tiers present in candidates"
        assert metadata["tiers_present_in_candidates"]["A"] > 0, "Should have Tier A in candidates"
        assert metadata["tiers_present_in_candidates"]["B"] > 0, "Should have Tier B in candidates"
        assert metadata["tiers_present_in_candidates"]["C"] > 0, "Should have Tier C in candidates"

    def test_metadata_tracks_tiers_used(self, policy):
        """Test that metadata tracks tiers used in evidence."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B"], require_tier_a=False, reject_tier_c=True)

        filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should track tiers used
        assert "tiers_used_in_evidence" in metadata, "Should track tiers used in evidence"
        assert metadata["tiers_used_in_evidence"]["A"] == sum(
            1 for s in filtered_sources if s.tier == SourceTier.TIER_A
        ), "Tier A count should match"
        assert metadata["tiers_used_in_evidence"]["B"] == sum(
            1 for s in filtered_sources if s.tier == SourceTier.TIER_B
        ), "Tier B count should match"

    def test_filtering_reasons_explained(self, policy):
        """Test that filtering_reasons explains why sources were filtered."""
        evidence = TestSourcePolicyFixtures.create_mixed_tier_evidence()
        constraints = SourceConstraints(allowed_source_tiers=["A", "B"], require_tier_a=False, reject_tier_c=True)

        _filtered_sources, metadata = policy.rank_and_filter(evidence, constraints)

        # Should have filtering reasons
        assert "filtering_reasons" in metadata, "Should have filtering_reasons"
        assert len(metadata["filtering_reasons"]) > 0, "Should have at least one filtering reason"

        # Should mention tier_not_allowed or tier_c_rejected
        reasons_text = " ".join(metadata["filtering_reasons"]).lower()
        assert "tier" in reasons_text or "removed" in reasons_text, (
            f"Should mention tier filtering, got: {metadata['filtering_reasons']}"
        )
