"""TMDB integration: image config, title resolver, scenes/backdrops."""

from .image_config import (
    SIZE_BACKDROP_GALLERY,
    SIZE_POSTER_GALLERY,
    TMDBImageConfig,
    build_image_url,
    clear_config_cache,
    fetch_config,
    get_config,
)
from .resolver import (
    TMDBCandidate,
    TMDBResolveResult,
    resolve_movie,
)
from .scenes import get_scenes_provider
