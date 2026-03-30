"""Persistent JSON-backed store for projects and project assets."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _asset_dedupe_key(asset: dict[str, Any]) -> str:
    page_id = _norm_text(asset.get("pageId"))
    if page_id:
        return "pageId:" + page_id.lower()
    page_url = _norm_text(asset.get("pageUrl"))
    if page_url:
        return "pageUrl:" + page_url.lower()
    title = _norm_text(asset.get("title")).lower()
    poster = _norm_text(asset.get("posterImageUrl")).lower()
    return "title:" + title + "|poster:" + poster


class ProjectsStore:
    """File-backed project storage used by API endpoints."""

    def __init__(self, storage_path: str | None = None) -> None:
        env_path = os.getenv("PROJECTS_STORE_PATH", "").strip()
        path_value = storage_path or env_path or "data/projects_store.json"
        self._path = Path(path_value)
        self._lock = threading.Lock()
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({"projects": []})

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"projects": []}
        with self._path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"projects": []}
        projects = data.get("projects")
        if not isinstance(projects, list):
            data["projects"] = []
        return data

    def _write(self, payload: dict[str, Any]) -> None:
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            out: list[dict[str, Any]] = []
            for project in data.get("projects", []):
                assets = project.get("assets", []) if isinstance(project.get("assets"), list) else []
                out.append(
                    {
                        "id": project.get("id"),
                        "name": project.get("name", "Untitled Project"),
                        "description": project.get("description"),
                        "contextFocus": project.get("contextFocus"),
                        "createdAt": project.get("createdAt", _utc_now_iso()),
                        "updatedAt": project.get("updatedAt", project.get("createdAt", _utc_now_iso())),
                        "assetCount": len(assets),
                    }
                )
            return out

    def create_project(self, *, name: str, description: str | None, context_focus: str | None) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            now = _utc_now_iso()
            project = {
                "id": uuid.uuid4().hex,
                "name": _norm_text(name),
                "description": _norm_text(description) or None,
                "contextFocus": _norm_text(context_focus) or None,
                "createdAt": now,
                "updatedAt": now,
                "assets": [],
            }
            data["projects"].insert(0, project)
            self._write(data)
            return {
                "id": project["id"],
                "name": project["name"],
                "description": project["description"],
                "contextFocus": project["contextFocus"],
                "createdAt": project["createdAt"],
                "updatedAt": project["updatedAt"],
                "assetCount": 0,
            }

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._read()
            for project in data.get("projects", []):
                if project.get("id") != project_id:
                    continue
                assets = project.get("assets", []) if isinstance(project.get("assets"), list) else []
                return {
                    "id": project.get("id"),
                    "name": project.get("name", "Untitled Project"),
                    "description": project.get("description"),
                    "contextFocus": project.get("contextFocus"),
                    "createdAt": project.get("createdAt", _utc_now_iso()),
                    "updatedAt": project.get("updatedAt", project.get("createdAt", _utc_now_iso())),
                    "assetCount": len(assets),
                    "assets": assets,
                }
            return None

    def add_assets(self, project_id: str, assets: list[dict[str, Any]]) -> dict[str, int] | None:
        with self._lock:
            data = self._read()
            for project in data.get("projects", []):
                if project.get("id") != project_id:
                    continue
                current_assets = project.get("assets")
                if not isinstance(current_assets, list):
                    current_assets = []
                    project["assets"] = current_assets
                seen = {_asset_dedupe_key(asset) for asset in current_assets if isinstance(asset, dict)}
                added = 0
                skipped = 0
                now = _utc_now_iso()
                for raw in assets:
                    if not isinstance(raw, dict):
                        skipped += 1
                        continue
                    candidate = {
                        "id": uuid.uuid4().hex,
                        "title": _norm_text(raw.get("title")),
                        "posterImageUrl": _norm_text(raw.get("posterImageUrl")) or None,
                        "pageUrl": _norm_text(raw.get("pageUrl")) or None,
                        "pageId": _norm_text(raw.get("pageId")) or None,
                        "conversationId": _norm_text(raw.get("conversationId")) or None,
                        "subConversationId": _norm_text(raw.get("subConversationId")) or None,
                        "capturedAt": _norm_text(raw.get("capturedAt")) or now,
                        "storedRef": _norm_text(raw.get("storedRef")) or None,
                    }
                    if not candidate["title"]:
                        skipped += 1
                        continue
                    key = _asset_dedupe_key(candidate)
                    if key in seen:
                        skipped += 1
                        continue
                    seen.add(key)
                    current_assets.append(candidate)
                    added += 1
                project["updatedAt"] = _utc_now_iso()
                self._write(data)
                return {"added": added, "skipped": skipped, "total": added + skipped}
            return None

    def delete_asset(self, project_id: str, asset_ref: str) -> bool | None:
        with self._lock:
            data = self._read()
            for project in data.get("projects", []):
                if project.get("id") != project_id:
                    continue
                assets = project.get("assets")
                if not isinstance(assets, list):
                    return False
                removed = False
                if str(asset_ref).isdigit():
                    idx = int(asset_ref)
                    if 0 <= idx < len(assets):
                        del assets[idx]
                        removed = True
                else:
                    for idx, asset in enumerate(assets):
                        if isinstance(asset, dict) and asset.get("id") == asset_ref:
                            del assets[idx]
                            removed = True
                            break
                if removed:
                    project["updatedAt"] = _utc_now_iso()
                    self._write(data)
                return removed
            return None
