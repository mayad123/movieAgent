"""TMDB integration: image config, title resolver, scenes/backdrops."""
from .image_config import (
    TMDBImageConfig, fetch_config, get_config, clear_config_cache,
    build_image_url, SIZE_POSTER_GALLERY, SIZE_BACKDROP_GALLERY,
)
from .resolver import (
    TMDBCandidate, TMDBResolveResult, resolve_movie,
)
from .scenes import get_scenes_provider
