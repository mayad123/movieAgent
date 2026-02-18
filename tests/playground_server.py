"""
Minimal local HTTP server for offline CineMind playground runner.

This server exposes the offline playground runner over HTTP for UI development.
It is completely offline (no OpenAI, no Tavily, no internet access).

Endpoints:
    GET  /health - Health check endpoint
    POST /query  - Execute a query through the offline playground runner

Usage:
    python -m tests.playground_server
    
    Server runs on http://localhost:8000 by default.
    
Examples:
    # Health check
    curl http://localhost:8000/health
    
    # Execute query
    curl -X POST http://localhost:8000/query \
         -H "Content-Type: application/json" \
         -d '{"user_query": "Who directed The Matrix?", "request_type": "info"}'
"""
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from tests.playground_runner import run_playground
from tests.playground_projects_store import (
    list_all as projects_list_all,
    get_by_id as projects_get_by_id,
    create as projects_create,
    seed_if_needed as projects_seed_if_needed,
    add_assets as projects_add_assets,
    remove_asset as projects_remove_asset,
)

# Create FastAPI app
app = FastAPI(
    title="CineMind Offline Playground Server",
    description="Offline HTTP server for CineMind agent playground (no external API calls)",
    version="1.0.0"
)

# Enable CORS for local UI development (file:// has origin "null")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",  # file:// opened HTML
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Static mounts are registered after API routes (see end of file) so /query and /health are not caught by "/"
web_dir = project_root / "web"


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    user_query: str
    request_type: Optional[str] = None  # Optional: if not provided, auto-inferred using rules-based router
    requestedAgentMode: Optional[str] = None  # UI hint; playground always runs PLAYGROUND, returns agent_mode


class ProjectCreate(BaseModel):
    """Request body for creating a project."""
    name: str
    description: Optional[str] = ""


class AssetIn(BaseModel):
    """One asset to capture (poster image, title, page, conversation)."""
    posterImageUrl: Optional[str] = None
    title: str
    pageUrl: Optional[str] = None
    pageId: Optional[str] = None
    conversationId: Optional[str] = None


class ProjectAssetsBody(BaseModel):
    """Request body for appending assets to a project."""
    assets: list


class HealthResponse(BaseModel):
    """Response model for health endpoint."""
    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for sanity checks.
    
    Returns:
        JSON with status and service name
    """
    return HealthResponse(
        status="ok",
        service="cinemind-offline-playground"
    )


@app.post("/query")
async def execute_query(request: QueryRequest) -> Dict[str, Any]:
    """
    Execute a user query through the offline playground runner.
    When a single movie entity is resolved, attaches media_strip (movie_title + optional primary_image_url).
    
    Args:
        request: QueryRequest with user_query and optional request_type
        
    Returns:
        Full structured result from CineMind agent, with media_strip when applicable
        
    Raises:
        HTTPException: If query execution fails
    """
    try:
        # Execute query through playground runner (offline, FakeLLM)
        # Media enrichment (media_strip) is attached by the agent via shared media_enrichment module
        # requestedAgentMode is ignored; backend is authority. Always return explicit mode metadata.
        result = await run_playground(
            user_query=request.user_query,
            request_type=request.request_type
        )
        result["agent_mode"] = "PLAYGROUND"
        result["actualAgentMode"] = "PLAYGROUND"
        result["requestedAgentMode"] = getattr(request, "requestedAgentMode", None) or "PLAYGROUND"
        result["modeFallback"] = False
        result["toolsUsed"] = ["wikipedia"]
        if getattr(request, "requestedAgentMode", None) == "REAL_AGENT":
            result["modeOverrideReason"] = (
                "Playground Server is running (offline only). Start the CineMind API (src.api.main) for Real Agent."
            )
        return result
    except Exception as e:
        # Return error details for debugging
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )


# --- Where to Watch (same contract as main API; requires WATCHMODE_API_KEY in .env) ---
def _playground_watchmode_500():
    return JSONResponse(status_code=500, content={"error": "missing_key", "message": "Where to Watch requires WATCHMODE_API_KEY in .env."})


@app.get("/api/watch/where-to-watch")
async def where_to_watch(
    tmdbId: Optional[str] = Query(None, alias="tmdbId"),
    mediaType: str = Query("movie", alias="mediaType"),
    country: str = Query("US"),
    title: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
):
    """Where to Watch: by tmdbId or by title. Same contract as main API; uses Watchmode."""
    from config import is_watchmode_configured
    if not is_watchmode_configured():
        return _playground_watchmode_500()
    from integrations.watchmode import get_watchmode_client
    from integrations.where_to_watch_normalizer import normalize_where_to_watch_response

    client = get_watchmode_client()
    if not client:
        return _playground_watchmode_500()
    mt = (mediaType or "movie").strip().lower()
    if mt not in ("movie", "tv"):
        return JSONResponse(status_code=400, content={"error": "invalid_media_type", "message": "mediaType must be movie or tv"})
    title_name = (title or "").strip() or None
    year_val = None
    if year and str(year).strip().isdigit():
        try:
            year_val = int(year)
        except (TypeError, ValueError):
            pass
    use_tmdb = bool((tmdbId or "").strip())
    if not use_tmdb and not title_name:
        return JSONResponse(status_code=400, content={"error": "missing_params", "message": "Provide tmdbId or title."})
    if use_tmdb:
        err, data = await client.get_availability((tmdbId or "").strip(), mt, (country or "US").strip())
    else:
        err, data = await client.get_availability_by_title(title_name, year_val, mt, (country or "US").strip())
    if err:
        if "not found" in err.lower() or "title not found" in err.lower():
            return JSONResponse(status_code=404, content={"error": "not_found", "message": err})
        if "rate limit" in err.lower():
            return JSONResponse(status_code=429, content={"error": "rate_limit_exceeded", "message": err})
        return JSONResponse(status_code=500, content={"error": "service_error", "message": err})
    payload = normalize_where_to_watch_response(
        data or {"movie": {}, "region": country or "US", "groups": []},
        title_id=(tmdbId or "").strip() or None,
        title_name=title_name,
        year=year_val,
        media_type=mt,
    )
    return JSONResponse(status_code=200, content=payload)


# --- Projects API (playground persistence; replace backend for auth/hosting) ---
projects_seed_if_needed()


@app.get("/api/projects")
async def get_projects():
    """Return all projects (id, name, createdAt, description). Loaded from file store."""
    return projects_list_all()


@app.post("/api/projects")
async def post_project(body: ProjectCreate):
    """Create a project. Returns the created project."""
    project = projects_create(name=body.name or "Unnamed", description=(body.description or "").strip())
    return project


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Return one project by id (with assets). For Project Assets view."""
    project = projects_get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/api/projects/{project_id}/assets")
async def post_project_assets(project_id: str, body: ProjectAssetsBody):
    """
    Append assets to a project (auto-capture when project scope is active).
    De-duplication is applied; returns number of assets added.
    """
    if not isinstance(body.assets, list):
        raise HTTPException(status_code=400, detail="assets must be a list")
    payloads = [a if isinstance(a, dict) else {} for a in body.assets]
    added = projects_add_assets(project_id, payloads)
    return {"added": added}


@app.delete("/api/projects/{project_id}/assets/{asset_index}")
async def delete_project_asset(project_id: str, asset_index: int):
    """Remove one asset from a project by index (0-based)."""
    if asset_index < 0:
        raise HTTPException(status_code=400, detail="asset_index must be >= 0")
    removed = projects_remove_asset(project_id, asset_index)
    if not removed:
        raise HTTPException(status_code=404, detail="Project or asset not found")
    return {"removed": True}


# Mount static files after API routes so /query and /health are matched first (avoid 405 on POST /query)
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="root")


def main():
    """Run the server using uvicorn."""
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    print("=" * 60)
    print("CineMind Offline Playground Server")
    print("=" * 60)
    print(f"Server: http://localhost:{port}")
    print(f"UI:     http://localhost:{port}/  (index.html from web/)")
    print(f"Health: http://localhost:{port}/health")
    print(f"Docs:   http://localhost:{port}/docs")
    print("=" * 60)
    print("\nThis server is OFFLINE ONLY (always PLAYGROUND):")
    print("  - No OpenAI API calls (uses FakeLLM); logs will not appear in OpenAI dashboard")
    print("  - No Tavily API calls (live data disabled)")
    print("  - requestedAgentMode is ignored; response is always Playground")
    print("\nFor Real Agent (OpenAI): run the CineMind API instead, e.g.")
    print("  python -m src.api.main   OR   uvicorn src.api.main:app --reload")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    # Run server (use PORT env var if 8000 is already in use)
    uvicorn.run(
        "tests.playground_server:app",
        host="0.0.0.0",
        port=port,
        reload=False  # Disable reload for stability
    )


if __name__ == "__main__":
    main()

