"""
Backend-controlled agent execution mode.

Single source of truth for which pipeline runs:
- PLAYGROUND: Wikipedia-only, deterministic (no OpenAI/Tavily).
- REAL_AGENT: Full agent with tools (OpenAI + optional Tavily).

The backend is the final authority. If REAL_AGENT is requested but
required environment variables are missing, we fall back to PLAYGROUND
and log a warning.
"""
import os
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Required env var for REAL_AGENT (others like TAVILY_API_KEY are optional)
REAL_AGENT_REQUIRED_ENV = "OPENAI_API_KEY"


class AgentMode(str, Enum):
    """Execution mode: playground (Wikipedia-only) or full agent."""
    PLAYGROUND = "PLAYGROUND"
    REAL_AGENT = "REAL_AGENT"


def get_configured_mode() -> AgentMode:
    """
    Read agent mode from environment. Single source of truth.
    Default is PLAYGROUND for safety.
    """
    raw = (os.getenv("AGENT_MODE") or "").strip().upper()
    if raw == AgentMode.REAL_AGENT.value:
        return AgentMode.REAL_AGENT
    return AgentMode.PLAYGROUND


def _has_required_keys_for_real_agent() -> bool:
    """Return True if OPENAI_API_KEY is set and non-empty."""
    key = os.getenv(REAL_AGENT_REQUIRED_ENV)
    return bool(key and str(key).strip())


def resolve_effective_mode(configured: Optional[AgentMode] = None) -> AgentMode:
    """
    Resolve the mode that will actually be used (safety guard).
    If configured is REAL_AGENT but required API keys are missing,
    fall back to PLAYGROUND and log a warning.
    """
    mode = configured if configured is not None else get_configured_mode()
    if mode == AgentMode.REAL_AGENT and not _has_required_keys_for_real_agent():
        logger.warning(
            "AGENT_MODE=REAL_AGENT but %s is missing or empty; falling back to PLAYGROUND",
            REAL_AGENT_REQUIRED_ENV,
        )
        return AgentMode.PLAYGROUND
    return mode
