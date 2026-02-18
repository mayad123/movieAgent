"""
Smoke test: playground server app boots and handles one basic request.

Uses FastAPI TestClient (no real server). Run with:
  pytest tests/smoke/test_playground_smoke.py -v
From repo root with PYTHONPATH=src (or install package).
"""
import sys
from pathlib import Path

import pytest

# Ensure src is on path when running from repo root
_repo_root = Path(__file__).resolve().parent.parent.parent
_src = _repo_root / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def test_playground_app_imports():
    """Playground server app can be imported (boot check)."""
    from tests.playground_server import app
    assert app is not None


def test_playground_health():
    """GET /health returns 200 and ok status."""
    from fastapi.testclient import TestClient
    from tests.playground_server import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "cinemind-offline-playground"


def test_playground_query_one_request():
    """POST /query with minimal body returns 200 and expected shape (smoke)."""
    from fastapi.testclient import TestClient
    from tests.playground_server import app

    client = TestClient(app)
    response = client.post(
        "/query",
        json={"user_query": "What year was The Matrix released?"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "response" in data
    assert "agent_mode" in data
    assert data.get("agent_mode") == "PLAYGROUND"
    assert isinstance(data.get("response"), str)
