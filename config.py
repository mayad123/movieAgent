"""
Configuration settings for CineMind movie agent.
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Agent Configuration
AGENT_NAME = "CineMind"
AGENT_VERSION = "1.0.0"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")  # Can be: gpt-4o, gpt-4, gpt-4-turbo, gpt-3.5-turbo

# Search Configuration
SEARCH_PROVIDERS = [
    "tavily",  # Primary real-time search
    "web"      # Fallback web search
]

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

# System Prompt (load from version)
def get_system_prompt(version: Optional[str] = None) -> str:
    """Get system prompt for specified version."""
    try:
        from prompt_versions import get_prompt_version
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
