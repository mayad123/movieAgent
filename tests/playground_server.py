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
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from tests.playground_runner import run_playground
from cinemind.wikipedia_entity_resolver import WikipediaEntityResolver, ResolvedEntity, ResolverResult
from cinemind.wikipedia_media_provider import WikipediaMediaProvider

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


# Common question prefixes to strip when resolving movie title (so "Who directed The Matrix?" → try "The Matrix")
# Order matters: try shorter prefixes first so we keep "The" in "The Matrix".
_MOVIE_QUERY_PREFIXES = (
    "who directed ",
    "who directed the ",
    "when was ",
    "when did ",
    "what is ",
    "what was ",
    "tell me about ",
    "information about ",
    "about ",
    "how to train your ",  # "How to Train Your Dragon"
    "recommend movies like ",
    "movies like ",
    "similar to ",
    "compare ",
    "difference between ",
)


def _extract_movie_phrase_for_resolution(user_query: str) -> list[str]:
    """
    Return search strings to try: [full_query, extracted_phrase?].
    Extracted phrase strips common prefixes and trailing '?' so questions resolve to the movie.
    """
    q = (user_query or "").strip()
    if not q:
        return []
    out = [q]
    low = q.lower()
    # Strip trailing ? and whitespace for a second attempt
    trimmed = q.rstrip("?").strip()
    if trimmed != q:
        out.append(trimmed)
    # Try without common prefixes (use trimmed)
    for prefix in _MOVIE_QUERY_PREFIXES:
        if low.startswith(prefix):
            rest = trimmed[len(prefix) :].strip()
            if len(rest) >= 2 and rest not in out:
                out.append(rest)
            break
    return out


def _entity_from_resolve_result(resolve_result: ResolverResult) -> Optional[ResolvedEntity]:
    """Get a ResolvedEntity from resolver output: either resolved_entity or first candidate."""
    if resolve_result.resolved_entity is not None:
        return resolve_result.resolved_entity
    if resolve_result.candidates:
        c = resolve_result.candidates[0]
        return ResolvedEntity(
            page_title=c.get("pageTitle", ""),
            display_title=c.get("displayTitle", c.get("pageTitle", "").replace("_", " ")),
        )
    return None


def _fallback_movie_title(result: Dict[str, Any], user_query: str) -> Optional[str]:
    """Use result.query or first source title so we can show a placeholder strip when Wikipedia fails."""
    title = (result.get("query") or "").strip()
    if title:
        return title
    sources = result.get("sources") or []
    if sources and isinstance(sources[0], dict):
        title = (sources[0].get("title") or "").strip()
        if title:
            return title
    return None


def _attach_media_strip_sync(user_query: str, result: Dict[str, Any]) -> None:
    """
    Attach media_strip so the UI can show image or placeholder.
    First tries Wikipedia (resolver + provider). If that fails, attaches placeholder from query/sources.
    """
    try:
        resolver = WikipediaEntityResolver()
        provider = WikipediaMediaProvider()
        for search_text in _extract_movie_phrase_for_resolution(user_query):
            resolve_result = resolver.resolve(search_text)
            entity = _entity_from_resolve_result(resolve_result)
            if entity is None:
                continue
            media_strip = provider.get_media_strip(entity)
            if media_strip.get("movie_title"):
                result["media_strip"] = media_strip
                return
    except Exception:
        pass
    # Fallback: Wikipedia failed or no candidates; still show placeholder strip using query/sources
    fallback_title = _fallback_movie_title(result, user_query) or (user_query or "").strip()
    if fallback_title:
        result["media_strip"] = {"movie_title": fallback_title}


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
        result = await run_playground(
            user_query=request.user_query,
            request_type=request.request_type
        )
        # Attach media_strip when one movie is resolved (Wikipedia only; never block or crash)
        await asyncio.to_thread(_attach_media_strip_sync, request.user_query, result)
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


# Mount static files after API routes so /query and /health are matched first (avoid 405 on POST /query)
if web_dir.is_dir():
    app.mount("/app", StaticFiles(directory=web_dir, html=True), name="app")
app.mount("/tests", StaticFiles(directory=project_root / "tests"), name="tests")
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="root")


def main():
    """Run the server using uvicorn."""
    import uvicorn
    
    print("=" * 60)
    print("CineMind Offline Playground Server")
    print("=" * 60)
    print("Server: http://localhost:8000")
    print("UI:     http://localhost:8000/  or  http://localhost:8000/app/  (canonical app in web/)")
    print("Legacy: http://localhost:8000/tests/playground_ui.html")
    print("Health: http://localhost:8000/health")
    print("Docs:   http://localhost:8000/docs")
    print("=" * 60)
    print("\nThis server is OFFLINE ONLY:")
    print("  - No OpenAI API calls (uses FakeLLM)")
    print("  - No Tavily API calls (live data disabled)")
    print("  - No internet access")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    # Run server
    uvicorn.run(
        "tests.playground_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # Disable reload for stability
    )


if __name__ == "__main__":
    main()

