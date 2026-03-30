"""
Backend-controlled agent execution mode.

Single source of truth for which pipeline runs:
- PLAYGROUND: Wikipedia-only, deterministic (no LLM/Tavily).
- REAL_AGENT: Full agent with tools (OpenAI-compatible LLM HTTP + optional Tavily).

The backend is the final authority. If REAL_AGENT is requested but
required environment variables are missing, we fall back to PLAYGROUND
and log a warning.
"""

import logging
import os
from enum import StrEnum

logger = logging.getLogger(__name__)


class AgentMode(StrEnum):
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
    """Return True if CINEMIND_LLM_BASE_URL and CINEMIND_LLM_MODEL are configured."""
    from config import is_llm_configured

    return is_llm_configured()


def resolve_effective_mode(configured: AgentMode | None = None) -> AgentMode:
    """
    Resolve the mode that will actually be used (safety guard).
    If configured is REAL_AGENT but required API keys are missing,
    fall back to PLAYGROUND and log a warning.
    """
    mode = configured if configured is not None else get_configured_mode()
    if mode == AgentMode.REAL_AGENT and not _has_required_keys_for_real_agent():
        logger.warning(
            "AGENT_MODE=REAL_AGENT but LLM is not configured "
            "(set CINEMIND_LLM_BASE_URL and CINEMIND_LLM_MODEL); falling back to PLAYGROUND",
        )
        return AgentMode.PLAYGROUND
    return mode
