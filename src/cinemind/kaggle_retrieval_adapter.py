"""
Kaggle-first retrieval adapter for movie-related queries.

Searches Kaggle datasets for relevant information based on prompt + extracted intent/entities.
Returns normalized evidence bundles that integrate with the existing FakeLLM flow.

Key features:
- Relevance gate: Only attempts for prompts likely to benefit from datasets
- Timeout protection: Strict timeout with clean fallback
- Configurable: Can be enabled/disabled for testing
- Graceful degradation: Never fails, always falls back to FakeLLM
"""
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default timeout for Kaggle searches (seconds)
DEFAULT_KAGGLE_TIMEOUT = 5.0

# Relevance keywords that suggest Kaggle datasets would be useful
KAGGLE_RELEVANT_KEYWORDS = {
    "rankings": ["rank", "ranking", "ranked", "top", "best", "worst", "highest", "lowest"],
    "lists": ["list", "all", "every", "collection", "catalog", "directory"],
    "statistics": ["statistics", "stats", "statistical", "average", "median", "percentile"],
    "trends": ["trend", "trending", "over time", "historical", "over years", "evolution"],
    "comparisons": ["compare", "comparison", "versus", "vs", "difference", "similar"],
    "large_scope": ["all movies", "every movie", "entire catalog", "complete list"]
}

# Intent types that benefit from Kaggle datasets
KAGGLE_RELEVANT_INTENTS = [
    "recommendation",  # Rankings/lists of similar movies
    "comparison",  # Large-scale comparisons
    "general_info",  # Comprehensive information
]


@dataclass
class KaggleEvidenceItem:
    """Normalized evidence item from Kaggle dataset."""
    title: str
    url: str  # Dataset URL or source URL
    content: str  # Short snippet/description (must be non-empty for EvidenceFormatter)
    source: str = "kaggle_imdb"  # Source identifier (EvidenceFormatter maps to "Structured IMDb dataset")
    year: Optional[int] = None  # Year for deduplication
    metadata: Optional[Dict] = None  # License, author, etc. (internal, not exposed to user)


@dataclass
class KaggleRetrievalResult:
    """Result of Kaggle retrieval attempt."""
    success: bool
    evidence_items: List[KaggleEvidenceItem]
    relevance_score: float  # 0.0 to 1.0
    error_message: Optional[str] = None
    timeout: bool = False


class KaggleRetrievalAdapter:
    """
    Adapter for retrieving evidence from Kaggle datasets.
    
    Provides relevance gating, timeout protection, and normalized evidence format.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        timeout_seconds: float = DEFAULT_KAGGLE_TIMEOUT,
        correlation_threshold: float = 0.6
    ):
        """
        Initialize Kaggle retrieval adapter.
        
        Args:
            enabled: Whether Kaggle retrieval is enabled (can be disabled for testing)
            timeout_seconds: Maximum time to wait for Kaggle search
            correlation_threshold: Minimum correlation score to consider results relevant
        """
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.correlation_threshold = correlation_threshold
        self._kaggle_searcher = None
    
    def _get_kaggle_searcher(self):
        """Lazy initialization of Kaggle searcher."""
        if self._kaggle_searcher is None:
            try:
                from .kaggle_search import KaggleDatasetSearcher
                self._kaggle_searcher = KaggleDatasetSearcher(
                    correlation_threshold=self.correlation_threshold
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Kaggle searcher: {e}")
                self._kaggle_searcher = None
        return self._kaggle_searcher
    
    def _is_relevant_for_kaggle(self, prompt: str, intent: str, entities: Dict) -> Tuple[bool, float]:
        """
        Determine if query is relevant for Kaggle dataset search.
        
        Args:
            prompt: User query
            intent: Extracted intent (e.g., "recommendation", "comparison")
            entities: Extracted entities {"movies": [...], "people": [...]}
            
        Returns:
            Tuple of (is_relevant: bool, relevance_score: float 0.0-1.0)
        """
        if not self.enabled:
            return False, 0.0
        
        prompt_lower = prompt.lower()
        relevance_score = 0.0
        
        # Check intent relevance
        if intent in KAGGLE_RELEVANT_INTENTS:
            relevance_score += 0.4
        
        # Check for relevant keywords
        keyword_matches = 0
        total_keyword_categories = len(KAGGLE_RELEVANT_KEYWORDS)
        
        for category, keywords in KAGGLE_RELEVANT_KEYWORDS.items():
            if any(keyword in prompt_lower for keyword in keywords):
                keyword_matches += 1
        
        if keyword_matches > 0:
            relevance_score += 0.3 * (keyword_matches / total_keyword_categories)
        
        # Check for large scope indicators
        large_scope_keywords = ["all", "every", "entire", "complete", "catalog", "directory"]
        if any(keyword in prompt_lower for keyword in large_scope_keywords):
            relevance_score += 0.2
        
        # Check if multiple entities suggest comparison/ranking
        if intent == "comparison" and len(entities.get("movies", [])) >= 2:
            relevance_score += 0.1
        
        # Threshold: require at least 0.4 relevance score
        is_relevant = relevance_score >= 0.4
        
        return is_relevant, min(1.0, relevance_score)
    
    def _normalize_kaggle_results(
        self,
        kaggle_results: List[Dict],
        dataset_url: str = ""
    ) -> List[KaggleEvidenceItem]:
        """
        Normalize Kaggle search results into EvidenceItem format compatible with EvidenceFormatter.
        
        EvidenceFormatter requirements:
        - Must have non-empty content (otherwise dropped)
        - Should have title for deduplication
        - Should have url for deduplication (if available)
        - Should have year/release_year for deduplication (if available)
        - Source should be "kaggle_imdb" (EvidenceFormatter maps to "Structured IMDb dataset")
        
        Args:
            kaggle_results: Raw results from KaggleDatasetSearcher.search()
            dataset_url: URL to the Kaggle dataset (optional)
            
        Returns:
            List of normalized KaggleEvidenceItem
        """
        evidence_items = []
        
        for result in kaggle_results:
            title = result.get("title", "IMDB Dataset Result")
            content = result.get("content", "")
            
            # EvidenceFormatter requirement: must have non-empty content
            if not content or not content.strip():
                logger.debug(f"Skipping Kaggle result '{title}' - no content")
                continue
            
            # Extract year from result (already extracted in kaggle_search.py)
            # Fallback to extracting from row_data if not present in result
            year = result.get("year")
            if year is None:
                row_data = result.get("row_data", {})
                if row_data:
                    # Try common year column names
                    year_cols = ["Year", "year", "Release Year", "release_year", "Release Date"]
                    for col in year_cols:
                        if col in row_data:
                            year_val = row_data[col]
                            if year_val:
                                # Extract year if it's a string like "1999" or datetime
                                if isinstance(year_val, (int, float)):
                                    year = int(year_val)
                                elif isinstance(year_val, str):
                                    # Try to extract 4-digit year
                                    import re
                                    year_match = re.search(r'\b(19|20)\d{2}\b', year_val)
                                    if year_match:
                                        year = int(year_match.group())
                                break
            
            # Build URL (prefer result URL, then dataset URL, then empty)
            # EvidenceFormatter uses url for deduplication, so we ensure it's set
            url = result.get("url", "") or dataset_url or ""
            
            # Create metadata (not exposed to user, but useful for debugging)
            metadata = {
                "correlation_score": result.get("correlation", 0.0),
                "match_score": result.get("match_score", 0.0),
                "match_reason": result.get("match_reason", ""),
                "source_type": "kaggle_dataset"
            }
            
            # Ensure content is not too long (EvidenceFormatter will truncate, but keep reasonable)
            # EvidenceFormatter max_snippet_length is 400, so we can be a bit longer here
            # but not excessive
            if len(content) > 1000:
                content = content[:1000] + "..."
            
            evidence_items.append(
                KaggleEvidenceItem(
                    title=title,
                    url=url,
                    content=content,
                    source="kaggle_imdb",  # EvidenceFormatter maps this to "Structured IMDb dataset"
                    year=year,  # For deduplication
                    metadata=metadata
                )
            )
        
        return evidence_items
    
    async def retrieve_evidence(
        self,
        prompt: str,
        intent: str,
        entities: Dict,
        max_results: int = 5
    ) -> KaggleRetrievalResult:
        """
        Retrieve evidence from Kaggle datasets.
        
        Args:
            prompt: User query
            intent: Extracted intent
            entities: Extracted entities {"movies": [...], "people": [...]}
            max_results: Maximum number of results to return
            
        Returns:
            KaggleRetrievalResult with evidence items or error information
        """
        # Check if enabled
        if not self.enabled:
            logger.debug("Kaggle retrieval disabled, skipping")
            return KaggleRetrievalResult(
                success=False,
                evidence_items=[],
                relevance_score=0.0,
                error_message="Kaggle retrieval disabled"
            )
        
        # Check relevance gate
        is_relevant, relevance_score = self._is_relevant_for_kaggle(prompt, intent, entities)
        
        if not is_relevant:
            logger.debug(f"Query not relevant for Kaggle (relevance_score: {relevance_score:.2f})")
            return KaggleRetrievalResult(
                success=False,
                evidence_items=[],
                relevance_score=relevance_score,
                error_message="Query not relevant for Kaggle datasets"
            )
        
        logger.info(f"Kaggle retrieval relevant (score: {relevance_score:.2f}), attempting search...")
        
        # Get Kaggle searcher
        searcher = self._get_kaggle_searcher()
        if searcher is None:
            logger.warning("Kaggle searcher not available, falling back to FakeLLM")
            return KaggleRetrievalResult(
                success=False,
                evidence_items=[],
                relevance_score=relevance_score,
                error_message="Kaggle searcher not available"
            )
        
        # Perform search with timeout
        try:
            # Run search in executor to allow timeout
            loop = asyncio.get_event_loop()
            
            # Create search task
            search_task = loop.run_in_executor(
                None,
                lambda: searcher.search(prompt, max_results=max_results)
            )
            
            # Wait with timeout
            results, max_correlation = await asyncio.wait_for(
                search_task,
                timeout=self.timeout_seconds
            )
            
            # Check if results meet correlation threshold
            if max_correlation < self.correlation_threshold:
                logger.info(f"Kaggle results below threshold (correlation: {max_correlation:.3f} < {self.correlation_threshold})")
                return KaggleRetrievalResult(
                    success=False,
                    evidence_items=[],
                    relevance_score=relevance_score,
                    error_message=f"Correlation below threshold ({max_correlation:.3f} < {self.correlation_threshold})"
                )
            
            # Normalize results
            evidence_items = self._normalize_kaggle_results(results)
            
            logger.info(f"Kaggle retrieval successful: {len(evidence_items)} evidence items (correlation: {max_correlation:.3f})")
            
            return KaggleRetrievalResult(
                success=True,
                evidence_items=evidence_items,
                relevance_score=relevance_score,
                error_message=None
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"Kaggle search timed out after {self.timeout_seconds}s, falling back to FakeLLM")
            return KaggleRetrievalResult(
                success=False,
                evidence_items=[],
                relevance_score=relevance_score,
                error_message="Kaggle search timed out",
                timeout=True
            )
        except Exception as e:
            logger.warning(f"Kaggle search failed: {e}, falling back to FakeLLM")
            return KaggleRetrievalResult(
                success=False,
                evidence_items=[],
                relevance_score=relevance_score,
                error_message=str(e)
            )
    
    def convert_to_evidence_bundle(self, result: KaggleRetrievalResult) -> Optional[Dict]:
        """
        Convert KaggleRetrievalResult to EvidenceBundle-compatible format.
        
        Ensures format matches EvidenceFormatter expectations:
        - Must have non-empty content (already filtered in _normalize_kaggle_results)
        - Should have title, url, year for deduplication
        - Source should be "kaggle_imdb" (will be mapped to "Structured IMDb dataset" by EvidenceFormatter)
        
        Args:
            result: KaggleRetrievalResult
            
        Returns:
            Dictionary compatible with EvidenceBundle format, or None if no evidence
        """
        if not result.success or not result.evidence_items:
            return None
        
        # Convert to search_results format (compatible with EvidenceFormatter)
        search_results = []
        for item in result.evidence_items:
            # Build search result dict in format expected by EvidenceFormatter
            search_result = {
                "title": item.title,
                "url": item.url,
                "content": item.content,  # Must be non-empty (already checked in _normalize_kaggle_results)
                "source": item.source,  # "kaggle_imdb" - EvidenceFormatter maps to "Structured IMDb dataset"
            }
            
            # Add year if available (for deduplication - EvidenceFormatter uses title+year)
            if item.year:
                search_result["year"] = item.year
            
            # Add metadata for internal tracking (not exposed to user via EvidenceFormatter)
            if item.metadata:
                search_result["metadata"] = item.metadata
            
            search_results.append(search_result)
        
        return {
            "search_results": search_results,
            "verified_facts": None,
            "source": "kaggle"
        }


# Global singleton instance (configurable)
_kaggle_adapter_instance: Optional[KaggleRetrievalAdapter] = None


def get_kaggle_adapter(
    enabled: bool = True,
    timeout_seconds: float = DEFAULT_KAGGLE_TIMEOUT
) -> KaggleRetrievalAdapter:
    """
    Get singleton instance of KaggleRetrievalAdapter.
    
    Args:
        enabled: Whether Kaggle retrieval is enabled
        timeout_seconds: Timeout for Kaggle searches
        
    Returns:
        KaggleRetrievalAdapter instance
    """
    global _kaggle_adapter_instance
    
    if _kaggle_adapter_instance is None or \
       _kaggle_adapter_instance.enabled != enabled or \
       _kaggle_adapter_instance.timeout_seconds != timeout_seconds:
        _kaggle_adapter_instance = KaggleRetrievalAdapter(
            enabled=enabled,
            timeout_seconds=timeout_seconds
        )
    
    return _kaggle_adapter_instance

