"""Unit tests for workflow orchestration (real agent + playground)."""
import asyncio

# Ensure src on path
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_src = Path(__file__).resolve().parent.parent.parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


@pytest.mark.asyncio
async def test_run_real_agent_workflow_success():
    """run_real_agent_with_fallback returns (result, None) when runner succeeds."""
    from workflows import run_real_agent_with_fallback

    result = {"response": "ok", "sources": []}
    runner = AsyncMock()
    runner.search_and_analyze = AsyncMock(return_value=result)

    out, reason = await run_real_agent_with_fallback(
        "test query", None, True, 30.0, runner
    )
    assert out == result
    assert reason is None
    runner.search_and_analyze.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_real_agent_workflow_timeout():
    """run_real_agent_with_fallback returns (None, reason) on timeout."""
    from workflows import run_real_agent_with_fallback

    async def slow(*args, **kwargs):
        await asyncio.sleep(10)

    runner = AsyncMock()
    runner.search_and_analyze = AsyncMock(side_effect=slow)

    out, reason = await run_real_agent_with_fallback(
        "test", None, True, 0.01, runner
    )
    assert out is None
    assert reason is not None
    assert "timed out" in reason or "Playground" in reason


@pytest.mark.asyncio
async def test_run_playground_returns_dict():
    """run_playground returns a dict with response and agent_mode."""
    from workflows import run_playground

    result = await run_playground("What year was The Matrix released?")
    assert isinstance(result, dict)
    assert "response" in result
    assert "agent_mode" in result or "sources" in result
