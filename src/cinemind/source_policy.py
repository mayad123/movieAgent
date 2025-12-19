"""
Source policy and ranking system for CineMind.
Implements Tier A/B/C source ranking with strict enforcement.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SourceTier(Enum):
    """Source quality tiers."""
    TIER_A = "A"  # Authoritative/structured
    TIER_B = "B"  # Reputable editorial
    TIER_C = "C"  # Low-trust
    UNKNOWN = "UNKNOWN"


@dataclass
class SourceMetadata:
    """Metadata about a source."""
    url: str
    domain: str
    tier: SourceTier
    title: str
    content: str
    score: float = 0.0
    published_date: Optional[str] = None
    last_updated: Optional[str] = None
    is_structured: bool = False  # True for APIs/structured data
    source_name: str = "unknown"  # Original source name (tavily, kaggle_imdb, etc.)


class SourcePolicy:
    """
    Source policy with tier-based ranking and filtering.
    """
    
    # Tier A: Authoritative/structured sources
    TIER_A_DOMAINS = {
        # IMDb
        "imdb.com",
        "www.imdb.com",
        
        # Wikipedia
        "en.wikipedia.org",
        "wikipedia.org",
        
        # Wikidata
        "wikidata.org",
        "www.wikidata.org",
        
        # TMDb (if using API)
        "themoviedb.org",
        "www.themoviedb.org",
    }
    
    # Tier B: Reputable editorial sources
    TIER_B_DOMAINS = {
        # Trade publications
        "variety.com",
        "www.variety.com",
        "deadline.com",
        "www.deadline.com",
        "hollywoodreporter.com",
        "www.hollywoodreporter.com",
        "indiewire.com",
        "www.indiewire.com",
        "entertainmentweekly.com",
        "www.entertainmentweekly.com",
        
        # Established film sites
        "rottentomatoes.com",
        "www.rottentomatoes.com",
        "metacritic.com",
        "www.metacritic.com",
        "empireonline.com",
        "www.empireonline.com",
    }
    
    # Tier C: Low-trust sources (auto-reject for facts)
    TIER_C_DOMAINS = {
        "quora.com",
        "www.quora.com",
        "facebook.com",
        "www.facebook.com",
        "reddit.com",
        "www.reddit.com",
        "blogspot.com",
        "wordpress.com",
        "medium.com",
        "tumblr.com",
    }
    
    # Patterns for Tier A identification
    TIER_A_PATTERNS = [
        r"imdb\.com/title/tt\d+",  # IMDb title pages
        r"wikipedia\.org/wiki/.*film",  # Wikipedia film pages
        r"wikidata\.org/wiki/Q\d+",  # Wikidata entities
    ]
    
    def __init__(self):
        """Initialize source policy."""
        pass
    
    def classify_source(self, url: str, title: str = "", content: str = "", source_name: str = "") -> SourceTier:
        """
        Classify a source into Tier A, B, C, or UNKNOWN.
        
        Args:
            url: Source URL
            title: Source title
            content: Source content (for pattern matching)
            source_name: Original source name (kaggle_imdb, tavily, etc.)
        
        Returns:
            SourceTier
        """
        # Kaggle IMDB dataset is Tier A (authoritative structured data)
        if source_name == "kaggle_imdb":
            return SourceTier.TIER_A
        
        if not url:
            return SourceTier.UNKNOWN
        
        # Parse domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            return SourceTier.UNKNOWN
        
        # Check Tier A
        if domain in self.TIER_A_DOMAINS:
            return SourceTier.TIER_A
        
        # Check Tier A patterns
        url_lower = url.lower()
        for pattern in self.TIER_A_PATTERNS:
            if re.search(pattern, url_lower):
                return SourceTier.TIER_A
        
        # Check Tier B
        if domain in self.TIER_B_DOMAINS:
            return SourceTier.TIER_B
        
        # Check Tier C
        if domain in self.TIER_C_DOMAINS:
            return SourceTier.TIER_C
        
        # Check for Tier C patterns in content
        content_lower = (title + " " + content).lower()
        if any(tier_c in content_lower for tier_c in ["quora", "facebook post", "reddit thread"]):
            return SourceTier.TIER_C
        
        return SourceTier.UNKNOWN
    
    def rank_and_filter(self, results: List[Dict], request_type: str, 
                       need_freshness: bool = False) -> List[SourceMetadata]:
        """
        Rank and filter search results by tier.
        
        Args:
            results: Raw search results from search engine
            request_type: Request classification type
            need_freshness: Whether query needs fresh data
        
        Returns:
            List of SourceMetadata, ranked by tier (A first, then B, then C)
        """
        # Classify all sources
        sources = []
        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")
            
            source_name = result.get("source", "unknown")
            tier = self.classify_source(url, title, content, source_name)
            
            # Extract domain
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
            except:
                domain = ""
                # For Kaggle sources, set domain to indicate it's from IMDB dataset
                if source_name == "kaggle_imdb":
                    domain = "imdb.com (via Kaggle dataset)"
            
            source = SourceMetadata(
                url=url,
                domain=domain,
                tier=tier,
                title=title,
                content=content,
                score=result.get("score", 0.0),
                published_date=result.get("published_date"),
                last_updated=result.get("last_updated"),
                is_structured=result.get("source") in ["tavily_answer", "kaggle_imdb"],  # Structured data sources
                source_name=source_name
            )
            sources.append(source)
        
        # Filter based on request type
        if request_type in ["info", "fact-check"]:
            # For facts: Tier A only, unless no Tier A exists
            tier_a_sources = [s for s in sources if s.tier == SourceTier.TIER_A]
            if tier_a_sources:
                # Return Tier A only, ranked by score
                return sorted(tier_a_sources, key=lambda x: x.score, reverse=True)
            else:
                # No Tier A, allow Tier B but mark as lower confidence
                tier_b_sources = [s for s in sources if s.tier == SourceTier.TIER_B]
                if tier_b_sources:
                    logger.warning(f"No Tier A sources found for {request_type}, using Tier B")
                    return sorted(tier_b_sources, key=lambda x: x.score, reverse=True)
                # Last resort: Tier C, but log warning
                tier_c_sources = [s for s in sources if s.tier == SourceTier.TIER_C]
                if tier_c_sources:
                    logger.warning(f"Only Tier C sources available for {request_type} - low confidence")
                    return sorted(tier_c_sources, key=lambda x: x.score, reverse=True)
        
        elif request_type == "release-date":
            # Release dates: Tier A preferred, Tier B allowed for news
            tier_a_sources = [s for s in sources if s.tier == SourceTier.TIER_A]
            tier_b_sources = [s for s in sources if s.tier == SourceTier.TIER_B]
            
            # Combine A and B, A first
            combined = sorted(tier_a_sources + tier_b_sources, 
                            key=lambda x: (x.tier.value != "A", -x.score))
            return combined
        
        elif request_type in ["recs", "comparison"]:
            # Recommendations/comparisons: All tiers allowed, but rank by tier
            return sorted(sources, 
                         key=lambda x: (
                             {"A": 0, "B": 1, "C": 2, "UNKNOWN": 3}.get(x.tier.value, 3),
                             -x.score
                         ))
        
        elif request_type == "spoiler":
            # Spoilers: Tier A preferred (Wikipedia plot summaries)
            tier_a_sources = [s for s in sources if s.tier == SourceTier.TIER_A]
            if tier_a_sources:
                return sorted(tier_a_sources, key=lambda x: x.score, reverse=True)
            # Fallback to others
            return sorted(sources, 
                         key=lambda x: (
                             {"A": 0, "B": 1, "C": 2, "UNKNOWN": 3}.get(x.tier.value, 3),
                             -x.score
                         ))
        
        # Default: Return all, ranked by tier
        return sorted(sources, 
                     key=lambda x: (
                         {"A": 0, "B": 1, "C": 2, "UNKNOWN": 3}.get(x.tier.value, 3),
                         -x.score
                     ))
    
    def filter_tier_c(self, sources: List[SourceMetadata], 
                     allow_tier_c: bool = False) -> List[SourceMetadata]:
        """
        Filter out Tier C sources unless explicitly allowed.
        
        Args:
            sources: List of sources
            allow_tier_c: Whether to allow Tier C sources
        
        Returns:
            Filtered list
        """
        if allow_tier_c:
            return sources
        
        return [s for s in sources if s.tier != SourceTier.TIER_C]
    
    def get_source_summary(self, sources: List[SourceMetadata]) -> Dict:
        """
        Get summary of source tiers used.
        
        Returns:
            Dict with tier counts and metadata
        """
        tier_counts = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
        tier_a_domains = set()
        tier_b_domains = set()
        tier_c_domains = set()
        
        for source in sources:
            tier_counts[source.tier.value] = tier_counts.get(source.tier.value, 0) + 1
            
            if source.tier == SourceTier.TIER_A:
                tier_a_domains.add(source.domain)
            elif source.tier == SourceTier.TIER_B:
                tier_b_domains.add(source.domain)
            elif source.tier == SourceTier.TIER_C:
                tier_c_domains.add(source.domain)
        
        return {
            "tier_counts": tier_counts,
            "tier_a_domains": list(tier_a_domains),
            "tier_b_domains": list(tier_b_domains),
            "tier_c_domains": list(tier_c_domains),
            "total_sources": len(sources),
            "has_tier_a": tier_counts["A"] > 0,
            "has_tier_c_only": tier_counts["A"] == 0 and tier_counts["B"] == 0 and tier_counts["C"] > 0
        }

