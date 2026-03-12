"""
Request planning and routing contract for CineMind.
Defines a canonical RequestPlan that every downstream step follows.
"""
import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ResponseFormat(Enum):
    """Response format requirements."""
    LIST = "list"  # Ordered list of items
    SHORT_FACT = "short_fact"  # Single fact or short answer
    COMPARISON = "comparison"  # Side-by-side comparison
    SPOILER_WARNING = "spoiler_warning"  # Requires spoiler warning
    DETAILED = "detailed"  # Detailed explanation
    VERIFIED_LIST = "verified_list"  # List with verification sources


class ToolType(Enum):
    """Types of tools that can be called."""
    SEARCH = "search"  # General web search (Tavily)
    IMDB_LOOKUP = "imdb_lookup"  # Direct IMDb API/dataset lookup
    WIKI_LOOKUP = "wiki_lookup"  # Wikipedia/Wikidata lookup
    TMDB_LOOKUP = "tmdb_lookup"  # TMDb API lookup
    NONE = "none"  # No external tools needed


@dataclass
class RequestPlan:
    """
    Canonical request plan that defines the routing contract.
    This is the single source of truth for how to handle a request.
    """
    # Core classification
    intent: str  # e.g., "info", "recs", "filmography_overlap", "release-date"
    request_type: str  # Classified type: "info", "recs", "comparison", etc.
    
    # Entities
    entities: List[str] = field(default_factory=list)  # Movie/person names (backward compatibility - flat list)
    entities_typed: Dict[str, List[str]] = field(default_factory=lambda: {"movies": [], "people": []})  # Typed entities: {"movies": [...], "people": [...]}
    entity_years: Dict[str, Optional[int]] = field(default_factory=dict)  # Optional year disambiguation
    
    # Freshness requirements
    freshness_signal: bool = False  # Weak signal from classifier (might need fresh data)
    need_freshness: bool = False  # Final decision made by ToolPlanner (based on intent + entity year + signal)
    freshness_ttl_hours: float = 24.0  # TTL in hours for this request type
    freshness_reason: Optional[str] = None  # Reason for final freshness decision
    
    # Source policy
    allowed_source_tiers: List[str] = field(default_factory=lambda: ["A", "B"])  # Which tiers are allowed
    require_tier_a: bool = False  # Must have at least one Tier A source
    reject_tier_c: bool = True  # Reject Tier C sources for facts
    
    # Tool selection
    tools_to_call: List[ToolType] = field(default_factory=list)
    
    # Response format
    response_format: ResponseFormat = ResponseFormat.SHORT_FACT
    
    # Metadata
    confidence: float = 1.0
    rule_hit: Optional[str] = None
    llm_used: bool = False
    original_query: str = ""
    
    # Intent extraction metadata
    intent_extraction_mode: str = "rules"  # "rules" or "llm" - which extractor path was used
    intent_confidence: float = 1.0  # Confidence of intent extraction (0-1)
    
    def __post_init__(self) -> None:
        """Validate and normalize the plan."""
        # Ensure tools_to_call is a list of ToolType enums
        if not isinstance(self.tools_to_call, list):
            self.tools_to_call = []
        self.tools_to_call = [t if isinstance(t, ToolType) else ToolType(t) for t in self.tools_to_call]
        
        # Ensure response_format is an enum
        if not isinstance(self.response_format, ResponseFormat):
            self.response_format = ResponseFormat(self.response_format)
        
        # Normalize allowed_source_tiers
        if not self.allowed_source_tiers:
            self.allowed_source_tiers = ["A", "B"]
        
        # Ensure entities_typed has required keys
        if not isinstance(self.entities_typed, dict):
            self.entities_typed = {"movies": [], "people": []}
        if "movies" not in self.entities_typed:
            self.entities_typed["movies"] = []
        if "people" not in self.entities_typed:
            self.entities_typed["people"] = []
        
        # If entities_typed is populated but entities is empty, populate entities for backward compatibility
        if not self.entities and self.entities_typed:
            self.entities = self.entities_typed.get("movies", []) + self.entities_typed.get("people", [])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent": self.intent,
            "request_type": self.request_type,
            "entities": self.entities,
            "entities_typed": self.entities_typed,
            "entity_years": self.entity_years,
            "freshness_signal": self.freshness_signal,
            "need_freshness": self.need_freshness,
            "freshness_ttl_hours": self.freshness_ttl_hours,
            "freshness_reason": self.freshness_reason,
            "allowed_source_tiers": self.allowed_source_tiers,
            "require_tier_a": self.require_tier_a,
            "reject_tier_c": self.reject_tier_c,
            "tools_to_call": [t.value for t in self.tools_to_call],
            "response_format": self.response_format.value,
            "confidence": self.confidence,
            "rule_hit": self.rule_hit,
            "llm_used": self.llm_used,
            "original_query": self.original_query,
            "intent_extraction_mode": self.intent_extraction_mode,
            "intent_confidence": self.intent_confidence,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequestPlan":
        """Create from dictionary."""
        data = data.copy()
        data["tools_to_call"] = [ToolType(t) for t in data.get("tools_to_call", [])]
        data["response_format"] = ResponseFormat(data.get("response_format", "short_fact"))
        return cls(**data)


class RequestPlanner:
    """
    Creates RequestPlan from user prompt.
    This is the single function that routes all requests.
    """
    
    # TTL by request type (in hours)
    TTL_BY_TYPE = {
        "release-date": 6.0,  # Release dates change frequently
        "info": 168.0,  # 7 days for general info
        "recs": 336.0,  # 14 days for recommendations
        "comparison": 168.0,  # 7 days
        "spoiler": 720.0,  # 30 days - spoilers don't change
        "fact-check": 168.0,  # 7 days
    }
    
    # Tool selection by intent
    TOOLS_BY_INTENT = {
        "filmography_overlap": [ToolType.SEARCH, ToolType.IMDB_LOOKUP],
        "director_info": [ToolType.SEARCH, ToolType.IMDB_LOOKUP],
        "release_date": [ToolType.SEARCH, ToolType.IMDB_LOOKUP],
        "cast_info": [ToolType.SEARCH, ToolType.IMDB_LOOKUP],
        "comparison": [ToolType.SEARCH],
        "recommendation": [ToolType.SEARCH],
        "general_info": [ToolType.SEARCH],
    }
    
    # Response format by intent
    FORMAT_BY_INTENT = {
        "filmography_overlap": ResponseFormat.VERIFIED_LIST,
        "director_info": ResponseFormat.SHORT_FACT,
        "release_date": ResponseFormat.SHORT_FACT,
        "cast_info": ResponseFormat.LIST,
        "comparison": ResponseFormat.COMPARISON,
        "recommendation": ResponseFormat.LIST,
        "general_info": ResponseFormat.SHORT_FACT,
    }
    
    def __init__(self, classifier: Any, intent_extractor: Any) -> None:
        """
        Initialize planner.
        
        Args:
            classifier: HybridClassifier instance
            intent_extractor: IntentExtractor instance
        """
        self.classifier = classifier
        self.intent_extractor = intent_extractor
    
    async def plan_request(self, prompt: str, client: Any, request_type: Optional[str] = None) -> RequestPlan:
        """
        Create RequestPlan from user prompt.
        This is the ONLY way to route requests.
        
        Can build a complete RequestPlan from only the prompt (prompt-only mode) using:
        - RequestTypeRouter (deterministic, offline) for request_type
        - IntentExtractor (rules-first + LLM fallback) for intent and entities
        - ToolPlanner for freshness decisions
        - Format selection based on intent
        
        Args:
            prompt: User's query
            client: OpenAI client (for LLM-based extraction if needed)
            request_type: Optional pre-determined request_type (if provided, uses it directly)
                        If None, infers from prompt using router
        
        Returns:
            RequestPlan with all routing information
        """
        # Step 1: Determine request_type
        # If not provided, infer it using rules-based router (offline, no LLM)
        router_confidence = 1.0  # Default confidence when request_type is provided
        router_rule_hit = "provided"  # Default rule_hit when request_type is provided
        router_used = False
        
        if not request_type:
            from .request_type_router import get_request_type_router
            router = get_request_type_router()
            router_result = router.route(prompt)
            router_used = True
            router_confidence = router_result.confidence
            router_rule_hit = router_result.rule_hit
            
            # Use inferred type if confidence is high enough, otherwise default to "info"
            if router.should_use_inferred_type(router_result):
                request_type = router_result.request_type
                logger.info(f"RequestTypeRouter inferred '{request_type}' (confidence: {router_confidence:.2f}, rule: {router_rule_hit})")
            else:
                request_type = "info"  # Safe default for low confidence
                logger.info(f"RequestTypeRouter confidence too low ({router_confidence:.2f}), defaulting to 'info'")
        else:
            logger.info(f"Using provided request_type: '{request_type}'")
        
        # Step 2: Extract structured intent using smart routing (rules-first + LLM fallback)
        # This provides: intent, entities, constraints, freshness needs, etc.
        structured_intent, extraction_mode, intent_confidence = await self.intent_extractor.extract_smart(
            prompt, client, request_type, force_llm=False
        )
        
        # Step 3: Extract typed entities (already extracted in structured_intent)
        entities_typed = structured_intent.entities if isinstance(structured_intent.entities, dict) else {"movies": [], "people": []}
        if "movies" not in entities_typed:
            entities_typed["movies"] = []
        if "people" not in entities_typed:
            entities_typed["people"] = []
        
        # Step 4: Determine freshness requirements
        # Use freshness signal from structured_intent (already determined by IntentExtractor)
        freshness_signal = structured_intent.need_freshness  # Use intent extractor's freshness determination
        
        # Get entity year for freshness decision
        candidate_year = structured_intent.candidate_year if hasattr(structured_intent, 'candidate_year') else None
        mentioned_year = structured_intent.mentioned_year if hasattr(structured_intent, 'mentioned_year') else None
        
        # Use ToolPlanner to make final freshness decision
        # ToolPlanner uses intent + signal + entity year to determine final freshness
        from .tool_plan import ToolPlanner
        tool_planner = ToolPlanner()
        need_freshness, ttl_hours, freshness_reason = tool_planner.determine_freshness(
            structured_intent.intent,
            freshness_signal,
            entities_typed,
            candidate_year=candidate_year,
            mentioned_year=mentioned_year
        )
        logger.info(f"Freshness decision: signal={freshness_signal}, final={need_freshness}, reason={freshness_reason}, ttl={ttl_hours}h")
        
        # Step 5: Determine source policy (based on request_type and intent)
        allowed_tiers, require_tier_a, reject_tier_c = self._determine_source_policy(
            request_type, structured_intent.intent
        )
        
        # Step 6: Select tools (based on intent and request_type)
        tools = self._select_tools(structured_intent.intent, request_type)
        
        # Step 7: Determine response format (based on intent, request_type, and constraints)
        response_format = self._determine_response_format(
            structured_intent.intent, 
            request_type,
            structured_intent.constraints
        )
        
        # Step 8: Extract entity years (entities_typed already extracted in Step 3)
        all_entities = entities_typed.get("movies", []) + entities_typed.get("people", [])
        entity_years = self._extract_entity_years(prompt, all_entities)
        
        # Step 9: Ensure schema consistency (candidate_year and order_by validation)
        # candidate_year must be None unless requires_disambiguation is True
        if not structured_intent.requires_disambiguation and structured_intent.candidate_year is not None:
            logger.warning(f"Schema validation: candidate_year set to None (requires_disambiguation is False)")
            structured_intent.candidate_year = None
        
        # constraints.order_by must be None unless user explicitly requested sorting
        order_by = structured_intent.constraints.get("order_by")
        if order_by and order_by not in {"release_year_asc", "release_year_desc", "chronological"}:
            logger.warning(f"Schema validation: invalid order_by value '{order_by}', set to None")
            structured_intent.constraints["order_by"] = None
        
        logger.info(f"Intent extraction: mode={extraction_mode}, confidence={intent_confidence:.2f}")
        
        # Determine overall confidence (use router confidence if router was used, otherwise use intent confidence)
        overall_confidence = router_confidence if router_used else intent_confidence
        # If both router and intent extraction were used, take the minimum (conservative)
        if router_used:
            overall_confidence = min(router_confidence, intent_confidence)
        
        # Determine rule_hit (prefer router rule_hit if router was used)
        rule_hit = router_rule_hit if router_used else None
        
        # Determine llm_used (true if intent extraction used LLM)
        llm_used = (extraction_mode == "llm")
        
        return RequestPlan(
            intent=structured_intent.intent,
            request_type=request_type,  # Use request_type directly (from router or provided)
            entities=all_entities,  # Flat list for backward compatibility
            entities_typed=entities_typed,  # Typed entities (preferred)
            entity_years=entity_years,
            freshness_signal=freshness_signal,  # Signal from structured_intent (from IntentExtractor)
            need_freshness=need_freshness,  # Final decision from ToolPlanner
            freshness_ttl_hours=ttl_hours,
            freshness_reason=freshness_reason,  # Reason for final decision
            allowed_source_tiers=allowed_tiers,
            require_tier_a=require_tier_a,
            reject_tier_c=reject_tier_c,
            tools_to_call=tools,
            response_format=response_format,
            confidence=overall_confidence,  # Overall confidence from router + intent extraction
            rule_hit=rule_hit,  # Rule hit from router
            llm_used=llm_used,  # Whether LLM was used in intent extraction
            original_query=prompt,
            intent_extraction_mode=extraction_mode,  # "rules" or "llm"
            intent_confidence=intent_confidence  # Confidence from intent extraction (0-1)
        )
    
    def _determine_source_policy(self, request_type: str, intent: str) -> Tuple[List[str], bool, bool]:
        """
        Determine source policy based on request type and intent.
        
        Returns:
            (allowed_tiers, require_tier_a, reject_tier_c)
        """
        # Facts require Tier A only
        if request_type in ["info", "fact-check"] or intent in ["filmography_overlap", "director_info", "cast_info"]:
            return (["A"], True, True)  # Only Tier A, require it, reject Tier C
        
        # Release dates can use Tier A and B
        if request_type == "release-date" or intent == "release_date":
            return (["A", "B"], True, True)  # Tier A/B, require A, reject C
        
        # Recommendations and comparisons can use all tiers but prefer A/B
        if request_type in ["recs", "comparison"]:
            return (["A", "B", "C"], False, False)  # All tiers, don't require A, don't reject C
        
        # Spoilers can use all tiers
        if request_type == "spoiler":
            return (["A", "B", "C"], False, False)
        
        # Default: Tier A and B, require A for facts
        return (["A", "B"], True, True)
    
    def _select_tools(self, intent: str, request_type: str) -> List[ToolType]:
        """Select tools to call based on intent."""
        # Check intent-specific tools
        if intent in self.TOOLS_BY_INTENT:
            return self.TOOLS_BY_INTENT[intent].copy()
        
        # Fallback to request type
        if request_type == "info":
            return [ToolType.SEARCH, ToolType.IMDB_LOOKUP]
        elif request_type == "release-date":
            return [ToolType.SEARCH, ToolType.IMDB_LOOKUP]
        elif request_type == "recs":
            return [ToolType.SEARCH]
        else:
            return [ToolType.SEARCH]
    
    def _determine_response_format(self, intent: str, request_type: str, 
                                   constraints: Dict[str, Any]) -> ResponseFormat:
        """Determine response format based on intent and constraints."""
        # Check constraints first
        if constraints.get("format") == "list":
            return ResponseFormat.LIST
        if constraints.get("format") == "comparison":
            return ResponseFormat.COMPARISON
        
        # Check intent
        if intent in self.FORMAT_BY_INTENT:
            return self.FORMAT_BY_INTENT[intent]
        
        # Check request type
        if request_type == "spoiler":
            return ResponseFormat.SPOILER_WARNING
        if request_type == "comparison":
            return ResponseFormat.COMPARISON
        if "list" in request_type.lower() or "name" in request_type.lower():
            return ResponseFormat.LIST
        
        return ResponseFormat.SHORT_FACT
    
    def _extract_entity_years(self, prompt: str, entities: List[str]) -> Dict[str, Optional[int]]:
        """Extract years associated with entities."""
        import re
        entity_years = {}
        
        # Find years in prompt
        year_pattern = r"\b(19\d{2}|20\d{2})\b"
        years = re.findall(year_pattern, prompt)
        
        # Try to associate years with entities (simple heuristic)
        # If year appears near an entity, associate it
        prompt_lower = prompt.lower()
        for entity in entities:
            entity_years[entity] = None
            entity_lower = entity.lower()
            # Find position of entity
            entity_pos = prompt_lower.find(entity_lower)
            if entity_pos != -1:
                # Look for year within 50 chars of entity
                context = prompt[max(0, entity_pos - 50):entity_pos + len(entity) + 50]
                year_matches = re.findall(year_pattern, context)
                if year_matches:
                    # Use the first year found
                    entity_years[entity] = int(year_matches[0])
        
        return entity_years

