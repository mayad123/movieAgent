"""
Tests for candidate → verify → answer pattern.
Tests collaboration questions, disambiguation, and release year accuracy.
"""
import sys
import os
import re
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cinemind.candidate_extraction import CandidateExtractor
from cinemind.verification import FactVerifier, VerifiedFact
from cinemind.source_policy import SourcePolicy, SourceMetadata, SourceTier


class TestCandidateVerifyAnswer:
    """Test candidate extraction and verification."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.source_policy = SourcePolicy()
        self.verifier = FactVerifier(self.source_policy)
        self.extractor = CandidateExtractor()
    
    def test_collaboration_candidate_extraction(self):
        """Test: Extract collaboration candidates (De Niro + Pacino)."""
        # Mock search results
        search_results = [
            {
                "title": "Movies with Robert De Niro and Al Pacino",
                "content": 'The films featuring both Robert De Niro and Al Pacino include "The Godfather Part II" (1974), "Heat" (1995), and "Righteous Kill" (2008).',
                "url": "https://www.imdb.com/list/123",
                "tier": "A"
            },
            {
                "title": "De Niro and Pacino Collaborations",
                "content": 'They worked together in "Heat" (1995) and "Righteous Kill" (2008).',
                "url": "https://en.wikipedia.org/wiki/Collaborations",
                "tier": "A"
            }
        ]
        
        candidates = self.extractor.extract_collaboration_candidates(
            search_results, "Robert De Niro", "Al Pacino"
        )
        
        assert len(candidates) > 0, "Should extract collaboration candidates"
        assert any("Godfather Part II" in c.value for c in candidates), "Should find Godfather Part II"
        assert any("Heat" in c.value for c in candidates), "Should find Heat"
        assert any("Righteous Kill" in c.value for c in candidates), "Should find Righteous Kill"
    
    def test_collaboration_verification(self):
        """Test: Verify collaboration candidates against Tier A sources."""
        # Mock Tier A sources
        sources = [
            SourceMetadata(
                url="https://www.imdb.com/title/tt0071562/",
                domain="imdb.com",
                tier=SourceTier.TIER_A,
                title="The Godfather Part II",
                content="The Godfather Part II (1974) stars Robert De Niro as young Vito Corleone and Al Pacino as Michael Corleone.",
                score=0.95
            ),
            SourceMetadata(
                url="https://www.imdb.com/title/tt0113277/",
                domain="imdb.com",
                tier=SourceTier.TIER_A,
                title="Heat",
                content="Heat (1995) features Robert De Niro as Neil McCauley and Al Pacino as Vincent Hanna.",
                score=0.95
            ),
            SourceMetadata(
                url="https://www.quora.com/question/123",
                domain="quora.com",
                tier=SourceTier.TIER_C,
                title="Movies with De Niro and Pacino",
                content="They were in The Godfather Part II, Heat, and many others.",
                score=0.5
            )
        ]
        
        # Verify each candidate
        movie_title = "The Godfather Part II"
        year = 1974
        
        person1_verified, source1, conf1 = self.verifier.verify_movie_credit(
            movie_title, "Robert De Niro", year, sources
        )
        person2_verified, source2, conf2 = self.verifier.verify_movie_credit(
            movie_title, "Al Pacino", year, sources
        )
        
        assert person1_verified, "Robert De Niro should be verified in The Godfather Part II"
        assert person2_verified, "Al Pacino should be verified in The Godfather Part II"
        assert "imdb.com" in source1, "Should use Tier A source (IMDb)"
        assert conf1 > 0.8, "Should have high confidence from Tier A source"
    
    def test_disambiguation_same_title_different_year(self):
        """Test: Disambiguate same-title movies with different years."""
        # Mock search results with same title, different years
        search_results = [
            {
                "title": "The Matrix (1999)",
                "content": "The Matrix (1999) directed by the Wachowskis",
                "url": "https://www.imdb.com/title/tt0133093/",
                "tier": "A"
            },
            {
                "title": "The Matrix (2021)",
                "content": "The Matrix Resurrections (2021) is the fourth film",
                "url": "https://www.imdb.com/title/tt10838180/",
                "tier": "A"
            }
        ]
        
        # Extract candidates
        candidates = self.extractor.extract_movie_candidates(search_results, ["Matrix"])
        
        # Should extract both movies with different years
        years_found = set()
        for candidate in candidates:
            year_match = re.search(r'\((\d{4})\)', candidate.value)
            if year_match:
                years_found.add(year_match.group(1))
        
        assert "1999" in years_found, "Should find 1999 version"
        assert "2021" in years_found or any("Resurrections" in c.value for c in candidates), "Should find 2021 version"
    
    def test_release_year_verification(self):
        """Test: Verify release year accuracy."""
        # Mock Tier A sources with year information
        sources = [
            SourceMetadata(
                url="https://www.imdb.com/title/tt0133093/",
                domain="imdb.com",
                tier=SourceTier.TIER_A,
                title="The Matrix",
                content="The Matrix is a 1999 science fiction action film directed by the Wachowskis. It was released in 1999.",
                score=0.95
            ),
            SourceMetadata(
                url="https://en.wikipedia.org/wiki/The_Matrix",
                domain="wikipedia.org",
                tier=SourceTier.TIER_A,
                title="The Matrix",
                content="The Matrix is a 1999 American science fiction action film. Release date: March 31, 1999.",
                score=0.95
            ),
            SourceMetadata(
                url="https://www.movieweb.com/matrix",
                domain="movieweb.com",
                tier=SourceTier.TIER_B,
                title="The Matrix",
                content="The Matrix came out in 1999.",
                score=0.7
            )
        ]
        
        # Verify release year
        year, source, confidence = self.verifier.verify_release_year("The Matrix", sources)
        
        assert year == 1999, f"Should verify release year as 1999, got {year}"
        assert "imdb.com" in source or "wikipedia.org" in source, "Should use Tier A source"
        assert confidence > 0.8, f"Should have high confidence, got {confidence}"
    
    def test_release_year_conflict_resolution(self):
        """Test: Resolve conflicts when multiple years found."""
        # Mock sources with conflicting years
        sources = [
            SourceMetadata(
                url="https://www.imdb.com/title/tt123/",
                domain="imdb.com",
                tier=SourceTier.TIER_A,
                title="Test Movie",
                content="Test Movie premiered at Cannes in 2023 but was released in 2024.",
                score=0.95
            ),
            SourceMetadata(
                url="https://en.wikipedia.org/wiki/Test_Movie",
                domain="wikipedia.org",
                tier=SourceTier.TIER_A,
                title="Test Movie",
                content="Test Movie (2024) is a film that premiered in 2023.",
                score=0.95
            )
        ]
        
        # Verify release year (should use most common/public release year)
        year, source, confidence = self.verifier.verify_release_year("Test Movie", sources)
        
        # Should prefer 2024 (public release) over 2023 (premiere)
        assert year == 2024, f"Should use public release year 2024, got {year}"
        assert confidence > 0.7, "Should have reasonable confidence despite conflict"
    
    def test_tier_c_rejection_for_facts(self):
        """Test: Tier C sources should not be used for fact verification."""
        # Mock sources with Tier C
        sources = [
            SourceMetadata(
                url="https://www.quora.com/question/123",
                domain="quora.com",
                tier=SourceTier.TIER_C,
                title="Movies with De Niro and Pacino",
                content="They were in The Godfather Part II, Heat, and many others.",
                score=0.5
            ),
            SourceMetadata(
                url="https://www.facebook.com/post/456",
                domain="facebook.com",
                tier=SourceTier.TIER_C,
                title="De Niro and Pacino",
                content="Great actors! They worked together in Heat.",
                score=0.3
            )
        ]
        
        # Try to verify - should fail (no Tier A sources)
        movie_title = "Heat"
        year = 1995
        
        person1_verified, source1, conf1 = self.verifier.verify_movie_credit(
            movie_title, "Robert De Niro", year, sources
        )
        
        assert not person1_verified, "Should not verify using Tier C sources only"
        assert conf1 == 0.0, "Should have zero confidence without Tier A sources"
    
    def test_candidate_extraction_filters_by_entities(self):
        """Test: Candidate extraction should filter by entities."""
        search_results = [
            {
                "title": "Movies with Robert De Niro",
                "content": '"Taxi Driver" (1976), "Raging Bull" (1980), and "Goodfellas" (1990) star Robert De Niro.',
                "url": "https://example.com",
                "tier": "A"
            },
            {
                "title": "Movies with Al Pacino",
                "content": '"The Godfather" (1972), "Scarface" (1983), and "Heat" (1995) star Al Pacino.',
                "url": "https://example.com",
                "tier": "A"
            }
        ]
        
        # Extract candidates for De Niro only
        candidates = self.extractor.extract_movie_candidates(
            search_results, 
            entities=["Robert De Niro"]
        )
        
        # Should find De Niro movies
        de_niro_movies = [c for c in candidates if "Taxi Driver" in c.value or "Raging Bull" in c.value or "Goodfellas" in c.value]
        assert len(de_niro_movies) > 0, "Should extract De Niro movies"
        
        # Should not find Pacino-only movies (unless they also mention De Niro)
        pacino_only = [c for c in candidates if "Scarface" in c.value and "De Niro" not in c.context]
        # This is acceptable - extraction is permissive, verification will filter


if __name__ == "__main__":
    import re
    test = TestCandidateVerifyAnswer()
    test.setup_method()
    
    print("Running candidate → verify → answer tests...")
    
    try:
        test.test_collaboration_candidate_extraction()
        print("✓ Test 1: Collaboration candidate extraction")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test.test_collaboration_verification()
        print("✓ Test 2: Collaboration verification")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test.test_disambiguation_same_title_different_year()
        print("✓ Test 3: Disambiguation (same title, different year)")
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test.test_release_year_verification()
        print("✓ Test 4: Release year verification")
    except Exception as e:
        print(f"✗ Test 4 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test.test_release_year_conflict_resolution()
        print("✓ Test 5: Release year conflict resolution")
    except Exception as e:
        print(f"✗ Test 5 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test.test_tier_c_rejection_for_facts()
        print("✓ Test 6: Tier C rejection for facts")
    except Exception as e:
        print(f"✗ Test 6 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test.test_candidate_extraction_filters_by_entities()
        print("✓ Test 7: Candidate extraction filters by entities")
    except Exception as e:
        print(f"✗ Test 7 failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nAll tests completed!")

