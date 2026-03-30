"""Tests for cinemind.infrastructure.projects_store."""
from __future__ import annotations

from cinemind.infrastructure.projects_store import ProjectsStore


def test_create_and_list_projects(tmp_path):
    store = ProjectsStore(storage_path=str(tmp_path / "projects.json"))
    created = store.create_project(name="Sci-Fi Picks", description="space focus", context_focus="genre:sci-fi")
    projects = store.list_projects()
    assert created["id"]
    assert len(projects) == 1
    assert projects[0]["name"] == "Sci-Fi Picks"
    assert projects[0]["assetCount"] == 0


def test_add_assets_dedupes_and_preserves_sub_conversation(tmp_path):
    store = ProjectsStore(storage_path=str(tmp_path / "projects.json"))
    project = store.create_project(name="Nolan", description=None, context_focus="director")
    result = store.add_assets(
        project["id"],
        [
            {
                "title": "Inception",
                "pageUrl": "https://example.com/inception",
                "conversationId": "conv_1",
                "subConversationId": "sub_1",
            },
            {
                "title": "Inception",
                "pageUrl": "https://example.com/inception",
                "conversationId": "conv_1",
                "subConversationId": "sub_1",
            },
        ],
    )
    detail = store.get_project(project["id"])
    assert result == {"added": 1, "skipped": 1, "total": 2}
    assert detail is not None
    assert len(detail["assets"]) == 1
    assert detail["assets"][0]["subConversationId"] == "sub_1"


def test_delete_asset_by_id_and_index(tmp_path):
    store = ProjectsStore(storage_path=str(tmp_path / "projects.json"))
    project = store.create_project(name="Favorites", description=None, context_focus=None)
    store.add_assets(project["id"], [{"title": "Heat"}, {"title": "Collateral"}])
    detail = store.get_project(project["id"])
    assert detail is not None
    first_asset_id = detail["assets"][0]["id"]

    removed_by_id = store.delete_asset(project["id"], first_asset_id)
    removed_by_index = store.delete_asset(project["id"], "0")
    final_detail = store.get_project(project["id"])

    assert removed_by_id is True
    assert removed_by_index is True
    assert final_detail is not None
    assert len(final_detail["assets"]) == 0
