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
    candidate_year: Optional[int] = None  # Optional year for disambiguation ONLY (must be None if requires_disambiguation is False)
    mentioned_year: Optional[int] = None  # Any year mentioned in query (for awards, etc.), even when not ambiguous
    need_freshness: bool = False  # Whether query needs up-to-date data
    freshness_reason: Optional[str] = None  # Reason for freshness requirement
    freshness_ttl_hours: Optional[float] = None  # Suggested TTL in hours
    needs_clarification: bool = False  # True if query is too ambiguous/vague and needs user clarification
    slots: Optional[Dict[str, Optional[str]]] = None  # Award slots: {"award_body": str|null, "award_category": str|null, "award_year_basis": "ceremony_year"|"release_year"|"ambiguous"|null}
    
    def __post_init__(self):
        """Normalize entities to typed format and validate constraints."""
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
        
        # Enforce constraint: candidate_year can only be set when requires_disambiguation is True
        if not self.requires_disambiguation and self.candidate_year is not None:
            self.candidate_year = None
        
        # Ensure slots always exists with proper structure (backward compatibility)
        if self.slots is None:
            self.slots = {
                "award_body": None,
                "award_category": None,
                "award_year_basis": None
            }
        else:
            # Validate slots structure
            if not isinstance(self.slots, dict):
                self.slots = {"award_body": None, "award_category": None, "award_year_basis": None}
            else:
                # Ensure all keys exist
                if "award_body" not in self.slots:
                    self.slots["award_body"] = None
                if "award_category" not in self.slots:
                    self.slots["award_category"] = None
                if "award_year_basis" not in self.slots:
                    self.slots["award_year_basis"] = None
                
                # Validate award_year_basis enum
                valid_year_basis = {"ceremony_year", "release_year", "ambiguous", None}
                if self.slots["award_year_basis"] not in valid_year_basis:
                    self.slots["award_year_basis"] = None
    
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
        
        # Determine intent (with fuzzy matching support)
        intent, match_strength, match_type = self._detect_intent(query_lower, request_type)
        
        # Extract typed entities
        typed_entities = self._extract_typed_entities(query)
        
        # Extract constraints
        constraints = self._extract_constraints(query_lower)
        
        # Check for ambiguity
        requires_disambiguation, candidate_year = self._check_ambiguity(query, typed_entities)
        
        # Extract mentioned_year (any year in query, even when not ambiguous)
        mentioned_year = self._extract_mentioned_year(query)
        
        # Determine freshness needs (with reason)
        need_freshness, freshness_reason = self._determine_freshness_needs(intent, request_type, query)
        freshness_ttl_hours = self._suggest_ttl(intent, request_type)
        
        # Extract award slots
        slots = self._extract_award_slots(query)
        
        # If award_year_basis is "ambiguous", set requires_disambiguation=true
        if slots.get("award_year_basis") == "ambiguous":
            requires_disambiguation = True
            # candidate_year should remain None for award queries (use mentioned_year instead)
        
        # Calculate confidence based on match strength and entities
        base_confidence = match_strength  # Use match strength as base confidence
        entity_boost = 0.1 if (typed_entities.get("movies") or typed_entities.get("people")) else 0.0
        final_confidence = min(base_confidence + entity_boost, 1.0)
        
        return StructuredIntent(
            intent=intent,
            entities=typed_entities,
            constraints=constraints,
            original_query=query,
            confidence=final_confidence,  # Now includes match strength from fuzzy matching
            requires_disambiguation=requires_disambiguation,
            candidate_year=candidate_year,
            mentioned_year=mentioned_year,
            need_freshness=need_freshness,
            freshness_reason=freshness_reason,
            freshness_ttl_hours=freshness_ttl_hours,
            needs_clarification=False,
            slots=slots
        )
    
    def _assess_rule_based_confidence(self, intent: StructuredIntent, query: str) -> Tuple[float, bool]:
        """
        Assess confidence level of rule-based extraction and whether LLM extraction is needed.
        
        Returns:
            (confidence: float, should_use_llm: bool)
        """
        query_lower = query.lower()
        
        # High confidence indicators (simple, well-structured queries)
        high_confidence_patterns = [
            r"who directed",
            r"who (played|starred|acted)",
            r"when was .* released",
            r"release date",
            r"director of",
            r"cast of",
        ]
        
        # Check if query matches known simple templates
        matches_template = any(re.search(pattern, query_lower) for pattern in high_confidence_patterns)
        
        # Low confidence indicators (complex/vague queries)
        vague_patterns = [
            r"something like",
            r"similar to.*but",
            r"compare.*style",
            r"recommend.*based on",
            r"that movie with",
            r"the one where",
        ]
        
        is_vague = any(re.search(pattern, query_lower) for pattern in vague_patterns)
        
        # Check for multi-intent indicators
        multi_intent_keywords = ["then", "and then", "also", "plus", "after that"]
        has_multiple_intents = any(keyword in query_lower for keyword in multi_intent_keywords)
        
        # Calculate base confidence
        base_confidence = intent.confidence
        
        # Adjust based on indicators
        has_entities = bool(intent.entities.get("movies") or intent.entities.get("people"))
        if matches_template and has_entities:
            # High confidence: matches template and has entities
            confidence = min(0.95, base_confidence + 0.1)
            use_llm = False
        elif is_vague or has_multiple_intents:
            # Low confidence: vague or multi-intent
            confidence = max(0.3, base_confidence - 0.3)
            use_llm = True
        elif base_confidence >= 0.85:
            # Medium-high confidence
            confidence = base_confidence
            use_llm = False
        else:
            # Medium-low confidence
            confidence = base_confidence
            use_llm = True
        
        return confidence, use_llm
    
    def _validate_and_correct_intent(self, intent: StructuredIntent) -> Tuple[StructuredIntent, List[str]]:
        """
        Validate StructuredIntent and auto-correct obvious issues.
        
        Returns:
            (corrected_intent: StructuredIntent, warnings: List[str])
        """
        warnings = []
        
        # Enforce candidate_year rule
        if not intent.requires_disambiguation and intent.candidate_year is not None:
            warnings.append(f"Corrected: candidate_year set to None (requires_disambiguation is False)")
            intent.candidate_year = None
        
        # Validate order_by values
        order_by = intent.constraints.get("order_by")
        valid_order_by = {"release_year_asc", "release_year_desc", "chronological", None}
        if order_by not in valid_order_by:
            warnings.append(f"Corrected: invalid order_by value '{order_by}', set to None")
            intent.constraints["order_by"] = None
        
        # Validate entities structure
        if not isinstance(intent.entities, dict):
            warnings.append("Corrected: entities must be a dict")
            intent.entities = {"movies": [], "people": []}
        
        if "movies" not in intent.entities:
            intent.entities["movies"] = []
        if "people" not in intent.entities:
            intent.entities["people"] = []
        
        # Apply stoplist filter to ensure no interrogatives/helper verbs are in entities
        original_movie_count = len(intent.entities["movies"])
        original_people_count = len(intent.entities["people"])
        intent.entities["movies"] = self._filter_entities_by_stoplist(intent.entities["movies"])
        intent.entities["people"] = self._filter_entities_by_stoplist(intent.entities["people"])
        if len(intent.entities["movies"]) < original_movie_count or len(intent.entities["people"]) < original_people_count:
            warnings.append("Filtered entities using stoplist (removed interrogatives/helper verbs)")
        
        # Validate slots structure
        if intent.slots is None:
            intent.slots = {"award_body": None, "award_category": None, "award_year_basis": None}
        elif not isinstance(intent.slots, dict):
            warnings.append("Corrected: slots must be a dict")
            intent.slots = {"award_body": None, "award_category": None, "award_year_basis": None}
        else:
            # Ensure all keys exist
            if "award_body" not in intent.slots:
                intent.slots["award_body"] = None
            if "award_category" not in intent.slots:
                intent.slots["award_category"] = None
            if "award_year_basis" not in intent.slots:
                intent.slots["award_year_basis"] = None
            
            # Validate award_year_basis enum
            valid_year_basis = {"ceremony_year", "release_year", "ambiguous", None}
            if intent.slots["award_year_basis"] not in valid_year_basis:
                warnings.append(f"Corrected: invalid award_year_basis '{intent.slots['award_year_basis']}', set to None")
                intent.slots["award_year_basis"] = None
            
            # If award query detected and year present but basis missing, compute it with rules
            is_award_query = intent.slots.get("award_body") or intent.slots.get("award_category")
            has_year = intent.mentioned_year is not None
            if is_award_query and has_year and intent.slots["award_year_basis"] is None:
                # Re-compute award_year_basis using the same logic as extraction
                # Note: This method is called from IntentExtractor, so self._extract_award_slots is available
                # But since we're in a validation method that might be called from elsewhere, 
                # we'll compute it inline here
                query_lower = intent.original_query.lower()
                is_oscars_like = intent.slots.get("award_body") == "Academy Awards"
                
                # Check for explicit "films released in YEAR" / "movies released in YEAR" / "from releases in YEAR"
                if re.search(r"\b(films?|movies?)\s+released\s+in\s+(19\d{2}|20\d{2})\b", query_lower) or \
                   re.search(r"\bfrom\s+releases?\s+in\s+(19\d{2}|20\d{2})\b", query_lower):
                    intent.slots["award_year_basis"] = "release_year"
                # Check for "Best Picture of YEAR" (ambiguous phrasing)
                elif re.search(r"\b(best\s+\w+)\s+of\s+(19\d{2}|20\d{2})\b", query_lower) or \
                     re.search(r"\b(best\s+\w+)\s+for\s+(19\d{2}|20\d{2})\b", query_lower):
                    intent.slots["award_year_basis"] = "ambiguous"
                # Check for Oscars-like query with "in YEAR" → ceremony_year
                elif is_oscars_like and re.search(r"\bin\s+(19\d{2}|20\d{2})\b", query_lower):
                    intent.slots["award_year_basis"] = "ceremony_year"
                # Default: if Oscars-like and has year but phrasing unclear, default to ceremony_year
                elif is_oscars_like:
                    intent.slots["award_year_basis"] = "ceremony_year"
                # For other award bodies with "in YEAR", also default to ceremony_year
                elif intent.slots.get("award_body") and re.search(r"\bin\s+(19\d{2}|20\d{2})\b", query_lower):
                    intent.slots["award_year_basis"] = "ceremony_year"
                # Otherwise, if award query has year but unclear, mark as ambiguous
                else:
                    intent.slots["award_year_basis"] = "ambiguous"
                
                if intent.slots["award_year_basis"]:
                    warnings.append(f"Computed missing award_year_basis: {intent.slots['award_year_basis']}")
        
        # If award_year_basis is "ambiguous", ensure requires_disambiguation is set
        if intent.slots.get("award_year_basis") == "ambiguous":
            if not intent.requires_disambiguation:
                warnings.append("Setting requires_disambiguation=true for ambiguous award year basis")
                intent.requires_disambiguation = True
        
        # Validate intent is one of known types
        valid_intents = {
            "filmography_overlap", "director_info", "release_date", "cast_info",
            "comparison", "recommendation", "general_info", "fact_check", "spoiler_info"
        }
        if intent.intent not in valid_intents:
            warnings.append(f"Corrected: invalid intent '{intent.intent}', set to 'general_info'")
            intent.intent = "general_info"
        
        return intent, warnings
    
    async def extract_smart(
        self, 
        query: str, 
        client=None, 
        request_type: str = "info",
        force_llm: bool = False
    ) -> Tuple[StructuredIntent, str, float]:
        """
        Smart routing: try rule-based extraction first, use LLM only if needed.
        
        Routing policy:
        1. Run rule-based extractor first
        2. Assess confidence
        3. If high confidence → return result
        4. If medium/low confidence → try LLM extraction
        5. Validate/sanitize LLM output
        6. If still uncertain → mark needs_clarification
        
        Args:
            query: User query
            client: OpenAI client (required if LLM extraction is needed)
            request_type: Classified request type
            force_llm: If True, skip rule-based and go straight to LLM
        
        Returns:
            Tuple of (StructuredIntent, extraction_mode: str, confidence: float)
            extraction_mode: "rules" or "llm"
            confidence: Final confidence score (0-1)
        """
        # Step 1: Try rule-based extraction first (unless forced to LLM)
        if not force_llm:
            rule_intent = self.extract(query, request_type)
            confidence, should_use_llm = self._assess_rule_based_confidence(rule_intent, query)
            
            # Update confidence in intent
            rule_intent.confidence = confidence
            
            # If high confidence, return immediately
            if not should_use_llm and confidence >= 0.8:
                logger.info(f"Using rule-based extraction (confidence: {confidence:.2f})")
                rule_intent, warnings = self._validate_and_correct_intent(rule_intent)
                if warnings:
                    logger.debug(f"Rule-based validation warnings: {warnings}")
                return (rule_intent, "rules", rule_intent.confidence)
        
        # Step 2: Use LLM extraction (either low confidence or forced)
        if client is None:
            logger.warning("LLM extraction requested but no client provided, using rule-based")
            rule_intent = self.extract(query, request_type)
            rule_intent.confidence = 0.6  # Lower confidence since we wanted LLM
            rule_intent.needs_clarification = True
            return (rule_intent, "rules", 0.6)  # Falls back to rules, but low confidence
        
        try:
            logger.info("Using LLM extraction")
            llm_intent = await self.extract_with_llm(query, client, request_type)
            
            # Step 3: Validate and correct LLM output
            llm_intent, warnings = self._validate_and_correct_intent(llm_intent)
            if warnings:
                logger.info(f"LLM validation corrections: {warnings}")
            
            # Step 4: Assess final confidence
            # If LLM extraction has low confidence or validation found issues, mark for clarification
            if llm_intent.confidence < 0.6 or len(warnings) > 2:
                llm_intent.needs_clarification = True
                logger.info(f"Marking intent for clarification (confidence: {llm_intent.confidence:.2f}, warnings: {len(warnings)})")
            
            return (llm_intent, "llm", llm_intent.confidence)
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}, falling back to rule-based")
            # Fallback to rule-based
            rule_intent = self.extract(query, request_type)
            rule_intent.confidence = 0.6  # Lower confidence since LLM failed
            rule_intent.needs_clarification = True
            return (rule_intent, "rules", 0.6)  # Falls back to rules due to LLM failure
    
    def _detect_intent(self, query_lower: str, request_type: str) -> Tuple[str, float, str]:
        """
        Detect intent from query with fuzzy matching support.
        
        Args:
            query_lower: User query (lowercased)
            request_type: Classified request type
            
        Returns:
            Tuple of (intent: str, match_strength: float, match_type: str)
            match_type: "exact", "fuzzy_typo", "fuzzy_paraphrase", or "fallback"
        """
        from .fuzzy_intent_matcher import get_fuzzy_matcher
        
        # Map request types to intents
        type_to_intent = {
            "info": "general_info",
            "recs": "recommendation",
            "comparison": "comparison",
            "release-date": "release_date",
            "spoiler": "spoiler_info",
            "fact-check": "fact_check",
        }
        
        # Compile exact patterns for exact matching
        exact_patterns = {}
        for intent, pattern_strings in self.INTENT_PATTERNS.items():
            exact_patterns[intent] = [re.compile(pattern, re.IGNORECASE) for pattern in pattern_strings]
        
        # Step 1: Try exact matching first (highest priority)
        fuzzy_matcher = get_fuzzy_matcher()
        exact_match = fuzzy_matcher.match_exact(query_lower, exact_patterns)
        
        if exact_match:
            return (exact_match.intent, exact_match.match_strength, exact_match.match_type)
        
        # Step 2: Try fuzzy matching (typos and paraphrases)
        fuzzy_match = fuzzy_matcher.match_fuzzy(query_lower, exact_match_found=False)
        
        if fuzzy_match:
            return (fuzzy_match.intent, fuzzy_match.match_strength, fuzzy_match.match_type)
        
        # Step 3: Fallback to request type mapping
        fallback_intent = type_to_intent.get(request_type, "general_info")
        return (fallback_intent, 0.6, "fallback")
    
    def _get_entity_stoplist(self) -> set:
        """
        Get stoplist of words/phrases that should never be extracted as entities.
        
        Returns:
            Set of lowercase stoplist terms (case-insensitive matching)
        """
        return {
            # Interrogatives
            "who", "what", "when", "where", "why", "how",
            # Helper verbs / common verbs
            "is", "was", "were", "are", "do", "did", "does", "can", "could", "would", "should",
            "has", "have", "had", "will", "shall", "may", "might", "must",
            # Common verbs in movie queries (optional but recommended)
            "directed", "director", "played", "actor", "cast", "starring", "stars", "featured",
            "filmed", "filming", "released", "release", "came", "come",
            # Common function words
            "the", "and", "or", "but", "for", "with", "from", "to", "in", "on", "at", "by",
            "of", "a", "an", "as", "this", "that", "these", "those",
            # Other common false positives
            "best", "worst", "top", "movie", "movies", "film", "films", "about"
        }
    
    def _filter_entities_by_stoplist(self, entities: List[str]) -> List[str]:
        """
        Filter entities using stoplist to remove interrogatives, helper verbs, etc.
        
        Args:
            entities: List of entity strings to filter
            
        Returns:
            Filtered list of entities (stoplist terms removed)
        """
        stoplist = self._get_entity_stoplist()
        filtered = []
        
        for entity in entities:
            # Check if entire entity is a stoplist term (case-insensitive)
            if entity.lower() not in stoplist:
                # Also check if any word in the entity is a stoplist term
                words = entity.split()
                # If it's a multi-word entity, check individual words
                if len(words) > 1:
                    # Only filter if ALL words are stoplist terms
                    if not all(w.lower() in stoplist for w in words):
                        filtered.append(entity)
                else:
                    # Single word entity - already checked above
                    filtered.append(entity)
        
        return filtered
    
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
        
        # Apply stoplist filter to both movies and people
        movies = self._filter_entities_by_stoplist(movies)
        people = self._filter_entities_by_stoplist(people)
        
        # Remove duplicates
        movies = list(set(movies))
        people = list(set(people))
        
        return {"movies": movies, "people": people}
    
    def _extract_mentioned_year(self, query: str) -> Optional[int]:
        """
        Extract any year mentioned in the query (for awards, etc.).
        
        Returns:
            Optional[int]: First year found in query, or None
        """
        year_pattern = r"\b(19\d{2}|20\d{2})\b"
        years = re.findall(year_pattern, query)
        return int(years[0]) if years else None
    
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
                # Extract year from query for disambiguation
                candidate_year = self._extract_mentioned_year(query)
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
    
    def _extract_award_slots(self, query: str) -> Dict[str, Optional[str]]:
        """
        Extract award-related slots from query.
        
        Returns:
            Dict with award_body, award_category, award_year_basis (all nullable)
        """
        query_lower = query.lower()
        slots = {
            "award_body": None,
            "award_category": None,
            "award_year_basis": None
        }
        
        # Award body keywords mapping
        award_body_patterns = {
            "Academy Awards": [r"\boscar(s)?\b", r"\bacademy award(s)?\b"],
            "BAFTA": [r"\bbafta(s)?\b", r"\bbritish academy\b"],
            "Golden Globes": [r"\bgolden globe(s)?\b"],
            "Palme d'Or": [r"\bpalme d['\u2019]or\b", r"\bcannes.*palme\b"],
            "Cannes": [r"\bcannes\b"],
            "Venice": [r"\bvenice.*film festival\b", r"\bvenice\b"],
            "Berlin": [r"\bberlin.*film festival\b", r"\bberlin\b"],
            "SAG": [r"\bsag award(s)?\b", r"\bscreen actors guild\b"]
        }
        
        # Detect award body
        is_oscars_like = False
        for body_name, patterns in award_body_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    slots["award_body"] = body_name
                    # Check if it's Oscars-like (Academy Awards/Oscars)
                    if body_name == "Academy Awards":
                        is_oscars_like = True
                    break
            if slots["award_body"]:
                break
        
        # Award category patterns (common categories)
        category_patterns = {
            "Best Picture": [r"\bbest picture\b"],
            "Best Actor": [r"\bbest actor\b"],
            "Best Actress": [r"\bbest actress\b"],
            "Best Director": [r"\bbest director\b"],
            "Best Supporting Actor": [r"\bbest supporting actor\b"],
            "Best Supporting Actress": [r"\bbest supporting actress\b"],
            "Best Original Screenplay": [r"\bbest original screenplay\b"],
            "Best Adapted Screenplay": [r"\bbest adapted screenplay\b"],
            "Best Screenplay": [r"\bbest screenplay\b"],
            "Best Cinematography": [r"\bbest cinematography\b"],
            "Best Film": [r"\bbest film\b"],
            "Best Foreign Film": [r"\bbest foreign film\b"],
            "Best Animated Feature": [r"\bbest animated feature\b"],
            "Best Documentary": [r"\bbest documentary\b"]
        }
        
        # Detect award category
        for category_name, patterns in category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    slots["award_category"] = category_name
                    break
            if slots["award_category"]:
                break
        
        # If category detected but no body specified, infer Academy Awards for common Oscar categories
        if not slots["award_body"] and slots["award_category"]:
            # Common Oscar categories
            oscar_categories = {
                "Best Picture", "Best Actor", "Best Actress", "Best Director",
                "Best Supporting Actor", "Best Supporting Actress",
                "Best Original Screenplay", "Best Adapted Screenplay", "Best Screenplay",
                "Best Cinematography", "Best Film"
            }
            if slots["award_category"] in oscar_categories:
                slots["award_body"] = "Academy Awards"
                is_oscars_like = True
        
        # Classify award_year_basis if this is an award query
        is_award_query = slots["award_body"] or slots["award_category"]
        has_year = bool(re.search(r"\b(19\d{2}|20\d{2})\b", query_lower))
        
        if is_award_query and has_year:
            # Check for explicit "films released in YEAR" / "movies released in YEAR" / "from releases in YEAR"
            if re.search(r"\b(films?|movies?)\s+released\s+in\s+(19\d{2}|20\d{2})\b", query_lower) or \
               re.search(r"\bfrom\s+releases?\s+in\s+(19\d{2}|20\d{2})\b", query_lower):
                slots["award_year_basis"] = "release_year"
            # Check for "Best Picture of YEAR" (ambiguous phrasing)
            elif re.search(r"\b(best\s+\w+)\s+of\s+(19\d{2}|20\d{2})\b", query_lower) or \
                 re.search(r"\b(best\s+\w+)\s+for\s+(19\d{2}|20\d{2})\b", query_lower):
                slots["award_year_basis"] = "ambiguous"
            # Check for Oscars-like query with "in YEAR" → ceremony_year
            elif is_oscars_like and re.search(r"\bin\s+(19\d{2}|20\d{2})\b", query_lower):
                slots["award_year_basis"] = "ceremony_year"
            # Default: if Oscars-like and has year but phrasing unclear, default to ceremony_year
            elif is_oscars_like:
                slots["award_year_basis"] = "ceremony_year"
            # For other award bodies with "in YEAR", also default to ceremony_year
            elif slots["award_body"] and re.search(r"\bin\s+(19\d{2}|20\d{2})\b", query_lower):
                slots["award_year_basis"] = "ceremony_year"
            # Otherwise, if award query has year but unclear, mark as ambiguous
            else:
                slots["award_year_basis"] = "ambiguous"
        
        return slots
    
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
        
        # Extract ordering constraints - only when explicitly requested
        # Always include order_by key for predictable JSON (None when not requested)
        constraints["order_by"] = None
        
        # Check for explicit ordering requests with specific patterns
        # Order matters: check most specific patterns first
        
        # "newest first" or "newest" → release_year_desc
        if re.search(r"\b(newest first|newest|most recent first|recent first)\b", query_lower):
            constraints["order_by"] = "release_year_desc"
        # "oldest first" or "oldest" → release_year_asc
        elif re.search(r"\b(oldest first|oldest|earliest first)\b", query_lower):
            constraints["order_by"] = "release_year_asc"
        # "in chronological order" → chronological
        elif re.search(r"\bin\s+chronological\s+order\b", query_lower):
            constraints["order_by"] = "chronological"
        # "chronological order" (without "in") → chronological
        elif re.search(r"\bchronological\s+order\b", query_lower):
            constraints["order_by"] = "chronological"
        # "sorted by release year" or "ordered by release year" → release_year_asc (default when direction not specified)
        elif re.search(r"\b(sorted|ordered|arranged)\s+by\s+(release\s+)?year\b", query_lower):
            constraints["order_by"] = "release_year_asc"
        # "in release year order" → release_year_asc
        elif re.search(r"\bin\s+release\s+year\s+order\b", query_lower):
            constraints["order_by"] = "release_year_asc"
        # "in order" (by itself, likely means chronological) → chronological
        elif re.search(r"\bin\s+order\b", query_lower):
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
  "mentioned_year": number or null,
  "need_freshness": true or false,
  "freshness_ttl_hours": number or null,
  "slots": {{
    "award_body": string or null,
    "award_category": string or null,
    "award_year_basis": "ceremony_year" or "release_year" or "ambiguous" or null
  }}
}}

Rules:
- intent: The specific intent category. For award queries (e.g., "Best Picture", "Oscar winner"), use "general_info" or appropriate category.
- entities: Object with "movies" and "people" arrays. Extract all movie titles and person names mentioned in the query, including those in award contexts. For award queries, extract any movies or people mentioned (winners, nominees, etc.).
- constraints: Object with min_count, order_by, format
  - order_by: CRITICAL - ONLY set when query EXPLICITLY requests ordering (e.g., "in chronological order", "sorted by release year", "newest first", "oldest first"). Use null if no ordering is requested. Valid values: "release_year_asc", "release_year_desc", "chronological", or null. DO NOT set order_by just because the query mentions a year (e.g., "best picture by year" is NOT an ordering request, "Best Picture in 2000" is NOT an ordering request).
  - min_count: Only set if query explicitly requests a minimum count (e.g., "three movies", "at least 5")
  - format: Only set if query explicitly requests a format (e.g., "list", "compare")
- requires_disambiguation: true ONLY if movie title is ambiguous (e.g., "Crash", "Glory", "It" - single-word common English words that could refer to multiple movies). Award queries do NOT require disambiguation.
- candidate_year: STRICT RULE - ONLY set if requires_disambiguation is true AND a year is mentioned for disambiguation. MUST be null if requires_disambiguation is false. DO NOT use for award years (e.g., "Best Picture in 2000" - use mentioned_year instead, not candidate_year).
- mentioned_year: Any year mentioned in the query (award years, release years, etc.), even when not ambiguous. Set to null if no year is mentioned. Use this for award queries, not candidate_year.
- need_freshness: true if query needs up-to-date data (release dates, upcoming movies, recent awards)
- freshness_ttl_hours: Suggested TTL in hours (6 for release dates, 720 for director/cast info, 168 for general info, etc.)
- slots: Object with award-related fields (MUST always be present, use null for non-award queries):
  - award_body: Award body name if detected (e.g., "Academy Awards", "BAFTA", "Golden Globes", "Palme d'Or", "Cannes", "Venice", "Berlin", "SAG"). Set to null if not an award query or body not detected.
  - award_category: Award category if detected (e.g., "Best Picture", "Best Actor", "Best Actress", "Best Director", "Best Original Screenplay", "Best Adapted Screenplay"). Set to null if not an award query or category not detected. If query is award-like but category not found, set to null and proceed.
  - award_year_basis: How to interpret the year in award queries. CRITICAL RULES:
    * If Oscars-like (Oscar/Academy Awards) AND phrased as "in YEAR" (e.g., "Best Picture in 2000") → use "ceremony_year"
    * If explicitly says "films released in YEAR" / "movies released in YEAR" / "from releases in YEAR" → use "release_year"
    * If phrased as "Best Picture of YEAR" or "for YEAR" without clarity (e.g., "Best Picture of 2000") → use "ambiguous"
    * Set to null if not an award query or no year is mentioned
    * Valid values: "ceremony_year", "release_year", "ambiguous", or null

CRITICAL RULES:
1. If requires_disambiguation is false, candidate_year MUST be null (use mentioned_year for award years instead).
2. order_by MUST be null unless the query explicitly requests sorting/ordering.
3. Extract all movies and people mentioned in entities, including those in award contexts.

Respond with ONLY the JSON, nothing else."""

            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an intent extractor. Respond with ONLY valid JSON, no other text."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=300
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
                # Apply stoplist filter to LLM-extracted entities
                typed_entities["movies"] = self._filter_entities_by_stoplist(typed_entities["movies"])
                typed_entities["people"] = self._filter_entities_by_stoplist(typed_entities["people"])
            
            # Parse constraints
            constraints = result_json.get("constraints", {})
            
            # Parse ambiguity and freshness
            requires_disambiguation = result_json.get("requires_disambiguation", False)
            candidate_year = result_json.get("candidate_year")
            if candidate_year is not None:
                candidate_year = int(candidate_year)
            
            # ENFORCE RULE: candidate_year can only be set when requires_disambiguation is True
            if not requires_disambiguation:
                candidate_year = None
            
            # Parse mentioned_year (any year in query, even when not ambiguous)
            mentioned_year = result_json.get("mentioned_year")
            if mentioned_year is not None:
                mentioned_year = int(mentioned_year)
            else:
                # Fallback: extract mentioned_year from query if LLM didn't provide it
                mentioned_year = self._extract_mentioned_year(query)
            
            need_freshness = result_json.get("need_freshness", False)
            freshness_ttl_hours = result_json.get("freshness_ttl_hours")
            if freshness_ttl_hours is not None:
                freshness_ttl_hours = float(freshness_ttl_hours)
            
            # Parse slots (award-related fields)
            slots_data = result_json.get("slots")
            if slots_data and isinstance(slots_data, dict):
                slots = {
                    "award_body": slots_data.get("award_body"),
                    "award_category": slots_data.get("award_category"),
                    "award_year_basis": slots_data.get("award_year_basis")
                }
                # Validate award_year_basis enum
                valid_year_basis = {"ceremony_year", "release_year", "ambiguous", None}
                if slots["award_year_basis"] not in valid_year_basis:
                    slots["award_year_basis"] = None
            else:
                # If slots missing or invalid, use null defaults
                slots = {
                    "award_body": None,
                    "award_category": None,
                    "award_year_basis": None
                }
            
            # If award query detected and year present but basis missing, compute it with rules
            is_award_query = slots.get("award_body") or slots.get("award_category")
            if is_award_query and mentioned_year and slots["award_year_basis"] is None:
                # Re-compute award_year_basis
                temp_slots = self._extract_award_slots(query)
                if temp_slots["award_year_basis"]:
                    slots["award_year_basis"] = temp_slots["award_year_basis"]
            
            # If award_year_basis is "ambiguous", set requires_disambiguation=true
            if slots.get("award_year_basis") == "ambiguous":
                requires_disambiguation = True
            
            # Always derive freshness_reason (not included in LLM JSON format for consistency)
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
                mentioned_year=mentioned_year,
                need_freshness=need_freshness,
                freshness_reason=freshness_reason,
                freshness_ttl_hours=freshness_ttl_hours,
                needs_clarification=False,
                slots=slots
            )
            
        except Exception as e:
            logger.warning(f"LLM intent extraction failed: {e}, using pattern-based")
            return self.extract(query, request_type)

