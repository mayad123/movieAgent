"""
CineMind - Real-time Movie Analysis and Discovery Agent

Performance optimizations:
- Fast pattern-based request classification (no blocking LLM call)
- Parallel search execution (multiple searches run concurrently)
- Non-blocking database writes (runs in background thread pool)
"""
import asyncio
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
from .prompting import PromptBuilder, EvidenceBundle, get_template
from .prompting.output_validator import OutputValidator
from .llm_client import LLMClient, OpenAILLMClient
from .media_enrichment import attach_media_to_result

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
                 enable_observability: bool = True, llm_client: Optional[LLMClient] = None):
        """
        Initialize CineMind agent.
        
        Args:
            openai_api_key: OpenAI API key for LLM (ignored if llm_client is provided)
            tavily_api_key: Tavily API key for real-time search
            enable_observability: Enable request tracking and metrics
            llm_client: Optional LLM client instance (for dependency injection in tests)
                       If not provided, creates OpenAI client from api_key
        """
        # Initialize LLM client (support dependency injection for testing)
        if llm_client:
            self.client = llm_client
        else:
            if not AsyncOpenAI:
                raise ImportError("OpenAI library not installed. Install with: pip install openai")
            
            self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            if not self.openai_api_key:
                raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
            
            # Wrap OpenAI client in adapter
            openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            self.client = OpenAILLMClient(openai_client)
        self.search_engine = SearchEngine(tavily_api_key=tavily_api_key)
        
        # Initialize source policy and related components
        self.source_policy = SourcePolicy()
        self.intent_extractor = IntentExtractor()
        self.verifier = FactVerifier(self.source_policy)
        self.candidate_extractor = CandidateExtractor()
        self.tool_planner = ToolPlanner()
        
        # Initialize aggregator with source policy
        self.aggregator = MovieDataAggregator(self.search_engine, self.source_policy)
        
        self.system_prompt = SYSTEM_PROMPT  # Kept for backward compatibility, but PromptBuilder is used for generation
        self.agent_name = AGENT_NAME
        self.version = AGENT_VERSION
        
        # Initialize prompt builder
        self.prompt_builder = PromptBuilder()
        
        # Initialize output validator
        self.output_validator = OutputValidator(enable_auto_fix=True)
        
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
            # Router will automatically infer request_type if not provided (offline, no LLM)
            try:
                request_plan = await self.planner.plan_request(user_query, self.client, request_type=request_type)
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
                
                # Wikipedia-only media enrichment (runs regardless of Tavily/OpenAI availability)
                await asyncio.to_thread(attach_media_to_result, user_query, result)
                
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
            
            # Step 0.5: Try Kaggle retrieval (works for both live and offline modes)
            # This runs before normal search to potentially use Kaggle datasets
            # All Kaggle logic (relevance gating, thresholds, timeouts) is inside the adapter
            kaggle_search_results = []
            if structured_intent:
                # Try Kaggle retrieval adapter (configurable, with timeout)
                from .kaggle_retrieval_adapter import get_kaggle_adapter
                # Get Kaggle adapter (can be enabled/disabled via environment or config)
                kaggle_enabled = os.getenv("CINEMIND_KAGGLE_ENABLED", "true").lower() == "true"
                kaggle_timeout = float(os.getenv("CINEMIND_KAGGLE_TIMEOUT", "5.0"))
                
                if kaggle_enabled:
                    try:
                        kaggle_adapter = get_kaggle_adapter(
                            enabled=kaggle_enabled,
                            timeout_seconds=kaggle_timeout
                        )
                        
                        kaggle_result = await kaggle_adapter.retrieve_evidence(
                            prompt=user_query,
                            intent=structured_intent.intent,
                            entities=structured_intent.entities,
                            max_results=5
                        )
                        
                        if kaggle_result.success and kaggle_result.evidence_items:
                            logger.info(f"[{request_id}] Kaggle retrieval successful: {len(kaggle_result.evidence_items)} items")
                            # Convert to evidence bundle format (normalized for EvidenceFormatter)
                            kaggle_evidence_bundle = kaggle_adapter.convert_to_evidence_bundle(kaggle_result)
                            if kaggle_evidence_bundle:
                                kaggle_search_results = kaggle_evidence_bundle.get("search_results", [])
                                logger.info(f"[{request_id}] Kaggle evidence retrieved: {len(kaggle_search_results)} results (will merge with web search if applicable)")
                        else:
                            logger.debug(f"[{request_id}] Kaggle retrieval: {kaggle_result.error_message or 'no relevant results'}, continuing with web search")
                    except Exception as e:
                        logger.warning(f"[{request_id}] Kaggle retrieval failed: {e}, continuing with web search")
            
            # Perform real-time search if requested AND tool plan allows it
            # Kaggle results will be merged with web search results (not replace them)
            search_results = []
            source_summary = {}
            verified_facts = []
            
            # Start with Kaggle results (if any)
            if kaggle_search_results:
                search_results.extend(kaggle_search_results)
                source_summary["kaggle"] = len(kaggle_search_results)
            
            should_skip_tavily = False  # Initialize outside if block to avoid UnboundLocalError
            
            # Perform live search (results will be merged with Kaggle results)
            if use_live_data:
                # Check if we should skip Tavily based on tool plan
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
                    # 2. Kaggle retrieval (handled by KaggleRetrievalAdapter above - already completed)
                    # 3. Tavily API (only if skip_tavily=False OR valid override_reason provided)
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
                        logger.info(f"[{request_id}] Performing search (Tavily: {'enabled' if not should_skip_tavily else ('override' if override_reason else 'skipped')})...")
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
                    
                    web_search_results = movie_info.get("results", [])
                    web_source_summary = movie_info.get("source_summary", {})
                    
                    # Merge Kaggle results with web search results
                    # EvidenceFormatter will handle deduplication later
                    if kaggle_search_results:
                        # Add web search results (EvidenceFormatter will dedupe by url/title/year)
                        search_results.extend(web_search_results)
                        source_summary.update(web_source_summary)
                        logger.info(f"[{request_id}] Merged Kaggle ({len(kaggle_search_results)}) + web ({len(web_search_results)}) = {len(search_results)} total results")
                    else:
                        # No Kaggle results, just use web search
                        search_results = web_search_results
                        source_summary = web_source_summary
                    
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
                            # Preserve Kaggle results before retry
                            kaggle_results_preserved = [r for r in search_results if r.get("source") == "kaggle_imdb"]
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
                            web_search_results_retry = movie_info.get("results", [])
                            # Merge preserved Kaggle results with retry web search results
                            search_results = kaggle_results_preserved + web_search_results_retry
                            source_summary = movie_info.get("source_summary", {})
                            if kaggle_results_preserved:
                                source_summary["kaggle"] = len(kaggle_results_preserved)
                        # Check for tier_a_missing (require_tier_a=True but no Tier A sources found)
                        elif source_summary.get("missing_required_tier", False):
                            final_override_reason = TavilyOverrideReason.TIER_A_MISSING.value
                            logger.info(f"[{request_id}] Override reason after search: {final_override_reason} (require_tier_a=True but no Tier A sources found)")
                            # Preserve Kaggle results before retry
                            kaggle_results_preserved = [r for r in search_results if r.get("source") == "kaggle_imdb"]
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
                            web_search_results_retry = movie_info.get("results", [])
                            # Merge preserved Kaggle results with retry web search results
                            search_results = kaggle_results_preserved + web_search_results_retry
                            source_summary = movie_info.get("source_summary", {})
                            if kaggle_results_preserved:
                                source_summary["kaggle"] = len(kaggle_results_preserved)
                    
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
                    
                    # Assemble routing decision record (single canonical decision object)
                    routing_decision = self._assemble_routing_decision(
                        request_id=request_id,
                        request_plan=request_plan,
                        structured_intent=structured_intent,
                        tool_plan=tool_plan,
                        cache_hit=cache_hit,
                        movie_info=movie_info,
                        source_summary=source_summary,
                        search_results=search_results
                    )
                    
                    # Persist routing decision to DB
                    if tracker:
                        tracker.log_metric(
                            "routing_decision",
                            1.0,
                            routing_decision,
                            metric_type="decision"
                        )
                    
                    # Log compact routing decision summary
                    self._log_routing_decision_summary(request_id, routing_decision)
                    
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
                        
                        # Verified facts will be included in EvidenceBundle by PromptBuilder
                    
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
                    
                except Exception as e:
                    if tracker:
                        tracker.log_error(f"Search failed: {e}")
                    logger.error(f"[{request_id}] Search failed: {e}")
                    relevant_results = []
                    verified_facts = []
            
            # Build messages using PromptBuilder
            # Initialize relevant_results if not already defined (for cache hit case)
            if 'relevant_results' not in locals():
                relevant_results = []
            
            # Build evidence bundle from all sources (Kaggle + web search)
            # EvidenceFormatter will handle deduplication and formatting
            # Both live and offline modes use the same methodology: merge all results into EvidenceBundle
            evidence_bundle = EvidenceBundle(
                search_results=search_results if search_results else [],
                verified_facts=verified_facts if verified_facts else None
            )
            
            logger.info(f"[{request_id}] Evidence bundle: {len(evidence_bundle.search_results)} total results (will be deduplicated and formatted by EvidenceFormatter)")
            
            messages, prompt_artifacts = self.prompt_builder.build_messages(
                request_plan=request_plan,
                evidence=evidence_bundle,
                user_query=user_query,
                structured_intent=structured_intent
            )
            
            # Construct full prompt for storage (legacy format for observability)
            system_content = messages[0]["content"] if messages else self.system_prompt
            user_content = messages[1]["content"] if len(messages) > 1 else user_query
            full_prompt = f"System: {system_content}\n\nUser: {user_content}"
            
            # Update request with full prompt in database
            if self.observability:
                self.observability.update_request_prompt(request_id, full_prompt)
                # Log prompt artifacts
                if tracker:
                    tracker.log_metric("prompt_artifacts", 1.0, {
                        "prompt_version": prompt_artifacts.prompt_version,
                        "instruction_template_id": prompt_artifacts.instruction_template_id,
                        "verbosity_budget": prompt_artifacts.verbosity_budget
                    })
            
            # Generate response using LLM client
            llm_start = time.time()
            try:
                if tracker:
                    with tracker.time_operation("openai_llm"):
                        llm_response = await self.client.chat_completions_create(
                            model=OPENAI_MODEL,
                            messages=messages,
                            temperature=0.7,
                            max_tokens=2000
                        )
                else:
                    llm_response = await self.client.chat_completions_create(
                        model=OPENAI_MODEL,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=2000
                    )
                
                agent_response = llm_response.content
                llm_time_ms = (time.time() - llm_start) * 1000
                
                # Validate response against template contract
                response_template = get_template(request_plan.request_type, request_plan.intent)
                validation_result = self.output_validator.validate(
                    response_text=agent_response,
                    template=response_template,
                    need_freshness=request_plan.need_freshness
                )
                
                # Log validation violations
                if validation_result.has_violations():
                    logger.warning(
                        f"[{request_id}] Response validation violations: {validation_result.violations}"
                    )
                    if tracker:
                        tracker.log_metric("validation_violations", len(validation_result.violations))
                
                # Extract token usage from initial response (needed for all paths)
                usage = llm_response.usage or {}
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                }
                
                # Use corrected text if auto-fix was applied, otherwise re-prompt if needed
                if validation_result.corrected_text:
                    agent_response = validation_result.corrected_text
                    logger.info(f"[{request_id}] Applied auto-fix for forbidden terms")
                elif validation_result.requires_reprompt:
                    # Re-prompt with strict correction instruction
                    logger.info(f"[{request_id}] Re-prompting due to validation violations")
                    correction_instruction = self.output_validator.build_correction_instruction(
                        validation_result.violations,
                        response_template
                    )
                    
                    # Add correction instruction to messages
                    correction_messages = messages + [
                        {"role": "assistant", "content": agent_response},
                        {"role": "user", "content": correction_instruction}
                    ]
                    
                    # Re-prompt
                    if tracker:
                        with tracker.time_operation("openai_llm_correction"):
                            correction_llm_response = await self.client.chat_completions_create(
                                model=OPENAI_MODEL,
                                messages=correction_messages,
                                temperature=0.3,  # Lower temperature for corrections
                                max_tokens=2000
                            )
                    else:
                        correction_llm_response = await self.client.chat_completions_create(
                            model=OPENAI_MODEL,
                            messages=correction_messages,
                            temperature=0.3,
                            max_tokens=2000
                        )
                    
                    agent_response = correction_llm_response.content
                    
                    # Update token usage to include correction request
                    correction_usage = correction_llm_response.usage or {}
                    initial_usage = llm_response.usage or {}
                    token_usage = {
                        "prompt_tokens": initial_usage.get("prompt_tokens", 0) + correction_usage.get("prompt_tokens", 0),
                        "completion_tokens": initial_usage.get("completion_tokens", 0) + correction_usage.get("completion_tokens", 0),
                        "total_tokens": initial_usage.get("total_tokens", 0) + correction_usage.get("total_tokens", 0)
                    }
                    logger.info(f"[{request_id}] Re-prompt completed, using corrected response")
                # token_usage already defined above
                
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
                                    
                                    # Extract intent signature components for cache keying
                                    intent = request_plan.intent if request_plan else None
                                    entities_typed = request_plan.entities_typed if request_plan else None
                                    constraints = None
                                    if structured_intent and hasattr(structured_intent, 'constraints'):
                                        constraints = structured_intent.constraints
                                    
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
                                        freshness_ttl_hours=freshness_ttl_hours,
                                        request_plan=request_plan,
                                        intent=intent,
                                        entities_typed=entities_typed,
                                        constraints=constraints
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

                # Pass recommended_movies for batch enrichment (e.g. similar movies from FakeLLM)
                meta = getattr(llm_response, "metadata", None) or {}
                if meta.get("similar_movies"):
                    result["recommended_movies"] = meta["similar_movies"]
                
                # Wikipedia-only media enrichment (runs regardless of Tavily/OpenAI availability)
                await asyncio.to_thread(attach_media_to_result, user_query, result)
                
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
    
    def _assemble_routing_decision(
        self,
        request_id: str,
        request_plan,
        structured_intent,
        tool_plan,
        cache_hit,
        movie_info: Dict,
        source_summary: Dict,
        search_results: List[Dict]
    ) -> Dict:
        """
        Assemble routing decision record (single canonical decision object).
        
        Returns:
            Dict with routing decision payload
        """
        # Extract request type and intent
        request_type = None
        intent = None
        if request_plan:
            if hasattr(request_plan, 'to_dict'):
                plan_dict = request_plan.to_dict()
            elif isinstance(request_plan, dict):
                plan_dict = request_plan
            else:
                plan_dict = {}
            request_type = plan_dict.get('request_type')
            intent = plan_dict.get('intent')
        
        # Extract typed entities
        entities_typed = {"movies": [], "people": []}
        if structured_intent and hasattr(structured_intent, 'entities'):
            entities_typed = structured_intent.entities if isinstance(structured_intent.entities, dict) else {"movies": [], "people": []}
        elif request_plan:
            entities_typed = plan_dict.get('entities_typed', {"movies": [], "people": []})
        
        # Extract mentioned_year
        mentioned_year = None
        if structured_intent and hasattr(structured_intent, 'mentioned_year'):
            mentioned_year = structured_intent.mentioned_year
        
        # Count Kaggle results used (just for tracking - no Kaggle-specific logic)
        kaggle_results_used = sum(1 for r in search_results if r.get("source") == "kaggle_imdb")
        
        # Extract tool plan info
        skip_tavily = False
        need_freshness = False
        freshness_reason = None
        freshness_ttl_hours = None
        if tool_plan:
            skip_tavily = tool_plan.tool_plan_skip_tavily if hasattr(tool_plan, 'tool_plan_skip_tavily') else False
            need_freshness = tool_plan.need_freshness if hasattr(tool_plan, 'need_freshness') else False
            freshness_reason = tool_plan.freshness_reason if hasattr(tool_plan, 'freshness_reason') else None
            freshness_ttl_hours = tool_plan.freshness_ttl_hours if hasattr(tool_plan, 'freshness_ttl_hours') else None
        elif request_plan:
            need_freshness = plan_dict.get('need_freshness', False)
            freshness_reason = plan_dict.get('freshness_reason')
            freshness_ttl_hours = plan_dict.get('freshness_ttl_hours')
        
        # Extract override fields
        override_used = movie_info.get("override_used", False)
        override_reason = movie_info.get("override_reason")
        if tool_plan:
            override_used = tool_plan.override_used if hasattr(tool_plan, 'override_used') else override_used
            override_reason = tool_plan.override_reason if hasattr(tool_plan, 'override_reason') else override_reason
        
        # Extract final tool usage
        cache_hit_bool = cache_hit is not None
        tavily_used = movie_info.get("tavily_used", False)
        fallback_used = movie_info.get("fallback_used", False)
        if tool_plan:
            tavily_used = tool_plan.tavily_used if hasattr(tool_plan, 'tavily_used') else tavily_used
            fallback_used = tool_plan.fallback_used if hasattr(tool_plan, 'fallback_used') else fallback_used
        
        # Extract evidence summary (tier counts)
        tier_counts_present = source_summary.get("tier_counts", {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0})
        # Count tiers used (from search_results)
        tier_counts_used = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
        for result in search_results:
            tier = result.get("tier", "UNKNOWN")
            tier_counts_used[tier] = tier_counts_used.get(tier, 0) + 1
        
        # Assemble routing decision
        routing_decision = {
            "request_id": request_id,
            "request_type": request_type,
            "intent": intent,
            "entities_typed": entities_typed,
            "mentioned_year": mentioned_year,
            "kaggle_results_used": kaggle_results_used,  # Simple count - no Kaggle-specific logic
            "tool_plan": {
                "skip_tavily": skip_tavily,
                "need_freshness": need_freshness,
                "freshness_reason": freshness_reason,
                "freshness_ttl_hours": freshness_ttl_hours
            },
            "override": {
                "override_used": override_used,
                "override_reason": override_reason
            },
            "tool_usage": {
                "cache_hit": cache_hit_bool,
                "tavily_used": tavily_used,
                "fallback_used": fallback_used
            },
            "evidence_summary": {
                "tier_counts_present": tier_counts_present,
                "tier_counts_used": tier_counts_used
            }
        }
        
        return routing_decision
    
    def _log_routing_decision_summary(self, request_id: str, routing_decision: Dict):
        """
        Log compact routing decision summary.
        
        Format: cache_hit, kaggle_results_used, tavily_used, override_reason, tiers_used
        """
        cache_hit = routing_decision.get("tool_usage", {}).get("cache_hit", False)
        kaggle_results_used = routing_decision.get("kaggle_results_used", 0)
        tavily_used = routing_decision.get("tool_usage", {}).get("tavily_used", False)
        override_reason = routing_decision.get("override", {}).get("override_reason")
        
        # Build tiers_used string
        tier_counts_used = routing_decision.get("evidence_summary", {}).get("tier_counts_used", {})
        tiers_parts = []
        for tier in ["A", "B", "C", "UNKNOWN"]:
            count = tier_counts_used.get(tier, 0)
            if count > 0:
                tiers_parts.append(f"{tier}:{count}")
        tiers_used = ",".join(tiers_parts) if tiers_parts else "none"
        
        # Build summary
        summary_parts = [
            f"cache_hit={cache_hit}",
            f"kaggle_results={kaggle_results_used}",
            f"tavily_used={tavily_used}",
            f"override_reason={override_reason or 'none'}",
            f"tiers_used={tiers_used}"
        ]
        
        logger.info(
            f"[{request_id}] Routing decision: " + ", ".join(summary_parts)
        )
    
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

