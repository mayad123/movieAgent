"""CineMind agent package."""
from config import AGENT_NAME, AGENT_VERSION, LLM_MODEL, SYSTEM_PROMPT

from .agent.core import CineMind
from .extraction.title_extraction import (
    TitleExtractionResult,
    extract_movie_titles,
    get_search_phrases,
)
from .media.media_cache import (
    MediaCache,
    get_default_media_cache,
)
from .media.media_enrichment import (
    MediaEnrichmentResult,
    attach_media_to_result,
    enrich,
    enrich_batch,
)

__all__ = [
    'AGENT_NAME',
    'AGENT_VERSION',
    'LLM_MODEL',
    'SYSTEM_PROMPT',
    'CineMind',
    'MediaCache',
    'MediaEnrichmentResult',
    'TitleExtractionResult',
    'attach_media_to_result',
    'enrich',
    'enrich_batch',
    'extract_movie_titles',
    'get_default_media_cache',
    'get_search_phrases',
]
