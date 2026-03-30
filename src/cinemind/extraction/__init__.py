"""Text and entity extraction modules."""

from .candidate_extraction import Candidate, CandidateExtractor, normalize_title
from .fuzzy_intent_matcher import FuzzyIntentMatcher, FuzzyMatchResult, get_fuzzy_matcher
from .intent_extraction import IntentExtractor, StructuredIntent
from .response_movie_extractor import (
    ExtractedMovie,
    ParseSignals,
    ParseStructure,
    ResponseParseResult,
    extract_titles_for_enrichment,
    parse_response,
)
from .title_extraction import TitleExtractionResult, extract_movie_titles, get_search_phrases
