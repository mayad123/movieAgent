"""
Real-time web search engine for movie data.

Performance optimizations:
- Parallel search execution: Multiple searches run concurrently using asyncio.gather
- Parallel movie and news searches: Movie info and news searches run simultaneously
- Kaggle dataset search first: Checks IMDB dataset before calling Tavily API
"""
import os
import requests
import httpx
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
    
    async def search(self, query: str, max_results: int = 5, skip_tavily: bool = False) -> List[Dict]:
        """
        Perform real-time search for movie information.
        
        NOTE: This is called AFTER cache check. Pipeline order:
        1. Cache (checked in agent.py before this method)
        2. Kaggle IMDB dataset (if enabled and highly correlated)
        3. Tavily API (if Kaggle results not highly correlated, OVERRIDES skip_tavily flag)
        4. Web search fallback (if above methods fail)
        
        IMPORTANT: If Kaggle correlation is low (< threshold), Tavily will be used
        even if skip_tavily=True (overriding tool plan decision for stable intents).
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            skip_tavily: Tool plan suggestion to skip Tavily (will be overridden if Kaggle correlation is low)
            
        Returns:
            List of search results with title, url, content, and timestamp
        """
        results = []
        
        # Step 1: Try Kaggle dataset first if enabled
        kaggle_tried_and_low_correlation = False
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
                
                if is_highly_correlated:
                    logger.info(f"Using Kaggle dataset results (correlation: {max_correlation:.3f})")
                    results.extend(kaggle_results)
                    # If we have highly correlated results, skip Tavily API call
                    return results[:max_results]
                else:
                    kaggle_tried_and_low_correlation = True
                    logger.info(f"Kaggle results not highly correlated ({max_correlation:.3f}), {('overriding skip_tavily to use Tavily' if skip_tavily else 'proceeding to Tavily')}")
            except Exception as e:
                logger.warning(f"Kaggle search failed: {e}, {('overriding skip_tavily to use Tavily' if skip_tavily else 'proceeding to Tavily')}")
                kaggle_tried_and_low_correlation = True
        
        # Step 2: Try Tavily if API key is available
        # Override skip_tavily flag if Kaggle was tried and correlation is low (even for stable intents)
        # If Kaggle is not enabled, respect the skip_tavily flag from tool plan
        should_use_tavily = not skip_tavily or kaggle_tried_and_low_correlation
        
        if should_use_tavily and self.tavily_api_key:
            if skip_tavily and kaggle_tried_and_low_correlation:
                logger.info(f"Kaggle correlation ({max_correlation:.3f}) is low - overriding tool plan to use Tavily API")
            try:
                tavily_results = await self._search_tavily(query, max_results)
                results.extend(tavily_results)
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")
        elif not should_use_tavily:
            logger.info(f"Skipping Tavily API (high Kaggle correlation or tool plan override)")
        
        # Step 3: Fallback to direct web search if needed (use same logic as Tavily)
        if not results and should_use_tavily:
            try:
                web_results = await self._search_web_fallback(query, max_results)
                results.extend(web_results)
            except Exception as e:
                logger.warning(f"Web search fallback failed: {e}")
        
        return results[:max_results]
    
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
    
    async def search_movie_specific(self, movie_title: str, year: Optional[int] = None) -> List[Dict]:
        """
        Search for specific movie information.
        
        Args:
            movie_title: Title of the movie
            year: Optional release year
            
        Returns:
            List of search results
        """
        query = f"{movie_title} movie"
        if year:
            query += f" {year}"
        
        # Search multiple sources in parallel
        queries = [
            f"{movie_title} {year if year else ''} IMDb",
            f"{movie_title} {year if year else ''} Rotten Tomatoes",
            f"{movie_title} {year if year else ''} review",
            f"{movie_title} {year if year else ''} cast crew"
        ]
        
        # Run all searches in parallel
        import asyncio
        search_tasks = [self.search(q, max_results=2) for q in queries]
        all_results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Flatten results and handle exceptions
        all_results = []
        for results in all_results_lists:
            if isinstance(results, Exception):
                logger.warning(f"Search task failed: {results}")
                continue
            all_results.extend(results)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        return unique_results[:10]
    
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
                           request_type: str = "info", skip_tavily: bool = False) -> Dict:
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
            tasks.append(self.search_engine.search(q, max_results=5, skip_tavily=skip_tavily))
        
        if include_recent_news and not skip_tavily:
            news_query = f"{query} movie news 2024 2025"
            tasks.append(self.search_engine.search(news_query, max_results=3, skip_tavily=skip_tavily))
        
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        raw_results = []
        for result_list in results_lists:
            if isinstance(result_list, Exception):
                logger.warning(f"Search task failed: {result_list}")
                continue
            if isinstance(result_list, list):
                raw_results.extend(result_list)
        
        # Apply source policy if available
        if self.source_policy:
            ranked_sources = self.source_policy.rank_and_filter(
                raw_results, request_type, need_freshness=False
            )
            
            # Convert back to dict format for compatibility
            results = []
            source_summary = self.source_policy.get_source_summary(ranked_sources)
            
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
        
        return {
            "query": query,
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "source_count": len(results),
            "source_summary": source_summary
        }

