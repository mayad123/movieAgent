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
from typing import List, Dict, Optional, AsyncGenerator, Tuple
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
from .verification import FactVerifier, VerifiedFact
from .request_plan import RequestPlanner, RequestPlan
from .candidate_extraction import CandidateExtractor
from .tool_plan import ToolPlanner, ToolPlan

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
        self.candidate_extractor = CandidateExtractor()
        self.tool_planner = ToolPlanner()
        
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
        
        # Initialize request planner (single source of truth for routing)
        self.planner = RequestPlanner(self.classifier, self.intent_extractor)
        
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
        
        # PIPELINE ORDER:
        # 1. Check cache FIRST (if nothing correlating returns, proceed to step 2)
        # 2. Check Kaggle dataset (if nothing correlating returns, proceed to step 3)
        # 3. Check Tavily API (fallback web search)
        #
        # CRITICAL: Check cache FIRST before any OpenAI calls
        # This prevents unnecessary API calls for intent extraction
        cache_hit = None
        request_plan = None
        
        if self.cache and use_live_data:  # Only check cache if we would normally use live data
            try:
                from .config import PROMPT_VERSION
                
                # Try cache lookup with minimal classification (rule-based only, no LLM)
                # We need a quick classification to know what to look for in cache
                # Use rule-based classification first (fast, no API calls)
                # For exact cache lookup, we don't need classification - hash is enough
                # For semantic cache, we'll try with default "info" type
                # The cache.get() method will handle exact hash matching first
                
                # Try cache lookup - exact match doesn't need classification
                # For semantic match, we'll use a default type
                cache_hit = self.cache.get(
                    prompt=user_query,
                    classifier_type="hybrid",
                    tool_config_version=f"cine_prompt_{PROMPT_VERSION}",
                    predicted_type="info",  # Default type for cache lookup (exact match doesn't need this)
                    entities=[],  # Empty for now - exact match doesn't need entities
                    need_freshness=False,  # Default - exact match doesn't need this
                    current_agent_version=self.version,
                    current_prompt_version=PROMPT_VERSION
                )
                
                # If cache hit, reconstruct RequestPlan from cached data
                if cache_hit:
                    # Reconstruct plan from cache entry (no OpenAI calls needed)
                    request_plan = RequestPlan(
                        intent=cache_hit.structured_facts.get("type", "general_info") if cache_hit.structured_facts else "general_info",
                        request_type=cache_hit.predicted_type,
                        entities=cache_hit.entities or [],
                        need_freshness=cache_hit.structured_facts.get("need_freshness", False) if cache_hit.structured_facts else False,
                        freshness_ttl_hours=6.0 if cache_hit.predicted_type == "release-date" else 168.0,
                        original_query=user_query,
                        rule_hit="cached",  # Mark as from cache
                        llm_used=False,  # No LLM used for cached response
                        confidence=1.0
                    )
                    request_type = request_plan.request_type
                    
            except Exception as e:
                logger.warning(f"Cache lookup failed: {e}, proceeding with normal flow")
        
        # Only create RequestPlan if cache miss (this will call OpenAI)
        if not cache_hit:
            # Step 1: Create RequestPlan (single source of truth for routing)
            # This will call OpenAI for classification and intent extraction
            if not request_type:
                try:
                    request_plan = await self.planner.plan_request(user_query, self.client)
                    request_type = request_plan.request_type
                except Exception as e:
                    logger.warning(f"[{request_id}] Planning failed: {e}, defaulting to 'info'")
                    request_type = "info"
                    # Create minimal plan as fallback
                    request_plan = RequestPlan(
                        intent="general_info",
                        request_type="info",
                        original_query=user_query
                    )
            else:
                # If request_type provided, still create plan for consistency
                try:
                    request_plan = await self.planner.plan_request(user_query, self.client)
                except Exception as e:
                    logger.warning(f"[{request_id}] Planning failed: {e}, using provided type")
                    request_plan = RequestPlan(
                        intent="general_info",
                        request_type=request_type,
                        original_query=user_query
                    )
        
        # Log classification metadata (from plan)
        if request_plan and self.observability:
            self.observability.log_classification_metadata(
                request_id,
                predicted_type=request_plan.request_type,
                rule_hit=request_plan.rule_hit,
                llm_used=request_plan.llm_used,
                confidence=request_plan.confidence,
                entities=request_plan.entities,
                need_freshness=request_plan.need_freshness
            )
        
        # If cache hit, check decision tree using RequestPlan
        if cache_hit and request_plan:
            # Prepare plan dict for cache validation
            plan_dict = request_plan.to_dict()
            plan_dict["agent_version"] = self.version
            plan_dict["prompt_version"] = PROMPT_VERSION
            plan_dict["tool_config_version"] = f"cine_prompt_{PROMPT_VERSION}"
            
            should_call_openai, reason = self.cache.should_call_openai_on_cache_hit(
                cache_hit, plan_dict, cache_hit.similarity_score
            )
            
            logger.info(f"[{request_id}] Cache {cache_hit.cache_tier} hit! (similarity: {cache_hit.similarity_score:.3f})")
            logger.info(f"[{request_id}] Decision: {'Call OpenAI' if should_call_openai else 'Serve cached'} - Reason: {reason}")
            
            # If decision tree says NO OpenAI, serve cached directly
            if not should_call_openai:
                # Track request for metrics
                if self.observability:
                    track_ctx = self.observability.track_request(
                        request_id, user_query, use_live_data, OPENAI_MODEL, request_type=request_type
                    )
                    tracker = track_ctx.__enter__()
                    tracker.log_metric("cache_hit", 1.0, {
                        "cache_tier": cache_hit.cache_tier,
                        "similarity_score": cache_hit.similarity_score,
                        "openai_skipped": True,
                        "skip_reason": reason
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
                    "cache_similarity": cache_hit.similarity_score,
                    "openai_skipped": True,
                    "skip_reason": reason
                }
                
                if track_ctx:
                    track_ctx.__exit__(None, None, None)
                
                return result
            
            # Decision tree says YES OpenAI (e.g., re-verify, rewrite, etc.)
            # Fall through to normal flow but use cached sources/data
            logger.info(f"[{request_id}] Cache hit but OpenAI needed for: {reason}")
            # Continue to normal flow but can use cached structured_facts if available
        
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
            
            # Use structured intent from RequestPlan (already extracted in plan_request)
            # This avoids duplicate intent extraction calls to OpenAI
            structured_intent = None
            if request_plan:
                # Reconstruct StructuredIntent from RequestPlan (no OpenAI call needed)
                from .intent_extraction import StructuredIntent
                # Use typed entities from RequestPlan (preferred over flat list)
                typed_entities = request_plan.entities_typed if hasattr(request_plan, 'entities_typed') and request_plan.entities_typed else {"movies": [], "people": []}
                # Ensure required keys exist
                if "movies" not in typed_entities:
                    typed_entities["movies"] = []
                if "people" not in typed_entities:
                    typed_entities["people"] = []
                
                structured_intent = StructuredIntent(
                    intent=request_plan.intent,
                    entities=typed_entities,
                    constraints={},  # RequestPlan doesn't store constraints separately
                    original_query=user_query,
                    confidence=request_plan.confidence,
                    requires_disambiguation=False,  # RequestPlan doesn't store this
                    need_freshness=request_plan.need_freshness,
                    freshness_ttl_hours=request_plan.freshness_ttl_hours
                )
                all_entities = structured_intent.get_all_entities()
                logger.info(f"[{request_id}] Using intent from RequestPlan: {structured_intent.intent}, entities: {all_entities}")
            else:
                # Fallback: only extract if RequestPlan wasn't created (shouldn't happen)
                logger.warning(f"[{request_id}] No RequestPlan available, extracting intent as fallback")
                try:
                    structured_intent = await self.intent_extractor.extract_with_llm(
                        user_query, self.client, request_type
                    )
                    all_entities = structured_intent.get_all_entities()
                    logger.info(f"[{request_id}] Extracted intent: {structured_intent.intent}, entities: {all_entities}")
                except Exception as e:
                    logger.warning(f"Intent extraction failed: {e}, using pattern-based")
                    structured_intent = self.intent_extractor.extract(user_query, request_type)
            
            # Step 1: Create tool plan based on freshness (decides before Tavily)
            tool_plan = None
            if structured_intent and request_plan:
                tool_plan = self.tool_planner.plan_tools(
                    intent=structured_intent.intent,
                    need_freshness=structured_intent.need_freshness,
                    freshness_reason=getattr(structured_intent, 'freshness_reason', None),
                    entities=structured_intent.entities,
                    candidate_year=structured_intent.candidate_year,
                    requires_disambiguation=structured_intent.requires_disambiguation
                )
                logger.info(f"[{request_id}] Tool plan: Tavily={tool_plan.use_tavily}, Reason: {tool_plan.freshness_reason or tool_plan.skip_reason}")
            
            # Perform real-time search if requested AND tool plan allows it
            search_results = []
            search_context = ""
            source_summary = {}
            verified_facts = []
            
            if use_live_data:
                # Check if we should skip Tavily based on tool plan
                should_skip_tavily = False
                skip_reason = ""
                need_freshness = request_plan.need_freshness if request_plan else False
                if tool_plan:
                    should_skip_tavily, skip_reason = self.tool_planner.should_skip_tavily(
                        tool_plan,
                        cache_hit=False,  # We're in the live data path, so no cache hit yet
                        need_freshness=need_freshness
                    )
                    
                    if should_skip_tavily:
                        logger.info(f"[{request_id}] Skipping Tavily based on tool plan: {skip_reason}")
                
                # Determine override reason for Tavily (only valid reasons can override skip_tavily)
                override_reason = None
                from .search_engine import TavilyOverrideReason
                
                # Check for disambiguation_needed
                if structured_intent and hasattr(structured_intent, 'requires_disambiguation') and structured_intent.requires_disambiguation:
                    override_reason = TavilyOverrideReason.DISAMBIGUATION_NEEDED.value
                    logger.info(f"[{request_id}] Override reason: {override_reason}")
                
                try:
                    # Use structured intent for optimized search
                    intent = structured_intent.intent if structured_intent else None
                    # Get all entities as flat list for search (backward compatibility)
                    entities = structured_intent.get_all_entities() if structured_intent else []
                    need_freshness = request_plan.need_freshness if request_plan else False
                    
                    # Search pipeline order (after cache miss):
                    # 1. Cache was checked first (above) - if nothing correlating, proceed here
                    # 2. Check Kaggle dataset (local lookup, free and fast)
                    # 3. Tavily API (only if skip_tavily=False OR valid override_reason provided)
                    #    NOTE: Low Kaggle correlation does NOT override skip_tavily flag
                    # Get typed entities from structured_intent
                    entities_typed = structured_intent.entities if structured_intent else None
                    
                    if tracker:
                        with tracker.time_operation("search"):
                            movie_info = await self.aggregator.get_movie_info(
                                user_query, 
                                include_recent_news=not should_skip_tavily,  # Only include news if Tavily allowed
                                intent=intent,
                                entities=entities,
                                request_type=request_type,
                                skip_tavily=should_skip_tavily,
                                override_reason=override_reason,
                                request_plan=request_plan,
                                entities_typed=entities_typed
                            )
                    else:
                        logger.info(f"[{request_id}] Performing search (Kaggle first, Tavily: {'enabled' if not should_skip_tavily else ('override' if override_reason else 'skipped')})...")
                        movie_info = await self.aggregator.get_movie_info(
                            user_query,
                            include_recent_news=not should_skip_tavily,
                            intent=intent,
                            entities=entities,
                            request_type=request_type,
                            skip_tavily=should_skip_tavily,
                            override_reason=override_reason,
                            request_plan=request_plan,
                            entities_typed=entities_typed
                        )
                    
                    search_results = movie_info.get("results", [])
                    source_summary = movie_info.get("source_summary", {})
                    search_time_ms = (time.time() - search_start) * 1000
                    
                    # Check for additional override reasons after initial search
                    final_override_reason = override_reason
                    # Track candidates for structured-only response if browsing is blocked
                    candidates_retrieved = 0
                    candidates_used = 0
                    
                    if should_skip_tavily and not movie_info.get("tavily_used", False):
                        # For fact-based queries, extract and verify candidates to check if we have usable evidence
                        if request_type in ["info", "fact-check"] and structured_intent:
                            # Convert search results to SourceMetadata for candidate extraction
                            from .source_policy import SourceMetadata
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
                            
                            # Extract candidates to check if we have any usable evidence
                            people = structured_intent.entities.get("people", [])
                            movies = structured_intent.entities.get("movies", [])
                            
                            if structured_intent.intent == "filmography_overlap" and len(people) >= 2:
                                candidates = self.candidate_extractor.extract_collaboration_candidates(
                                    search_results, people[0], people[1]
                                )
                                candidates_retrieved = len(candidates)
                                # Count verified candidates
                                for candidate in candidates:
                                    title_year_match = re.match(r'(.+?)\s*\((\d{4})\)', candidate.value)
                                    if title_year_match:
                                        movie_title = title_year_match.group(1)
                                        year = int(title_year_match.group(2))
                                        person1_verified, _, _ = self.verifier.verify_movie_credit(
                                            movie_title, people[0], year, source_metadata_list
                                        )
                                        person2_verified, _, _ = self.verifier.verify_movie_credit(
                                            movie_title, people[1], year, source_metadata_list
                                        )
                                        if person1_verified and person2_verified:
                                            candidates_used += 1
                            elif structured_intent.intent in ["director_info", "cast_info"]:
                                all_entities = structured_intent.get_all_entities()
                                candidates = self.candidate_extractor.extract_movie_candidates(
                                    search_results, all_entities
                                )
                                candidates_retrieved = len(candidates)
                                # Count verified candidates
                                for candidate in candidates:
                                    title_year_match = re.match(r'(.+?)\s*\((\d{4})\)', candidate.value)
                                    if title_year_match and people:
                                        movie_title = title_year_match.group(1)
                                        year = int(title_year_match.group(2))
                                        person = people[0]
                                        verified, _, _ = self.verifier.verify_movie_credit(
                                            movie_title, person, year, source_metadata_list
                                        )
                                        if verified:
                                            candidates_used += 1
                            elif structured_intent.intent == "release_date" and movies:
                                movie_title = movies[0]
                                candidates = self.candidate_extractor.extract_release_year_candidates(
                                    search_results, movie_title
                                )
                                candidates_retrieved = len(candidates)
                                # Count verified candidates (if year was verified)
                                year, _, _ = self.verifier.verify_release_year(
                                    movie_title, source_metadata_list
                                )
                                if year:
                                    candidates_used = 1
                        
                        # Check for structured_lookup_empty (no results OR no candidates after filtering)
                        if not search_results or (candidates_retrieved > 0 and candidates_used == 0):
                            final_override_reason = TavilyOverrideReason.STRUCTURED_LOOKUP_EMPTY.value
                            logger.info(f"[{request_id}] Override reason after search: {final_override_reason} (no usable evidence: {candidates_retrieved} candidates retrieved, {candidates_used} used)")
                            # Retry with override
                            # Get typed entities from structured_intent
                            entities_typed_for_search = structured_intent.entities if structured_intent else None
                            movie_info = await self.aggregator.get_movie_info(
                                user_query,
                                include_recent_news=False,
                                intent=intent,
                                entities=entities,
                                request_type=request_type,
                                skip_tavily=True,
                                override_reason=final_override_reason,
                                request_plan=request_plan,
                                entities_typed=entities_typed_for_search
                            )
                            search_results = movie_info.get("results", [])
                            source_summary = movie_info.get("source_summary", {})
                        # Check for tier_a_missing (require_tier_a=True but no Tier A sources found)
                        elif source_summary.get("missing_required_tier", False):
                            final_override_reason = TavilyOverrideReason.TIER_A_MISSING.value
                            logger.info(f"[{request_id}] Override reason after search: {final_override_reason} (require_tier_a=True but no Tier A sources found)")
                            # Retry with override
                            # Get typed entities from structured_intent
                            entities_typed_for_search = structured_intent.entities if structured_intent else None
                            movie_info = await self.aggregator.get_movie_info(
                                user_query,
                                include_recent_news=False,
                                intent=intent,
                                entities=entities,
                                request_type=request_type,
                                skip_tavily=True,
                                override_reason=final_override_reason,
                                request_plan=request_plan,
                                entities_typed=entities_typed_for_search
                            )
                            search_results = movie_info.get("results", [])
                            source_summary = movie_info.get("source_summary", {})
                    
                    # Update tool plan with actual search usage info (exactly once per request)
                    if tool_plan:
                        tool_plan.tavily_used = movie_info.get("tavily_used", False)
                        tool_plan.fallback_used = movie_info.get("fallback_used", False)
                        tool_plan.fallback_provider = movie_info.get("fallback_provider")
                        tool_plan.override_used = movie_info.get("override_used", False)
                        tool_plan.override_reason = movie_info.get("override_reason") or final_override_reason
                        
                        # Log search usage metadata exactly once per request
                        search_metadata_parts = []
                        if tool_plan.tavily_used:
                            search_metadata_parts.append("tavily_used=true")
                        if tool_plan.fallback_used:
                            search_metadata_parts.append(f"fallback_used=true, fallback_provider={tool_plan.fallback_provider}")
                        if tool_plan.override_used:
                            search_metadata_parts.append(f"override_used=true, override_reason={tool_plan.override_reason}")
                        
                        if search_metadata_parts:
                            logger.info(
                                f"[{request_id}] Search metadata: "
                                + ", ".join(search_metadata_parts)
                            )
                        else:
                            logger.info(
                                f"[{request_id}] Search metadata: "
                                f"tavily_used=false, fallback_used=false, override_used=false"
                            )
                    
                    # Log metrics for observability (exactly once per request)
                    if tracker and tool_plan:
                        tracker.log_metric("tool_plan_skip_tavily", 1.0 if tool_plan.tool_plan_skip_tavily else 0.0)
                        tracker.log_metric("tavily_used", 1.0 if tool_plan.tavily_used else 0.0)
                        tracker.log_metric("fallback_used", 1.0 if tool_plan.fallback_used else 0.0)
                        if tool_plan.fallback_provider:
                            tracker.log_metric(f"fallback_provider_{tool_plan.fallback_provider}", 1.0)
                        tracker.log_metric("override_used", 1.0 if tool_plan.override_used else 0.0)
                        if tool_plan.override_reason:
                            tracker.log_metric(f"override_reason_{tool_plan.override_reason}", 1.0)
                    
                    if should_skip_tavily and search_results:
                        logger.info(f"[{request_id}] Kaggle provided {len(search_results)} results (Tavily skipped per tool plan)")
                    
                    # Log source transparency
                    if tracker and source_summary:
                        tracker.log_metric("source_tier_counts", 1.0, source_summary.get("tier_counts", {}))
                        tracker.log_metric("has_tier_a_sources", 1.0 if source_summary.get("has_tier_a") else 0.0)
                        tracker.log_metric("has_tier_c_only", 1.0 if source_summary.get("has_tier_c_only") else 0.0)
                    
                    # Perform "candidate → verify → answer" pattern for fact-based queries
                    if request_type in ["info", "fact-check"] and structured_intent:
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
                        
                        # Step 1: Extract candidates based on intent
                        people = structured_intent.entities.get("people", [])
                        movies = structured_intent.entities.get("movies", [])
                        
                        if structured_intent.intent == "filmography_overlap" and len(people) >= 2:
                            # Extract collaboration candidates
                            candidates = self.candidate_extractor.extract_collaboration_candidates(
                                search_results, 
                                people[0],
                                people[1]
                            )
                            
                            logger.info(f"[{request_id}] Extracted {len(candidates)} collaboration candidates")
                            
                            # Step 2: Verify each candidate against Tier A sources
                            verified_facts = []
                            for candidate in candidates:
                                # Parse title and year from candidate value
                                title_year_match = re.match(r'(.+?)\s*\((\d{4})\)', candidate.value)
                                if title_year_match:
                                    movie_title = title_year_match.group(1)
                                    year = int(title_year_match.group(2))
                                    
                                    # Verify both people have credits in this movie
                                    person1_verified, source1, conf1 = self.verifier.verify_movie_credit(
                                        movie_title, people[0], year, source_metadata_list
                                    )
                                    person2_verified, source2, conf2 = self.verifier.verify_movie_credit(
                                        movie_title, people[1], year, source_metadata_list
                                    )
                                    
                                    if person1_verified and person2_verified:
                                        # Both verified - use higher confidence source
                                        best_source = source1 if conf1 >= conf2 else source2
                                        best_conf = max(conf1, conf2)
                                        
                                        verified_facts.append(VerifiedFact(
                                            fact_type="collaboration",
                                            value=candidate.value,
                                            verified=True,
                                            source_url=best_source,
                                            source_tier="A",
                                            confidence=best_conf
                                        ))
                                        logger.info(f"[{request_id}] Verified collaboration: {candidate.value}")
                            
                            logger.info(f"[{request_id}] Verified {len([f for f in verified_facts if f.verified])} collaborations out of {len(candidates)} candidates")
                        
                        elif structured_intent.intent in ["director_info", "cast_info"]:
                            # Extract movie candidates
                            all_entities = structured_intent.get_all_entities()
                            candidates = self.candidate_extractor.extract_movie_candidates(
                                search_results,
                                all_entities
                            )
                            
                            logger.info(f"[{request_id}] Extracted {len(candidates)} movie candidates")
                            
                            # Verify each candidate
                            verified_facts = []
                            for candidate in candidates:
                                title_year_match = re.match(r'(.+?)\s*\((\d{4})\)', candidate.value)
                                if title_year_match:
                                    movie_title = title_year_match.group(1)
                                    year = int(title_year_match.group(2))
                                    
                                    # Verify person has credit in movie
                                    if people:
                                        person = people[0]
                                        verified, source, conf = self.verifier.verify_movie_credit(
                                            movie_title, person, year, source_metadata_list
                                        )
                                        
                                        if verified:
                                            verified_facts.append(VerifiedFact(
                                                fact_type="credit",
                                                value=candidate.value,
                                                verified=True,
                                                source_url=source,
                                                source_tier="A",
                                                confidence=conf
                                            ))
                        
                        elif structured_intent.intent == "release_date":
                            # Extract release year candidates
                            if movies:
                                movie_title = movies[0]
                                candidates = self.candidate_extractor.extract_release_year_candidates(
                                    search_results,
                                    movie_title
                                )
                                
                                logger.info(f"[{request_id}] Extracted {len(candidates)} year candidates for {movie_title}")
                                
                                # Verify release year
                                verified_facts = []
                                year, source, conf = self.verifier.verify_release_year(
                                    movie_title, source_metadata_list
                                )
                                
                                if year:
                                    verified_facts.append(VerifiedFact(
                                        fact_type="release_year",
                                        value=str(year),
                                        verified=True,
                                        source_url=source,
                                        source_tier="A",
                                        confidence=conf
                                    ))
                                    logger.info(f"[{request_id}] Verified release year: {year} for {movie_title}")
                        
                        # Store verified facts for use in response generation
                        if verified_facts:
                            # Add verified facts to search context for LLM
                            verified_context = "\n\n=== VERIFIED FACTS (Tier A Sources) ===\n"
                            for fact in verified_facts:
                                if fact.verified:
                                    verified_context += f"- {fact.value} (verified via {fact.source_url})\n"
                            search_context += verified_context
                    
                    # Step 1: Deduplicate search results
                    deduplicated_results, dedup_stats = self._deduplicate_search_results(search_results)
                    
                    # Step 2: Filter for relevance based on query entities
                    query_entities = structured_intent.entities if structured_intent else {"movies": [], "people": []}
                    mentioned_year = getattr(structured_intent, 'mentioned_year', None) if structured_intent else None
                    relevant_results, exclusion_reasons = self._filter_relevant_results(
                        deduplicated_results,
                        query_entities,
                        mentioned_year
                    )
                    
                    # Step 3: Log search operation with detailed stats (single call, no duplicates)
                    if tracker:
                        tracker.log_search(
                            query=user_query,
                            provider="mixed",  # Combined Kaggle + Tavily
                            results_count=len(relevant_results),
                            search_time_ms=search_time_ms
                        )
                    
                    # Log detailed stats for debugging
                    logger.info(
                        f"[{request_id}] Search results: "
                        f"retrieved={dedup_stats['candidates_retrieved']}, "
                        f"deduped={dedup_stats['candidates_deduped']}, "
                        f"evidence_used={len(relevant_results)}, "
                        f"excluded={len(exclusion_reasons)}"
                    )
                    if exclusion_reasons and logger.isEnabledFor(logging.DEBUG):
                        for excl in exclusion_reasons[:5]:  # Log first 5 exclusions
                            logger.debug(f"[{request_id}] Excluded: {excl['title']} - {excl['reason']}")
                    
                    # Format search results for context (prioritize Tier A sources) - only include relevant, deduplicated results
                    if relevant_results:
                        # Identify source types (using relevant_results, not raw search_results)
                        kaggle_results = [r for r in relevant_results if r.get("source") == "kaggle_imdb"]
                        tavily_results = [r for r in relevant_results if "tavily" in r.get("source", "").lower()]
                        
                        # Determine header based on sources
                        if kaggle_results and not tavily_results:
                            search_context = "\n\n=== KAGGLE IMDB DATASET RESULTS ===\n"
                            search_context += "(These results are from the Kaggle IMDB dataset - authoritative structured data)\n"
                        elif kaggle_results and tavily_results:
                            search_context = "\n\n=== SEARCH RESULTS (Kaggle Dataset + Tavily) ===\n"
                        else:
                            search_context = "\n\n=== REAL-TIME SEARCH RESULTS (Ranked by Source Quality) ===\n"
                        
                        # Sort by tier (A first), then by source (Kaggle first if same tier)
                        tier_order = {"A": 0, "B": 1, "C": 2, "UNKNOWN": 3}
                        def sort_key(result):
                            tier_val = tier_order.get(result.get("tier", "UNKNOWN"), 3)
                            source_val = 0 if result.get("source") == "kaggle_imdb" else 1
                            return (tier_val, source_val, -result.get("score", 0.0))
                        
                        sorted_results = sorted(relevant_results, key=sort_key)
                        
                        tier_a_count = sum(1 for r in sorted_results if r.get("tier") == "A")
                        tier_c_count = sum(1 for r in sorted_results if r.get("tier") == "C")
                        
                        # Limit to top 5 results for search_context
                        for i, result in enumerate(sorted_results[:5], 1):
                            source = result.get("source", "unknown")
                            tier = result.get("tier", "UNKNOWN")
                            title = result.get("title", "No title")
                            # For Kaggle results, content is already well-formatted, allow more length
                            # For other sources, truncate to 500 chars
                            raw_content = result.get("content", "")
                            if source == "kaggle_imdb":
                                content = raw_content  # Already formatted and truncated in kaggle_search.py
                            else:
                                content = raw_content[:500]  # Truncate long content
                            url = result.get("url", "")
                            correlation = result.get("correlation")  # Kaggle correlation score
                            
                            # Format source name nicely
                            if source == "kaggle_imdb":
                                source_display = "Kaggle IMDB Dataset"
                                if correlation:
                                    source_display += f" (correlation: {correlation:.2f})"
                            else:
                                source_display = source.replace("_", " ").title()
                            
                            search_context += f"\n[{i}] Source: {source_display} (Tier {tier})\n"
                            search_context += f"Title: {title}\n"
                            if url:
                                search_context += f"URL: {url}\n"
                            elif source == "kaggle_imdb":
                                search_context += f"Source: IMDB Dataset (via Kaggle)\n"
                            search_context += f"Content:\n{content}\n"
                        
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
                                    entities = request_plan.entities if request_plan else []
                                    need_freshness = request_plan.need_freshness if request_plan else False
                                    
                                    # Get freshness metadata from structured_intent if available
                                    freshness_reason = None
                                    freshness_ttl_hours = None
                                    if structured_intent:
                                        freshness_reason = getattr(structured_intent, 'freshness_reason', None)
                                        freshness_ttl_hours = getattr(structured_intent, 'freshness_ttl_hours', None)
                                    
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
                                        },
                                        freshness_reason=freshness_reason,
                                        freshness_ttl_hours=freshness_ttl_hours
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
                    "agent_config_version": f"cine_prompt_{PROMPT_VERSION}",  # Agent config version
                    # Search metadata (auditable, logged exactly once per request)
                    "tavily_used": tool_plan.tavily_used if tool_plan else False,
                    "fallback_used": tool_plan.fallback_used if tool_plan else False,
                    "fallback_provider": tool_plan.fallback_provider if tool_plan else None,
                    "override_used": tool_plan.override_used if tool_plan else False,
                    "override_reason": tool_plan.override_reason if tool_plan else None
                }
                
                # Add structured-only response payload if browsing was blocked
                if should_skip_tavily and tool_plan and not tool_plan.tavily_used and not tool_plan.override_used:
                    result["structured_only"] = {
                        "candidates_retrieved": candidates_retrieved if 'candidates_retrieved' in locals() else len(search_results),
                        "candidates_used": candidates_used if 'candidates_used' in locals() else len([r for r in search_results if r.get("tier") == "A"]),
                        "no_browse_reason": "skip_tavily_enforced"
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
    
    def _deduplicate_search_results(self, results: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Deduplicate search results based on (source_name/url, title, year).
        
        Returns:
            (deduplicated_results, stats) where stats contains counts of duplicates
        """
        seen_keys = {}
        deduplicated = []
        duplicate_count = 0
        
        for result in results:
            # Extract dedup key components
            source_name = result.get("source", "unknown")
            url = result.get("url", "")
            title = result.get("title", "").strip().lower()
            
            # Extract year from title if present (e.g., "The Matrix (1999)")
            year = None
            year_match = re.search(r'\((\d{4})\)', title)
            if year_match:
                year = year_match.group(1)
            
            # Create dedup key: (source_name or url, title_normalized, year)
            # Use source_name for Kaggle, url for others
            source_key = source_name if source_name == "kaggle_imdb" else url
            # Normalize title: remove year, trim, lowercase
            title_normalized = re.sub(r'\s*\(\d{4}\)', '', title).strip()
            dedup_key = (source_key, title_normalized, year)
            
            # Check if we've seen this key
            if dedup_key in seen_keys:
                duplicate_count += 1
                continue
            
            seen_keys[dedup_key] = True
            deduplicated.append(result)
        
        stats = {
            "candidates_retrieved": len(results),
            "duplicates_removed": duplicate_count,
            "candidates_deduped": len(deduplicated)
        }
        
        return deduplicated, stats
    
    def _filter_relevant_results(
        self, 
        results: List[Dict], 
        query_entities: Dict[str, List[str]],
        mentioned_year: Optional[int] = None
    ) -> Tuple[List[Dict], List[Dict[str, str]]]:
        """
        Filter search results for relevance to query entities.
        
        Args:
            results: Search results to filter
            query_entities: Dict with "movies" and "people" keys
            mentioned_year: Optional year from query (for award queries, etc.)
        
        Returns:
            (relevant_results, exclusion_reasons) where exclusion_reasons is a list of dicts with 
            reason and result info
        """
        relevant = []
        exclusion_reasons = []
        movies = [m.lower() for m in query_entities.get("movies", [])]
        people = [p.lower() for p in query_entities.get("people", [])]
        
        for result in results:
            title = result.get("title", "").lower()
            content = result.get("content", "").lower()
            source = result.get("source", "")
            
            # Extract year from result title if present
            result_year = None
            year_match = re.search(r'\((\d{4})\)', title)
            if year_match:
                result_year = int(year_match.group(1))
            
            # Check if result matches query entities
            is_relevant = False
            match_reason = ""
            
            # Check movie title matches
            if movies:
                for movie in movies:
                    # Exact title match (with or without year)
                    title_normalized = re.sub(r'\s*\(\d{4}\)', '', title).strip()
                    movie_normalized = re.sub(r'\s*\(\d{4}\)', '', movie).strip()
                    if movie_normalized in title_normalized or title_normalized in movie_normalized:
                        is_relevant = True
                        match_reason = f"title_match:{movie}"
                        break
                    # Content match
                    if movie in content or movie in title:
                        is_relevant = True
                        match_reason = f"content_match:{movie}"
                        break
            
            # Check person name matches
            if not is_relevant and people:
                for person in people:
                    if person in content or person in title:
                        is_relevant = True
                        match_reason = f"person_match:{person}"
                        break
            
            # For Kaggle results, also check correlation score (if high, likely relevant)
            if not is_relevant and source == "kaggle_imdb":
                correlation = result.get("correlation", 0.0)
                if correlation > 0.7:  # High correlation threshold
                    is_relevant = True
                    match_reason = f"high_correlation:{correlation:.2f}"
            
            # Year matching for award queries (if year mentioned and matches)
            if not is_relevant and mentioned_year and result_year:
                if abs(result_year - mentioned_year) <= 1:  # Allow ±1 year for award queries
                    # Only consider year match if no entities, or if it's an award-related query
                    if not movies and not people:
                        is_relevant = True
                        match_reason = f"year_match:{mentioned_year}"
            
            # Fallback: If no entities extracted, allow high-scoring results through
            # (Query might be too vague for entity extraction, but results could still be relevant)
            if not is_relevant and not movies and not people:
                score = result.get("score", 0.0)
                correlation = result.get("correlation", 0.0)
                if score > 0.8 or correlation > 0.8:
                    is_relevant = True
                    match_reason = f"high_score_fallback:{score:.2f}"
            
            if is_relevant:
                relevant.append(result)
            else:
                exclusion_reasons.append({
                    "reason": "low_relevance",
                    "title": result.get("title", "")[:50],
                    "source": source,
                    "details": f"no_match_for_entities"
                })
        
        return relevant, exclusion_reasons
    
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

