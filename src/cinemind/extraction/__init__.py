"""Text and entity extraction modules."""
from .title_extraction import extract_movie_titles, get_search_phrases, TitleExtractionResult
from .candidate_extraction import Candidate, CandidateExtractor, normalize_title
from .intent_extraction import StructuredIntent, IntentExtractor
from .response_movie_extractor import (
    ExtractedMovie, ParseStructure, ParseSignals, ResponseParseResult,
    parse_response, extract_titles_for_enrichment,
)
from .fuzzy_intent_matcher import FuzzyMatchResult, FuzzyIntentMatcher, get_fuzzy_matcher
