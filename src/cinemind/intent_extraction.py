"""
Structured intent extraction for CineMind.
Converts natural language queries into structured intent + entities + constraints.
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class StructuredIntent:
    """Structured representation of user intent."""
    intent: str  # e.g., "filmography_overlap", "director_info", "release_date"
    entities: List[str]  # Extracted entities (person names, movie titles, etc.)
    constraints: Dict[str, Any]  # Constraints like min_count, order_by, format
    original_query: str
    confidence: float = 1.0


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
        Extract structured intent from query.
        
        Args:
            query: User query
            request_type: Classified request type
        
        Returns:
            StructuredIntent
        """
        query_lower = query.lower()
        
        # Determine intent
        intent = self._detect_intent(query_lower, request_type)
        
        # Extract entities
        entities = self._extract_entities(query)
        
        # Extract constraints
        constraints = self._extract_constraints(query_lower)
        
        return StructuredIntent(
            intent=intent,
            entities=entities,
            constraints=constraints,
            original_query=query,
            confidence=0.9 if entities else 0.7
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
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities (people, movies, years) from query."""
        entities = []
        
        # Extract person names (common actor/director patterns)
        person_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
        persons = re.findall(person_pattern, query)
        entities.extend(persons)
        
        # Extract quoted titles
        quoted = re.findall(r'"([^"]+)"', query)
        entities.extend(quoted)
        
        # Extract years (for context, not as primary entities)
        years = re.findall(r"\b(19\d{2}|20\d{2})\b", query)
        # Store years in constraints instead
        
        # Remove duplicates and clean
        entities = list(set(entities))
        entities = [e.strip() for e in entities if len(e.strip()) > 2]
        
        return entities
    
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
  "entities": ["person name", "movie title", ...],
  "constraints": {{
    "min_count": number or null,
    "order_by": "release_year" or "chronological" or null,
    "format": "list" or "comparison" or null
  }}
}}

Rules:
- intent: The specific intent category
- entities: List of person names, movie titles mentioned (empty array if none)
- constraints: Object with min_count, order_by, format (null if not specified)

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
            
            return StructuredIntent(
                intent=result_json.get("intent", "general_info"),
                entities=result_json.get("entities", []),
                constraints=result_json.get("constraints", {}),
                original_query=query,
                confidence=0.95
            )
            
        except Exception as e:
            logger.warning(f"LLM intent extraction failed: {e}, using pattern-based")
            return self.extract(query, request_type)

