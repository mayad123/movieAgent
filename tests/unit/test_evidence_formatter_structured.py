"""
Unit tests for EvidenceFormatter structured metadata.

Tests that EvidenceFormatter returns structured metadata correctly,
including deduplication counts and snippet length tracking.
"""
import pytest
from cinemind.prompting.evidence_formatter import EvidenceFormatter, EvidenceFormatResult, FormattedEvidenceItem
from cinemind.prompting import EvidenceBundle


def test_format_returns_structured_result():
    """Test that format() returns EvidenceFormatResult."""
    formatter = EvidenceFormatter()
    bundle = EvidenceBundle(search_results=[
        {
            "title": "Test Movie",
            "url": "http://example.com/movie",
            "content": "This is test content for the movie.",
            "source": "test"
        }
    ])
    
    result = formatter.format(bundle)
    
    assert isinstance(result, EvidenceFormatResult)
    assert hasattr(result, "text")
    assert hasattr(result, "items")
    assert hasattr(result, "counts")
    assert hasattr(result, "max_snippet_len")
    assert hasattr(result, "dedupe_removed")
    assert len(result.text) > 0


def test_backward_compatibility_string_usage():
    """Test that EvidenceFormatResult can be used as a string."""
    formatter = EvidenceFormatter()
    bundle = EvidenceBundle(search_results=[
        {
            "title": "Test Movie",
            "url": "http://example.com/movie",
            "content": "This is test content.",
            "source": "test"
        }
    ])
    
    result = formatter.format(bundle)
    
    # Should work as string (backward compatibility)
    text = str(result)
    assert isinstance(text, str)
    assert len(text) > 0
    
    # Should work with len()
    assert len(result) > 0


def test_deduplication_counts():
    """Test that deduplication counts are tracked correctly."""
    formatter = EvidenceFormatter()
    
    # Create bundle with duplicates
    bundle = EvidenceBundle(search_results=[
        {
            "title": "The Matrix",
            "url": "http://example.com/matrix",
            "content": "Content 1",
            "source": "test",
            "year": 1999
        },
        {
            "title": "The Matrix",
            "url": "http://example.com/matrix",  # Same URL = duplicate
            "content": "Content 2",
            "source": "test",
            "year": 1999
        },
        {
            "title": "Inception",
            "url": "http://example.com/inception",
            "content": "Content 3",
            "source": "test",
            "year": 2010
        }
    ])
    
    result = formatter.format(bundle)
    
    assert result.counts["before"] == 3
    assert result.counts["after"] == 2  # One duplicate removed
    assert result.dedupe_removed == 1
    assert len(result.items) == 2


def test_max_snippet_length():
    """Test that max snippet length is tracked correctly."""
    formatter = EvidenceFormatter(max_snippet_length=50)
    
    bundle = EvidenceBundle(search_results=[
        {
            "title": "Movie 1",
            "url": "http://example.com/1",
            "content": "Short content.",
            "source": "test"
        },
        {
            "title": "Movie 2",
            "url": "http://example.com/2",
            "content": "This is a much longer piece of content that should be truncated to fit the max snippet length limit.",
            "source": "test"
        }
    ])
    
    result = formatter.format(bundle)
    
    # Max snippet length should be at most max_snippet_length
    assert result.max_snippet_len <= formatter.max_snippet_length
    # Should be at least the length of the shorter content
    assert result.max_snippet_len >= len("Short content.")


def test_formatted_item_metadata():
    """Test that FormattedEvidenceItem metadata is correct."""
    formatter = EvidenceFormatter()
    
    bundle = EvidenceBundle(search_results=[
        {
            "title": "Test Movie",
            "url": "http://example.com/movie",
            "content": "Test content here.",
            "source": "test",
            "year": 2020
        }
    ])
    
    result = formatter.format(bundle)
    
    assert len(result.items) == 1
    item = result.items[0]
    
    assert isinstance(item, FormattedEvidenceItem)
    assert item.url == "http://example.com/movie"
    assert item.title == "Test Movie"
    assert item.year == 2020
    assert item.snippet_len > 0
    assert item.index == 1


def test_empty_bundle():
    """Test that empty bundle returns empty result."""
    formatter = EvidenceFormatter()
    bundle = EvidenceBundle(search_results=[])
    
    result = formatter.format(bundle)
    
    assert isinstance(result, EvidenceFormatResult)
    assert result.text == ""
    assert result.counts["before"] == 0
    assert result.counts["after"] == 0
    assert result.max_snippet_len == 0
    assert len(result.items) == 0


def test_items_with_no_content_excluded():
    """Test that items with no content are excluded from items list."""
    formatter = EvidenceFormatter()
    
    bundle = EvidenceBundle(search_results=[
        {
            "title": "Movie 1",
            "url": "http://example.com/1",
            "content": "Has content",
            "source": "test"
        },
        {
            "title": "Movie 2",
            "url": "http://example.com/2",
            "content": "",  # No content
            "source": "test"
        }
    ])
    
    result = formatter.format(bundle)
    
    # Should only have 1 item (the one with content)
    assert result.counts["after"] == 1
    assert len(result.items) == 1
    assert result.items[0].title == "Movie 1"

