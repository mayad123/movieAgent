"""
Unit tests for Kaggle search regression tests.

Tests matching, normalization, Stage A/B pipeline, and row indexing.
"""
import pytest
import sys
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cinemind.search.kaggle_search import (
    KaggleDatasetSearcher, 
    normalize_title, 
    tokenize,
    STAGE_A_CANDIDATE_LIMIT
)


class TestKaggleSearchFixtures:
    """Helper functions for creating test dataframes."""
    
    @staticmethod
    def create_test_dataframe() -> pd.DataFrame:
        """
        Create a small in-memory dataframe representing Kaggle IMDB dataset.
        
        Returns:
            DataFrame with Title, Year, Director, Genre, Star Cast, Rating columns
        """
        data = {
            "Title": [
                "Inglourious Basterds",
                "The Matrix",
                "Inception",
                "Pulp Fiction",
                "The Dark Knight",
                "Fight Club",
                "Se7en",
                "WALL·E",
                "The Shawshank Redemption",
                "Forrest Gump"
            ],
            "Year": [2009, 1999, 2010, 1994, 2008, 1999, 1995, 2008, 1994, 1994],
            "Director": [
                "Quentin Tarantino",
                "Lana Wachowski, Lilly Wachowski",
                "Christopher Nolan",
                "Quentin Tarantino",
                "Christopher Nolan",
                "David Fincher",
                "David Fincher",
                "Andrew Stanton",
                "Frank Darabont",
                "Robert Zemeckis"
            ],
            "Genre": [
                "Action, Drama, War",
                "Action, Sci-Fi",
                "Action, Adventure, Sci-Fi",
                "Crime, Drama",
                "Action, Crime, Drama",
                "Drama",
                "Crime, Drama, Mystery",
                "Animation, Adventure, Family",
                "Drama",
                "Drama, Romance"
            ],
            "Star Cast": [
                "Brad Pitt, Christoph Waltz, Mélanie Laurent",
                "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss",
                "Leonardo DiCaprio, Marion Cotillard, Tom Hardy",
                "John Travolta, Uma Thurman, Samuel L. Jackson",
                "Christian Bale, Heath Ledger, Aaron Eckhart",
                "Brad Pitt, Edward Norton, Helena Bonham Carter",
                "Brad Pitt, Morgan Freeman, Gwyneth Paltrow",
                "Ben Burtt, Elissa Knight, Jeff Garlin",
                "Tim Robbins, Morgan Freeman, Bob Gunton",
                "Tom Hanks, Robin Wright, Gary Sinise"
            ],
            "Rating": [8.3, 8.7, 8.8, 8.9, 9.0, 8.8, 8.6, 8.4, 9.3, 8.8]
        }
        return pd.DataFrame(data)
    
    @staticmethod
    def create_dataframe_with_punctuation() -> pd.DataFrame:
        """Create dataframe with titles that have punctuation."""
        data = {
            "Title": [
                "WALL·E",
                "Se7en",
                "The Matrix: Reloaded",
                "Spider-Man: Homecoming",
                "Dr. Strangelove"
            ],
            "Year": [2008, 1995, 2003, 2017, 1964],
            "Director": [
                "Andrew Stanton",
                "David Fincher",
                "Lana Wachowski, Lilly Wachowski",
                "Jon Watts",
                "Stanley Kubrick"
            ],
            "Genre": ["Animation", "Crime", "Action", "Action", "Comedy"],
            "Star Cast": ["Ben Burtt", "Brad Pitt", "Keanu Reeves", "Tom Holland", "Peter Sellers"],
            "Rating": [8.4, 8.6, 7.2, 7.4, 8.4]
        }
        return pd.DataFrame(data)


class TestExactMatch:
    """Tests for exact title matching."""
    
    @pytest.fixture
    def searcher(self):
        """Create KaggleDatasetSearcher instance."""
        return KaggleDatasetSearcher()
    
    @pytest.fixture
    def test_df(self):
        """Create test dataframe."""
        return TestKaggleSearchFixtures.create_test_dataframe()
    
    def test_exact_match_inglourious_basterds(self, searcher, test_df):
        """Test that exact match 'Inglourious Basterds' returns correct row and director."""
        # Set the dataset directly
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "Inglourious Basterds"
        results, max_correlation = searcher.search(query, max_results=5)
        
        # Should return at least one result
        assert len(results) > 0, \
            f"Should return results for exact match, got: {len(results)}"
        
        # Check that the result is correct
        top_result = results[0]
        assert "Inglourious Basterds" in top_result["title"], \
            f"Top result should be 'Inglourious Basterds', got: {top_result['title']}"
        
        # Check director field
        assert "Quentin Tarantino" in top_result["content"], \
            f"Result should contain director 'Quentin Tarantino', got: {top_result['content']}"
        
        # Check correlation is high for exact match
        assert max_correlation >= 0.7, \
            f"Exact match should have high correlation, got: {max_correlation}"
    
    def test_exact_match_returns_correct_row_data(self, searcher, test_df):
        """Test that exact match returns correct row data fields."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "The Matrix"
        results, _ = searcher.search(query, max_results=1)
        
        assert len(results) > 0, "Should return result"
        top_result = results[0]
        
        # Check that key fields are present
        assert "The Matrix" in top_result["title"], \
            f"Title should match, got: {top_result['title']}"
        assert "1999" in top_result["content"] or "Year: 1999" in top_result["content"], \
            f"Should contain year 1999, got: {top_result['content']}"
        assert "Wachowski" in top_result["content"], \
            f"Should contain director, got: {top_result['content']}"


class TestQueryNormalization:
    """Tests for query normalization (punctuation, casing)."""
    
    @pytest.fixture
    def searcher(self):
        """Create KaggleDatasetSearcher instance."""
        return KaggleDatasetSearcher()
    
    @pytest.fixture
    def test_df(self):
        """Create test dataframe with punctuation."""
        return TestKaggleSearchFixtures.create_dataframe_with_punctuation()
    
    def test_normalization_handles_punctuation(self, searcher, test_df):
        """Test that query normalization handles punctuation correctly."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        # Test with punctuation in query
        query = "WALL·E"
        results, _ = searcher.search(query, max_results=5)
        
        # Should find WALL·E despite punctuation
        assert len(results) > 0, \
            f"Should find results for 'WALL·E', got: {len(results)}"
        assert any("WALL" in r["title"] or "wall" in r["title"].lower() for r in results), \
            f"Should find WALL·E, got: {[r['title'] for r in results]}"
    
    def test_normalization_handles_casing(self, searcher, test_df):
        """Test that query normalization handles casing correctly."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        # Test with different casing
        query = "wall·e"  # Lowercase
        results, _ = searcher.search(query, max_results=5)
        
        # Should find WALL·E despite different casing
        assert len(results) > 0, \
            f"Should find results for lowercase query, got: {len(results)}"
        assert any("WALL" in r["title"] or "wall" in r["title"].lower() for r in results), \
            f"Should find WALL·E with lowercase query, got: {[r['title'] for r in results]}"
    
    def test_normalization_se7en(self, searcher, test_df):
        """Test normalization with Se7en (number in title)."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "Se7en"
        results, _ = searcher.search(query, max_results=5)
        
        # Should find Se7en
        assert len(results) > 0, \
            f"Should find Se7en, got: {len(results)}"
        assert any("Se7en" in r["title"] or "se7en" in r["title"].lower() for r in results), \
            f"Should find Se7en, got: {[r['title'] for r in results]}"
    
    def test_normalize_title_function(self):
        """Test normalize_title function directly."""
        # Test punctuation removal
        assert normalize_title("WALL·E") == "walle", \
            f"Should remove middle dot, got: {normalize_title('WALL·E')}"
        assert normalize_title("Se7en") == "se7en", \
            f"Should keep numbers, got: {normalize_title('Se7en')}"
        assert normalize_title("Spider-Man: Homecoming") == "spiderman homecoming", \
            f"Should remove hyphens and colons, got: {normalize_title('Spider-Man: Homecoming')}"
        
        # Test casing
        assert normalize_title("The Matrix") == "the matrix", \
            f"Should lowercase, got: {normalize_title('The Matrix')}"
        
        # Test whitespace
        assert normalize_title("  The   Matrix  ") == "the matrix", \
            f"Should normalize whitespace, got: {normalize_title('  The   Matrix  ')}"


class TestStageACandidateRetrieval:
    """Tests for Stage A candidate retrieval."""
    
    @pytest.fixture
    def searcher(self):
        """Create KaggleDatasetSearcher instance."""
        return KaggleDatasetSearcher()
    
    @pytest.fixture
    def test_df(self):
        """Create test dataframe."""
        return TestKaggleSearchFixtures.create_test_dataframe()
    
    def test_stage_a_produces_candidates_exact_match(self, searcher, test_df):
        """Test that Stage A produces candidates for exact match."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "Inglourious Basterds"
        candidates = searcher._stage_a_candidate_retrieval(query, top_n=10)
        
        # Should have candidates
        assert len(candidates) > 0, \
            f"Stage A should produce candidates, got: {len(candidates)}"
        
        # Top candidate should be exact match
        top_candidate = candidates[0]
        row_idx, score, reason = top_candidate
        assert score == 1.0, \
            f"Exact match should have score 1.0, got: {score}"
        assert reason == "exact_title", \
            f"Exact match should have reason 'exact_title', got: {reason}"
    
    def test_stage_a_produces_candidates_substring_match(self, searcher, test_df):
        """Test that Stage A produces candidates for substring match."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "Matrix"  # Substring of "The Matrix"
        candidates = searcher._stage_a_candidate_retrieval(query, top_n=10)
        
        # Should have candidates
        assert len(candidates) > 0, \
            f"Stage A should produce candidates for substring, got: {len(candidates)}"
        
        # Should find "The Matrix"
        found_matrix = any(
            test_df.iloc[row_idx]["Title"] == "The Matrix" 
            for row_idx, _, _ in candidates
        )
        assert found_matrix, \
            f"Should find 'The Matrix' in candidates, got: {[test_df.iloc[r[0]]['Title'] for r in candidates]}"
    
    def test_stage_a_limits_candidates(self, searcher, test_df):
        """Test that Stage A limits candidates to top_n."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "movie"  # Generic query that might match many
        candidates = searcher._stage_a_candidate_retrieval(query, top_n=5)
        
        # Should not exceed top_n
        assert len(candidates) <= 5, \
            f"Should limit to top_n=5, got: {len(candidates)}"
    
    def test_stage_a_token_overlap(self, searcher, test_df):
        """Test that Stage A uses token overlap matching."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "Dark Knight"  # Should match "The Dark Knight" via token overlap
        candidates = searcher._stage_a_candidate_retrieval(query, top_n=10)
        
        # Should have candidates
        assert len(candidates) > 0, \
            f"Stage A should produce candidates via token overlap, got: {len(candidates)}"
        
        # Should find "The Dark Knight"
        found_dark_knight = any(
            test_df.iloc[row_idx]["Title"] == "The Dark Knight" 
            for row_idx, _, _ in candidates
        )
        assert found_dark_knight, \
            f"Should find 'The Dark Knight' via token overlap, got: {[test_df.iloc[r[0]]['Title'] for r in candidates]}"


class TestStageBLimitedScoring:
    """Tests for Stage B limited scoring (only top-N candidates)."""
    
    @pytest.fixture
    def searcher(self):
        """Create KaggleDatasetSearcher instance."""
        return KaggleDatasetSearcher()
    
    @pytest.fixture
    def test_df(self):
        """Create test dataframe."""
        return TestKaggleSearchFixtures.create_test_dataframe()
    
    def test_stage_b_only_scores_top_n_candidates(self, searcher, test_df):
        """Test that Stage B only scores top-N candidates from Stage A."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        # Mock _calculate_correlation to track calls
        correlation_calls = []
        original_calculate = searcher._calculate_correlation
        
        def tracked_calculate(query, row_dict):
            correlation_calls.append((query, row_dict.get("Title", "")))
            return original_calculate(query, row_dict)
        
        searcher._calculate_correlation = tracked_calculate
        
        # Use a query that will match multiple titles (e.g., "The" matches "The Matrix", "The Dark Knight", etc.)
        query = "The"
        results, _ = searcher.search(query, max_results=5)
        
        # Should only call _calculate_correlation for Stage A candidates (limited to STAGE_A_CANDIDATE_LIMIT)
        assert len(correlation_calls) <= STAGE_A_CANDIDATE_LIMIT, \
            f"Should only score top {STAGE_A_CANDIDATE_LIMIT} candidates, got: {len(correlation_calls)}"
        
        # Should have called it at least once
        assert len(correlation_calls) > 0, \
            "Should call _calculate_correlation at least once"
    
    def test_stage_b_limits_to_stage_a_candidates(self, searcher, test_df):
        """Test that Stage B is limited to Stage A candidate count."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        # Get Stage A candidates first
        query = "movie"
        stage_a_candidates = searcher._stage_a_candidate_retrieval(query, top_n=STAGE_A_CANDIDATE_LIMIT)
        
        # Track correlation calls
        correlation_calls = []
        original_calculate = searcher._calculate_correlation
        
        def tracked_calculate(query, row_dict):
            correlation_calls.append(row_dict.get("Title", ""))
            return original_calculate(query, row_dict)
        
        searcher._calculate_correlation = tracked_calculate
        
        # Run full search
        results, _ = searcher.search(query, max_results=5)
        
        # Should not exceed Stage A candidate count
        assert len(correlation_calls) <= len(stage_a_candidates), \
            f"Should not score more than Stage A candidates ({len(stage_a_candidates)}), got: {len(correlation_calls)}"
        assert len(correlation_calls) <= STAGE_A_CANDIDATE_LIMIT, \
            f"Should not exceed STAGE_A_CANDIDATE_LIMIT ({STAGE_A_CANDIDATE_LIMIT}), got: {len(correlation_calls)}"


class TestRowIndexingRegression:
    """Regression tests for row indexing (prevent iloc/loc mismatch)."""
    
    @pytest.fixture
    def searcher(self):
        """Create KaggleDatasetSearcher instance."""
        return KaggleDatasetSearcher()
    
    @pytest.fixture
    def test_df(self):
        """Create test dataframe."""
        return TestKaggleSearchFixtures.create_test_dataframe()
    
    def test_row_indexing_uses_iloc_correctly(self, searcher, test_df):
        """
        Regression test: Ensure row selection uses correct indexing (iloc, not loc).
        
        This prevents bugs where iloc/loc mismatch causes wrong rows to be selected.
        """
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        # Get Stage A candidates (which return row indices)
        query = "Inglourious Basterds"
        candidates = searcher._stage_a_candidate_retrieval(query, top_n=5)
        
        assert len(candidates) > 0, "Should have candidates"
        
        # Test that iloc[row_idx] returns the correct row
        for row_idx, score, reason in candidates:
            # This is what happens in search() method: df.iloc[row_idx]
            row = test_df.iloc[row_idx]
            row_dict = row.to_dict()
            
            # Verify the row matches what we expect
            # For exact match, should be "Inglourious Basterds"
            if score == 1.0 and reason == "exact_title":
                assert row_dict["Title"] == "Inglourious Basterds", \
                    f"Row index {row_idx} should be 'Inglourious Basterds', got: {row_dict['Title']}"
                assert row_dict["Director"] == "Quentin Tarantino", \
                    f"Row index {row_idx} should have correct director, got: {row_dict['Director']}"
    
    def test_row_indexing_with_non_sequential_indices(self, searcher):
        """
        Regression test: Ensure indexing works correctly even with non-sequential indices.
        
        This tests the case where dataframe might have been filtered/reindexed.
        """
        # Create dataframe with non-sequential index
        data = {
            "Title": ["Movie A", "Movie B", "Movie C"],
            "Year": [2000, 2001, 2002],
            "Director": ["Director A", "Director B", "Director C"],
            "Genre": ["Action", "Drama", "Comedy"],
            "Star Cast": ["Actor A", "Actor B", "Actor C"],
            "Rating": [8.0, 8.5, 9.0]
        }
        df = pd.DataFrame(data, index=[10, 20, 30])  # Non-sequential indices
        
        searcher._dataset = df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        # Search for a movie
        query = "Movie B"
        candidates = searcher._stage_a_candidate_retrieval(query, top_n=5)
        
        assert len(candidates) > 0, "Should have candidates"
        
        # Test that iloc works correctly with non-sequential index
        for row_idx, score, reason in candidates:
            # iloc uses positional index (0, 1, 2), not label index (10, 20, 30)
            # row_idx from _stage_a_candidate_retrieval should be positional
            row = df.iloc[row_idx]
            row_dict = row.to_dict()
            
            # Verify we can access the row correctly
            assert "Title" in row_dict, \
                f"Row should have Title field, got: {list(row_dict.keys())}"
            assert row_dict["Title"] in ["Movie A", "Movie B", "Movie C"], \
                f"Row should be one of the test movies, got: {row_dict['Title']}"
    
    def test_row_indexing_in_search_method(self, searcher, test_df):
        """
        Regression test: Ensure search() method uses iloc correctly.
        
        This directly tests the line: row = df.iloc[row_idx] in search() method.
        """
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "The Matrix"
        results, _ = searcher.search(query, max_results=5)
        
        # Should return results
        assert len(results) > 0, "Should return results"
        
        # Verify results have correct data
        top_result = results[0]
        assert "The Matrix" in top_result["title"], \
            f"Top result should be 'The Matrix', got: {top_result['title']}"
        assert "1999" in top_result["content"] or "Year: 1999" in top_result["content"], \
            f"Should contain year 1999, got: {top_result['content']}"


class TestQueryUsesTitle:
    """Tests that query matching uses title field correctly."""
    
    @pytest.fixture
    def searcher(self):
        """Create KaggleDatasetSearcher instance."""
        return KaggleDatasetSearcher()
    
    @pytest.fixture
    def test_df(self):
        """Create test dataframe."""
        return TestKaggleSearchFixtures.create_test_dataframe()
    
    def test_query_matches_title_field(self, searcher, test_df):
        """Test that query matching primarily uses Title field."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        query = "Pulp Fiction"
        results, _ = searcher.search(query, max_results=5)
        
        # Should find "Pulp Fiction"
        assert len(results) > 0, "Should return results"
        assert any("Pulp Fiction" in r["title"] for r in results), \
            f"Should find 'Pulp Fiction', got: {[r['title'] for r in results]}"
    
    def test_title_index_built_correctly(self, searcher, test_df):
        """Test that title index is built from Title column."""
        searcher._dataset = test_df
        searcher._dataset_loaded = True
        searcher._build_title_index()
        
        # Check that index was built
        assert searcher._title_index_loaded, "Title index should be loaded"
        assert len(searcher._normalized_title_index) > 0, \
            f"Should have normalized titles in index, got: {len(searcher._normalized_title_index)}"
        assert len(searcher._token_index) > 0, \
            f"Should have tokens in index, got: {len(searcher._token_index)}"
        
        # Check that "Inglourious Basterds" is in index
        normalized = normalize_title("Inglourious Basterds")
        found_in_index = any(
            normalized_title == normalized 
            for normalized_title in searcher._normalized_title_index.values()
        )
        assert found_in_index, \
            f"Should have 'Inglourious Basterds' in normalized index"

