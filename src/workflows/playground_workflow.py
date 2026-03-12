"""
Playground workflow: deterministic pipeline with TMDB media.

Thin orchestration layer; implementation lives in cinemind.playground.
Callers (API, tests) use this entry point so wiring stays thin.
"""
from typing import Any, Dict, Optional

# Implementation remains in cinemind; workflow layer delegates
from cinemind.agent.playground import run_playground_query


async def run_playground(
    user_query: str,
    request_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a query through the playground pipeline (TMDB media, no real LLM).

    Returns:
        Full structured result (response, sources, attachments, etc.).
    """
    return await run_playground_query(
        user_query=user_query,
        request_type=request_type,
    )
