"""CineMind agent package."""
from .agent.core import CineMind
from config import SYSTEM_PROMPT, AGENT_NAME, AGENT_VERSION, LLM_MODEL
from .media.media_enrichment import (
    MediaEnrichmentResult,
    enrich,
    enrich_batch,
    attach_media_to_result,
)
from .extraction.title_extraction import (
    extract_movie_titles,
    get_search_phrases,
    TitleExtractionResult,
)
from .media.media_cache import (
    MediaCache,
    get_default_media_cache,
)

__all__ = [
    'CineMind',
    'SYSTEM_PROMPT',
    'AGENT_NAME',
    'AGENT_VERSION',
    'LLM_MODEL',
    'MediaEnrichmentResult',
    'enrich',
    'enrich_batch',
    'attach_media_to_result',
    'extract_movie_titles',
    'get_search_phrases',
    'TitleExtractionResult',
    'MediaCache',
    'get_default_media_cache',
]
