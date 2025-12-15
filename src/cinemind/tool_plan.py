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
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "use_tavily": self.use_tavily,
            "use_imdb_lookup": self.use_imdb_lookup,
            "use_wiki_lookup": self.use_wiki_lookup,
            "use_cache": self.use_cache,
            "use_structured_db": self.use_structured_db,
            "freshness_reason": self.freshness_reason,
            "skip_reason": self.skip_reason
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
            return ToolPlan(
                use_tavily=requires_disambiguation,  # Only if ambiguous title
                use_imdb_lookup=True,  # Prefer structured sources
                use_wiki_lookup=True,  # Prefer structured sources
                use_cache=True,  # Always check cache first
                use_structured_db=True,  # Try structured DB first
                freshness_reason=freshness_reason or "stable metadata",
                skip_reason="no freshness needed, using cache/structured sources" if not requires_disambiguation else "only if disambiguation needed"
            )
        else:
            # Volatile intent: Allow Tavily but prefer Tier A sources
            return ToolPlan(
                use_tavily=True,  # Allow web search for fresh data
                use_imdb_lookup=True,  # Still prefer Tier A sources
                use_wiki_lookup=True,  # Still prefer Tier A sources
                use_cache=True,  # Check cache first (may be stale)
                use_structured_db=False,  # Skip structured DB for volatile data
                freshness_reason=freshness_reason or "time-volatile intent",
                skip_reason=None
            )
    
    def should_skip_tavily(self, tool_plan: ToolPlan, cache_hit: bool = False, 
                           entity_resolved: bool = True) -> Tuple[bool, str]:
        """
        Final decision: Should we skip Tavily?
        
        Args:
            tool_plan: Tool plan from plan_tools()
            cache_hit: Whether we have a cache hit
            entity_resolved: Whether entity was successfully resolved
        
        Returns:
            (should_skip: bool, reason: str)
        """
        # If tool plan says don't use Tavily
        if not tool_plan.use_tavily:
            return (True, tool_plan.skip_reason or "stable intent, no Tavily needed")
        
        # If we have a cache hit and freshness not needed
        if cache_hit and not tool_plan.freshness_reason:
            return (True, "cache hit for stable intent")
        
        # If entity resolution failed, we need Tavily
        if not entity_resolved:
            return (False, "entity resolution failed, need Tavily")
        
        # Default: follow tool plan
        return (not tool_plan.use_tavily, tool_plan.skip_reason or "tool plan decision")

