"""
Verification module for CineMind.
Verifies extracted facts against Tier A sources (IMDb, Wikipedia, Wikidata).
Implements "candidate → verify → answer" pattern for fact/list questions.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


@dataclass
class VerifiedFact:
    """A verified fact with source attribution."""
    fact_type: str  # "cast", "director", "release_year", "collaboration"
    value: str  # The fact value
    verified: bool
    source_url: str
    source_tier: str
    confidence: float
    conflicts: List[str] = None  # List of conflicting sources if any
    
    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []


class FactVerifier:
    """
    Verifies facts against Tier A sources.
    """
    
    def __init__(self, source_policy):
        """
        Initialize verifier.
        
        Args:
            source_policy: SourcePolicy instance
        """
        self.source_policy = source_policy
    
    def verify_movie_credit(self, movie_title: str, person_name: str, 
                           year: Optional[int] = None,
                           sources: List = None) -> Tuple[bool, str, float]:
        """
        Verify if a person has a credit (cast/director) in a movie.
        Reusable verification component.
        
        Args:
            movie_title: Movie title
            person_name: Person name (actor/director)
            year: Optional year for disambiguation
            sources: List of SourceMetadata objects (if None, returns unverified)
        
        Returns:
            (verified: bool, source_url: str, confidence: float)
        """
        if not sources:
            return (False, "", 0.0)
        
        # Filter to Tier A sources only
        tier_a_sources = [s for s in sources if hasattr(s, 'tier') and s.tier.value == "A"]
        
        if not tier_a_sources:
            logger.warning(f"No Tier A sources for verification of {person_name} in {movie_title}")
            return (False, "", 0.0)
        
        # Check IMDb sources first (highest confidence)
        imdb_sources = [s for s in tier_a_sources if "imdb.com" in s.domain.lower()]
        for source in imdb_sources:
            if self._check_credit_in_content(source.content, movie_title, person_name, year):
                return (True, source.url, 0.95)
        
        # Check Wikipedia sources
        wiki_sources = [s for s in tier_a_sources if "wikipedia.org" in s.domain.lower()]
        for source in wiki_sources:
            if self._check_credit_in_content(source.content, movie_title, person_name, year):
                return (True, source.url, 0.85)
        
        return (False, "", 0.0)
    
    def verify_release_year(self, movie_title: str, 
                           sources: List = None) -> Tuple[Optional[int], str, float]:
        """
        Verify release year for a movie.
        Reusable verification component.
        
        Args:
            movie_title: Movie title
            sources: List of SourceMetadata objects
        
        Returns:
            (year: Optional[int], source_url: str, confidence: float)
        """
        if not sources:
            return (None, "", 0.0)
        
        # Filter to Tier A sources only
        tier_a_sources = [s for s in sources if hasattr(s, 'tier') and s.tier.value == "A"]
        
        if not tier_a_sources:
            return (None, "", 0.0)
        
        # Extract years from Tier A sources
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        years_found = {}  # year -> [source_urls]
        
        for source in tier_a_sources:
            content_lower = source.content.lower()
            title_lower = movie_title.lower()
            
            # Only consider sources that mention the movie title
            if title_lower in content_lower or any(word in content_lower for word in title_lower.split() if len(word) > 3):
                years = re.findall(year_pattern, source.content)
                for year_str in years:
                    year = int(year_str)
                    if year not in years_found:
                        years_found[year] = []
                    years_found[year].append(source.url)
        
        if not years_found:
            return (None, "", 0.0)
        
        # Get most common year (likely the release year)
        most_common_year = max(years_found.keys(), key=lambda y: len(years_found[y]))
        source_url = years_found[most_common_year][0]
        
        # Confidence based on agreement
        agreement_count = len(years_found[most_common_year])
        total_sources = len(tier_a_sources)
        confidence = min(0.95, 0.7 + (agreement_count / max(total_sources, 1)) * 0.25)
        
        # Check for conflicts
        if len(years_found) > 1:
            confidence *= 0.9  # Reduce confidence if multiple years found
        
        return (most_common_year, source_url, confidence)
    
    def _check_credit_in_content(self, content: str, movie_title: str, 
                                person_name: str, year: Optional[int] = None) -> bool:
        """Check if person has credit in movie based on content."""
        content_lower = content.lower()
        title_lower = movie_title.lower()
        person_lower = person_name.lower()
        
        # Check if movie title is mentioned
        title_words = title_lower.split()
        title_mentioned = (
            title_lower in content_lower or
            any(word in content_lower for word in title_words if len(word) > 3)
        )
        
        if not title_mentioned:
            return False
        
        # Check if year matches (if provided)
        if year:
            year_pattern = rf'\b{year}\b'
            if not re.search(year_pattern, content):
                return False
        
        # Check if person is mentioned
        # Handle name variations
        person_words = person_lower.split()
        person_variations = [
            person_lower,
            person_words[-1] if len(person_words) > 1 else person_lower,  # Last name
            " ".join(person_words[-2:]) if len(person_words) > 2 else person_lower,  # Last two words
        ]
        
        person_found = any(
            var in content_lower 
            for var in person_variations 
            if len(var) > 3
        )
        
        return person_found
    
    def verify_filmography_overlap(self, person1: str, person2: str, 
                                  candidate_titles: List[str],
                                  sources: List) -> List[VerifiedFact]:
        """
        Verify filmography overlap between two people.
        
        Args:
            person1: First person name
            person2: Second person name
            candidate_titles: List of candidate movie titles
            sources: List of SourceMetadata objects
        
        Returns:
            List of VerifiedFact objects
        """
        verified_facts = []
        
        # Filter to Tier A sources only
        tier_a_sources = [s for s in sources if s.tier.value == "A"]
        
        if not tier_a_sources:
            logger.warning(f"No Tier A sources for verification of {person1} and {person2}")
            return verified_facts
        
        # For each candidate title, check if both people are in cast
        for title in candidate_titles:
            # Look for IMDb or Wikipedia sources
            imdb_sources = [s for s in tier_a_sources if "imdb.com" in s.domain]
            wiki_sources = [s for s in tier_a_sources if "wikipedia.org" in s.domain]
            
            verified = False
            source_url = ""
            confidence = 0.0
            
            # Check IMDb sources
            for source in imdb_sources:
                if self._check_both_in_content(source.content, person1, person2, title):
                    verified = True
                    source_url = source.url
                    confidence = 0.9
                    break
            
            # Check Wikipedia sources
            if not verified:
                for source in wiki_sources:
                    if self._check_both_in_content(source.content, person1, person2, title):
                        verified = True
                        source_url = source.url
                        confidence = 0.85
                        break
            
            if verified:
                verified_facts.append(VerifiedFact(
                    fact_type="collaboration",
                    value=title,
                    verified=True,
                    source_url=source_url,
                    source_tier="A",
                    confidence=confidence
                ))
            else:
                # Mark as unverified
                verified_facts.append(VerifiedFact(
                    fact_type="collaboration",
                    value=title,
                    verified=False,
                    source_url="",
                    source_tier="",
                    confidence=0.0
                ))
        
        return verified_facts
    
    def _check_both_in_content(self, content: str, person1: str, person2: str, title: str) -> bool:
        """Check if both people are mentioned in content about the title."""
        content_lower = content.lower()
        title_lower = title.lower()
        person1_lower = person1.lower()
        person2_lower = person2.lower()
        
        # Check if title is mentioned
        if title_lower not in content_lower:
            return False
        
        # Check if both people are mentioned
        # Handle name variations (e.g., "Robert De Niro" vs "De Niro")
        person1_variations = [
            person1_lower,
            person1_lower.split()[-1] if len(person1_lower.split()) > 1 else person1_lower,
            person1_lower.split()[0] if len(person1_lower.split()) > 1 else person1_lower,
        ]
        person2_variations = [
            person2_lower,
            person2_lower.split()[-1] if len(person2_lower.split()) > 1 else person2_lower,
            person2_lower.split()[0] if len(person2_lower.split()) > 1 else person2_lower,
        ]
        
        person1_found = any(var in content_lower for var in person1_variations if len(var) > 3)
        person2_found = any(var in content_lower for var in person2_variations if len(var) > 3)
        
        return person1_found and person2_found
    
    def extract_release_year(self, title: str, sources: List) -> Optional[VerifiedFact]:
        """
        Extract and verify release year for a movie.
        
        Args:
            title: Movie title
            sources: List of SourceMetadata objects
        
        Returns:
            VerifiedFact with release year, or None
        """
        tier_a_sources = [s for s in sources if s.tier.value == "A"]
        
        # Look for year patterns in Tier A sources
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        
        years_found = {}
        
        for source in tier_a_sources:
            if title.lower() in source.content.lower():
                years = re.findall(year_pattern, source.content)
                for year in years:
                    if year not in years_found:
                        years_found[year] = []
                    years_found[year].append(source.url)
        
        if not years_found:
            return None
        
        # Get most common year (likely the release year)
        most_common_year = max(years_found.keys(), key=lambda y: len(years_found[y]))
        
        # Check for conflicts
        conflicts = []
        if len(years_found) > 1:
            other_years = [y for y in years_found.keys() if y != most_common_year]
            conflicts = other_years
        
        return VerifiedFact(
            fact_type="release_year",
            value=most_common_year,
            verified=True,
            source_url=years_found[most_common_year][0],
            source_tier="A",
            confidence=0.9 if not conflicts else 0.7,
            conflicts=conflicts
        )
    
    def resolve_conflicts(self, facts: List[VerifiedFact]) -> List[VerifiedFact]:
        """
        Resolve conflicts between facts using conflict resolution rules.
        
        Rules:
        - Same title, different years: Use most common year from Tier A
        - Release year vs premiere: Use first public release year
        - Cast overlaps: Use credited cast only
        
        Args:
            facts: List of VerifiedFact objects
        
        Returns:
            Resolved facts
        """
        resolved = []
        
        # Group by fact type and value
        fact_groups = {}
        for fact in facts:
            key = f"{fact.fact_type}:{fact.value}"
            if key not in fact_groups:
                fact_groups[key] = []
            fact_groups[key].append(fact)
        
        # Resolve each group
        for key, group in fact_groups.items():
            if len(group) == 1:
                resolved.append(group[0])
            else:
                # Multiple sources - use highest confidence Tier A source
                tier_a_facts = [f for f in group if f.source_tier == "A"]
                if tier_a_facts:
                    best = max(tier_a_facts, key=lambda x: x.confidence)
                    # Add conflicts from other sources
                    other_sources = [f.source_url for f in group if f != best]
                    if other_sources:
                        best.conflicts = other_sources
                    resolved.append(best)
                else:
                    # No Tier A, use highest confidence
                    best = max(group, key=lambda x: x.confidence)
                    resolved.append(best)
        
        return resolved

