"""
Tests for search result deduplication in SearchEngine.
"""
import pytest
import asyncio
from typing import List, Dict
from src.cinemind.search_engine import SearchEngine, SearchDecision


class TestSearchDeduplication:
    """Test search result deduplication logic."""
    
    def test_deduplicate_results_by_url(self):
        """Test that results with same URL are deduplicated."""
        engine = SearchEngine(enable_kaggle=False)
        
        results = [
            {"title": "Movie A", "url": "https://example.com/movie-a", "score": 0.9, "source": "tavily"},
            {"title": "Movie A (duplicate)", "url": "https://example.com/movie-a", "score": 0.8, "source": "tavily"},
            {"title": "Movie B", "url": "https://example.com/movie-b", "score": 0.7, "source": "tavily"},
        ]
        
        deduplicated = engine._deduplicate_results(results)
        
        # Should only have 2 unique results (by URL)
        assert len(deduplicated) == 2
        # First result (highest score) should be kept
        assert deduplicated[0]["url"] == "https://example.com/movie-a"
        assert deduplicated[0]["score"] == 0.9
    
    def test_deduplicate_results_by_title_year_source(self):
        """Test that results without URL are deduplicated by title + year + source."""
        engine = SearchEngine(enable_kaggle=False)
        
        results = [
            {"title": "Movie A", "url": "", "score": 0.9, "source": "tavily", "published_date": "2024-01-01"},
            {"title": "Movie A", "url": "", "score": 0.8, "source": "tavily", "published_date": "2024-01-01"},
            {"title": "Movie A", "url": "", "score": 0.7, "source": "kaggle", "published_date": "2024-01-01"},
        ]
        
        deduplicated = engine._deduplicate_results(results)
        
        # Should have 2 unique results (different sources)
        assert len(deduplicated) == 2
        # Check that both sources are present
        sources = {r["source"] for r in deduplicated}
        assert "tavily" in sources
        assert "kaggle" in sources
    
    def test_deduplicate_results_empty_url(self):
        """Test that results with empty URL use fallback deduplication."""
        engine = SearchEngine(enable_kaggle=False)
        
        results = [
            {"title": "Movie A", "url": None, "score": 0.9, "source": "tavily"},
            {"title": "Movie A", "url": "", "score": 0.8, "source": "tavily"},
            {"title": "Movie B", "url": None, "score": 0.7, "source": "tavily"},
        ]
        
        deduplicated = engine._deduplicate_results(results)
        
        # Should have 2 unique results (Movie A and Movie B)
        assert len(deduplicated) == 2
        titles = {r["title"] for r in deduplicated}
        assert "Movie A" in titles
        assert "Movie B" in titles
    
    def test_sort_results_by_score(self):
        """Test that results are sorted by score (highest first)."""
        engine = SearchEngine(enable_kaggle=False)
        
        results = [
            {"title": "Movie A", "url": "https://example.com/a", "score": 0.7, "source": "tavily"},
            {"title": "Movie B", "url": "https://example.com/b", "score": 0.9, "source": "tavily"},
            {"title": "Movie C", "url": "https://example.com/c", "score": 0.5, "source": "tavily"},
        ]
        
        sorted_results = engine._sort_results_by_score(results)
        
        # Should be sorted by score descending
        assert sorted_results[0]["score"] == 0.9
        assert sorted_results[1]["score"] == 0.7
        assert sorted_results[2]["score"] == 0.5
        assert sorted_results[0]["title"] == "Movie B"
    
    def test_sort_results_stable_ordering(self):
        """Test that results with same score have stable ordering (by title)."""
        engine = SearchEngine(enable_kaggle=False)
        
        results = [
            {"title": "Movie B", "url": "https://example.com/b", "score": 0.9, "source": "tavily"},
            {"title": "Movie A", "url": "https://example.com/a", "score": 0.9, "source": "tavily"},
            {"title": "Movie C", "url": "https://example.com/c", "score": 0.9, "source": "tavily"},
        ]
        
        sorted_results = engine._sort_results_by_score(results)
        
        # Should be sorted by title (alphabetical) when scores are equal
        assert sorted_results[0]["title"] == "Movie A"
        assert sorted_results[1]["title"] == "Movie B"
        assert sorted_results[2]["title"] == "Movie C"
    
    def test_deduplicate_handles_missing_fields(self):
        """Test that deduplication handles missing fields gracefully."""
        engine = SearchEngine(enable_kaggle=False)
        
        results = [
            {"title": "Movie A", "url": None, "score": 0.9},  # Missing source
            {"title": None, "url": "https://example.com/a", "score": 0.8},  # Missing title
            {},  # Empty dict
            {"title": "Movie B", "url": "", "score": 0.7, "source": "tavily"},
        ]
        
        deduplicated = engine._deduplicate_results(results)
        
        # Should not crash and should handle missing fields
        assert len(deduplicated) > 0
        # All results should be dicts
        assert all(isinstance(r, dict) for r in deduplicated)
    
    @pytest.mark.asyncio
    async def test_search_movie_specific_deduplicates_overlapping_results(self):
        """Test that search_movie_specific deduplicates overlapping results from multiple queries."""
        # Create a mock search engine that returns overlapping results
        engine = SearchEngine(enable_kaggle=False)
        
        # Mock the search method to return overlapping results
        original_search = engine.search
        call_count = 0
        
        async def mock_search(query: str, max_results: int = 5, skip_tavily: bool = False, override_reason: str = None):
            nonlocal call_count
            call_count += 1
            # Return same result for different queries to simulate overlap
            if "IMDb" in query:
                return ([
                    {"title": "The Matrix", "url": "https://imdb.com/title/tt0133093", "score": 0.95, "source": "tavily"},
                    {"title": "The Matrix Reviews", "url": "https://imdb.com/title/tt0133093/reviews", "score": 0.85, "source": "tavily"},
                ], SearchDecision(tavily_used=True))
            elif "Rotten Tomatoes" in query:
                return ([
                    {"title": "The Matrix", "url": "https://imdb.com/title/tt0133093", "score": 0.90, "source": "tavily"},  # Duplicate URL
                    {"title": "The Matrix - Rotten Tomatoes", "url": "https://rottentomatoes.com/m/the_matrix", "score": 0.80, "source": "tavily"},
                ], SearchDecision(tavily_used=True))
            else:
                return ([
                    {"title": "The Matrix", "url": "https://imdb.com/title/tt0133093", "score": 0.88, "source": "tavily"},  # Duplicate URL
                ], SearchDecision(tavily_used=True))
        
        engine.search = mock_search
        
        results = await engine.search_movie_specific("The Matrix", year=1999)
        
        # Should deduplicate results with same URL
        urls = [r.get("url") for r in results if r.get("url")]
        unique_urls = set(urls)
        
        # Should not have duplicate URLs
        assert len(urls) == len(unique_urls), f"Found duplicate URLs: {urls}"
        
        # Should have results sorted by score
        if len(results) > 1:
            scores = [r.get("score", 0) for r in results]
            assert scores == sorted(scores, reverse=True), "Results not sorted by score"
    
    @pytest.mark.asyncio
    async def test_search_movie_specific_handles_empty_results(self):
        """Test that search_movie_specific handles empty results gracefully."""
        engine = SearchEngine(enable_kaggle=False)
        
        # Mock the search method to return empty results
        original_search = engine.search
        
        async def mock_search(query: str, max_results: int = 5, skip_tavily: bool = False, override_reason: str = None):
            return ([], SearchDecision(tavily_used=False))
        
        engine.search = mock_search
        
        results = await engine.search_movie_specific("Nonexistent Movie", year=9999)
        
        # Should return empty list, not crash
        assert isinstance(results, list)
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_search_movie_specific_handles_exceptions(self):
        """Test that search_movie_specific handles exceptions gracefully."""
        engine = SearchEngine(enable_kaggle=False)
        
        # Mock the search method to raise exceptions
        original_search = engine.search
        
        async def mock_search(query: str, max_results: int = 5, skip_tavily: bool = False, override_reason: str = None):
            raise Exception("Search failed")
        
        engine.search = mock_search
        
        results = await engine.search_movie_specific("Test Movie")
        
        # Should return empty list, not crash
        assert isinstance(results, list)
        assert len(results) == 0

