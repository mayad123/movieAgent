"""
Configuration settings for CineMind movie agent.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


def _find_dotenv() -> Optional[str]:
    """Find .env in current directory or any parent (e.g. repo root)."""
    cwd = Path.cwd()
    for d in [cwd] + list(cwd.parents):
        p = d / ".env"
        if p.is_file():
            return str(p)
    return None


_env_path = _find_dotenv()
if _env_path:
    load_dotenv(_env_path)
else:
    load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
# --- TMDB (single source of truth for backend) ---
# TMDB enablement is backend config only (env vars). There is no UI toggle; the UI requestedAgentMode
# controls PLAYGROUND vs REAL_AGENT, not TMDB. Env: ENABLE_TMDB_SCENES (true/false/1/0), TMDB_READ_ACCESS_TOKEN.
# Token is trimmed; empty token disables TMDB. Never log or send token to client.

def _parse_bool_env(name: str, default: str = "false") -> bool:
    """Parse env as boolean deterministically: true, 1, yes -> True; false, 0, no, '' -> False."""
    raw = (os.getenv(name, default) or "").strip().lower()
    return raw in ("true", "1", "yes")


# Raw values (used only for startup log and is_tmdb_enabled)
_TMDB_TOKEN_RAW = (os.getenv("TMDB_READ_ACCESS_TOKEN", "") or "").strip()
_TMDB_ENABLED_FLAG = _parse_bool_env("ENABLE_TMDB_SCENES", "false")

# Single source of truth: enabled only when flag is true AND token is non-empty
def is_tmdb_enabled() -> bool:
    """True only when ENABLE_TMDB_SCENES is true and TMDB_READ_ACCESS_TOKEN is non-empty."""
    return bool(_TMDB_TOKEN_RAW and _TMDB_ENABLED_FLAG)


def get_tmdb_access_token() -> str:
    """Return the TMDB read access token (empty if not set). Do not log or expose to client."""
    return _TMDB_TOKEN_RAW


# Poster mode: "fallback_only" (default) = use TMDB poster when Wikipedia missing/low confidence
TMDB_POSTER_MODE = (os.getenv("TMDB_POSTER_MODE", "fallback_only") or "fallback_only").strip().lower()

# Legacy names for backward compatibility (enrichment/scenes import these)
ENABLE_TMDB_SCENES = is_tmdb_enabled()
TMDB_READ_ACCESS_TOKEN = _TMDB_TOKEN_RAW


def _log_tmdb_status() -> None:
    """Startup diagnostic: tmdb_enabled and token_present only (no secrets)."""
    import logging
    log = logging.getLogger(__name__)
    token_present = bool(_TMDB_TOKEN_RAW)
    tmdb_enabled = is_tmdb_enabled()
    log.info(
        "TMDB config: tmdb_enabled=%s, token_present=%s",
        tmdb_enabled,
        token_present,
    )
    if not tmdb_enabled and _TMDB_ENABLED_FLAG and not token_present:
        log.debug("TMDB disabled: set TMDB_READ_ACCESS_TOKEN in .env to enable")


# Run once at config load so any process that imports config sees the status
_log_tmdb_status()

# Agent Configuration
AGENT_NAME = "CineMind"
AGENT_VERSION = "1.0.0"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")  # Can be: gpt-4o, gpt-4, gpt-4-turbo, gpt-3.5-turbo

# Search Configuration
SEARCH_PROVIDERS = [
    "tavily",  # Primary real-time search
    "web"      # Fallback: Web search
]
# Note: Kaggle is handled by KaggleRetrievalAdapter (not listed here as it's not a search provider)

# Kaggle Dataset Configuration
# NOTE: These constants are ONLY used by KaggleRetrievalAdapter.
# No other part of the system should reference these directly.
KAGGLE_CORRELATION_THRESHOLD = float(os.getenv("KAGGLE_CORRELATION_THRESHOLD", "0.7"))  # 0.0-1.0
KAGGLE_DATASET_PATH = os.getenv("KAGGLE_DATASET_PATH", "")  # Optional: specific file path
ENABLE_KAGGLE_SEARCH = os.getenv("ENABLE_KAGGLE_SEARCH", "true").lower() == "true"

# Movie Data Sources
MOVIE_DATA_SOURCES = {
    "imdb": "https://www.imdb.com",
    "rotten_tomatoes": "https://www.rottentomatoes.com",
    "wikipedia": "https://en.wikipedia.org",
    "variety": "https://variety.com",
    "deadline": "https://deadline.com",
    "metacritic": "https://www.metacritic.com"
}

# Prompt Version Configuration
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")  # v1, v2, v3

# Real Agent safety limits (backend-enforced; prevent runaway cost / uncontrolled execution)
REAL_AGENT_TIMEOUT_SECONDS = float(os.getenv("CINEMIND_REAL_AGENT_TIMEOUT", "90"))
REAL_AGENT_MAX_TOKENS = int(os.getenv("CINEMIND_REAL_AGENT_MAX_TOKENS", "2000"))
REAL_AGENT_MAX_TOOL_CALLS = int(os.getenv("CINEMIND_REAL_AGENT_MAX_TOOL_CALLS", "10"))

# System Prompt (load from version)
def get_system_prompt(version: Optional[str] = None) -> str:
    """Get system prompt for specified version."""
    try:
        from ..prompting.versions import get_prompt_version
        version = version or PROMPT_VERSION
        return get_prompt_version(version)
    except ImportError:
        # Fallback if prompt_versions not available
        return """You are CineMind, an expert movie analysis and discovery agent.

Your sole domain is movies, including:
- Films (all countries and eras)
- Directors, writers, producers
- Actors and filmographies
- Genres, themes, cinematography, visual styles
- Box office, awards, reception
- Plot summaries (no spoilers unless user explicitly requests)
- Trivia, behind-the-scenes, production history
- Comparative analysis
- Recommendations

You may NOT answer questions outside film unless it directly supports film understanding.

DATA EXPECTATIONS:
- Always attempt to use current data when possible
- Perform live searches (Wikipedia, IMDb, Rotten Tomatoes, Variety, Deadline, YouTube interviews, etc.)
- Prefer recent updates (cast confirmations, release schedules, festival debuts, awards news)
- Clearly distinguish between confirmed information, industry rumors, and speculation
- If internal knowledge conflicts with current data, prioritize external real-time sources

When providing information:
1. Start with the most current/relevant data from real-time searches
2. Cite your sources
3. Distinguish facts from rumors
4. Provide comprehensive but organized responses
5. Offer additional context when relevant"""

# System Prompt (default version)
SYSTEM_PROMPT = get_system_prompt()
