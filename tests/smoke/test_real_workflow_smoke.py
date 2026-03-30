"""
Smoke test: real LLM workflow runs on a minimal input.

Requires a reachable OpenAI-compatible server and:
  CINEMIND_LLM_BASE_URL, CINEMIND_LLM_MODEL
Optional: CINEMIND_LLM_API_KEY

  CINEMIND_LLM_BASE_URL=http://127.0.0.1:8000/v1 CINEMIND_LLM_MODEL=... \\
    pytest tests/smoke/test_real_workflow_smoke.py -v
From repo root with PYTHONPATH=src.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

# Ensure src is on path when running from repo root
_repo_root = Path(__file__).resolve().parent.parent.parent
_src = _repo_root / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def _llm_configured():
    from config import is_llm_configured

    return is_llm_configured()


@pytest.mark.skipif(not _llm_configured(), reason="CINEMIND_LLM_BASE_URL + CINEMIND_LLM_MODEL not set; smoke skipped")
@pytest.mark.asyncio
async def test_real_workflow_minimal_query():
    """Real agent returns a non-empty response for a minimal query (smoke)."""
    from cinemind.agent import CineMind

    agent = CineMind(enable_observability=False)
    try:
        result = await asyncio.wait_for(
            agent.search_and_analyze(
                user_query="What year was The Matrix released?",
                use_live_data=True,
                request_type="info",
            ),
            timeout=90.0,
        )
    finally:
        await agent.close()

    assert result is not None
    assert isinstance(result, dict)
    assert "response" in result
    assert isinstance(result["response"], str)
    assert len(result["response"].strip()) > 0
