"""
Real agent workflow: run LLM pipeline with timeout and optional fallback.

Orchestration only: depends on IAgentRunner from services. The API passes
the concrete agent (CineMind); workflows do not import cinemind.agent.
"""
import asyncio
import logging
from typing import Any

from services.interfaces import IAgentRunner

logger = logging.getLogger(__name__)


async def run_real_agent_with_fallback(
    user_query: str,
    request_type: str | None,
    use_live_data: bool,
    timeout_seconds: float,
    agent_runner: IAgentRunner,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Run real agent with timeout. On timeout or exception, return (None, fallback_reason)
    so the caller can switch to playground. No silent crash.

    Returns:
        (result, None) on success; (None, fallback_reason) on timeout or error.
    """
    try:
        result = await asyncio.wait_for(
            agent_runner.search_and_analyze(
                user_query,
                use_live_data=use_live_data,
                request_type=request_type,
            ),
            timeout=timeout_seconds,
        )
        return result, None
    except TimeoutError:
        logger.error(
            "Real agent timed out after %.0fs (query: %s...). Falling back to PLAYGROUND.",
            timeout_seconds,
            (user_query or "")[:80],
        )
        return None, "Request timed out; switched to Playground mode."
    except Exception as e:
        logger.exception(
            "Real agent failed (query: %s...). Falling back to PLAYGROUND.",
            (user_query or "")[:80],
        )
        return None, str(e) or "Real agent error; switched to Playground mode."
