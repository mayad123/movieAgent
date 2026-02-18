"""CineMind agent package."""
from .agent import CineMind
from config import SYSTEM_PROMPT, AGENT_NAME, AGENT_VERSION, OPENAI_MODEL
from .wikipedia_entity_resolver import (
    WikipediaEntityResolver,
    ResolverResult,
    ResolvedEntity,
)
from .wikipedia_media_provider import WikipediaMediaProvider
from .media_enrichment import (
    MediaEnrichmentResult,
    enrich,
    enrich_batch,
    attach_media_to_result,
)
from .title_extraction import (
    extract_movie_titles,
    get_search_phrases,
    TitleExtractionResult,
)
from .wikipedia_cache import (
    WikipediaCache,
    get_default_wikipedia_cache,
    WIKIPEDIA_CACHE_OPERATIONAL_LIMITS,
)

__all__ = [
    'CineMind',
    'SYSTEM_PROMPT',
    'AGENT_NAME',
    'AGENT_VERSION',
    'OPENAI_MODEL',
    'WikipediaEntityResolver',
    'ResolverResult',
    'ResolvedEntity',
    'WikipediaMediaProvider',
    'MediaEnrichmentResult',
    'enrich',
    'enrich_batch',
    'attach_media_to_result',
    'extract_movie_titles',
    'get_search_phrases',
    'TitleExtractionResult',
    'WikipediaCache',
    'get_default_wikipedia_cache',
    'WIKIPEDIA_CACHE_OPERATIONAL_LIMITS',
]

