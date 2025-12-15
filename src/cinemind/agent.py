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
import re
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from .config import SYSTEM_PROMPT, AGENT_NAME, AGENT_VERSION, OPENAI_MODEL, PROMPT_VERSION
from .search_engine import SearchEngine, MovieDataAggregator
from .database import Database
from .observability import Observability, calculate_openai_cost
from .tagging import RequestTagger, HybridClassifier, classify_with_llm
from .cache import SemanticCache
from .source_policy import SourcePolicy
from .intent_extraction import IntentExtractor
from .verification import FactVerifier

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
        
        # Initialize source policy and related components
        self.source_policy = SourcePolicy()
        self.intent_extractor = IntentExtractor()
        self.verifier = FactVerifier(self.source_policy)
        
        # Initialize aggregator with source policy
        self.aggregator = MovieDataAggregator(self.search_engine, self.source_policy)
        
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
        
        # Initialize tagger and hybrid classifier
        self.tagger = RequestTagger()
        self.classifier = HybridClassifier()
        
        # Initialize semantic cache
        if enable_observability:
            self.cache = SemanticCache(self.observability.db)
        else:
            # Create a temporary database for cache if observability is disabled
            temp_db = Database()
            self.cache = SemanticCache(temp_db)
        
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
        
        # Auto-classify request type if not provided using hybrid classifier
        classification_result = None
        if not request_type:
            # Use hybrid classifier (rules → LLM → guardrails)
            classification_result = await self.classifier.classify(user_query, self.client)
            request_type = classification_result.predicted_type
            
            # Log classification metadata
            if self.observability:
                self.observability.log_classification_metadata(
                    request_id,
                    predicted_type=classification_result.predicted_type,
                    rule_hit=classification_result.rule_hit,
                    llm_used=classification_result.llm_used,
                    confidence=classification_result.confidence,
                    entities=classification_result.entities,
                    need_freshness=classification_result.need_freshness
                )
        else:
            # If request_type was provided, create a minimal classification result
            classification_result = type('obj', (object,), {
                'predicted_type': request_type,
                'entities': [],
                'need_freshness': False
            })()
            # Still log it
            if self.observability:
                self.observability.log_classification_metadata(
                    request_id,
                    predicted_type=request_type,
                    rule_hit="user_provided",
                    llm_used=False,
                    confidence=1.0
                )
        
        # Check cache before making API calls
        cache_hit = None
        if self.cache and use_live_data:  # Only check cache if we would normally use live data
            try:
                entities = getattr(classification_result, 'entities', []) if classification_result else []
                need_freshness = getattr(classification_result, 'need_freshness', False) if classification_result else False
                
                cache_hit = self.cache.get(
                    prompt=user_query,
                    classifier_type="hybrid",
                    tool_config_version=f"cine_prompt_{PROMPT_VERSION}",
                    predicted_type=request_type,
                    entities=entities,
                    need_freshness=need_freshness
                )
            except Exception as e:
                logger.warning(f"Cache lookup failed: {e}, proceeding with normal flow")
        
        # If cache hit, return cached response
        if cache_hit:
            logger.info(f"[{request_id}] Cache {cache_hit.cache_tier} hit! Returning cached response")
            
            # Track request for metrics
            if self.observability:
                track_ctx = self.observability.track_request(
                    request_id, user_query, use_live_data, OPENAI_MODEL, request_type=request_type
                )
                tracker = track_ctx.__enter__()
                tracker.log_metric("cache_hit", 1.0, {
                    "cache_tier": cache_hit.cache_tier,
                    "similarity_score": cache_hit.similarity_score
                })
                tracker.log_metric("cache_savings_usd", cache_hit.cost_metrics.get("saved_cost", 0))
            else:
                tracker = None
                track_ctx = None
            
            # Get configuration versions
            from .config import PROMPT_VERSION, AGENT_VERSION
            
            result = {
                "agent": self.agent_name,
                "version": self.version,
                "request_id": request_id,
                "query": user_query,
                "response": cache_hit.response_text,
                "sources": cache_hit.sources,
                "timestamp": datetime.now().isoformat(),
                "live_data_used": False,  # Cache hit means no live data needed
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "cost_usd": 0.0,  # No cost for cache hit
                "request_type": request_type,
                "outcome": outcome or "success",
                "model_version": OPENAI_MODEL,
                "prompt_version": PROMPT_VERSION,
                "agent_config_version": f"cine_prompt_{PROMPT_VERSION}",
                "cache_hit": True,
                "cache_tier": cache_hit.cache_tier,
                "cache_similarity": cache_hit.similarity_score
            }
            
            if track_ctx:
                track_ctx.__exit__(None, None, None)
            
            return result
        
        # No cache hit - proceed with normal flow
        logger.info(f"[{request_id}] Cache miss, proceeding with API calls")
        
        # Track request if observability is enabled
        if self.observability:
            track_ctx = self.observability.track_request(
                request_id, user_query, use_live_data, OPENAI_MODEL, request_type=request_type
            )
            tracker = track_ctx.__enter__()
            tracker.log_metric("cache_hit", 0.0)
        else:
            tracker = None
            track_ctx = None
            logger.info(f"[{request_id}] Processing query: {user_query} [type: {request_type}]")
        
        try:
            search_start = time.time()
            
            # Extract structured intent before search
            structured_intent = None
            try:
                # Use LLM extraction for better accuracy, fallback to pattern-based
                structured_intent = await self.intent_extractor.extract_with_llm(
                    user_query, self.client, request_type
                )
                logger.info(f"[{request_id}] Extracted intent: {structured_intent.intent}, entities: {structured_intent.entities}")
            except Exception as e:
                logger.warning(f"Intent extraction failed: {e}, using pattern-based")
                structured_intent = self.intent_extractor.extract(user_query, request_type)
            
            # Perform real-time search if requested
            search_results = []
            search_context = ""
            source_summary = {}
            verified_facts = []
            
            if use_live_data:
                try:
                    # Use structured intent for optimized search
                    intent = structured_intent.intent if structured_intent else None
                    entities = structured_intent.entities if structured_intent else []
                    need_freshness = getattr(classification_result, 'need_freshness', False) if classification_result else False
                    
                    if tracker:
                        with tracker.time_operation("search"):
                            movie_info = await self.aggregator.get_movie_info(
                                user_query, 
                                include_recent_news=True,
                                intent=intent,
                                entities=entities,
                                request_type=request_type
                            )
                    else:
                        logger.info(f"[{request_id}] Performing real-time search...")
                        movie_info = await self.aggregator.get_movie_info(
                            user_query,
                            include_recent_news=True,
                            intent=intent,
                            entities=entities,
                            request_type=request_type
                        )
                    
                    search_results = movie_info.get("results", [])
                    source_summary = movie_info.get("source_summary", {})
                    search_time_ms = (time.time() - search_start) * 1000
                    
                    # Log source transparency
                    if tracker and source_summary:
                        tracker.log_metric("source_tier_counts", 1.0, source_summary.get("tier_counts", {}))
                        tracker.log_metric("has_tier_a_sources", 1.0 if source_summary.get("has_tier_a") else 0.0)
                        tracker.log_metric("has_tier_c_only", 1.0 if source_summary.get("has_tier_c_only") else 0.0)
                    
                    # Perform verification for fact-based queries
                    if request_type in ["info", "fact-check"] and structured_intent:
                        if structured_intent.intent == "filmography_overlap" and len(structured_intent.entities) >= 2:
                            # Extract candidate titles from search results
                            candidate_titles = self._extract_candidate_titles(search_results, structured_intent.entities)
                            
                            # Convert search results to SourceMetadata for verification
                            from .source_policy import SourceMetadata, SourceTier
                            source_metadata_list = []
                            for r in search_results:
                                tier = self.source_policy.classify_source(
                                    r.get("url", ""), 
                                    r.get("title", ""), 
                                    r.get("content", "")
                                )
                                source_metadata_list.append(SourceMetadata(
                                    url=r.get("url", ""),
                                    domain=r.get("domain", ""),
                                    tier=tier,
                                    title=r.get("title", ""),
                                    content=r.get("content", ""),
                                    score=r.get("score", 0.0)
                                ))
                            
                            # Verify against Tier A sources
                            try:
                                verified_facts = self.verifier.verify_filmography_overlap(
                                    structured_intent.entities[0],
                                    structured_intent.entities[1],
                                    candidate_titles,
                                    source_metadata_list
                                )
                                logger.info(f"[{request_id}] Verified {len([f for f in verified_facts if f.verified])} facts")
                            except Exception as e:
                                logger.warning(f"Verification failed: {e}")
                    
                    # Log search operation
                    if tracker:
                        tracker.log_search(
                            query=user_query,
                            provider="tavily",
                            results_count=len(search_results),
                            search_time_ms=search_time_ms
                        )
                    
                    # Log search operation
                    if tracker:
                        tracker.log_search(
                            query=user_query,
                            provider="tavily",
                            results_count=len(search_results),
                            search_time_ms=search_time_ms
                        )
                    
                    # Format search results for context (prioritize Tier A sources)
                    if search_results:
                        search_context = "\n\n=== REAL-TIME SEARCH RESULTS (Ranked by Source Quality) ===\n"
                        
                        # Sort by tier (A first)
                        tier_order = {"A": 0, "B": 1, "C": 2, "UNKNOWN": 3}
                        sorted_results = sorted(search_results, 
                                               key=lambda x: tier_order.get(x.get("tier", "UNKNOWN"), 3))
                        
                        tier_a_count = sum(1 for r in sorted_results if r.get("tier") == "A")
                        tier_c_count = sum(1 for r in sorted_results if r.get("tier") == "C")
                        
                        for i, result in enumerate(sorted_results[:5], 1):
                            source = result.get("source", "unknown")
                            tier = result.get("tier", "UNKNOWN")
                            title = result.get("title", "No title")
                            content = result.get("content", "")[:500]  # Truncate long content
                            url = result.get("url", "")
                            
                            search_context += f"\n[{i}] Source: {source} (Tier {tier})\n"
                            search_context += f"Title: {title}\n"
                            if url:
                                search_context += f"URL: {url}\n"
                            search_context += f"Content: {content}\n"
                        
                        # Add verification results if available
                        if verified_facts:
                            verified_titles = [f.value for f in verified_facts if f.verified]
                            if verified_titles:
                                search_context += f"\n\nVERIFIED FACTS (from Tier A sources):\n"
                                for title in verified_titles:
                                    search_context += f"- {title}\n"
                        
                        search_context += "\nIMPORTANT: Use Tier A sources (IMDb, Wikipedia) for facts.\n"
                        if tier_c_count > 0:
                            search_context += f"WARNING: {tier_c_count} Tier C sources found - use only for context, not facts.\n"
                        search_context += "Distinguish between confirmed facts (Tier A) and rumors/speculation.\n"
                
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
                            
                            # Store in cache for future use
                            if self.cache:
                                try:
                                    entities = getattr(classification_result, 'entities', []) if classification_result else []
                                    need_freshness = getattr(classification_result, 'need_freshness', False) if classification_result else False
                                    
                                    self.cache.put(
                                        prompt=user_query,
                                        response_text=agent_response,
                                        sources=sources_list,
                                        predicted_type=request_type,
                                        entities=entities,
                                        need_freshness=need_freshness,
                                        classifier_type="hybrid",
                                        tool_config_version=f"cine_prompt_{PROMPT_VERSION}",
                                        agent_version=self.version,
                                        prompt_version=PROMPT_VERSION,
                                        cost_metrics={
                                            "saved_cost": cost_usd,  # Cost that would be saved on cache hit
                                            "original_cost": cost_usd
                                        }
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to cache response: {e}")
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
    
    def _extract_candidate_titles(self, search_results: List[Dict], entities: List[str]) -> List[str]:
        """
        Extract candidate movie titles from search results.
        Simple extraction - could be enhanced with NER.
        """
        titles = []
        for result in search_results:
            content = result.get("content", "").lower()
            title = result.get("title", "").lower()
            
            # Look for movie title patterns
            # This is a simplified version - could use more sophisticated extraction
            if any(entity.lower() in content or entity.lower() in title for entity in entities):
                # Try to extract movie titles from content
                # Pattern: "Movie Title (Year)" or "Movie Title"
                title_patterns = [
                    r'"([^"]+)"',  # Quoted titles
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\(\d{4}\)",  # "Title (Year)"
                ]
                for pattern in title_patterns:
                    matches = re.findall(pattern, result.get("content", ""))
                    titles.extend(matches)
        
        # Remove duplicates and return
        return list(set(titles))[:10]  # Limit to 10 candidates
    
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

