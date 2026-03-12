"""
Deterministic rules-first router for request_type inference.

This router maps raw user prompts to request_type (info, recs, comparison, release-date, etc.)
with confidence scores, working fully offline without any LLM calls.

Used to automatically infer request_type when not provided externally, enabling
seamless routing without requiring user selection.
"""
import re
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RequestTypeResult:
    """Result of request_type routing with confidence score."""
    request_type: str
    confidence: float  # 0.0 to 1.0
    rule_hit: Optional[str] = None  # Which rule matched (for debugging)


class RequestTypeRouter:
    """
    Deterministic rules-first router for request_type inference.
    
    Maps user prompts to request_type with confidence scores. Fully offline,
    no LLM calls required. Defaults to "info" if confidence is low.
    """
    
    # High-confidence patterns (specific, unambiguous)
    HIGH_CONFIDENCE_PATTERNS = {
        "comparison": [
            r"\b(compare|comparison)\b.*\b(and|with)\b",  # "compare X and Y"
            r"\bvs\.|\bversus\b|\bvs\s+",  # "X vs Y" or "X versus Y"
            r"\b(difference|differences)\s+(between|among)\b",  # "difference between X and Y"
        ],
        "recs": [
            r"\b(recommend|suggest)\s+(me\s+)?(a|some|any)\s+(movie|film)",  # "recommend me a movie"
            r"\b(movies|films)\s+(like|similar to)\b",  # "movies like X"
            r"\b(similar to|like)\s+.*\b(recommend|suggest)\b",  # "similar to X, recommend"
            r"\b(should i watch|what should i watch|what to watch)\b",  # "what should I watch"
            r"\b(recommendations?|suggestions?)\s+(for|based on)",  # "recommendations for X"
        ],
        "release-date": [
            r"\b(when\s+)?(is|was)\s+.*\s+(out|released|coming out)\b",  # "when is X out"
            r"\b(out yet|is it out|coming out|release date)\b",  # "is X out yet"
            r"\b(when\s+)?(does|did)\s+.*\s+(come out|release|premiere)\b",  # "when does X come out"
            r"\b(premiere|premieres|debut)\s+(date|dates)\b",  # "premiere date"
        ],
        "info": [
            r"\bwho\s+(directed|starred|stars|wrote|produced|played|acted in)\b",  # "who directed X"
            r"\bwhat\s+(is|was|are|were)\s+.*\s+(director|cast|runtime|rating|genre)\b",  # "what is X's director"
            r"\b(cast|actors?|director|runtime|rating|genre)\s+(of|in)\b",  # "cast of X"
            r"\b(how long|how many|how much)\s+(is|was|are|were)\b",  # "how long is X"
        ],
    }
    
    # Medium-confidence patterns (less specific, may overlap)
    MEDIUM_CONFIDENCE_PATTERNS = {
        "recs": [
            r"\b(similar to|like|alike)\b",  # "similar to X" (without explicit recommend)
            r"\b(best|top|great|good)\s+(movie|film|movies|films)\b",  # "best movies"
            r"\b(worth watching|watch next|what to watch|what movie)\b",  # "worth watching"
        ],
        "comparison": [
            r"\b(better|worse|best|worst)\s+(movie|film)\b",  # "better movie"
            r"\b(which\s+)?(is|are)\s+(better|worse|best|worst)\b",  # "which is better"
            r"\b(similar|similarities|alike|same|different)\b",  # "similar X and Y"
        ],
        "release-date": [
            r"\b(released|release)\s+(date|dates|when)\b",  # "release date"
            r"\b(when\s+)?(was|were)\s+.*\s+(released|released in)\b",  # "when was X released"
        ],
        "info": [
            r"\b(what|who|when|where|how)\s+(is|was|are|were|did|does)\b",  # General questions
            r"\b(tell me|tell me about|information about|info about)\b",  # "tell me about X"
        ],
    }
    
    # Low-confidence patterns (ambiguous, should default to info)
    LOW_CONFIDENCE_PATTERNS = {
        "recs": [
            r"\b(movie|film)\b",  # Just mentions "movie" (very generic)
        ],
    }
    
    # Guardrail patterns (override everything else, highest priority)
    GUARDRAILS = [
        # "similar" + "recommend" → recs (high confidence)
        (
            lambda q: bool(re.search(r"\b(similar|like)\b", q, re.IGNORECASE) and 
                          re.search(r"\b(recommend|suggest)\b", q, re.IGNORECASE)),
            "recs", 0.95, "guardrail: similar+recommend"
        ),
        # "explain ending" → spoiler
        (
            lambda q: bool(re.search(r"\b(explain\s+the\s+ending|explain\s+ending|ending\s+of)\b", q, re.IGNORECASE)),
            "spoiler", 0.95, "guardrail: explain ending"
        ),
        # "is it out yet" → release-date
        (
            lambda q: bool(re.search(r"\b(is\s+it\s+out\s+yet|out\s+yet|is\s+.*\s+out\s+yet)\b", q, re.IGNORECASE)),
            "release-date", 0.95, "guardrail: out yet"
        ),
        # "movies in order" → info (not recs)
        (
            lambda q: bool(re.search(r"\b(movies\s+in\s+order|order\s+of|chronological\s+order)\b", q, re.IGNORECASE)),
            "info", 0.95, "guardrail: movies in order"
        ),
    ]
    
    # Default confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    MEDIUM_CONFIDENCE_THRESHOLD = 0.5
    LOW_CONFIDENCE_THRESHOLD = 0.3
    
    def route(self, query: str) -> RequestTypeResult:
        """
        Route a user query to a request_type with confidence score.
        
        Args:
            query: User's query string
            
        Returns:
            RequestTypeResult with request_type, confidence, and rule_hit
            
        Rules:
        1. Check guardrails first (highest priority)
        2. Check high-confidence patterns
        3. Check medium-confidence patterns
        4. If confidence is low, default to "info"
        """
        query_lower = query.lower().strip()
        
        # Empty query defaults to info
        if not query_lower:
            return RequestTypeResult(
                request_type="info",
                confidence=0.5,
                rule_hit="default: empty query"
            )
        
        # Step 1: Check guardrails (highest priority, override everything)
        for guardrail_fn, req_type, confidence, rule_name in self.GUARDRAILS:
            if guardrail_fn(query):
                logger.debug(f"RequestTypeRouter: Guardrail hit - {rule_name} → {req_type} (confidence: {confidence})")
                return RequestTypeResult(
                    request_type=req_type,
                    confidence=confidence,
                    rule_hit=rule_name
                )
        
        # Step 2: Check high-confidence patterns (most specific first)
        for req_type, patterns in self.HIGH_CONFIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.debug(f"RequestTypeRouter: High-confidence match - {pattern[:40]} → {req_type}")
                    return RequestTypeResult(
                        request_type=req_type,
                        confidence=0.9,
                        rule_hit=f"high_confidence:{pattern[:30]}"
                    )
        
        # Step 3: Check medium-confidence patterns
        matches_by_type = {}
        for req_type, patterns in self.MEDIUM_CONFIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    if req_type not in matches_by_type:
                        matches_by_type[req_type] = []
                    matches_by_type[req_type].append(pattern)
        
        # If we have medium-confidence matches, pick the most specific one
        if matches_by_type:
            # Prioritize: comparison > recs > release-date > info
            priority_order = ["comparison", "recs", "release-date", "info"]
            for req_type in priority_order:
                if req_type in matches_by_type:
                    pattern = matches_by_type[req_type][0]
                    logger.debug(f"RequestTypeRouter: Medium-confidence match - {pattern[:40]} → {req_type}")
                    return RequestTypeResult(
                        request_type=req_type,
                        confidence=0.65,
                        rule_hit=f"medium_confidence:{pattern[:30]}"
                    )
        
        # Step 4: Check low-confidence patterns (but still assign lower confidence)
        for req_type, patterns in self.LOW_CONFIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.debug(f"RequestTypeRouter: Low-confidence match - {pattern[:40]} → {req_type} (defaulting to info)")
                    # Low confidence, but we matched something - still default to info
                    break
        
        # Step 5: Default to "info" with low confidence
        logger.debug(f"RequestTypeRouter: No pattern match, defaulting to info")
        return RequestTypeResult(
            request_type="info",
            confidence=0.4,  # Low confidence default
            rule_hit="default: no pattern match"
        )
    
    def should_use_inferred_type(self, result: RequestTypeResult) -> bool:
        """
        Determine if inferred request_type should be used.
        
        Args:
            result: RequestTypeResult from route()
            
        Returns:
            True if confidence is high enough to use, False to default to "info"
        """
        # Use inferred type if confidence >= medium threshold
        # If confidence is below threshold, we'll default to "info" anyway
        return result.confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD


# Global singleton instance
_router_instance: Optional[RequestTypeRouter] = None


def get_request_type_router() -> RequestTypeRouter:
    """Get singleton instance of RequestTypeRouter."""
    global _router_instance
    if _router_instance is None:
        _router_instance = RequestTypeRouter()
    return _router_instance

