"""
Fuzzy intent matching for typos and paraphrases.

Provides deterministic, offline-capable fuzzy matching for intent detection
that handles common misspellings and paraphrases while preserving exact-match
behavior.
"""
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FuzzyMatchResult:
    """Result of fuzzy intent matching."""
    intent: str
    match_strength: float  # 0.0 to 1.0, where 1.0 is exact match
    match_type: str  # "exact", "fuzzy_typo", "fuzzy_paraphrase"
    matched_pattern: Optional[str] = None


class FuzzyIntentMatcher:
    """
    Fuzzy matcher for intent detection that handles typos and paraphrases.
    
    Deterministic and offline-capable. Provides match strength scores
    and never overrides strong exact matches.
    """
    
    # Common misspelling patterns (typo → correct)
    TYPO_PATTERNS = {
        "director_info": [
            (r"directer", "directed"),  # "directer" → "directed"
            (r"direktor", "directed"),
            (r"directerd", "directed"),
            (r"directer", "director"),
        ],
        "release_date": [
            (r"realease", "release"),  # "realease" → "release"
            (r"relese", "release"),
            (r"relase", "release"),
            (r"realeased", "released"),
            (r"premiere", "premiere"),  # Already correct, but handle variations
            (r"premire", "premiere"),
        ],
        "recommendation": [
            (r"recomend", "recommend"),  # "recomend" → "recommend"
            (r"recomand", "recommend"),
            (r"recomended", "recommended"),
            (r"sugest", "suggest"),
            (r"suggesst", "suggest"),
        ],
        "comparison": [
            (r"comparr", "compare"),  # "comparr" → "compare"
            (r"compre", "compare"),
            (r"compar", "compare"),
            (r"diffrence", "difference"),
            (r"diference", "difference"),
        ],
        "cast_info": [
            (r"wathc", "watch"),  # "wathc" → "watch" (context-dependent)
            (r"stared", "starred"),
            (r"starred", "starred"),  # Already correct
            (r"actores", "actors"),
        ],
        "general_info": [
            (r"streamin", "streaming"),  # "streamin" → "streaming"
            (r"streamng", "streaming"),
            (r"watch", "watch"),  # Already correct
        ],
    }
    
    # Common paraphrase patterns (alternative phrasings)
    PARAPHRASE_PATTERNS = {
        "director_info": [
            r"who made",  # "who made X" → director_info
            r"who created",  # "who created X"
            r"made by",  # "X made by Y"
            r"created by",  # "X created by Y"
            r"helmed by",  # "helmed by"
            r"directed by",  # Already in exact patterns, but included here for completeness
        ],
        "cast_info": [
            r"who's in",  # "who's in X"
            r"who is in",  # "who is in X"
            r"starring",  # "starring"
            r"features",  # "features"
            r"appears in",  # "appears in"
            r"played by",  # "played by"
            r"actors?",  # "actors" or "actor"
            r"cast members?",  # "cast members"
        ],
        "release_date": [
            r"when did it come out",  # "when did it come out"
            r"when does it come out",  # "when does it come out"
            r"when was it released",  # "when was it released"
            r"what year",  # "what year was X"
            r"came out",  # "X came out"
            r"debuted",  # "debuted"
            r"premiered",  # "premiered"
        ],
        "general_info": [
            r"what's it about",  # "what's it about"
            r"what is it about",  # "what is it about"
            r"tell me about",  # "tell me about X"
            r"tell me more",  # "tell me more about X"
            r"information about",  # "information about X"
            r"info on",  # "info on X"
        ],
        "recommendation": [
            r"movies similar to",  # "movies similar to X"
            r"films like",  # "films like X"
            r"anything like",  # "anything like X"
            r"same as",  # "same as X"
            r"comparable to",  # "comparable to X"
            r"in the same vein",  # "in the same vein as X"
        ],
        "comparison": [
            r"difference between",  # "difference between X and Y"
            r"different from",  # "different from"
            r"similarities",  # "similarities between"
            r"compare and contrast",  # "compare and contrast"
        ],
    }
    
    # Match strength thresholds
    EXACT_MATCH_STRENGTH = 1.0
    FUZZY_TYPO_STRENGTH = 0.85  # High confidence for typos
    FUZZY_PARAPHRASE_STRENGTH = 0.80  # Good confidence for paraphrases
    
    def __init__(self) -> None:
        """Initialize the fuzzy matcher."""
        # Pre-compile regex patterns for performance
        self._compiled_typo_patterns = self._compile_typo_patterns()
        self._compiled_paraphrase_patterns = self._compile_paraphrase_patterns()
    
    def _compile_typo_patterns(self) -> Dict[str, List[Tuple[re.Pattern, str]]]:
        """Compile typo patterns into regex."""
        compiled = {}
        for intent, patterns in self.TYPO_PATTERNS.items():
            compiled[intent] = []
            for typo, correct in patterns:
                # Create pattern that matches typo in context (word boundaries)
                pattern = re.compile(rf"\b{re.escape(typo)}\b", re.IGNORECASE)
                compiled[intent].append((pattern, correct))
        return compiled
    
    def _compile_paraphrase_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile paraphrase patterns into regex."""
        compiled = {}
        for intent, patterns in self.PARAPHRASE_PATTERNS.items():
            compiled[intent] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        return compiled
    
    def match_fuzzy(self, query: str, exact_match_found: bool = False) -> Optional[FuzzyMatchResult]:
        """
        Attempt fuzzy matching for typos and paraphrases.
        
        Args:
            query: User query (lowercased)
            exact_match_found: Whether an exact match was already found (if True, fuzzy won't override)
        
        Returns:
            FuzzyMatchResult if fuzzy match found, None otherwise
            
        Note:
            If exact_match_found is True, this returns None to preserve exact-match behavior.
        """
        query_lower = query.lower()
        
        # Never override exact matches
        if exact_match_found:
            return None
        
        # Try typo matching first (higher confidence)
        for intent, patterns in self._compiled_typo_patterns.items():
            for pattern, correct_form in patterns:
                if pattern.search(query_lower):
                    # Found a typo match
                    return FuzzyMatchResult(
                        intent=intent,
                        match_strength=self.FUZZY_TYPO_STRENGTH,
                        match_type="fuzzy_typo",
                        matched_pattern=pattern.pattern
                    )
        
        # Try paraphrase matching (slightly lower confidence)
        for intent, patterns in self._compiled_paraphrase_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    # Found a paraphrase match
                    return FuzzyMatchResult(
                        intent=intent,
                        match_strength=self.FUZZY_PARAPHRASE_STRENGTH,
                        match_type="fuzzy_paraphrase",
                        matched_pattern=pattern.pattern
                    )
        
        return None
    
    def match_exact(self, query: str, exact_patterns: Dict[str, List[re.Pattern]]) -> Optional[FuzzyMatchResult]:
        """
        Check for exact pattern matches.
        
        Args:
            query: User query (lowercased)
            exact_patterns: Dict of intent -> list of compiled regex patterns
            
        Returns:
            FuzzyMatchResult if exact match found, None otherwise
        """
        query_lower = query.lower()
        
        for intent, patterns in exact_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    return FuzzyMatchResult(
                        intent=intent,
                        match_strength=self.EXACT_MATCH_STRENGTH,
                        match_type="exact",
                        matched_pattern=pattern.pattern
                    )
        
        return None


# Global singleton instance
_matcher_instance: Optional[FuzzyIntentMatcher] = None


def get_fuzzy_matcher() -> FuzzyIntentMatcher:
    """Get singleton instance of FuzzyIntentMatcher."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = FuzzyIntentMatcher()
    return _matcher_instance

