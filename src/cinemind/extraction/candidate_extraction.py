"""
Candidate extraction for fact/list questions.
Extracts candidate items from search results before verification.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Common award/category phrases that should not be treated as movie titles
AWARD_PHRASES = {
    "best picture", "academy award", "oscar", "golden globe",
    "best actor", "best actress", "best director", "best screenplay",
    "best supporting actor", "best supporting actress", "best cinematography",
    "best original score", "best visual effects", "best editing",
    "best costume design", "best production design", "best sound",
    "best foreign language film", "best animated feature", "best documentary",
    "emmy award", "grammy award", "tony award", "sag award",
    "palme d'or", "golden bear", "venice film festival", "cannes film festival",
    "best film", "best movie", "film of the year", "movie of the year"
}


def normalize_title(title: str) -> str:
    """
    Normalize movie title for consistent matching.
    
    - Unifies apostrophes/quotes (', ', ', ", ")
    - Strips extra whitespace
    - Normalizes punctuation variants (em dash, en dash to hyphen)
    - Preserves meaningful punctuation (colon, hyphen)
    
    Args:
        title: Raw title string
        
    Returns:
        Normalized title string
    """
    if not title or not isinstance(title, str):
        return ""
    
    # Strip leading/trailing whitespace
    normalized = title.strip()
    
    # Unify apostrophes and quotes
    # Replace various apostrophe/quote characters with standard apostrophe
    normalized = re.sub(r'[''′‛`]', "'", normalized)
    # Replace various quote characters with standard quotes
    normalized = re.sub(r'["""„]', '"', normalized)
    
    # Normalize dashes (em dash, en dash, figure dash to hyphen)
    normalized = re.sub(r'[—–−]', '-', normalized)
    
    # Normalize middle dots and other separators
    normalized = re.sub(r'[·•]', '·', normalized)  # Keep middle dot as-is for titles like WALL·E
    
    # Collapse multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Final strip
    normalized = normalized.strip()
    
    return normalized


def is_award_phrase(text: str) -> bool:
    """
    Check if a text string is likely an award/category phrase, not a movie title.
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be an award phrase
    """
    text_lower = text.lower().strip()
    
    # Check exact matches
    if text_lower in AWARD_PHRASES:
        return True
    
    # Check if text starts with award phrase
    for phrase in AWARD_PHRASES:
        if text_lower.startswith(phrase + " ") or text_lower.startswith(phrase + ":"):
            return True
    
    # Check if text is very short and matches common award patterns
    if len(text_lower.split()) <= 3:
        if any(word in text_lower for word in ["best", "award", "oscar", "golden", "emmy"]):
            return True
    
    return False


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
    
    def _extract_title_year_patterns(self, text: str) -> List[Tuple[str, str, int, int]]:
        """
        Extract movie title and year pairs from text using multiple patterns.
        
        Patterns supported:
        - "Title" (Year)
        - Title (Year)
        - Title — Year (em dash)
        - Title, Year (comma)
        - Titles with numerals and punctuation (Se7en, WALL·E, Spider-Man: Homecoming)
        
        Args:
            text: Text to search for titles
            
        Returns:
            List of tuples: (title, year, start_pos, end_pos)
        """
        matches = []
        
        # Pattern 1: Quoted title with parentheses year: "Title" (Year)
        pattern1 = r'"([^"]+)"\s*\((\d{4})\)'
        for match in re.finditer(pattern1, text):
            title = match.group(1)
            year = match.group(2)
            matches.append((title, year, match.start(), match.end()))
        
        # Pattern 2: Title with parentheses year: Title (Year)
        # Handles titles with numerals, punctuation, colons, hyphens, middle dots
        # Examples: Se7en, WALL·E, Spider-Man: Homecoming, The Matrix (1999)
        # Excludes quoted titles (handled by pattern1) - uses negative lookbehind/lookahead
        pattern2 = r'(?<!")([A-Z][A-Za-z0-9:·\-\'\s]+?)\s*\((\d{4})\)'
        for match in re.finditer(pattern2, text):
            title = match.group(1).strip()
            year = match.group(2)
            # Skip if it's just a year in parentheses (e.g., "(1999)")
            if len(title) < 2:
                continue
            # Skip if title contains quotes (already handled by pattern1)
            if '"' in title:
                continue
            # Skip if it looks like an award phrase
            if is_award_phrase(title):
                continue
            matches.append((title, year, match.start(), match.end()))
        
        # Pattern 3: Title with em dash/en dash: Title — Year or Title – Year
        # Handles both quoted and unquoted titles
        pattern3_quoted = r'"([^"]+)"\s*[—–]\s*(\d{4})\b'
        for match in re.finditer(pattern3_quoted, text):
            title = match.group(1).strip()
            year = match.group(2)
            if len(title) < 2 or is_award_phrase(title):
                continue
            matches.append((title, year, match.start(), match.end()))
        
        pattern3_unquoted = r'(?<!")([A-Z][A-Za-z0-9:·\-\'\s]+?)\s*[—–]\s*(\d{4})\b'
        for match in re.finditer(pattern3_unquoted, text):
            title = match.group(1).strip()
            year = match.group(2)
            if len(title) < 2 or is_award_phrase(title):
                continue
            # Skip if title contains quotes (already handled by pattern3_quoted)
            if '"' in title:
                continue
            matches.append((title, year, match.start(), match.end()))
        
        # Pattern 4: Title with comma: Title, Year
        pattern4 = r'([A-Z][A-Za-z0-9:·\-\'\"\s]+?),\s*(\d{4})\b'
        for match in re.finditer(pattern4, text):
            title = match.group(1).strip()
            year = match.group(2)
            if len(title) < 2 or is_award_phrase(title):
                continue
            # Additional check: make sure comma isn't part of a list (e.g., "Actor, Director, 1999")
            # If title is very short and contains common words, skip
            title_words = title.split()
            if len(title_words) <= 2 and any(word.lower() in ["actor", "director", "writer", "producer", "star", "stars"] 
                                            for word in title_words):
                continue
            matches.append((title, year, match.start(), match.end()))
        
        return matches
    
    def extract_movie_candidates(self, search_results: List[Dict], 
                                 entities: Optional[List[str]] = None) -> List[Candidate]:
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
            
            # Extract movie titles with years using expanded patterns
            title_year_matches = self._extract_title_year_patterns(content)
            
            for movie_title, year, start_pos, end_pos in title_year_matches:
                # Normalize title
                normalized_title = normalize_title(movie_title)
                if not normalized_title:
                    continue
                
                # Filter out award phrases
                if is_award_phrase(normalized_title):
                    continue
                
                # Create unique key using normalized title
                key = f"{normalized_title.lower()}_{year}"
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                
                # Filter by entities if provided
                if entities:
                    title_lower = normalized_title.lower()
                    if not any(entity.lower() in title_lower or title_lower in entity.lower() 
                              for entity in entities if len(entity) > 2):
                        continue
                
                candidates.append(Candidate(
                    value=f"{normalized_title} ({year})",
                    source_url=url,
                    source_tier=tier,
                    confidence=0.7,  # Medium confidence for extraction
                    context=content[max(0, start_pos-50):min(len(content), end_pos+50)]  # Context around match
                ))
            
            # Also extract from result title if it looks like a movie
            if title:
                title_matches = self._extract_title_year_patterns(title)
                for movie_title, year, start_pos, end_pos in title_matches:
                    normalized_title = normalize_title(movie_title)
                    if not normalized_title or is_award_phrase(normalized_title):
                        continue
                    
                    key = f"{normalized_title.lower()}_{year}"
                    if key not in seen_titles:
                        seen_titles.add(key)
                        candidates.append(Candidate(
                            value=f"{normalized_title} ({year})",
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
            
            # Extract movie titles from this result using improved patterns
            title_year_matches = self._extract_title_year_patterns(content)
            
            for movie_title, year, start_pos, end_pos in title_year_matches:
                # Normalize title
                normalized_title = normalize_title(movie_title)
                if not normalized_title:
                    continue
                
                # Filter out award phrases
                if is_award_phrase(normalized_title):
                    continue
                
                key = f"{normalized_title.lower()}_{year}"
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                
                candidates.append(Candidate(
                    value=f"{normalized_title} ({year})",
                    source_url=url,
                    source_tier=tier,
                    confidence=0.6,  # Lower confidence - needs verification
                    context=content[max(0, start_pos-50):min(len(content), end_pos+100)]
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

