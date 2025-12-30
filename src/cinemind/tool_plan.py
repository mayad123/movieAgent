"""
Tool planning and routing based on freshness requirements.
Decides which tools to call (or skip) before making any API calls.
"""
import logging
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ToolAction(Enum):
    """Actions for tool usage."""
    SKIP = "skip"  # Don't call this tool
    ALLOW = "allow"  # Allow this tool
    PREFER = "prefer"  # Prefer this tool over others
    REQUIRED = "required"  # This tool is required


@dataclass
class ToolPlan:
    """
    Plan for which tools to use based on freshness and intent.
    """
    use_tavily: bool = False  # Should we call Tavily/web search?
    use_imdb_lookup: bool = False  # Should we use IMDb API/dataset?
    use_wiki_lookup: bool = False  # Should we use Wikipedia/Wikidata?
    use_cache: bool = True  # Should we check cache first?
    use_structured_db: bool = True  # Should we try structured sources first?
    freshness_reason: Optional[str] = None
    skip_reason: Optional[str] = None
    
    # Search usage tracking (populated after execution)
    tool_plan_skip_tavily: bool = False  # What the tool plan said (before overrides)
    tavily_used: bool = False  # Whether Tavily was actually used
    fallback_used: bool = False  # Whether fallback search was used
    fallback_provider: Optional[str] = None  # Name of fallback provider (e.g., "duckduckgo")
    override_used: bool = False  # Whether tool plan decision was overridden
    override_reason: Optional[str] = None  # Reason for override: "disambiguation_needed", "structured_lookup_empty", "tier_a_missing"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "use_tavily": self.use_tavily,
            "use_imdb_lookup": self.use_imdb_lookup,
            "use_wiki_lookup": self.use_wiki_lookup,
            "use_cache": self.use_cache,
            "use_structured_db": self.use_structured_db,
            "freshness_reason": self.freshness_reason,
            "skip_reason": self.skip_reason,
            "tool_plan_skip_tavily": self.tool_plan_skip_tavily,
            "tavily_used": self.tavily_used,
            "fallback_used": self.fallback_used,
            "fallback_provider": self.fallback_provider,
            "override_used": self.override_used,
            "override_reason": self.override_reason
        }


class ToolPlanner:
    """
    Creates tool plans based on freshness requirements and intent.
    Implements freshness-based routing that happens before Tavily is considered.
    """
    
    # Movie age threshold (years) - movies older than this don't need freshness for stable metadata
    MOVIE_AGE_THRESHOLD = 2  # 2-3 years old = stable
    
    def __init__(self, current_year: Optional[int] = None):
        """
        Initialize tool planner.
        
        Args:
            current_year: Current year (defaults to 2024 if not provided)
        """
        from datetime import datetime
        self.current_year = current_year or datetime.now().year
    
    def determine_freshness(self, intent: str, freshness_signal: bool, entities: Dict[str, List[str]], 
                           candidate_year: Optional[int] = None, mentioned_year: Optional[int] = None) -> Tuple[bool, float, str]:
        """
        Determine final freshness requirement based on intent + entity year + signal.
        
        Args:
            intent: Intent type (e.g., "director_info", "release_status")
            freshness_signal: Weak signal from classifier (might need fresh data - e.g., "today", "currently")
            entities: Typed entities {"movies": [...], "people": [...]}
            candidate_year: Optional year for disambiguation
            mentioned_year: Optional year mentioned in query (for award queries, etc.)
        
        Returns:
            (need_freshness: bool, ttl_hours: float, reason: str)
        """
        # Determine which year to use (prefer candidate_year for disambiguation, then mentioned_year)
        entity_year = candidate_year or mentioned_year
        
        # Step 1: Check if intent is stable (metadata that doesn't change)
        stable_intents = ["director_info", "cast_info", "filmography_overlap", "general_info", "comparison"]
        is_stable_intent = intent in stable_intents
        
        # Step 2: For volatile intents, always need freshness
        volatile_intents = ["release_status", "where_to_watch", "awards_current_year"]
        if intent in volatile_intents:
            ttl_hours = 6.0  # 6 hours for volatile data
            reason = f"volatile intent '{intent}' requires fresh data"
            logger.info(f"Freshness decision: {reason} - need_freshness=True")
            return (True, ttl_hours, reason)
        
        # Step 3: For release_date intent, check if it's about upcoming/recent releases
        if intent == "release_date":
            # If no year or recent year, likely needs freshness
            if not entity_year or (entity_year >= self.current_year - 1):
                ttl_hours = 6.0
                reason = "release_date intent for recent/upcoming movies"
                logger.info(f"Freshness decision: {reason} - need_freshness=True")
                return (True, ttl_hours, reason)
            else:
                ttl_hours = 720.0  # Old release dates are stable
                reason = f"release_date intent for old movie ({entity_year})"
                logger.info(f"Freshness decision: {reason} - need_freshness=False")
                return (False, ttl_hours, reason)
        
        # Step 4: For stable intents with old movies, override signal to False
        if is_stable_intent and entity_year and (self.current_year - entity_year) > self.MOVIE_AGE_THRESHOLD:
            reason = f"stable intent '{intent}' with old movie ({entity_year}, age > {self.MOVIE_AGE_THRESHOLD} years)"
            ttl_hours = 720.0  # 30 days for stable metadata
            logger.info(f"Freshness override: {reason} - need_freshness=False (signal was {freshness_signal})")
            return (False, ttl_hours, reason)
        
        # Step 5: For stable intents without old movie, respect freshness_signal
        # (e.g., "where to watch today" should have freshness_signal=True and result in need_freshness=True)
        if is_stable_intent:
            if freshness_signal:
                ttl_hours = 6.0  # Short TTL for time-sensitive queries
                reason = f"stable intent '{intent}' but freshness_signal=True (e.g., 'today', 'currently')"
                logger.info(f"Freshness decision: {reason} - need_freshness=True")
                return (True, ttl_hours, reason)
            else:
                ttl_hours = 720.0  # 30 days for stable metadata
                reason = f"stable intent '{intent}' - metadata doesn't change"
                return (False, ttl_hours, reason)
        
        # Step 6: Default: use signal
        ttl_hours = 168.0  # 7 days default
        reason = f"default decision based on freshness_signal={freshness_signal}"
        logger.info(f"Freshness decision: {reason} - need_freshness={freshness_signal}")
        return (freshness_signal, ttl_hours, reason)
    
    def plan_tools(self, intent: str, need_freshness: bool, freshness_reason: Optional[str],
                   entities: Dict[str, List[str]], candidate_year: Optional[int] = None,
                   requires_disambiguation: bool = False) -> ToolPlan:
        """
        Create tool plan based on freshness requirements.
        
        Args:
            intent: Intent type (e.g., "director_info", "release_status")
            need_freshness: Whether query needs fresh data
            freshness_reason: Reason for freshness requirement
            entities: Typed entities {"movies": [...], "people": [...]}
            candidate_year: Optional year from query
            requires_disambiguation: Whether title is ambiguous
        
        Returns:
            ToolPlan with tool usage decisions
        """
        movies = entities.get("movies", [])
        movie_year = candidate_year
        
        # Step 1: For stable intents, check movie age as second gate
        stable_intents = ["director_info", "cast_info", "filmography_overlap", "general_info", "comparison"]
        is_stable_intent = intent in stable_intents
        
        # If we have a movie year and it's an old movie, force no freshness for stable intents
        if is_stable_intent and movie_year and (self.current_year - movie_year) > self.MOVIE_AGE_THRESHOLD:
            # Old movie + stable intent = no freshness needed
            need_freshness = False
            freshness_reason = f"movie from {movie_year} is stable metadata (age > {self.MOVIE_AGE_THRESHOLD} years)"
            logger.info(f"Movie age gate: {movie_year} is old enough, forcing need_freshness=False for stable intent")
        
        # Step 2: Create tool plan based on freshness
        if not need_freshness:
            # Stable intent: Try cache → structured DB → Tier A lookup first
            # Only allow Tavily if entity resolution fails or ambiguity detected
            tool_plan = ToolPlan(
                use_tavily=requires_disambiguation,  # Only if ambiguous title
                use_imdb_lookup=True,  # Prefer structured sources
                use_wiki_lookup=True,  # Prefer structured sources
                use_cache=True,  # Always check cache first
                use_structured_db=True,  # Try structured DB first
                freshness_reason=freshness_reason or "stable metadata",
                skip_reason="no freshness needed, using cache/structured sources" if not requires_disambiguation else "only if disambiguation needed"
            )
            tool_plan.tool_plan_skip_tavily = not requires_disambiguation
            return tool_plan
        else:
            # Volatile intent: Allow Tavily but prefer Tier A sources
            tool_plan = ToolPlan(
                use_tavily=True,  # Allow web search for fresh data
                use_imdb_lookup=True,  # Still prefer Tier A sources
                use_wiki_lookup=True,  # Still prefer Tier A sources
                use_cache=True,  # Check cache first (may be stale)
                use_structured_db=False,  # Skip structured DB for volatile data
                freshness_reason=freshness_reason or "time-volatile intent",
                skip_reason=None
            )
            tool_plan.tool_plan_skip_tavily = False
            return tool_plan
    
    def should_skip_tavily(self, tool_plan: ToolPlan, cache_hit: bool = False, 
                           need_freshness: bool = False) -> Tuple[bool, str]:
        """
        Final decision: Should we skip Tavily?
        
        Simplified logic:
        - If cache_hit and need_freshness == False → skip Tavily
        
        Args:
            tool_plan: Tool plan from plan_tools()
            cache_hit: Whether we have a cache hit
            need_freshness: Whether query needs fresh data
        
        Returns:
            (should_skip: bool, reason: str)
        """
        # Store the tool plan's original decision
        tool_plan.tool_plan_skip_tavily = not tool_plan.use_tavily
        
        # Simplified logic: skip if cache hit and no freshness needed
        if cache_hit and not need_freshness:
            return (True, "cache hit for stable intent")
        
        # Default: follow tool plan
        should_skip = not tool_plan.use_tavily
        reason = tool_plan.skip_reason or ("stable intent, no Tavily needed" if should_skip else "tool plan allows Tavily")
        return (should_skip, reason)

