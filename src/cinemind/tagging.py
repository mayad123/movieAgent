"""
Request tagging and classification for CineMind.
"""
import re
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

# Valid request types
REQUEST_TYPES = {
    "info": "General information request",
    "recs": "Recommendation request",
    "comparison": "Comparison between movies/directors/etc",
    "spoiler": "Request with spoilers",
    "release-date": "Release date inquiry",
    "fact-check": "Fact verification request"
}

# Valid outcomes
OUTCOMES = {
    "success": "Request was successfully answered",
    "unclear": "Response was unclear or ambiguous",
    "hallucination": "Response contained hallucinations or incorrect information",
    "user-corrected": "User provided corrections to the response"
}


class RequestTagger:
    """Classifies requests by type and tracks outcomes."""
    
    def __init__(self):
        self.request_type_patterns = {
            "info": [
                r"\b(what|tell me|explain|describe|who|when|where|how|what is|what are)\b",
                r"\b(information|about|details|info)\b"
            ],
            "recs": [
                r"\b(recommend|suggest|best|top|favorite|good|great|awesome)\b",
                r"\b(should i watch|worth watching|watch next)\b"
            ],
            "comparison": [
                r"\b(compare|vs|versus|difference|better|which is|similar|different)\b",
                r"\b(vs\.|vs |versus)\b"
            ],
            "spoiler": [
                r"\b(spoiler|ending|plot|what happens|dies|kills|death)\b",
                r"\b(ending|finale|climax|twist)\b"
            ],
            "release-date": [
                r"\b(release|coming out|when does|premiere|trailer)\b",
                r"\b(release date|release dates|released|debut)\b",
                r"\b(2024|2025|coming soon)\b"
            ],
            "fact-check": [
                r"\b(true|false|accurate|correct|verify|fact|facts|confirm|check)\b",
                r"\b(is it true|is this true|did|really|actually)\b"
            ]
        }
    
    def classify_request_type(self, query: str) -> str:
        """
        Classify the request type based on query content.
        
        Returns the most likely request type or 'info' as default.
        """
        query_lower = query.lower()
        scores = {}
        
        for req_type, patterns in self.request_type_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, query_lower, re.IGNORECASE))
                score += matches
            scores[req_type] = score
        
        # Get the type with highest score
        if any(scores.values()):
            best_type = max(scores.items(), key=lambda x: x[1])
            if best_type[1] > 0:
                return best_type[0]
        
        # Default to 'info' if no clear match
        return "info"
    
    def validate_request_type(self, request_type: str) -> bool:
        """Validate that request type is in allowed list."""
        return request_type.lower() in REQUEST_TYPES
    
    def validate_outcome(self, outcome: str) -> bool:
        """Validate that outcome is in allowed list."""
        return outcome.lower() in OUTCOMES
    
    def get_request_type_description(self, request_type: str) -> str:
        """Get description for a request type."""
        return REQUEST_TYPES.get(request_type.lower(), "Unknown type")
    
    def get_outcome_description(self, outcome: str) -> str:
        """Get description for an outcome."""
        return OUTCOMES.get(outcome.lower(), "Unknown outcome")


async def classify_with_llm(query: str, client) -> str:
    """
    Use LLM to classify request type (more accurate than pattern matching).
    
    Args:
        query: User query
        client: OpenAI client
        
    Returns:
        Classified request type
    """
    try:
        from config import OPENAI_MODEL
        
        classification_prompt = f"""Classify this movie-related query into one of these categories:
- info: General information request
- recs: Recommendation request  
- comparison: Comparison between movies/directors/actors
- spoiler: Request asking for spoilers or plot details
- release-date: Release date or premiere inquiry
- fact-check: Fact verification request

Query: "{query}"

Respond with ONLY the category name (one word), nothing else."""
        
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a query classifier. Respond with only the category name."},
                {"role": "user", "content": classification_prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip().lower()
        
        # Validate result
        tagger = RequestTagger()
        if tagger.validate_request_type(result):
            return result
        
        return "info"  # Default fallback
        
    except Exception as e:
        logger.warning(f"LLM classification failed: {e}, using pattern matching")
        tagger = RequestTagger()
        return tagger.classify_request_type(query)

