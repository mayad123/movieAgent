"""
REST API wrapper for CineMind agent.
For operationalization and deployment.
"""
import os
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

try:
    from cinemind import CineMind
    from database import Database
    from observability import Observability
    from tagging import RequestTagger, OUTCOMES
except ImportError as e:
    raise ImportError(
        f"CineMind module not found. Make sure all dependencies are installed: {e}"
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="CineMind API",
    description="Real-time Movie Analysis and Discovery Agent API",
    version="1.0.0"
)

# CORS middleware for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance (lazy initialization)
_agent: Optional[CineMind] = None
_observability: Optional[Observability] = None


def get_agent() -> CineMind:
    """Get or create agent instance."""
    global _agent
    if _agent is None:
        _agent = CineMind(enable_observability=True)
    return _agent

def get_observability() -> Observability:
    """Get or create observability instance."""
    global _observability
    if _observability is None:
        db = Database()
        _observability = Observability(db)
    return _observability


# Request/Response Models
class MovieQuery(BaseModel):
    query: str = Field(..., description="Movie-related question or search query")
    use_live_data: bool = Field(True, description="Whether to perform real-time searches")
    stream: bool = Field(False, description="Whether to stream the response")
    request_type: Optional[str] = Field(None, description="Request type tag (info/recs/comparison/spoiler/release-date/fact-check)")
    outcome: Optional[str] = Field(None, description="Outcome tag (success/unclear/hallucination/user-corrected)")


class MovieResponse(BaseModel):
    agent: str
    version: str
    query: str
    response: str
    sources: list
    timestamp: str
    live_data_used: bool
    request_id: Optional[str] = None
    token_usage: Optional[dict] = None
    cost_usd: Optional[float] = None
    request_type: Optional[str] = None
    outcome: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    agent: str
    version: str


# API Endpoints
@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "CineMind",
        "version": "1.0.0"
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    try:
        agent = get_agent()
        return {
            "status": "healthy",
            "agent": agent.agent_name,
            "version": agent.version
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@app.post("/search", response_model=MovieResponse)
async def search_movies(query: MovieQuery):
    """
    Search and analyze movie information.
    
    Args:
        query: Movie query with optional parameters
        
    Returns:
        Movie analysis response with sources
    """
    try:
        if not query.query or not query.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        agent = get_agent()
        logger.info(f"Processing query: {query.query[:100]}...")
        
        result = await agent.search_and_analyze(
            query.query,
            use_live_data=query.use_live_data,
            request_type=query.request_type,
            outcome=query.outcome
        )
        
        logger.info(f"Query processed successfully: {query.query[:50]}...")
        return MovieResponse(**result)
    
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/search")
async def search_movies_get(query: str, use_live_data: bool = True):
    """
    GET endpoint for movie search (simpler interface).
    
    Args:
        query: Movie-related question
        use_live_data: Whether to use real-time data
        
    Returns:
        Movie analysis response
    """
    try:
        agent = get_agent()
        result = await agent.search_and_analyze(query, use_live_data=use_live_data)
        return MovieResponse(**result)
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/stream")
async def search_movies_stream(query: MovieQuery):
    """
    Stream movie analysis response token by token.
    
    Args:
        query: Movie query
        
    Returns:
        Server-Sent Events stream
    """
    from fastapi.responses import StreamingResponse
    import json
    
    async def generate():
        try:
            agent = get_agent()
            async for token in agent.stream_response(
                query.query,
                use_live_data=query.use_live_data
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/observability/requests/{request_id}")
async def get_request_trace(request_id: str):
    """
    Get complete trace for a specific request.
    
    Returns request details, response, metrics, and search operations.
    """
    try:
        obs = get_observability()
        trace = obs.get_request_trace(request_id)
        
        if not trace:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
        
        return trace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting request trace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/observability/requests")
async def get_recent_requests(limit: int = Query(100, ge=1, le=1000)):
    """
    Get recent requests.
    
    Args:
        limit: Maximum number of requests to return (1-1000)
    """
    try:
        obs = get_observability()
        requests = obs.db.get_recent_requests(limit=limit)
        return {"requests": requests, "count": len(requests)}
    except Exception as e:
        logger.error(f"Error getting recent requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/observability/stats")
async def get_stats(days: int = Query(7, ge=1, le=365),
                    request_type: Optional[str] = Query(None, description="Filter by request type"),
                    outcome: Optional[str] = Query(None, description="Filter by outcome")):
    """
    Get statistics for the last N days, optionally filtered by type/outcome.
    
    Args:
        days: Number of days to include in statistics (1-365)
        request_type: Optional filter by request type
        outcome: Optional filter by outcome
    """
    try:
        obs = get_observability()
        stats = obs.db.get_stats(days=days, request_type=request_type, outcome=outcome)
        return {"period_days": days, "request_type": request_type, "outcome": outcome, "statistics": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/observability/tags")
async def get_tag_distribution(days: int = Query(7, ge=1, le=365)):
    """
    Get distribution of request types and outcomes.
    
    Args:
        days: Number of days to include (1-365)
    """
    try:
        obs = get_observability()
        distribution = obs.db.get_tag_distribution(days=days)
        return {"period_days": days, "distribution": distribution}
    except Exception as e:
        logger.error(f"Error getting tag distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/observability/requests/{request_id}/outcome")
async def update_request_outcome(request_id: str, outcome: str = Query(..., description="Outcome tag")):
    """
    Update the outcome tag for a request.
    
    Valid outcomes: success, unclear, hallucination, user-corrected
    """
    tagger = RequestTagger()
    if not tagger.validate_outcome(outcome):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome. Must be one of: {list(OUTCOMES.keys())}"
        )
    
    try:
        obs = get_observability()
        obs.db.update_request(request_id, outcome=outcome)
        return {"request_id": request_id, "outcome": outcome, "status": "updated"}
    except Exception as e:
        logger.error(f"Error updating outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _agent, _observability
    if _agent:
        await _agent.close()
        _agent = None
    if _observability and hasattr(_observability, 'db'):
        _observability.db.close()
        _observability = None


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    run_server(port=port)

