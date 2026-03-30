"""
Unit tests for EvidenceFormatter.

Tests deduplication, truncation, and source label formatting.
"""
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cinemind.prompting.evidence_formatter import EvidenceFormatter
from cinemind.prompting.prompt_builder import EvidenceBundle


class TestEvidenceFormatterFixtures:
    """Fixture builder helpers for creating test evidence."""

    @staticmethod
    def create_result(title: str, url: str, content: str, source: str = "unknown",
                     tier: str = "UNKNOWN", year: int | None = None) -> dict:
        """Create a single search result dictionary."""
        result = {
            "title": title,
            "url": url,
            "content": content,
            "source": source,
            "tier": tier
        }
        if year:
            result["year"] = year
        return result

    @staticmethod
    def create_evidence_bundle(results: list) -> EvidenceBundle:
        """Create an EvidenceBundle from a list of results."""
        return EvidenceBundle(search_results=results)

    @staticmethod
    def create_long_content(length: int = 500) -> str:
        """Create a long content string for truncation tests."""
        base = "This is a test sentence. " * (length // 25)
        return base[:length]


class TestDeduplication:
    """Tests for deduplication of evidence items."""

    @pytest.fixture
    def formatter(self):
        """Create EvidenceFormatter instance."""
        return EvidenceFormatter()

    def test_deduplicate_same_url(self, formatter):
        """Test that items with same URL are deduplicated."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "Content about The Matrix",
                source="kaggle_imdb"
            ),
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix (1999)",
                "https://www.imdb.com/title/tt0133093/",
                "Different content about The Matrix",
                source="tavily"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should only have one item (first occurrence kept)
        assert formatted.count("[1]") == 1, "Should have only one item after deduplication"
        assert "[2]" not in formatted, "Second duplicate should be removed"

    def test_deduplicate_same_title_and_year(self, formatter):
        """Test that items with same title and year are deduplicated."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://example.com/matrix1",
                "Content 1",
                source="kaggle_imdb",
                year=1999
            ),
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://example.com/matrix2",
                "Content 2",
                source="tavily",
                year=1999
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should only have one item
        assert formatted.count("[1]") == 1
        assert "[2]" not in formatted

    def test_deduplicate_url_with_query_params(self, formatter):
        """Test that URLs with query parameters are normalized for deduplication."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/?ref_=fn_al_tt_1",
                "Content 1",
                source="kaggle_imdb"
            ),
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "Content 2",
                source="tavily"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should be deduplicated (query params removed)
        assert formatted.count("[1]") == 1
        assert "[2]" not in formatted

    def test_keep_different_items(self, formatter):
        """Test that different items are kept."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "Content about The Matrix",
                source="kaggle_imdb",
                year=1999
            ),
            TestEvidenceFormatterFixtures.create_result(
                "Inception",
                "https://www.imdb.com/title/tt1375666/",
                "Content about Inception",
                source="kaggle_imdb",
                year=2010
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should have both items
        assert formatted.count("[1]") == 1
        assert formatted.count("[2]") == 1
        assert "The Matrix" in formatted
        assert "Inception" in formatted


class TestTruncation:
    """Tests for content truncation."""

    @pytest.fixture
    def formatter(self):
        """Create EvidenceFormatter with custom max length."""
        return EvidenceFormatter(max_snippet_length=100)

    def test_truncate_long_content(self, formatter):
        """Test that long content is truncated."""
        long_content = TestEvidenceFormatterFixtures.create_long_content(500)
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "Test Movie",
                "https://example.com",
                long_content,
                source="kaggle_imdb"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Content should be truncated
        assert "Content:" in formatted
        content_section = formatted.split("Content:\n")[1].split("\n")[0]
        assert len(content_section) <= 103, f"Content should be truncated to ~100 chars, got {len(content_section)}"

    def test_truncate_at_sentence_boundary(self, formatter):
        """Test that truncation tries to break at sentence boundaries."""
        # Create content with sentences that would be cut mid-sentence
        content = "First sentence. Second sentence. Third sentence. " * 10
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "Test Movie",
                "https://example.com",
                content,
                source="kaggle_imdb"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should truncate at sentence boundary (ends with period)
        content_section = formatted.split("Content:\n")[1].split("\n")[0]
        # Should end with period or ellipsis
        assert content_section.endswith(".") or content_section.endswith("..."), \
            f"Content should end at sentence boundary, got: {content_section[-10:]}"

    def test_no_truncation_for_short_content(self, formatter):
        """Test that short content is not truncated."""
        short_content = "This is short content."
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "Test Movie",
                "https://example.com",
                short_content,
                source="kaggle_imdb"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Content should be unchanged
        assert short_content in formatted
        assert "..." not in formatted

    def test_truncate_at_word_boundary(self, formatter):
        """Test that truncation falls back to word boundary if sentence boundary is too short."""
        # Create content without sentence boundaries in the first 70% of max_length
        content = "word " * 200  # Long content without periods
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "Test Movie",
                "https://example.com",
                content,
                source="kaggle_imdb"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should truncate at word boundary (ends with space or ellipsis)
        content_section = formatted.split("Content:\n")[1].split("\n")[0]
        assert content_section.endswith("...") or content_section.endswith(" "), \
            f"Content should end at word boundary, got: {content_section[-10:]}"


class TestSourceLabelFormatting:
    """Tests for source label formatting."""

    @pytest.fixture
    def formatter(self):
        """Create EvidenceFormatter instance."""
        return EvidenceFormatter()

    def test_no_internal_terms_in_output(self, formatter):
        """Test that output does not contain internal terms like 'Tier A', 'Kaggle', 'Tavily'."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "Content about The Matrix",
                source="kaggle_imdb",
                tier="A"
            ),
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://en.wikipedia.org/wiki/The_Matrix",
                "Wikipedia content",
                source="tavily",
                tier="B"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should not contain internal terms
        assert "Tier A" not in formatted, "Output should not contain 'Tier A'"
        assert "Tier B" not in formatted, "Output should not contain 'Tier B'"
        assert "Tier C" not in formatted, "Output should not contain 'Tier C'"
        assert "Kaggle" not in formatted, "Output should not contain 'Kaggle'"
        assert "Tavily" not in formatted, "Output should not contain 'Tavily'"
        assert "tier" not in formatted.lower(), "Output should not contain 'tier'"

    def test_kaggle_imdb_label(self, formatter):
        """Test that kaggle_imdb source is labeled as 'Structured IMDb dataset'."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "Content",
                source="kaggle_imdb",
                tier="A"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should show friendly label
        assert "Structured IMDb dataset" in formatted or "IMDb" in formatted, \
            f"Should show friendly label, got: {formatted}"
        assert "kaggle_imdb" not in formatted, "Should not show technical source name"

    def test_imdb_com_label(self, formatter):
        """Test that imdb.com URLs are labeled as 'IMDb'."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "Content",
                source="tavily",  # Tavily source, but URL infers IMDb
                tier="A"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should infer from URL
        assert "IMDb" in formatted, f"Should infer IMDb from URL, got: {formatted}"
        assert "Tavily" not in formatted, "Should not show Tavily"

    def test_wikipedia_label(self, formatter):
        """Test that wikipedia.org URLs are labeled as 'Wikipedia'."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://en.wikipedia.org/wiki/The_Matrix",
                "Content",
                source="tavily",
                tier="B"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should infer from URL
        assert "Wikipedia" in formatted, f"Should infer Wikipedia from URL, got: {formatted}"
        assert "Tavily" not in formatted, "Should not show Tavily"

    def test_mixed_sources(self, formatter):
        """Test formatting with mixed sources: imdb.com, wikipedia.org, kaggle_imdb."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "IMDb content",
                source="kaggle_imdb",
                tier="A"
            ),
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://en.wikipedia.org/wiki/The_Matrix",
                "Wikipedia content",
                source="tavily",
                tier="B"
            ),
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.imdb.com/title/tt0133093/",
                "Another IMDb content",
                source="imdb",
                tier="A"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should have friendly labels
        assert "IMDb" in formatted or "Structured IMDb dataset" in formatted
        assert "Wikipedia" in formatted

        # Should not have internal terms
        assert "Tier A" not in formatted
        assert "Tier B" not in formatted
        assert "Kaggle" not in formatted
        assert "Tavily" not in formatted

    def test_unknown_source_with_url(self, formatter):
        """Test that unknown source with recognizable URL gets inferred label."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://www.rottentomatoes.com/m/the_matrix",
                "Rotten Tomatoes content",
                source="unknown",
                tier="C"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should infer from URL
        assert "Rotten Tomatoes" in formatted, f"Should infer from URL, got: {formatted}"
        assert "unknown" not in formatted, "Should not show 'unknown'"


class TestInsideOutExclusion:
    """Tests for Inside Out vs Inside Out 2 handling."""

    @pytest.fixture
    def formatter(self):
        """Create EvidenceFormatter instance."""
        return EvidenceFormatter()

    def test_inside_out_vs_inside_out_2_separate(self, formatter):
        """
        Test that Inside Out and Inside Out 2 are treated as separate items.

        Note: EvidenceFormatter doesn't filter - it formats what's in the bundle.
        Filtering should happen at the search/candidate extraction level.
        This test verifies that if both are present, they are formatted separately.
        """
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "Inside Out (2015)",
                "https://www.imdb.com/title/tt2096673/",
                "Inside Out is a 2015 animated film directed by Pete Docter.",
                source="kaggle_imdb",
                year=2015
            ),
            TestEvidenceFormatterFixtures.create_result(
                "Inside Out 2 (2024)",
                "https://www.imdb.com/title/tt1464335/",
                "Inside Out 2 is a 2024 animated film sequel.",
                source="kaggle_imdb",
                year=2024
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Both should be formatted (formatter doesn't filter)
        assert "Inside Out (2015)" in formatted or "Inside Out" in formatted
        assert "Inside Out 2" in formatted

        # Should have both items
        assert formatted.count("[1]") == 1
        assert formatted.count("[2]") == 1

    def test_inside_out_director_query_formatting(self, formatter):
        """
        Test formatting for 'Inside Out director' query.

        In a real scenario, 'Inside Out 2' should be filtered out before
        reaching the formatter. This test verifies that if only 'Inside Out'
        is in the bundle, it's formatted correctly.
        """
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "Inside Out (2015)",
                "https://www.imdb.com/title/tt2096673/",
                "Inside Out is a 2015 animated film directed by Pete Docter.",
                source="kaggle_imdb",
                year=2015
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should format Inside Out correctly
        assert "Inside Out" in formatted
        assert "Pete Docter" in formatted or "directed" in formatted

        # Should NOT contain Inside Out 2
        assert "Inside Out 2" not in formatted

    def test_inside_out_2_excluded_when_not_relevant(self, formatter):
        """
        Test that Inside Out 2 is excluded when query is about Inside Out director.

        This demonstrates the expected behavior: if the evidence bundle only
        contains Inside Out (after filtering), Inside Out 2 should not appear.
        """
        # Simulate filtered results (only Inside Out, no Inside Out 2)
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "Inside Out (2015)",
                "https://www.imdb.com/title/tt2096673/",
                "Inside Out is a 2015 animated film directed by Pete Docter.",
                source="kaggle_imdb",
                year=2015
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should only have Inside Out
        assert "Inside Out" in formatted
        assert "Inside Out 2" not in formatted

        # Should have exactly one item
        assert formatted.count("[1]") == 1
        assert "[2]" not in formatted


class TestEvidenceFormatterEdgeCases:
    """Edge case tests for EvidenceFormatter."""

    @pytest.fixture
    def formatter(self):
        """Create EvidenceFormatter instance."""
        return EvidenceFormatter()

    def test_empty_evidence_bundle(self, formatter):
        """Test that empty evidence bundle returns empty string."""
        bundle = EvidenceBundle(search_results=[])
        formatted = formatter.format(bundle)

        assert formatted == "", "Empty bundle should return empty string"

    def test_no_content_results(self, formatter):
        """Test that results with no content are skipped."""
        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://example.com",
                "",  # Empty content
                source="kaggle_imdb"
            ),
            TestEvidenceFormatterFixtures.create_result(
                "Inception",
                "https://example.com",
                "Has content",
                source="kaggle_imdb"
            )
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = formatter.format(bundle)

        # Should only have item with content
        assert "Inception" in formatted
        assert "The Matrix" not in formatted or formatted.count("[") == 1

    def test_max_items_limit(self, formatter):
        """Test that max_items limit is respected."""
        limited_formatter = EvidenceFormatter(max_items=2)

        results = [
            TestEvidenceFormatterFixtures.create_result(
                f"Movie {i}",
                f"https://example.com/movie{i}",
                f"Content {i}",
                source="kaggle_imdb"
            )
            for i in range(5)
        ]

        bundle = TestEvidenceFormatterFixtures.create_evidence_bundle(results)
        formatted = limited_formatter.format(bundle)

        # Should only have 2 items
        assert formatted.count("[1]") == 1
        assert formatted.count("[2]") == 1
        assert "[3]" not in formatted

    def test_verified_facts_included(self, formatter):
        """Test that verified facts are included in output."""
        # Create a mock verified fact object
        class MockVerifiedFact:
            def __init__(self, value, verified=True):
                self.value = value
                self.verified = verified

        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://example.com",
                "Content",
                source="kaggle_imdb"
            )
        ]

        bundle = EvidenceBundle(
            search_results=results,
            verified_facts=[MockVerifiedFact("The Matrix was released in 1999")]
        )

        formatted = formatter.format(bundle)

        # Should include verified facts section
        assert "VERIFIED INFORMATION" in formatted
        assert "The Matrix was released in 1999" in formatted

    def test_verified_facts_limit(self, formatter):
        """Test that verified facts are limited to top 5."""
        class MockVerifiedFact:
            def __init__(self, value, verified=True):
                self.value = value
                self.verified = verified

        results = [
            TestEvidenceFormatterFixtures.create_result(
                "The Matrix",
                "https://example.com",
                "Content",
                source="kaggle_imdb"
            )
        ]

        bundle = EvidenceBundle(
            search_results=results,
            verified_facts=[MockVerifiedFact(f"Fact {i}") for i in range(10)]
        )

        formatted = formatter.format(bundle)

        # Should have verified facts section
        assert "VERIFIED INFORMATION" in formatted

        # Should only show first 5
        fact_count = formatted.count("- Fact")
        assert fact_count <= 5, f"Should limit to 5 facts, got {fact_count}"

