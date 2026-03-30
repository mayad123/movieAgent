"""
Playground projects store: file-based persistence for Projects (no auth).

Data model: projects[] with id, name, createdAt, optional description, assets[].
Asset registry: original external URL (posterImageUrl, pageUrl); optional storedRef for
future cached/local hosting; title, pageId, conversationId, capturedAt.
Storage: single JSON file. Replace this backend with a real DB/auth later.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Default path: project_root/data/playground_projects.json (create data/ if needed)
_project_root = Path(__file__).resolve().parent.parent
_data_dir = _project_root / "data"
_store_path = _data_dir / "playground_projects.json"


def _ensure_data_dir() -> None:
    _data_dir.mkdir(parents=True, exist_ok=True)


def _read_raw() -> list[dict]:
    """Read projects from file. Returns empty list if missing or invalid."""
    if not _store_path.exists():
        return []
    try:
        with open(_store_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return data


def _write_raw(projects: list[dict]) -> None:
    _ensure_data_dir()
    with open(_store_path, "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=2, ensure_ascii=False)


def _normalize(raw: dict) -> dict:
    """Ensure id, name, createdAt, description, assets; return a clean dict for API."""
    assets = raw.get("assets")
    if not isinstance(assets, list):
        assets = []
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "name": str(raw.get("name") or "").strip() or "Unnamed",
        "createdAt": raw.get("createdAt") or datetime.now(UTC).isoformat(),
        "description": str(raw.get("description") or "").strip() if raw.get("description") is not None else "",
        "assets": [_normalize_asset(a) for a in assets if isinstance(a, dict)],
    }


def _normalize_asset(raw: dict) -> dict:
    """
    One asset: original external URL (posterImageUrl, pageUrl); optional storedRef for
    future cached/local file reference; title, pageId, conversationId, capturedAt.
    """
    page_url = (raw.get("pageUrl") or "").strip()
    page_id = raw.get("pageId")
    if not page_id and page_url:
        m = re.search(r"/wiki/([^/?#]+)", page_url)
        if m:
            page_id = m.group(1)
    stored_ref = raw.get("storedRef")
    if stored_ref is not None:
        stored_ref = (stored_ref or "").strip() or None
    return {
        "posterImageUrl": (raw.get("posterImageUrl") or "").strip() or None,
        "title": str(raw.get("title") or "").strip() or "Unnamed",
        "pageUrl": page_url or None,
        "pageId": (page_id or "").strip() or None,
        "conversationId": str(raw.get("conversationId") or "").strip() or None,
        "capturedAt": raw.get("capturedAt") or datetime.now(UTC).isoformat(),
        "storedRef": stored_ref,
    }


def _asset_dedup_key(asset: dict) -> str:
    """Key for de-duplication: same poster/page + title = same asset."""
    url = asset.get("pageUrl") or asset.get("posterImageUrl") or ""
    title = (asset.get("title") or "").strip()
    return (url + "|" + title) if (url or title) else str(id(asset))


# --- Public API (replace implementation for auth/hosting later) ---


def list_all() -> list[dict]:
    """Return all projects (id, name, createdAt, description, assets)."""
    raw_list = _read_raw()
    return [_normalize(p) for p in raw_list if isinstance(p, dict)]


def get_by_id(project_id: str) -> dict | None:
    """Return one project by id (with assets) or None."""
    project_id = str(project_id).strip()
    if not project_id:
        return None
    raw_list = _read_raw()
    for p in raw_list:
        if isinstance(p, dict) and str(p.get("id") or "") == project_id:
            return _normalize(p)
    return None


def add_assets(project_id: str, new_assets: list[dict]) -> int:
    """
    Append assets to a project with de-duplication (by pageUrl or posterImageUrl+title).
    Returns the number of assets actually added.
    """
    project_id = str(project_id).strip()
    if not project_id:
        return 0
    projects = _read_raw()
    for p in projects:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "")
        if pid != project_id:
            continue
        existing = p.get("assets")
        if not isinstance(existing, list):
            existing = []
        existing_keys = {_asset_dedup_key(_normalize_asset(a)) for a in existing}
        added = 0
        for a in new_assets:
            if not isinstance(a, dict):
                continue
            norm = _normalize_asset(a)
            key = _asset_dedup_key(norm)
            if key in existing_keys:
                continue
            existing.append(norm)
            existing_keys.add(key)
            added += 1
        p["assets"] = existing
        _write_raw(projects)
        return added
    return 0


def remove_asset(project_id: str, asset_index: int) -> bool:
    """
    Remove one asset from a project by index. Returns True if removed.
    """
    project_id = str(project_id).strip()
    if not project_id or asset_index < 0:
        return False
    projects = _read_raw()
    for p in projects:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "")
        if pid != project_id:
            continue
        existing = p.get("assets")
        if not isinstance(existing, list) or asset_index >= len(existing):
            return False
        existing.pop(asset_index)
        p["assets"] = existing
        _write_raw(projects)
        return True
    return False


def create(name: str, description: str = "") -> dict:
    """Create a project; return the created project."""
    projects = _read_raw()
    project = _normalize(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "createdAt": datetime.now(UTC).isoformat(),
            "description": description,
        }
    )
    projects.append(project)
    _write_raw(projects)
    return project


def seed_if_needed() -> None:
    """If the store is empty, seed with default projects."""
    if _read_raw():
        return
    _write_raw(
        [
            _normalize({"name": "Project 1", "description": "Default project"}),
            _normalize({"name": "Project 2", "description": "Default project"}),
        ]
    )
