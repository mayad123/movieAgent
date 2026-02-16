"""
Playground pipeline: Wikipedia-only, deterministic execution.

Uses FakeLLM (no OpenAI) and use_live_data=False (no Tavily).
Same execution path as offline e2e tests; media_strip comes from
shared media_enrichment (Wikipedia).
"""
import logging
from typing import Any, Dict, Optional

from .agent import CineMind
from .llm_client import FakeLLMClient

logger = logging.getLogger(__name__)


async def run_playground_query(
    user_query: str,
    request_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a query through the playground pipeline (Wikipedia-only).

    Args:
        user_query: User question or prompt.
        request_type: Optional request type (info/recs/etc.); inferred if not set.

    Returns:
        Full structured result from CineMind (response, sources, media_strip, etc.).
    """
    fake_llm_client = FakeLLMClient()
    agent = CineMind(
        openai_api_key="playground",
        enable_observability=False,
        llm_client=fake_llm_client,
    )
    try:
        result = await agent.search_and_analyze(
            user_query=user_query,
            use_live_data=False,
            request_type=request_type,
        )
        return result
    finally:
        await agent.close()
