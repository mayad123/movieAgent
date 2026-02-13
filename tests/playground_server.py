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
from pydantic import BaseModel

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from tests.playground_runner import run_playground

# Create FastAPI app
app = FastAPI(
    title="CineMind Offline Playground Server",
    description="Offline HTTP server for CineMind agent playground (no external API calls)",
    version="1.0.0"
)

# Enable CORS for local UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/query")
async def execute_query(request: QueryRequest) -> Dict[str, Any]:
    """
    Execute a user query through the offline playground runner.
    
    Args:
        request: QueryRequest with user_query and optional request_type
        
    Returns:
        Full structured result from CineMind agent (unchanged)
        
    Raises:
        HTTPException: If query execution fails
    """
    try:
        # Execute query through playground runner (offline, FakeLLM)
        result = await run_playground(
            user_query=request.user_query,
            request_type=request.request_type
        )
        
        # Return agent's result unchanged
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


def main():
    """Run the server using uvicorn."""
    import uvicorn
    
    print("=" * 60)
    print("CineMind Offline Playground Server")
    print("=" * 60)
    print("Server: http://localhost:8000")
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

