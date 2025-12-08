"""
Real-time web search engine for movie data.
"""
import os
import requests
import httpx
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SearchEngine:
    """Handles real-time web searches for movie information."""
    
    def __init__(self, tavily_api_key: Optional[str] = None):
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.session = httpx.AsyncClient(timeout=30.0)
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Perform real-time search for movie information.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of search results with title, url, content, and timestamp
        """
        results = []
        
        # Try Tavily first if API key is available
        if self.tavily_api_key:
            try:
                tavily_results = await self._search_tavily(query, max_results)
                results.extend(tavily_results)
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")
        
        # Fallback to direct web search if needed
        if not results:
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
        
        # Search multiple sources
        queries = [
            f"{movie_title} {year if year else ''} IMDb",
            f"{movie_title} {year if year else ''} Rotten Tomatoes",
            f"{movie_title} {year if year else ''} review",
            f"{movie_title} {year if year else ''} cast crew"
        ]
        
        all_results = []
        for q in queries:
            results = await self.search(q, max_results=2)
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
    """Aggregates movie data from multiple sources."""
    
    def __init__(self, search_engine: SearchEngine):
        self.search_engine = search_engine
    
    async def get_movie_info(self, query: str, include_recent_news: bool = True) -> Dict:
        """
        Get comprehensive movie information from multiple sources.
        
        Args:
            query: Movie title or search query
            include_recent_news: Whether to include recent news/articles
            
        Returns:
            Dictionary with aggregated movie information
        """
        results = await self.search_engine.search_movie_specific(query)
        
        if include_recent_news:
            news_query = f"{query} movie news 2024 2025"
            news_results = await self.search_engine.search(news_query, max_results=3)
            results.extend(news_results)
        
        return {
            "query": query,
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "source_count": len(results)
        }

