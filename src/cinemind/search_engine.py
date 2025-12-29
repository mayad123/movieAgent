"""
Real-time web search engine for movie data.

Performance optimizations:
- Parallel search execution: Multiple searches run concurrently using asyncio.gather
- Parallel movie and news searches: Movie info and news searches run simultaneously
- Kaggle dataset search first: Checks IMDB dataset before calling Tavily API
"""
import os
import re
import requests
import httpx
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TavilyOverrideReason(Enum):
    """Valid reasons for overriding skip_tavily flag."""
    DISAMBIGUATION_NEEDED = "disambiguation_needed"
    STRUCTURED_LOOKUP_EMPTY = "structured_lookup_empty"
    TIER_A_REQUIRED_BUT_MISSING = "tier_a_required_but_missing"


@dataclass
class SearchDecision:
    """Structured metadata about search decisions."""
    tavily_used: bool = False
    override_used: bool = False
    override_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tavily_used": self.tavily_used,
            "override_used": self.override_used,
            "override_reason": self.override_reason
        }


class SearchEngine:
    """Handles real-time web searches for movie information."""
    
    def __init__(self, tavily_api_key: Optional[str] = None, enable_kaggle: Optional[bool] = None):
        """
        Initialize search engine.
        
        Args:
            tavily_api_key: Tavily API key for real-time search
            enable_kaggle: Whether to enable Kaggle dataset search (default: from config)
        """
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.session = httpx.AsyncClient(timeout=30.0)
        
        # Initialize Kaggle searcher if enabled
        from .config import ENABLE_KAGGLE_SEARCH, KAGGLE_CORRELATION_THRESHOLD, KAGGLE_DATASET_PATH
        self.enable_kaggle = enable_kaggle if enable_kaggle is not None else ENABLE_KAGGLE_SEARCH
        self.kaggle_searcher = None
        
        if self.enable_kaggle:
            try:
                from .kaggle_search import KaggleDatasetSearcher
                self.kaggle_searcher = KaggleDatasetSearcher(
                    dataset_path=KAGGLE_DATASET_PATH,
                    correlation_threshold=KAGGLE_CORRELATION_THRESHOLD
                )
                logger.info(f"Kaggle dataset search enabled (threshold: {KAGGLE_CORRELATION_THRESHOLD})")
            except Exception as e:
                logger.warning(f"Failed to initialize Kaggle searcher: {e}. Continuing without Kaggle search.")
                self.kaggle_searcher = None
                self.enable_kaggle = False
    
    def build_intent_queries(self, intent: str, entities: List[str], 
                           request_type: str = "info") -> List[str]:
        """
        Build intent-specific search queries that bias toward Tier A sources.
        
        Args:
            intent: Structured intent (e.g., "filmography_overlap")
            entities: Extracted entities (person names, movie titles)
            request_type: Request classification type
        
        Returns:
            List of optimized search queries
        """
        queries = []
        
        if intent == "filmography_overlap" and len(entities) >= 2:
            # Filmography overlap: bias to IMDb and Wikipedia
            person1, person2 = entities[0], entities[1]
            
            # IMDb-specific queries
            queries.append(f'site:imdb.com "{person1}" "{person2}" film')
            queries.append(f'site:imdb.com {person1} {person2} movies together')
            
            # Wikipedia-specific queries
            queries.append(f'site:wikipedia.org {person1} {person2} film')
            queries.append(f'site:wikipedia.org "{person1}" "{person2}" collaboration')
            
            # General query (fallback)
            queries.append(f'{person1} {person2} movies together')
        
        elif intent == "director_info" and entities:
            # Director info: IMDb and Wikipedia
            movie = entities[0] if entities else ""
            queries.append(f'site:imdb.com "{movie}" director')
            queries.append(f'site:wikipedia.org "{movie}" film director')
            queries.append(f'who directed {movie}')
        
        elif intent == "release_date" and entities:
            # Release date: IMDb and Wikipedia
            movie = entities[0] if entities else ""
            queries.append(f'site:imdb.com "{movie}" release date')
            queries.append(f'site:wikipedia.org "{movie}" film {movie} release')
            queries.append(f'{movie} release date')
        
        elif intent == "cast_info" and entities:
            # Cast info: IMDb
            movie = entities[0] if entities else ""
            queries.append(f'site:imdb.com "{movie}" cast')
            queries.append(f'site:imdb.com/title "{movie}" full cast')
            queries.append(f'{movie} cast actors')
        
        else:
            # Generic query
            entity_str = " ".join(entities) if entities else ""
            queries.append(entity_str if entity_str else "movie")
        
        return queries
    
    async def search(self, query: str, max_results: int = 5, skip_tavily: bool = False,
                    override_reason: Optional[str] = None) -> Tuple[List[Dict], SearchDecision]:
        """
        Perform real-time search for movie information.
        
        NOTE: This is called AFTER cache check. Pipeline order:
        1. Cache (checked in agent.py before this method)
        2. Kaggle IMDB dataset (if enabled and highly correlated)
        3. Tavily API (only if skip_tavily=False OR valid override_reason provided)
        4. Web search fallback (if above methods fail)
        
        IMPORTANT: Low Kaggle correlation does NOT override skip_tavily flag.
        Tavily can only be used when skip_tavily=True if an explicit override_reason is provided:
        - disambiguation_needed
        - structured_lookup_empty (no usable Kaggle/structured results)
        - tier_a_required_but_missing (fact-check/info requires Tier A but no Tier A evidence found)
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            skip_tavily: Tool plan suggestion to skip Tavily
            override_reason: Optional explicit reason for overriding skip_tavily (must be one of TavilyOverrideReason values)
            
        Returns:
            (results: List[Dict], decision: SearchDecision) where decision contains:
            - tavily_used: bool - Whether Tavily was actually used
            - override_used: bool - Whether tool plan decision was overridden
            - override_reason: Optional[str] - Reason for override (if any)
        """
        results = []
        decision = SearchDecision()
        
        # Step 1: Try Kaggle dataset first if enabled
        kaggle_has_results = False
        max_correlation = 0.0
        if self.enable_kaggle and self.kaggle_searcher:
            try:
                # Run Kaggle search in thread pool to avoid blocking event loop
                import asyncio
                loop = asyncio.get_event_loop()
                is_highly_correlated, kaggle_results, max_correlation = await loop.run_in_executor(
                    None,
                    self.kaggle_searcher.is_highly_correlated,
                    query,
                    max_results
                )
                
                if is_highly_correlated and kaggle_results:
                    logger.info(f"Using Kaggle dataset results (correlation: {max_correlation:.3f})")
                    results.extend(kaggle_results)
                    kaggle_has_results = True
                    # If we have highly correlated results, skip Tavily API call
                    decision.tavily_used = False
                    decision.override_used = False
                    decision.override_reason = None
                    return (results[:max_results], decision)
                else:
                    logger.info(f"Kaggle results not highly correlated ({max_correlation:.3f}) or empty")
            except Exception as e:
                logger.warning(f"Kaggle search failed: {e}")
        
        # Step 2: Determine if Tavily should be used
        # Only allow Tavily if skip_tavily=False OR a valid override_reason is provided
        should_use_tavily = False
        if not skip_tavily:
            # Tool plan allows Tavily
            should_use_tavily = True
            logger.info(f"Tavily allowed by tool plan")
        elif override_reason:
            # Check if override_reason is valid
            valid_reasons = [reason.value for reason in TavilyOverrideReason]
            if override_reason in valid_reasons:
                should_use_tavily = True
                decision.override_used = True
                decision.override_reason = override_reason
                logger.info(f"Tavily override: {override_reason} (skip_tavily was True)")
            else:
                logger.warning(f"Invalid override_reason '{override_reason}', ignoring. Valid reasons: {valid_reasons}")
        else:
            # skip_tavily=True and no override_reason provided - do NOT use Tavily
            logger.info(f"Skipping Tavily API (skip_tavily=True, no valid override_reason provided)")
        
        # Step 3: Try Tavily if allowed
        if should_use_tavily and self.tavily_api_key:
            try:
                tavily_results = await self._search_tavily(query, max_results)
                results.extend(tavily_results)
                decision.tavily_used = True
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")
        
        # Step 4: Fallback to direct web search if needed (use same logic as Tavily)
        if not results and should_use_tavily:
            try:
                web_results = await self._search_web_fallback(query, max_results)
                results.extend(web_results)
                decision.tavily_used = True  # Web fallback counts as Tavily usage
            except Exception as e:
                logger.warning(f"Web search fallback failed: {e}")
        
        return (results[:max_results], decision)
    
    async def _search_tavily(self, query: str, max_results: int) -> List[Dict]:
        """Search using Tavily API."""
        try:
            from tavily import TavilyClient
            
            client = TavilyClient(api_key=self.tavily_api_key)
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,
                include_raw_content=False
            )
            
            results = []
            for result in response.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "published_date": result.get("published_date"),
                    "source": "tavily"
                })
            
            # Include answer if available
            if response.get("answer"):
                results.insert(0, {
                    "title": "Tavily Answer",
                    "url": "",
                    "content": response["answer"],
                    "score": 1.0,
                    "source": "tavily_answer"
                })
            
            return results
        except ImportError:
            logger.error("Tavily client not installed. Install with: pip install tavily-python")
            return []
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []
    
    async def _search_web_fallback(self, query: str, max_results: int) -> List[Dict]:
        """
        Fallback web search using DuckDuckGo or similar.
        Note: This is a basic implementation. For production, consider
        using official APIs or more robust search providers.
        """
        try:
            # DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com"
            params = {
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
                "skip_disambig": "1"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    # Extract abstract/answer
                    if data.get("AbstractText"):
                        results.append({
                            "title": data.get("Heading", query),
                            "url": data.get("AbstractURL", ""),
                            "content": data.get("AbstractText", ""),
                            "source": "duckduckgo"
                        })
                    
                    # Extract related topics
                    for topic in data.get("RelatedTopics", [])[:max_results-1]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else query,
                                "url": topic.get("FirstURL", ""),
                                "content": topic.get("Text", ""),
                                "source": "duckduckgo"
                            })
                    
                    return results[:max_results]
        except Exception as e:
            logger.error(f"Web search fallback error: {e}")
        
        return []
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """
        Deduplicate search results using a composite key.
        
        Dedup key: (url if present) else (title + year + source)
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            Deduplicated list of results
        """
        seen_keys = set()
        unique_results = []
        
        for result in results:
            # Skip if result is not a dict
            if not isinstance(result, dict):
                continue
            
            # Build deduplication key
            url = result.get("url", "") or ""
            if url:
                # Use URL as primary key
                dedup_key = url
            else:
                # Fallback to title + year + source
                title = str(result.get("title", "") or "")
                published_date = result.get("published_date")
                year = ""
                if published_date:
                    # Extract year from published_date if available
                    try:
                        if isinstance(published_date, str):
                            # Try to parse date string (handle various formats)
                            date_str = published_date.replace('Z', '+00:00')
                            try:
                                date_obj = datetime.fromisoformat(date_str)
                                year = str(date_obj.year)
                            except (ValueError, AttributeError):
                                # Try extracting year from string (e.g., "2024-01-01" -> "2024")
                                year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
                                if year_match:
                                    year = year_match.group(0)
                        elif isinstance(published_date, (int, float)):
                            year = str(int(published_date))
                    except (ValueError, AttributeError, TypeError):
                        pass
                source = str(result.get("source", "") or "")
                dedup_key = f"{title}|{year}|{source}"
            
            # Add result if we haven't seen this key before
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                unique_results.append(result)
        
        return unique_results
    
    def _sort_results_by_score(self, results: List[Dict]) -> List[Dict]:
        """
        Sort results by score (highest first) for stable ordering.
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            Sorted list of results (highest score first)
        """
        # Sort by score (descending), then by title for stable ordering
        def sort_key(result: Dict) -> Tuple[float, str]:
            score = float(result.get("score", 0.0) or 0.0)
            title = str(result.get("title", "") or "")
            return (-score, title)  # Negative score for descending order
        
        return sorted(results, key=sort_key)
    
    async def search_movie_specific(self, movie_title: str, year: Optional[int] = None) -> List[Dict]:
        """
        Search for specific movie information.
        
        Args:
            movie_title: Title of the movie
            year: Optional release year
            
        Returns:
            List of deduplicated, sorted search results (highest score first)
        """
        # Search multiple sources in parallel
        queries = [
            f"{movie_title} {year if year else ''} IMDb",
            f"{movie_title} {year if year else ''} Rotten Tomatoes",
            f"{movie_title} {year if year else ''} review",
            f"{movie_title} {year if year else ''} cast crew"
        ]
        
        # Run all searches in parallel
        import asyncio
        search_tasks = [self.search(q, max_results=2, skip_tavily=False) for q in queries]
        all_results_tuples = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Flatten results and handle exceptions
        all_results = []
        for result_tuple in all_results_tuples:
            if isinstance(result_tuple, Exception):
                logger.warning(f"Search task failed: {result_tuple}")
                continue
            if isinstance(result_tuple, tuple):
                # Extract results from tuple (results, decision)
                results, decision = result_tuple
                if isinstance(results, list):
                    all_results.extend(results)
            elif isinstance(result_tuple, list):
                # Backward compatibility: handle old return format (list only)
                all_results.extend(result_tuple)
        
        # Deduplicate results
        unique_results = self._deduplicate_results(all_results)
        
        # Sort by score (highest first) for stable ordering
        sorted_results = self._sort_results_by_score(unique_results)
        
        return sorted_results[:10]
    
    def close(self):
        """Close the HTTP session (synchronous wrapper)."""
        # Note: In async context, call async_close() instead
        pass
    
    async def async_close(self):
        """Close the HTTP session."""
        await self.session.aclose()


class MovieDataAggregator:
    """Aggregates movie data from multiple sources with source policy enforcement."""
    
    def __init__(self, search_engine: SearchEngine, source_policy=None):
        self.search_engine = search_engine
        self.source_policy = source_policy
    
    async def get_movie_info(self, query: str, include_recent_news: bool = True,
                           intent: Optional[str] = None, entities: Optional[List[str]] = None,
                           request_type: str = "info", skip_tavily: bool = False,
                           override_reason: Optional[str] = None,
                           request_plan = None) -> Dict:
        """
        Get comprehensive movie information from multiple sources with source policy.
        
        Args:
            query: Movie title or search query
            include_recent_news: Whether to include recent news/articles
            intent: Structured intent (for query optimization)
            entities: Extracted entities (for query optimization)
            request_type: Request classification type (for source filtering)
            
        Returns:
            Dictionary with aggregated movie information and source metadata
        """
        import asyncio
        
        # Build intent-specific queries if available
        if intent and entities and self.source_policy:
            queries = self.search_engine.build_intent_queries(intent, entities, request_type)
        else:
            queries = [query]
        
        # Run searches in parallel
        tasks = []
        for q in queries[:3]:  # Limit to 3 queries to avoid too many API calls
            tasks.append(self.search_engine.search(q, max_results=5, skip_tavily=skip_tavily, override_reason=override_reason))
        
        if include_recent_news and not skip_tavily:
            news_query = f"{query} movie news 2024 2025"
            tasks.append(self.search_engine.search(news_query, max_results=3, skip_tavily=skip_tavily, override_reason=override_reason))
        
        results_tuples = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results and aggregate Tavily usage metadata
        raw_results = []
        tavily_used_any = False
        override_used_any = False
        override_reasons = set()
        
        for result_tuple in results_tuples:
            if isinstance(result_tuple, Exception):
                logger.warning(f"Search task failed: {result_tuple}")
                continue
            if isinstance(result_tuple, tuple):
                results, decision = result_tuple
                # Handle both SearchDecision objects and old dict format for backward compatibility
                if isinstance(decision, SearchDecision):
                    raw_results.extend(results)
                    if decision.tavily_used:
                        tavily_used_any = True
                    if decision.override_used:
                        override_used_any = True
                    if decision.override_reason:
                        override_reasons.add(decision.override_reason)
                elif isinstance(decision, dict):
                    # Backward compatibility: handle old dict format
                    raw_results.extend(results)
                    if decision.get("tavily_used"):
                        tavily_used_any = True
                    if decision.get("override_used"):
                        override_used_any = True
                    if decision.get("override_reason"):
                        override_reasons.add(decision["override_reason"])
            elif isinstance(result_tuple, list):
                # Backward compatibility: handle old return format (list only)
                raw_results.extend(result_tuple)
        
        # Apply source policy if available
        if self.source_policy:
            # Use RequestPlan if provided, otherwise fallback to request_type
            if request_plan is not None:
                ranked_sources, filter_metadata = self.source_policy.rank_and_filter(
                    raw_results, plan_or_constraints=request_plan
                )
            else:
                ranked_sources, filter_metadata = self.source_policy.rank_and_filter(
                    raw_results, plan_or_constraints=request_type
                )
            
            # Convert back to dict format for compatibility
            results = []
            source_summary = self.source_policy.get_source_summary(ranked_sources)
            # Include filtering metadata in source_summary
            source_summary.update(filter_metadata)
            
            for source in ranked_sources:
                results.append({
                    "title": source.title,
                    "url": source.url,
                    "content": source.content,
                    "score": source.score,
                    "published_date": source.published_date,
                    "source": source.source_name,  # Preserve original source (kaggle_imdb, tavily, etc.)
                    "tier": source.tier.value,
                    "domain": source.domain
                })
        else:
            results = raw_results
            source_summary = {}
        
        # Determine final override reason (use first one if multiple)
        override_reason_final = list(override_reasons)[0] if override_reasons else None
        
        return {
            "query": query,
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "source_count": len(results),
            "source_summary": source_summary,
            "tavily_used": tavily_used_any,
            "override_used": override_used_any,
            "override_reason": override_reason_final
        }

