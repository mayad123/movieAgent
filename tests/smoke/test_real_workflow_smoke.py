"""
Smoke test: real LLM workflow runs on a minimal input.

Requires OPENAI_API_KEY. Skips if not set. Run with:
  OPENAI_API_KEY=sk-... pytest tests/smoke/test_real_workflow_smoke.py -v
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


def _has_openai_key():
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


@pytest.mark.skipif(not _has_openai_key(), reason="OPENAI_API_KEY not set; real LLM smoke skipped")
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
