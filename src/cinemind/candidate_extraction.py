"""
Candidate extraction for fact/list questions.
Extracts candidate items from search results before verification.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    """A candidate item extracted from search results."""
    value: str  # The candidate value (title, year, etc.)
    source_url: str
    source_tier: str
    confidence: float  # Extraction confidence (not verification confidence)
    context: str  # Context where candidate was found


class CandidateExtractor:
    """
    Extracts candidate items from search results for verification.
    """
    
    def extract_movie_candidates(self, search_results: List[Dict], 
                                 entities: List[str] = None) -> List[Candidate]:
        """
        Extract candidate movie titles from search results.
        
        Args:
            search_results: List of search result dictionaries
            entities: Optional list of entities to filter by
        
        Returns:
            List of Candidate objects
        """
        candidates = []
        seen_titles = set()
        
        for result in search_results:
            content = result.get("content", "")
            title = result.get("title", "")
            url = result.get("url", "")
            tier = result.get("tier", "UNKNOWN")
            
            # Extract movie titles with years
            # Pattern: "Movie Title (Year)" or "Movie Title" (Year)
            title_year_pattern = r'"([^"]+)"\s*\((\d{4})\)|([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\((\d{4})\)'
            matches = re.finditer(title_year_pattern, content)
            
            for match in matches:
                # Extract title and year
                if match.group(1):  # Quoted title
                    movie_title = match.group(1)
                    year = match.group(2)
                else:  # Unquoted title
                    movie_title = match.group(3)
                    year = match.group(4)
                
                # Normalize title
                movie_title = movie_title.strip()
                if not movie_title:
                    continue
                
                # Create unique key
                key = f"{movie_title.lower()}_{year}"
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                
                # Filter by entities if provided
                if entities:
                    title_lower = movie_title.lower()
                    if not any(entity.lower() in title_lower or title_lower in entity.lower() 
                              for entity in entities if len(entity) > 2):
                        continue
                
                candidates.append(Candidate(
                    value=f"{movie_title} ({year})",
                    source_url=url,
                    source_tier=tier,
                    confidence=0.7,  # Medium confidence for extraction
                    context=content[match.start():match.end()+50]  # Context around match
                ))
            
            # Also extract from result title if it looks like a movie
            if title and not any(title.lower() in c.value.lower() for c in candidates):
                # Check if title contains year pattern
                title_match = re.search(r'(.+?)\s*\((\d{4})\)', title)
                if title_match:
                    movie_title = title_match.group(1).strip()
                    year = title_match.group(2)
                    
                    key = f"{movie_title.lower()}_{year}"
                    if key not in seen_titles:
                        seen_titles.add(key)
                        candidates.append(Candidate(
                            value=f"{movie_title} ({year})",
                            source_url=url,
                            source_tier=tier,
                            confidence=0.8,  # Higher confidence for title field
                            context=title
                        ))
        
        # Sort by confidence and source tier (Tier A first)
        tier_priority = {"A": 3, "B": 2, "C": 1, "UNKNOWN": 0}
        candidates.sort(key=lambda c: (tier_priority.get(c.source_tier, 0), c.confidence), reverse=True)
        
        return candidates[:20]  # Limit to top 20 candidates
    
    def extract_collaboration_candidates(self, search_results: List[Dict],
                                        person1: str, person2: str) -> List[Candidate]:
        """
        Extract candidate movies where two people collaborated.
        
        Args:
            search_results: List of search result dictionaries
            person1: First person name
            person2: Second person name
        
        Returns:
            List of Candidate objects (movies)
        """
        candidates = []
        seen_titles = set()
        
        person1_lower = person1.lower()
        person2_lower = person2.lower()
        
        for result in search_results:
            content = result.get("content", "")
            url = result.get("url", "")
            tier = result.get("tier", "UNKNOWN")
            content_lower = content.lower()
            
            # Check if both people are mentioned
            person1_found = any(word in content_lower for word in person1_lower.split() if len(word) > 3)
            person2_found = any(word in content_lower for word in person2_lower.split() if len(word) > 3)
            
            if not (person1_found and person2_found):
                continue
            
            # Extract movie titles from this result
            title_year_pattern = r'"([^"]+)"\s*\((\d{4})\)|([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\((\d{4})\)'
            matches = re.finditer(title_year_pattern, content)
            
            for match in matches:
                if match.group(1):
                    movie_title = match.group(1)
                    year = match.group(2)
                else:
                    movie_title = match.group(3)
                    year = match.group(4)
                
                movie_title = movie_title.strip()
                if not movie_title:
                    continue
                
                key = f"{movie_title.lower()}_{year}"
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                
                candidates.append(Candidate(
                    value=f"{movie_title} ({year})",
                    source_url=url,
                    source_tier=tier,
                    confidence=0.6,  # Lower confidence - needs verification
                    context=content[match.start():match.end()+100]
                ))
        
        # Sort by confidence and tier
        tier_priority = {"A": 3, "B": 2, "C": 1, "UNKNOWN": 0}
        candidates.sort(key=lambda c: (tier_priority.get(c.source_tier, 0), c.confidence), reverse=True)
        
        return candidates[:15]  # Limit to top 15 candidates
    
    def extract_release_year_candidates(self, search_results: List[Dict],
                                        movie_title: str) -> List[Candidate]:
        """
        Extract candidate release years for a movie.
        
        Args:
            search_results: List of search result dictionaries
            movie_title: Movie title to find year for
        
        Returns:
            List of Candidate objects (years)
        """
        candidates = []
        seen_years = set()
        
        title_lower = movie_title.lower()
        title_words = [w for w in title_lower.split() if len(w) > 2]
        
        for result in search_results:
            content = result.get("content", "")
            url = result.get("url", "")
            tier = result.get("tier", "UNKNOWN")
            content_lower = content.lower()
            
            # Check if movie title is mentioned
            title_mentioned = (
                title_lower in content_lower or
                all(word in content_lower for word in title_words[:3])  # First 3 words
            )
            
            if not title_mentioned:
                continue
            
            # Extract years
            year_pattern = r'\b(19\d{2}|20\d{2})\b'
            years = re.findall(year_pattern, content)
            
            for year_str in years:
                year = int(year_str)
                if year in seen_years:
                    continue
                seen_years.add(year)
                
                # Find context around the year
                year_pos = content.find(year_str)
                context_start = max(0, year_pos - 50)
                context_end = min(len(content), year_pos + len(year_str) + 50)
                context = content[context_start:context_end]
                
                candidates.append(Candidate(
                    value=str(year),
                    source_url=url,
                    source_tier=tier,
                    confidence=0.7,
                    context=context
                ))
        
        # Sort by tier and confidence
        tier_priority = {"A": 3, "B": 2, "C": 1, "UNKNOWN": 0}
        candidates.sort(key=lambda c: (tier_priority.get(c.source_tier, 0), c.confidence), reverse=True)
        
        return candidates[:10]  # Limit to top 10 years

