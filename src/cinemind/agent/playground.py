"""
Playground pipeline: Wikipedia-only, deterministic execution.

Uses FakeLLM (no OpenAI) and use_live_data=False (no Tavily).
Same execution path as offline e2e tests; media_strip comes from
shared media_enrichment (Wikipedia).

Playground-only attachment behavior (single movie → poster + scenes; multi → posters only)
is applied here via apply_playground_attachment_behavior. The switch is: this code path
is only used when running the playground; real agent mode does not use it.
"""
import logging
from typing import Any, Dict, Optional

from .core import CineMind
from ..llm.client import FakeLLMClient
from ..media.playground_attachments import apply_playground_attachment_behavior

logger = logging.getLogger(__name__)

# Documented switch: when True, playground runs extraction/classification and applies
# single → [primary_movie, scenes], multi → [movie_list]. Set False to disable and use
# default agent attachment behavior (e.g. for testing).
PLAYGROUND_ATTACHMENT_RULE_ENABLED = True


async def run_playground_query(
    user_query: str,
    request_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a query through the playground pipeline (Wikipedia-only).

    Runs the movie extraction/classification pipeline on the response (and query when
    the user only typed a title). Applies playground attachment rule when
    PLAYGROUND_ATTACHMENT_RULE_ENABLED: single movie → poster + scenes; multi → posters only.

    Args:
        user_query: User question or prompt.
        request_type: Optional request type (info/recs/etc.); inferred if not set.

    Returns:
        Full structured result from CineMind (response, sources, attachments, attachment_debug, etc.).
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
            playground_mode=PLAYGROUND_ATTACHMENT_RULE_ENABLED,
        )
        if PLAYGROUND_ATTACHMENT_RULE_ENABLED:
            apply_playground_attachment_behavior(user_query, result)
        return result
    finally:
        await agent.close()
