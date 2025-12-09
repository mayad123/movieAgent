"""
CineMind - Real-time Movie Analysis and Discovery Agent

Performance optimizations:
- Fast pattern-based request classification (no blocking LLM call)
- Parallel search execution (multiple searches run concurrently)
- Non-blocking database writes (runs in background thread pool)
"""
import os
import json
import logging
import uuid
import time
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from .config import SYSTEM_PROMPT, AGENT_NAME, AGENT_VERSION, OPENAI_MODEL
from .search_engine import SearchEngine, MovieDataAggregator
from .database import Database
from .observability import Observability, calculate_openai_cost
from .tagging import RequestTagger, classify_with_llm

# Configure logging (simple format, request_id added in observability)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CineMind:
    """
    CineMind agent for real-time movie analysis and discovery.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None, tavily_api_key: Optional[str] = None,
                 enable_observability: bool = True):
        """
        Initialize CineMind agent.
        
        Args:
            openai_api_key: OpenAI API key for LLM
            tavily_api_key: Tavily API key for real-time search
            enable_observability: Enable request tracking and metrics
        """
        if not AsyncOpenAI:
            raise ImportError("OpenAI library not installed. Install with: pip install openai")
        
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = AsyncOpenAI(api_key=self.openai_api_key)
        self.search_engine = SearchEngine(tavily_api_key=tavily_api_key)
        self.aggregator = MovieDataAggregator(self.search_engine)
        self.system_prompt = SYSTEM_PROMPT
        self.agent_name = AGENT_NAME
        self.version = AGENT_VERSION
        
        # Initialize observability
        self.enable_observability = enable_observability
        if enable_observability:
            db = Database()
            self.observability = Observability(db)
        else:
            self.observability = None
        
        # Initialize tagger
        self.tagger = RequestTagger()
        
        logger.info(f"Initialized {self.agent_name} v{self.version} (observability: {enable_observability})")
    
    async def search_and_analyze(self, user_query: str, use_live_data: bool = True,
                                request_id: Optional[str] = None,
                                request_type: Optional[str] = None,
                                outcome: Optional[str] = None) -> Dict:
        """
        Search for real-time movie data and provide analysis.
        
        Args:
            user_query: User's question about movies
            use_live_data: Whether to perform real-time searches
            request_id: Optional request ID for tracking (auto-generated if not provided)
            request_type: Optional request type tag (auto-classified if not provided)
            outcome: Optional outcome tag (can be set later)
            
        Returns:
            Dictionary with agent response and sources
        """
        # Generate or use provided request ID
        if not request_id:
            request_id = self.observability.generate_request_id() if self.observability else str(uuid.uuid4())
        
        # Auto-classify request type if not provided
        # Use fast pattern matching by default (LLM classification is slow and adds latency)
        if not request_type:
            request_type = self.tagger.classify_request_type(user_query)
        
        # Track request if observability is enabled
        if self.observability:
            track_ctx = self.observability.track_request(
                request_id, user_query, use_live_data, OPENAI_MODEL, request_type=request_type
            )
            tracker = track_ctx.__enter__()
        else:
            tracker = None
            track_ctx = None
            logger.info(f"[{request_id}] Processing query: {user_query} [type: {request_type}]")
        
        try:
            search_start = time.time()
            
            # Perform real-time search if requested
            search_results = []
            search_context = ""
            
            if use_live_data:
                try:
                    if tracker:
                        with tracker.time_operation("search"):
                            movie_info = await self.aggregator.get_movie_info(user_query, include_recent_news=True)
                    else:
                        logger.info(f"[{request_id}] Performing real-time search...")
                        movie_info = await self.aggregator.get_movie_info(user_query, include_recent_news=True)
                    
                    search_results = movie_info.get("results", [])
                    search_time_ms = (time.time() - search_start) * 1000
                    
                    # Log search operation
                    if tracker:
                        tracker.log_search(
                            query=user_query,
                            provider="tavily",
                            results_count=len(search_results),
                            search_time_ms=search_time_ms
                        )
                    
                    # Format search results for context
                    if search_results:
                        search_context = "\n\n=== REAL-TIME SEARCH RESULTS ===\n"
                        for i, result in enumerate(search_results[:5], 1):
                            source = result.get("source", "unknown")
                            title = result.get("title", "No title")
                            content = result.get("content", "")[:500]  # Truncate long content
                            url = result.get("url", "")
                            
                            search_context += f"\n[{i}] Source: {source}\n"
                            search_context += f"Title: {title}\n"
                            if url:
                                search_context += f"URL: {url}\n"
                            search_context += f"Content: {content}\n"
                        
                        search_context += "\nUse this current data to answer the user's question.\n"
                        search_context += "Distinguish between confirmed facts and rumors.\n"
                
                except Exception as e:
                    if tracker:
                        tracker.log_error(f"Search failed: {e}")
                    logger.error(f"[{request_id}] Search failed: {e}")
                    search_context = "\n\nNote: Real-time search encountered an error. Providing answer based on training data.\n"
            
            # Construct the prompt with search context
            user_message = user_query
            if search_context:
                user_message = search_context + "\n\nUser Question: " + user_query
            
            # Construct full prompt (system + user message) for storage
            full_prompt = f"System: {self.system_prompt}\n\nUser: {user_message}"
            
            # Update request with full prompt in database
            if self.observability:
                self.observability.update_request_prompt(request_id, full_prompt)
            
            # Generate response using OpenAI
            llm_start = time.time()
            try:
                if tracker:
                    with tracker.time_operation("openai_llm"):
                        response = await self.client.chat.completions.create(
                            model=OPENAI_MODEL,
                            messages=[
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": user_message}
                            ],
                            temperature=0.7,
                            max_tokens=2000
                        )
                else:
                    response = await self.client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=[
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=0.7,
                        max_tokens=2000
                    )
                
                agent_response = response.choices[0].message.content
                llm_time_ms = (time.time() - llm_start) * 1000
                
                # Extract token usage and calculate cost
                usage = response.usage.__dict__ if response.usage else {}
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
                cost_usd = calculate_openai_cost(token_usage, OPENAI_MODEL)
                
                # Log metrics
                if tracker:
                    tracker.log_metric("llm_response_time_ms", llm_time_ms)
                    tracker.log_metric("prompt_tokens", token_usage["prompt_tokens"])
                    tracker.log_metric("completion_tokens", token_usage["completion_tokens"])
                    tracker.log_metric("total_tokens", token_usage["total_tokens"])
                    tracker.log_metric("cost_usd", cost_usd)
                
                # Save response to database (non-blocking)
                sources_list = [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "source": r.get("source", "unknown")
                    }
                    for r in search_results
                ]
                
                # Format search results for test results (with rank, metadata)
                formatted_searches = []
                if use_live_data and search_results:
                    # Get search query from movie_info if available, otherwise use user_query
                    search_query = user_query
                    search_timestamp = datetime.now().isoformat()
                    try:
                        if 'movie_info' in locals() and movie_info:
                            search_query = movie_info.get("query", user_query)
                            search_timestamp = movie_info.get("timestamp", search_timestamp)
                    except:
                        pass
                    
                    search_results_formatted = []
                    
                    for rank, result in enumerate(search_results, 1):
                        # Extract source name (e.g., "tavily" -> "Tavily", "imdb" -> "IMDb")
                        source_name = result.get("source", "unknown")
                        if source_name == "tavily":
                            # Try to infer source from URL
                            url = result.get("url", "")
                            if "wikipedia.org" in url:
                                source_name = "Wikipedia"
                            elif "imdb.com" in url:
                                source_name = "IMDb"
                            elif "rottentomatoes.com" in url:
                                source_name = "Rotten Tomatoes"
                            elif "variety.com" in url:
                                source_name = "Variety"
                            elif "deadline.com" in url:
                                source_name = "Deadline"
                            else:
                                source_name = "Tavily"
                        elif source_name == "tavily_answer":
                            source_name = "Tavily Answer"
                        else:
                            source_name = source_name.capitalize()
                        
                        search_results_formatted.append({
                            "rank": rank,
                            "source": source_name,
                            "url": result.get("url", ""),
                            "title": result.get("title", ""),
                            "published_at": result.get("published_date") or result.get("published_at"),
                            "last_updated_at": result.get("last_updated_at") or search_timestamp
                        })
                    
                    formatted_searches.append({
                        "query": search_query,
                        "results": search_results_formatted
                    })
                
                # Run database writes in background to avoid blocking
                if self.observability:
                    import asyncio
                    def save_to_db():
                        try:
                            self.observability.db.save_response(
                                request_id=request_id,
                                response_text=agent_response,
                                sources=sources_list,
                                token_usage=token_usage,
                                cost_usd=cost_usd
                            )
                            if outcome:
                                self.observability.db.update_request(request_id, outcome=outcome)
                        except Exception as e:
                            logger.error(f"Background DB write failed: {e}")
                    
                    # Fire and forget - run sync DB writes in thread pool
                    asyncio.create_task(asyncio.to_thread(save_to_db))
                
                # Update outcome if provided (for metrics)
                if outcome and tracker:
                    tracker.log_metric("outcome", 1.0, {"outcome": outcome})
                
                # Get configuration versions
                from .config import PROMPT_VERSION, AGENT_VERSION
                
                result = {
                    "agent": self.agent_name,
                    "version": self.version,
                    "request_id": request_id,
                    "query": user_query,
                    "response": agent_response,
                    "sources": sources_list,
                    "timestamp": datetime.now().isoformat(),
                    "live_data_used": use_live_data,
                    "token_usage": token_usage,
                    "cost_usd": cost_usd,
                    "request_type": request_type,
                    "outcome": outcome or "success",  # Default to success if not set
                    "prompt": full_prompt,  # Include the full prompt that was sent
                    "searches": formatted_searches,  # Formatted search results
                    "model_version": OPENAI_MODEL,  # Model version (e.g., "gpt-3.5-turbo")
                    "prompt_version": PROMPT_VERSION,  # Prompt version (e.g., "v1")
                    "agent_config_version": f"cine_prompt_{PROMPT_VERSION}"  # Agent config version
                }
                
                if track_ctx:
                    track_ctx.__exit__(None, None, None)
                
                return result
            
            except Exception as e:
                if tracker:
                    tracker.log_error(f"OpenAI API error: {e}")
                logger.error(f"[{request_id}] OpenAI API error: {e}")
                error_msg = str(e)
                
                # Provide helpful error messages
                if "model" in error_msg.lower() and ("not found" in error_msg.lower() or "does not exist" in error_msg.lower()):
                    raise Exception(
                        f"Model '{OPENAI_MODEL}' not found or not accessible.\n"
                        f"Please set OPENAI_MODEL in .env file to one of: gpt-3.5-turbo, gpt-4, gpt-4o"
                    )
                elif "quota" in error_msg.lower() or "429" in error_msg or "insufficient_quota" in error_msg.lower():
                    raise Exception(
                        "OpenAI API quota exceeded. Please check your billing and usage at:\n"
                        "https://platform.openai.com/usage\n"
                        "You may need to add payment method or upgrade your plan."
                    )
                elif "api key" in error_msg.lower() or "invalid" in error_msg.lower() or "401" in error_msg:
                    raise Exception(
                        "Invalid OpenAI API key. Please check your OPENAI_API_KEY in .env file."
                    )
                raise Exception(f"Failed to generate response: {e}")
        
        except Exception as e:
            if track_ctx:
                track_ctx.__exit__(type(e), e, e.__traceback__)
            raise
    
    async def stream_response(self, user_query: str, use_live_data: bool = True, 
                             request_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        Stream response token by token.
        
        Args:
            user_query: User's question
            use_live_data: Whether to perform real-time searches
            request_id: Optional request ID for tracking
            
        Yields:
            Response tokens
        """
        # Generate or use provided request ID
        if not request_id:
            request_id = self.observability.generate_request_id() if self.observability else str(uuid.uuid4())
        
        # Perform search first
        search_context = ""
        if use_live_data:
            try:
                movie_info = await self.aggregator.get_movie_info(user_query, include_recent_news=True)
                search_results = movie_info.get("results", [])
                
                if search_results:
                    search_context = "\n\n=== REAL-TIME SEARCH RESULTS ===\n"
                    for i, result in enumerate(search_results[:5], 1):
                        search_context += f"\n[{i}] {result.get('title', '')}\n"
                        search_context += f"{result.get('content', '')[:300]}\n"
                    search_context += "\nUse this current data to answer.\n"
            except Exception as e:
                logger.error(f"Search failed: {e}")
        
        user_message = search_context + "\n\nUser Question: " + user_query if search_context else user_query
        
        # Construct full prompt for storage
        full_prompt = f"System: {self.system_prompt}\n\nUser: {user_message}"
        
        # Save request with prompt if observability is enabled
        if self.observability:
            self.observability.db.save_request(
                request_id, user_query, use_live_data, OPENAI_MODEL, "pending",
                prompt=full_prompt
            )
        
        try:
            stream = await self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=2000,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"Error: {e}"
    
    async def close(self):
        """Close connections and cleanup."""
        await self.search_engine.async_close()
        if self.observability and hasattr(self.observability, 'db'):
            self.observability.db.close()
        logger.info("CineMind agent closed")


# CLI interface
async def main():
    """Command-line interface for CineMind."""
    import sys
    
    print(f"{AGENT_NAME} v{AGENT_VERSION} - Real-time Movie Analysis Agent")
    print("=" * 60)
    
    agent = CineMind()
    
    try:
        if len(sys.argv) > 1:
            # Single query mode
            query = " ".join(sys.argv[1:])
            print(f"\nQuery: {query}\n")
            print("Searching for latest information...\n")
            
            try:
                result = await agent.search_and_analyze(query, use_live_data=True)
                
                print("\n" + "=" * 60)
                print("RESPONSE:")
                print("=" * 60)
                print(result["response"])
                
                if result.get("sources"):
                    print("\n" + "=" * 60)
                    print("SOURCES:")
                    print("=" * 60)
                    for i, source in enumerate(result["sources"], 1):
                        if source.get("url"):
                            print(f"{i}. {source.get('title', 'Unknown')}")
                            print(f"   {source['url']}\n")
            except Exception as e:
                print(f"\n[Error]: {str(e)}\n")
                sys.exit(1)
        else:
            # Interactive mode
            print("\nEnter your movie questions (type 'exit' to quit):\n")
            
            while True:
                try:
                    query = input("[You]: ").strip()
                    
                    if query.lower() in ['exit', 'quit', 'q']:
                        break
                    
                    if not query:
                        continue
                    
                    print("\n[Searching for latest information...]")
                    result = await agent.search_and_analyze(query, use_live_data=True)
                    
                    print(f"\n[{AGENT_NAME}]:")
                    print(result["response"])
                    
                    if result["sources"]:
                        print("\n[Sources]:")
                        for i, source in enumerate(result["sources"][:3], 1):
                            if source["url"]:
                                print(f"  {i}. {source['title']} - {source['url']}")
                    
                    print("\n" + "-" * 60 + "\n")
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    error_msg = str(e)
                    print(f"\n[Error]: {error_msg}\n")
    
    finally:
        await agent.close()
        print("\n[Goodbye!]")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

