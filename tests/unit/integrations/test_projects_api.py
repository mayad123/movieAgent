"""Tests for /api/projects endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_src = Path(__file__).resolve().parent.parent.parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECTS_STORE_PATH", str(tmp_path / "projects_api.json"))
    from fastapi.testclient import TestClient

    from api import main as api_main

    api_main._projects_store = None
    with TestClient(api_main.app) as test_client:
        yield test_client
    api_main._projects_store = None


def test_projects_create_list_get_and_assets_flow(client):
    create = client.post(
        "/api/projects",
        json={"name": "Neo-noir", "description": "city thrillers", "contextFocus": "genre"},
    )
    assert create.status_code == 200
    project = create.json()
    project_id = project["id"]

    listing = client.get("/api/projects")
    assert listing.status_code == 200
    data = listing.json()
    assert isinstance(data, list)
    assert data[0]["id"] == project_id

    add_assets = client.post(
        f"/api/projects/{project_id}/assets",
        json={
            "assets": [
                {"title": "Heat", "pageUrl": "https://example.com/heat", "conversationId": "conv_1"},
                {"title": "Heat", "pageUrl": "https://example.com/heat", "conversationId": "conv_1"},
            ]
        },
    )
    assert add_assets.status_code == 200
    assert add_assets.json()["added"] == 1
    assert add_assets.json()["skipped"] == 1

    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["assetCount"] == 1
    assert detail_body["assets"][0]["title"] == "Heat"


def test_projects_delete_asset_by_index(client):
    create = client.post("/api/projects", json={"name": "Favorites"})
    project_id = create.json()["id"]
    client.post(
        f"/api/projects/{project_id}/assets",
        json={"assets": [{"title": "Inception"}, {"title": "Interstellar"}]},
    )

    delete = client.delete(f"/api/projects/{project_id}/assets/0")
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True

    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["assetCount"] == 1
