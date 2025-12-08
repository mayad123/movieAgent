"""
CineMind - Real-time Movie Analysis and Discovery Agent
"""
import os
import json
import logging
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from config import SYSTEM_PROMPT, AGENT_NAME, AGENT_VERSION, OPENAI_MODEL
from search_engine import SearchEngine, MovieDataAggregator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CineMind:
    """
    CineMind agent for real-time movie analysis and discovery.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None, tavily_api_key: Optional[str] = None):
        """
        Initialize CineMind agent.
        
        Args:
            openai_api_key: OpenAI API key for LLM
            tavily_api_key: Tavily API key for real-time search
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
        
        logger.info(f"Initialized {self.agent_name} v{self.version}")
    
    async def search_and_analyze(self, user_query: str, use_live_data: bool = True) -> Dict:
        """
        Search for real-time movie data and provide analysis.
        
        Args:
            user_query: User's question about movies
            use_live_data: Whether to perform real-time searches
            
        Returns:
            Dictionary with agent response and sources
        """
        logger.info(f"Processing query: {user_query}")
        
        # Perform real-time search if requested
        search_results = []
        search_context = ""
        
        if use_live_data:
            try:
                logger.info("Performing real-time search...")
                movie_info = await self.aggregator.get_movie_info(user_query, include_recent_news=True)
                search_results = movie_info.get("results", [])
                
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
                logger.error(f"Search failed: {e}")
                search_context = "\n\nNote: Real-time search encountered an error. Providing answer based on training data.\n"
        
        # Construct the prompt with search context
        user_message = user_query
        if search_context:
            user_message = search_context + "\n\nUser Question: " + user_query
        
        # Generate response using OpenAI
        try:
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
            
            return {
                "agent": self.agent_name,
                "version": self.version,
                "query": user_query,
                "response": agent_response,
                "sources": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "source": r.get("source", "unknown")
                    }
                    for r in search_results
                ],
                "timestamp": datetime.now().isoformat(),
                "live_data_used": use_live_data
            }
        
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
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
    
    async def stream_response(self, user_query: str, use_live_data: bool = True) -> AsyncGenerator[str, None]:
        """
        Stream response token by token.
        
        Args:
            user_query: User's question
            use_live_data: Whether to perform real-time searches
            
        Yields:
            Response tokens
        """
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

