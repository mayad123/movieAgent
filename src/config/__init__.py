"""
Configuration and env parsing for CineMind.
"""

import os
from typing import Optional

from dotenv import load_dotenv

from config.env import find_dotenv_path

_env_path = find_dotenv_path()
if _env_path:
    load_dotenv(_env_path)
else:
    load_dotenv()


def _parse_bool_env(name: str, default: str = "false") -> bool:
    raw = (os.getenv(name, default) or "").strip().lower()
    return raw in ("true", "1", "yes")


# API Keys
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


def _normalize_llm_base_url(raw: str) -> str:
    u = (raw or "").strip().rstrip("/")
    if not u:
        return ""
    # Accept base host only or full .../v1 — chat path is always /v1/chat/completions
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


_CINEMIND_LLM_BASE_URL = _normalize_llm_base_url(os.getenv("CINEMIND_LLM_BASE_URL", ""))
CINEMIND_LLM_MODEL = (os.getenv("CINEMIND_LLM_MODEL") or "").strip()
CINEMIND_LLM_API_KEY = (os.getenv("CINEMIND_LLM_API_KEY") or "").strip()
CINEMIND_LLM_TIMEOUT_SECONDS = float(os.getenv("CINEMIND_LLM_TIMEOUT_SECONDS", "120"))
CINEMIND_LLM_EMBEDDING_MODEL = (os.getenv("CINEMIND_LLM_EMBEDDING_MODEL") or "").strip()
CINEMIND_LLM_SUPPORTS_JSON_MODE = _parse_bool_env("CINEMIND_LLM_SUPPORTS_JSON_MODE", "false")

# Primary model id for chat + intent/tagging (same HTTP server)
LLM_MODEL = CINEMIND_LLM_MODEL


def is_llm_configured() -> bool:
    """True when REAL_AGENT can reach an OpenAI-compatible LLM server."""
    return bool(_CINEMIND_LLM_BASE_URL and CINEMIND_LLM_MODEL)


# Resolved base URL for httpx (includes /v1)
def get_llm_base_url() -> str:
    return _CINEMIND_LLM_BASE_URL


# --- Watchmode (server-side only; never expose to client / web bundle) ---
_WATCHMODE_API_KEY_RAW = (os.getenv("WATCHMODE_API_KEY", "") or "").strip()


def get_watchmode_api_key() -> str:
    """Return the Watchmode API key for server-side use only. Never send to client."""
    return _WATCHMODE_API_KEY_RAW


def is_watchmode_configured() -> bool:
    """True if WATCHMODE_API_KEY is set and non-empty."""
    return bool(_WATCHMODE_API_KEY_RAW)


def _log_watchmode_status() -> None:
    import logging

    log = logging.getLogger(__name__)
    if not _WATCHMODE_API_KEY_RAW:
        log.info(
            "Watchmode: WATCHMODE_API_KEY not set. Where-to-watch routes will return 500. "
            "Get an API key from https://watchmode.com and set WATCHMODE_API_KEY in .env or your secrets manager."
        )
    else:
        log.info("Watchmode: API key configured (Where-to-watch available).")


# --- TMDB (single source of truth for backend) ---
_TMDB_TOKEN_RAW = (os.getenv("TMDB_READ_ACCESS_TOKEN", "") or "").strip()
_TMDB_ENABLED_FLAG = _parse_bool_env("ENABLE_TMDB_SCENES", "false")


def is_tmdb_enabled() -> bool:
    return bool(_TMDB_TOKEN_RAW and _TMDB_ENABLED_FLAG)


def get_tmdb_access_token() -> str:
    return _TMDB_TOKEN_RAW


TMDB_POSTER_MODE = (os.getenv("TMDB_POSTER_MODE", "fallback_only") or "fallback_only").strip().lower()
ENABLE_TMDB_SCENES = is_tmdb_enabled()
TMDB_READ_ACCESS_TOKEN = _TMDB_TOKEN_RAW


def _log_tmdb_status() -> None:
    import logging

    log = logging.getLogger(__name__)
    token_present = bool(_TMDB_TOKEN_RAW)
    tmdb_enabled = is_tmdb_enabled()
    log.info("TMDB config: tmdb_enabled=%s, token_present=%s", tmdb_enabled, token_present)
    if not tmdb_enabled and _TMDB_ENABLED_FLAG and not token_present:
        log.debug("TMDB disabled: set TMDB_READ_ACCESS_TOKEN in .env to enable")


_log_tmdb_status()
_log_watchmode_status()

# Agent Configuration
AGENT_NAME = "CineMind"
AGENT_VERSION = "1.0.0"

# Search Configuration
SEARCH_PROVIDERS = ["tavily", "web"]

# Kaggle Dataset Configuration
KAGGLE_CORRELATION_THRESHOLD = float(os.getenv("KAGGLE_CORRELATION_THRESHOLD", "0.7"))
KAGGLE_DATASET_PATH = os.getenv("KAGGLE_DATASET_PATH", "")
ENABLE_KAGGLE_SEARCH = os.getenv("ENABLE_KAGGLE_SEARCH", "true").lower() == "true"

# Movie Data Sources
MOVIE_DATA_SOURCES = {
    "imdb": "https://www.imdb.com",
    "rotten_tomatoes": "https://www.rottentomatoes.com",
    "wikipedia": "https://en.wikipedia.org",
    "variety": "https://variety.com",
    "deadline": "https://deadline.com",
    "metacritic": "https://www.metacritic.com",
}

# Prompt Version Configuration
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")

# Real Agent safety limits
REAL_AGENT_TIMEOUT_SECONDS = float(os.getenv("CINEMIND_REAL_AGENT_TIMEOUT", "90"))
REAL_AGENT_MAX_TOKENS = int(os.getenv("CINEMIND_REAL_AGENT_MAX_TOKENS", "2000"))
REAL_AGENT_MAX_TOOL_CALLS = int(os.getenv("CINEMIND_REAL_AGENT_MAX_TOOL_CALLS", "10"))


def get_system_prompt(version: str | None = None) -> str:
    """Get system prompt for specified version."""
    try:
        from cinemind.prompting.versions import get_prompt_version

        version = version or PROMPT_VERSION
        return get_prompt_version(version)
    except ImportError:
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


SYSTEM_PROMPT = get_system_prompt()
