"""
Structured intent extraction for CineMind.
Converts natural language queries into structured intent + entities + constraints.
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class StructuredIntent:
    """Structured representation of user intent."""
    intent: str  # e.g., "filmography_overlap", "director_info", "release_date"
    entities: Dict[str, List[str]]  # Typed entities: {"movies": [...], "people": [...]}
    constraints: Dict[str, Any]  # Constraints like min_count, order_by, format
    original_query: str
    confidence: float = 1.0
    requires_disambiguation: bool = False  # True if title is ambiguous (e.g., "Crash", "Glory")
    candidate_year: Optional[int] = None  # Optional year for disambiguation
    need_freshness: bool = False  # Whether query needs up-to-date data
    freshness_reason: Optional[str] = None  # Reason for freshness requirement
    freshness_ttl_hours: Optional[float] = None  # Suggested TTL in hours
    
    def __post_init__(self):
        """Normalize entities to typed format."""
        # If entities is a list (old format), convert to typed dict
        if isinstance(self.entities, list):
            # Try to infer types (simple heuristic)
            movies = []
            people = []
            for entity in self.entities:
                # Simple heuristic: if it looks like a person name (2+ capitalized words), it's a person
                words = entity.split()
                if len(words) >= 2 and all(word[0].isupper() if word else False for word in words):
                    people.append(entity)
                else:
                    movies.append(entity)
            self.entities = {"movies": movies, "people": people}
        
        # Ensure entities dict has both keys
        if not isinstance(self.entities, dict):
            self.entities = {"movies": [], "people": []}
        if "movies" not in self.entities:
            self.entities["movies"] = []
        if "people" not in self.entities:
            self.entities["people"] = []
    
    def get_all_entities(self) -> List[str]:
        """Get all entities as a flat list (for backward compatibility)."""
        return self.entities.get("movies", []) + self.entities.get("people", [])


class IntentExtractor:
    """
    Extracts structured intent from natural language queries.
    """
    
    # Intent patterns
    INTENT_PATTERNS = {
        "filmography_overlap": [
            r"(movies|films).*(with|starring|featuring).*(both|and)",
            r"(both|and).*(in|starring|featuring)",
            r"collaboration",
            r"worked together",
        ],
        "director_info": [
            r"who directed",
            r"director of",
            r"directed by",
        ],
        "release_date": [
            r"when.*released",
            r"release date",
            r"when.*come out",
            r"premiere",
        ],
        "cast_info": [
            r"who.*starred",
            r"who.*in.*cast",
            r"cast of",
            r"actors in",
        ],
        "comparison": [
            r"compare",
            r"difference",
            r"vs\.|versus",
            r"better",
        ],
        "recommendation": [
            r"recommend",
            r"suggest",
            r"similar to",
            r"like.*but",
        ],
    }
    
    # Entity extraction patterns
    ENTITY_PATTERNS = {
        "person": [
            r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",  # "Robert De Niro"
            r"\b([A-Z]\. [A-Z][a-z]+)\b",  # "A. Pacino"
        ],
        "movie": [
            r'"([^"]+)"',  # Quoted titles
            r"the ([A-Z][a-z]+(?: [A-Z][a-z]+)*)",  # "The Matrix"
        ],
        "year": [
            r"\b(19\d{2}|20\d{2})\b",  # Years
        ],
    }
    
    # Constraint patterns
    CONSTRAINT_PATTERNS = {
        "min_count": [
            r"(three|3|three|four|4|five|5|ten|10)",
            r"at least (\d+)",
            r"(\d+) or more",
        ],
        "order_by": [
            r"ordered by (release year|year|date|chronological)",
            r"in (chronological|release) order",
            r"by (release year|year)",
        ],
        "format": [
            r"list",
            r"name",
            r"provide",
        ],
    }
    
    def extract(self, query: str, request_type: str = "info") -> StructuredIntent:
        """
        Extract structured intent from query (pattern-based, no LLM).
        
        Args:
            query: User query
            request_type: Classified request type
        
        Returns:
            StructuredIntent
        """
        query_lower = query.lower()
        
        # Determine intent
        intent = self._detect_intent(query_lower, request_type)
        
        # Extract typed entities
        typed_entities = self._extract_typed_entities(query)
        
        # Extract constraints
        constraints = self._extract_constraints(query_lower)
        
        # Check for ambiguity
        requires_disambiguation, candidate_year = self._check_ambiguity(query, typed_entities)
        
        # Determine freshness needs (with reason)
        need_freshness, freshness_reason = self._determine_freshness_needs(intent, request_type, query)
        freshness_ttl_hours = self._suggest_ttl(intent, request_type)
        
        return StructuredIntent(
            intent=intent,
            entities=typed_entities,
            constraints=constraints,
            original_query=query,
            confidence=0.9 if typed_entities.get("movies") or typed_entities.get("people") else 0.7,
            requires_disambiguation=requires_disambiguation,
            candidate_year=candidate_year,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            freshness_ttl_hours=freshness_ttl_hours
        )
    
    def _detect_intent(self, query_lower: str, request_type: str) -> str:
        """Detect intent from query."""
        # Map request types to intents
        type_to_intent = {
            "info": "general_info",
            "recs": "recommendation",
            "comparison": "comparison",
            "release-date": "release_date",
            "spoiler": "spoiler_info",
            "fact-check": "fact_check",
        }
        
        # Check for specific intent patterns
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent
        
        # Fallback to request type mapping
        return type_to_intent.get(request_type, "general_info")
    
    def _extract_typed_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract typed entities (movies vs people) from query."""
        movies = []
        people = []
        
        # Extract quoted titles (definitely movies)
        quoted = re.findall(r'"([^"]+)"', query)
        movies.extend(quoted)
        
        # Extract person names (common actor/director patterns)
        # Pattern: 2+ capitalized words (e.g., "Robert De Niro", "Denis Villeneuve")
        person_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
        persons = re.findall(person_pattern, query)
        
        # Filter out common false positives
        common_words = {"the", "and", "or", "but", "for", "with", "from", "when", "who", "what", "where"}
        for person in persons:
            words = person.split()
            # Person names typically have 2-4 words, all capitalized
            if 2 <= len(words) <= 4 and not any(w.lower() in common_words for w in words):
                people.append(person)
        
        # Extract unquoted movie titles (heuristic: capitalized words that aren't people)
        # This is a simplified approach - LLM extraction will be more accurate
        title_patterns = [
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",  # Capitalized phrases
        ]
        for pattern in title_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                # Skip if it's already a person or quoted title
                if match not in people and match not in movies and len(match) > 2:
                    # Simple heuristic: if it's a single word or starts with "The", likely a movie
                    if len(match.split()) == 1 or match.startswith("The "):
                        movies.append(match)
        
        # Remove duplicates
        movies = list(set(movies))
        people = list(set(people))
        
        return {"movies": movies, "people": people}
    
    def _check_ambiguity(self, query: str, typed_entities: Dict[str, List[str]]) -> Tuple[bool, Optional[int]]:
        """
        Check if query requires disambiguation (e.g., "Crash", "Glory", "It").
        
        Returns:
            (requires_disambiguation: bool, candidate_year: Optional[int])
        """
        # Common ambiguous movie titles (single word, common English words)
        ambiguous_titles = {
            "crash", "glory", "it", "heat", "rush", "prisoners", "alien", 
            "gravity", "focus", "drive", "rush", "crash", "glory"
        }
        
        movies = typed_entities.get("movies", [])
        for movie in movies:
            movie_lower = movie.lower()
            # Check if it's a single word and in ambiguous list
            if len(movie.split()) == 1 and movie_lower in ambiguous_titles:
                # Try to extract year from query
                year_pattern = r"\b(19\d{2}|20\d{2})\b"
                years = re.findall(year_pattern, query)
                candidate_year = int(years[0]) if years else None
                return (True, candidate_year)
        
        return (False, None)
    
    def _check_freshness_trigger_words(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Check for trigger words that force freshness even for older movies.
        
        Returns:
            (needs_freshness: bool, reason: Optional[str])
        """
        query_lower = query.lower()
        
        # Trigger words that force freshness
        freshness_triggers = {
            "currently": "availability/status changes",
            "now": "current availability",
            "today": "current information",
            "this week": "recent updates",
            "latest": "recent information",
            "recent update": "recent changes",
            "streaming": "availability changes constantly",
            "where can i watch": "availability changes",
            "where to watch": "availability changes",
            "announced": "recent announcements",
            "confirmed": "recent confirmations",
            "rumor": "recent rumors",
            "re-release": "re-release information",
            "remaster": "remaster information",
            "director's cut coming out": "upcoming release",
            "new trailer": "recent content",
            "as of today": "current status",
            "as of this week": "recent status"
        }
        
        for trigger, reason in freshness_triggers.items():
            if trigger in query_lower:
                return (True, reason)
        
        return (False, None)
    
    def _determine_freshness_needs(self, intent: str, request_type: str, query: str = "") -> Tuple[bool, Optional[str]]:
        """
        Determine if query needs fresh data based on intent and trigger words.
        
        Returns:
            (need_freshness: bool, reason: Optional[str])
        """
        # Step 1: Check for trigger words first (overrides intent-based decision)
        trigger_freshness, trigger_reason = self._check_freshness_trigger_words(query)
        if trigger_freshness:
            return (True, trigger_reason)
        
        # Step 2: Intent-based freshness policy
        
        # Freshness usually NOT needed (stable metadata)
        stable_intents = {
            "director_info": "director is stable metadata",
            "cast_info": "cast for released films is stable",
            "filmography_overlap": "collaborations are stable",
            "general_info": "synopsis/themes/genre are stable",
            "comparison": "comparisons between older films are stable"
        }
        
        if intent in stable_intents:
            return (False, stable_intents[intent])
        
        # Release date for older films doesn't need freshness
        # (We'll check movie age later as a second gate)
        if intent == "release_date" or request_type == "release-date":
            # Check if query mentions "out yet" or "when does it release" (upcoming)
            if any(phrase in query.lower() for phrase in ["out yet", "when does it release", "when will", "coming out"]):
                return (True, "release status for upcoming films")
            # Otherwise, it's asking about past release date (stable)
            return (False, "release date for released films is stable")
        
        # Freshness usually needed (time-volatile)
        volatile_intents = {
            "release_status": "release status changes",
            "casting_news": "casting news is time-sensitive",
            "awards_current_year": "awards change annually",
            "where_to_watch": "availability changes constantly"
        }
        
        if intent in volatile_intents:
            return (True, volatile_intents[intent])
        
        # Default: no freshness needed
        return (False, "default: stable metadata")
    
    def _suggest_ttl(self, intent: str, request_type: str) -> Optional[float]:
        """Suggest TTL in hours based on intent."""
        ttl_by_intent = {
            "release_date": 6.0,  # 6 hours for release dates
            "director_info": 720.0,  # 30 days for director info
            "cast_info": 720.0,  # 30 days for cast info
            "filmography_overlap": 720.0,  # 30 days for collaborations
            "general_info": 168.0,  # 7 days for general info
        }
        
        return ttl_by_intent.get(intent, 168.0)
    
    def _extract_constraints(self, query_lower: str) -> Dict[str, Any]:
        """Extract constraints from query."""
        constraints = {}
        
        # Extract count constraints
        count_match = re.search(r"(three|3|four|4|five|5|ten|10|at least (\d+))", query_lower)
        if count_match:
            count_str = count_match.group(1)
            count_map = {
                "three": 3, "3": 3,
                "four": 4, "4": 4,
                "five": 5, "5": 5,
                "ten": 10, "10": 10,
            }
            constraints["min_count"] = count_map.get(count_str.lower(), 3)
        
        # Extract ordering constraints
        if re.search(r"ordered by|in.*order|by (release year|year|chronological)", query_lower):
            if "release year" in query_lower or "year" in query_lower:
                constraints["order_by"] = "release_year"
            elif "chronological" in query_lower:
                constraints["order_by"] = "chronological"
        
        # Extract format constraints
        if "list" in query_lower or "name" in query_lower:
            constraints["format"] = "list"
        elif "compare" in query_lower:
            constraints["format"] = "comparison"
        
        return constraints
    
    async def extract_with_llm(self, query: str, client, request_type: str = "info") -> StructuredIntent:
        """
        Extract structured intent using LLM for better accuracy.
        
        Args:
            query: User query
            client: OpenAI client
            request_type: Classified request type
        
        Returns:
            StructuredIntent
        """
        try:
            from .config import OPENAI_MODEL
            
            extraction_prompt = f"""Extract structured intent from this movie query.

Query: "{query}"

Respond with ONLY valid JSON in this exact format:
{{
  "intent": "one of: filmography_overlap, director_info, release_date, cast_info, comparison, recommendation, general_info",
  "entities": {{
    "movies": ["movie title 1", "movie title 2"],
    "people": ["person name 1", "person name 2"]
  }},
  "constraints": {{
    "min_count": number or null,
    "order_by": "release_year_asc" or "release_year_desc" or "chronological" or null,
    "format": "list" or "comparison" or null
  }},
  "requires_disambiguation": true or false,
  "candidate_year": number or null,
  "need_freshness": true or false,
  "freshness_ttl_hours": number or null
}}

Rules:
- intent: The specific intent category
- entities: Object with "movies" and "people" arrays (separate movie titles from person names)
- constraints: Object with min_count, order_by (use release_year_asc/desc, not just release_year), format
- requires_disambiguation: true if movie title is ambiguous (e.g., "Crash", "Glory", "It")
- candidate_year: Year mentioned in query if disambiguation needed (null otherwise)
- need_freshness: true if query needs up-to-date data (release dates, upcoming movies)
- freshness_ttl_hours: Suggested TTL in hours (6 for release dates, 720 for director/cast info, etc.)

Respond with ONLY the JSON, nothing else."""

            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an intent extractor. Respond with ONLY valid JSON, no other text."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON
            try:
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()
                
                result_json = json.loads(result_text)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[^}]+\}', result_text)
                if json_match:
                    result_json = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found")
            
            # Parse entities (handle both old list format and new typed format)
            entities_data = result_json.get("entities", {})
            if isinstance(entities_data, list):
                # Old format - convert to typed
                typed_entities = self._extract_typed_entities(query)
            else:
                # New format - ensure both keys exist
                typed_entities = {
                    "movies": entities_data.get("movies", []),
                    "people": entities_data.get("people", [])
                }
            
            # Parse constraints
            constraints = result_json.get("constraints", {})
            
            # Parse ambiguity and freshness
            requires_disambiguation = result_json.get("requires_disambiguation", False)
            candidate_year = result_json.get("candidate_year")
            if candidate_year is not None:
                candidate_year = int(candidate_year)
            
            need_freshness = result_json.get("need_freshness", False)
            freshness_reason = result_json.get("freshness_reason")
            freshness_ttl_hours = result_json.get("freshness_ttl_hours")
            if freshness_ttl_hours is not None:
                freshness_ttl_hours = float(freshness_ttl_hours)
            
            # If LLM didn't provide freshness_reason, determine it
            if not freshness_reason:
                _, freshness_reason = self._determine_freshness_needs(
                    result_json.get("intent", "general_info"), 
                    request_type, 
                    query
                )
            
            return StructuredIntent(
                intent=result_json.get("intent", "general_info"),
                entities=typed_entities,
                constraints=constraints,
                original_query=query,
                confidence=0.95,
                requires_disambiguation=requires_disambiguation,
                candidate_year=candidate_year,
                need_freshness=need_freshness,
                freshness_reason=freshness_reason,
                freshness_ttl_hours=freshness_ttl_hours
            )
            
        except Exception as e:
            logger.warning(f"LLM intent extraction failed: {e}, using pattern-based")
            return self.extract(query, request_type)

