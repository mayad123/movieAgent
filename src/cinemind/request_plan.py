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
    entities: List[str] = field(default_factory=list)  # Movie/person names
    entity_years: Dict[str, Optional[int]] = field(default_factory=dict)  # Optional year disambiguation
    
    # Freshness requirements
    need_freshness: bool = False
    freshness_ttl_hours: float = 24.0  # TTL in hours for this request type
    
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
    
    def __post_init__(self):
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent": self.intent,
            "request_type": self.request_type,
            "entities": self.entities,
            "entity_years": self.entity_years,
            "need_freshness": self.need_freshness,
            "freshness_ttl_hours": self.freshness_ttl_hours,
            "allowed_source_tiers": self.allowed_source_tiers,
            "require_tier_a": self.require_tier_a,
            "reject_tier_c": self.reject_tier_c,
            "tools_to_call": [t.value for t in self.tools_to_call],
            "response_format": self.response_format.value,
            "confidence": self.confidence,
            "rule_hit": self.rule_hit,
            "llm_used": self.llm_used,
            "original_query": self.original_query,
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
    
    def __init__(self, classifier, intent_extractor):
        """
        Initialize planner.
        
        Args:
            classifier: HybridClassifier instance
            intent_extractor: IntentExtractor instance
        """
        self.classifier = classifier
        self.intent_extractor = intent_extractor
    
    async def plan_request(self, prompt: str, client) -> RequestPlan:
        """
        Create RequestPlan from user prompt.
        This is the ONLY way to route requests.
        
        Args:
            prompt: User's query
            client: OpenAI client (for LLM-based extraction if needed)
        
        Returns:
            RequestPlan with all routing information
        """
        # Step 1: Classify the request
        classification = await self.classifier.classify(prompt, client)
        
        # Step 2: Extract structured intent
        structured_intent = await self.intent_extractor.extract_with_llm(
            prompt, client, classification.predicted_type
        )
        
        # Step 3: Determine freshness requirements
        # Use freshness hints from StructuredIntent if available, otherwise use classification
        need_freshness = structured_intent.need_freshness if hasattr(structured_intent, 'need_freshness') and structured_intent.need_freshness else classification.need_freshness
        ttl_hours = structured_intent.freshness_ttl_hours if hasattr(structured_intent, 'freshness_ttl_hours') and structured_intent.freshness_ttl_hours else self.TTL_BY_TYPE.get(classification.predicted_type, 168.0)
        
        # Step 4: Determine source policy
        allowed_tiers, require_tier_a, reject_tier_c = self._determine_source_policy(
            classification.predicted_type, structured_intent.intent
        )
        
        # Step 5: Select tools
        tools = self._select_tools(structured_intent.intent, classification.predicted_type)
        
        # Step 6: Determine response format
        response_format = self._determine_response_format(
            structured_intent.intent, 
            classification.predicted_type,
            structured_intent.constraints
        )
        
        # Step 7: Extract entity years if present
        # Get all entities as flat list for RequestPlan (backward compatibility)
        all_entities = structured_intent.get_all_entities() if hasattr(structured_intent, 'get_all_entities') else (
            structured_intent.entities if isinstance(structured_intent.entities, list) 
            else structured_intent.entities.get("movies", []) + structured_intent.entities.get("people", [])
        )
        entity_years = self._extract_entity_years(prompt, all_entities)
        
        return RequestPlan(
            intent=structured_intent.intent,
            request_type=classification.predicted_type,
            entities=all_entities,  # RequestPlan stores as flat list for now
            entity_years=entity_years,
            need_freshness=need_freshness,
            freshness_ttl_hours=ttl_hours,
            allowed_source_tiers=allowed_tiers,
            require_tier_a=require_tier_a,
            reject_tier_c=reject_tier_c,
            tools_to_call=tools,
            response_format=response_format,
            confidence=classification.confidence,
            rule_hit=classification.rule_hit,
            llm_used=classification.llm_used,
            original_query=prompt
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

