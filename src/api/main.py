"""
REST API wrapper for CineMind agent.
For operationalization and deployment.
"""
import asyncio
import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

try:
    import sys
    from pathlib import Path
    # Add src to path for imports
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from cinemind.agent import CineMind
    from cinemind.agent_mode import AgentMode, get_configured_mode, resolve_effective_mode
    from cinemind.config import REAL_AGENT_TIMEOUT_SECONDS
    from cinemind.database import Database
    from cinemind.observability import Observability
    from cinemind.playground import run_playground_query
    from cinemind.tagging import RequestTagger, OUTCOMES
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


@app.on_event("startup")
def _log_agent_mode_at_startup():
    """Log whether Real Agent is available so you can confirm the right server and env."""
    key_set = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    effective = resolve_effective_mode(AgentMode.REAL_AGENT).value
    logger.info(
        "CineMind API startup: OPENAI_API_KEY=%s, Real Agent when requested=%s",
        "set" if key_set else "not set",
        effective,
    )
    if not key_set:
        logger.info(
            "To use Real Agent, set OPENAI_API_KEY and run this API (src.api.main), not the Playground Server."
        )


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
    requested_agent_mode: Optional[str] = Field(None, alias="requestedAgentMode", description="UI hint: PLAYGROUND | REAL_AGENT (backend may override)")


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
    agent_mode: Optional[str] = None  # PLAYGROUND | REAL_AGENT (which pipeline ran)
    actualAgentMode: Optional[str] = None
    requestedAgentMode: Optional[str] = None
    modeFallback: Optional[bool] = None
    toolsUsed: Optional[list] = None
    fallback_reason: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    agent: str
    version: str
    agent_mode: Optional[str] = None  # Effective mode (PLAYGROUND | REAL_AGENT)


class DiagnosticResponse(BaseModel):
    """Backend config and TMDB diagnostic; no secrets."""
    status: str
    config_loaded: bool
    tmdb_enabled: bool
    tmdb_token_present: bool
    tmdb_config_reachable: Optional[bool] = None  # None = not checked


async def _run_real_agent_with_fallback(user_query: str, request_type: Optional[str], use_live_data: bool = True):
    """
    Run real agent with timeout. On timeout or exception: fall back to playground,
    return result with modeFallback=True and clear error messaging. No silent crash.
    """
    agent = get_agent()
    try:
        result = await asyncio.wait_for(
            agent.search_and_analyze(
                user_query,
                use_live_data=use_live_data,
                request_type=request_type,
            ),
            timeout=REAL_AGENT_TIMEOUT_SECONDS,
        )
        return result, None
    except asyncio.TimeoutError:
        logger.error(
            "Real agent timed out after %.0fs (query: %s...). Falling back to PLAYGROUND.",
            REAL_AGENT_TIMEOUT_SECONDS,
            (user_query or "")[:80],
        )
        return None, "Request timed out; switched to Playground mode."
    except Exception as e:
        logger.exception("Real agent failed (query: %s...). Falling back to PLAYGROUND.", (user_query or "")[:80])
        return None, str(e) or "Real agent error; switched to Playground mode."


def _inject_mode_metadata(
    result: dict,
    actual_agent_mode: str,
    requested_agent_mode: Optional[str],
    mode_fallback: bool,
    mode_override_reason: Optional[str] = None,
) -> None:
    """Inject explicit mode metadata into every response. No ambiguity about which path ran."""
    result["actualAgentMode"] = actual_agent_mode
    result["requestedAgentMode"] = requested_agent_mode or actual_agent_mode
    result["modeFallback"] = mode_fallback
    if mode_override_reason:
        result["modeOverrideReason"] = mode_override_reason
    tools_used = []
    if actual_agent_mode == "REAL_AGENT" and not mode_fallback:
        if result.get("tavily_used"):
            tools_used.append("tavily")
        if result.get("fallback_used"):
            tools_used.append("fallback_search")
        if result.get("sources"):
            tools_used.append("sources")
    elif actual_agent_mode == "PLAYGROUND":
        tools_used = ["wikipedia"]  # Playground uses Wikipedia-only media
    result["toolsUsed"] = tools_used


def _effective_mode(requested: Optional[str] = None) -> str:
    """
    Resolve effective agent mode. If requested is PLAYGROUND or REAL_AGENT, use as hint;
    backend still applies safety (e.g. fallback to PLAYGROUND if keys missing).
    """
    if requested in ("REAL_AGENT", "PLAYGROUND"):
        try:
            return resolve_effective_mode(AgentMode(requested)).value
        except ValueError:
            pass
    return resolve_effective_mode(get_configured_mode()).value


class QueryRequest(BaseModel):
    """Request body for /query (UI contract: same as playground server)."""
    user_query: str = Field(..., description="User message")
    request_type: Optional[str] = Field(None, description="Optional request type")
    requested_agent_mode: Optional[str] = Field(None, alias="requestedAgentMode", description="UI hint: PLAYGROUND | REAL_AGENT")


# API Endpoints
@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "CineMind",
        "version": "1.0.0",
        "agent_mode": _effective_mode(),
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    mode = _effective_mode()
    try:
        if mode == AgentMode.REAL_AGENT.value:
            agent = get_agent()
            return {
                "status": "healthy",
                "agent": agent.agent_name,
                "version": agent.version,
                "agent_mode": mode,
            }
        return {
            "status": "healthy",
            "agent": "CineMind",
            "version": "1.0.0",
            "agent_mode": mode,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@app.get("/health/diagnostic", response_model=DiagnosticResponse)
async def health_diagnostic():
    """
    Config and TMDB diagnostic. Confirms config loads and optionally that TMDB config endpoint is reachable.
    TMDB enablement is backend config only (ENABLE_TMDB_SCENES + TMDB_READ_ACCESS_TOKEN in .env).
    """
    config_loaded = False
    tmdb_enabled = False
    tmdb_token_present = False
    try:
        from cinemind.config import is_tmdb_enabled, get_tmdb_access_token
        config_loaded = True
        tmdb_enabled = is_tmdb_enabled()
        token = get_tmdb_access_token()
        tmdb_token_present = bool((token or "").strip())
    except Exception as e:
        logger.debug("Diagnostic config load failed: %s", e)

    tmdb_config_reachable: Optional[bool] = None
    if tmdb_enabled and config_loaded and tmdb_token_present:
        try:
            from cinemind.config import get_tmdb_access_token as _get_token
            from cinemind.tmdb_image_config import fetch_config
            fetch_config(_get_token(), timeout=3.0)
            tmdb_config_reachable = True
        except Exception as e:
            logger.debug("TMDB config fetch failed: %s", e)
            tmdb_config_reachable = False

    return {
        "status": "healthy",
        "config_loaded": config_loaded,
        "tmdb_enabled": tmdb_enabled,
        "tmdb_token_present": tmdb_token_present,
        "tmdb_config_reachable": tmdb_config_reachable,
    }


@app.post("/search", response_model=MovieResponse)
async def search_movies(query: MovieQuery):
    """
    Search and analyze movie information.
    Dispatches to PLAYGROUND (Wikipedia-only) or REAL_AGENT based on backend config.
    """
    try:
        if not query.query or not query.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        mode = _effective_mode(query.requested_agent_mode)
        logger.info("Executing request in mode: %s (query: %s...)", mode, query.query[:80])

        if mode == AgentMode.PLAYGROUND.value:
            result = await run_playground_query(
                user_query=query.query,
                request_type=query.request_type,
            )
        else:
            result, fallback_reason = await _run_real_agent_with_fallback(
                query.query, query.request_type, query.use_live_data
            )
            if fallback_reason is not None:
                result = await run_playground_query(
                    user_query=query.query,
                    request_type=query.request_type,
                )
                result["agent_mode"] = AgentMode.PLAYGROUND.value
                result["modeFallback"] = True
                result["fallback_reason"] = fallback_reason
                _inject_mode_metadata(result, "PLAYGROUND", query.requested_agent_mode, mode_fallback=True)
                logger.info("Request completed in mode: PLAYGROUND (fallback). reason=%s", fallback_reason)
                return MovieResponse(**result)

        result["agent_mode"] = mode
        _inject_mode_metadata(result, mode, query.requested_agent_mode, mode_fallback=False)
        logger.info("Request completed in mode: %s", mode)
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


@app.post("/query")
async def query(req: QueryRequest):
    """
    Query endpoint for UI (same contract as playground server).
    Accepts requestedAgentMode; backend validates and may override.
    """
    try:
        if not req.user_query or not req.user_query.strip():
            raise HTTPException(status_code=400, detail="user_query cannot be empty")

        mode = _effective_mode(req.requested_agent_mode)
        logger.info("Executing /query in mode: %s (query: %s...)", mode, req.user_query[:80])

        if mode == AgentMode.PLAYGROUND.value:
            result = await run_playground_query(
                user_query=req.user_query,
                request_type=req.request_type,
            )
        else:
            result, fallback_reason = await _run_real_agent_with_fallback(
                req.user_query, req.request_type, use_live_data=True
            )
            if fallback_reason is not None:
                result = await run_playground_query(
                    user_query=req.user_query,
                    request_type=req.request_type,
                )
                result["agent_mode"] = AgentMode.PLAYGROUND.value
                result["modeFallback"] = True
                result["fallback_reason"] = fallback_reason
                _inject_mode_metadata(result, "PLAYGROUND", req.requested_agent_mode, mode_fallback=True)
                logger.info("Request completed in mode: PLAYGROUND (fallback). reason=%s", fallback_reason)
                return result

        result["agent_mode"] = mode
        mode_override_reason = None
        if (
            mode == AgentMode.PLAYGROUND.value
            and req.requested_agent_mode == "REAL_AGENT"
            and not (os.getenv("OPENAI_API_KEY") or "").strip()
        ):
            mode_override_reason = "OPENAI_API_KEY not set; Real Agent unavailable."
        _inject_mode_metadata(
            result, mode, req.requested_agent_mode, mode_fallback=False, mode_override_reason=mode_override_reason
        )
        logger.info("Request completed in mode: %s", mode)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def search_movies_get(query: str, use_live_data: bool = True):
    """
    GET endpoint for movie search. Dispatches by agent mode (PLAYGROUND / REAL_AGENT).
    """
    try:
        if not query or not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        mode = _effective_mode()
        logger.info("Executing request in mode: %s (query: %s...)", mode, query[:80])

        if mode == AgentMode.PLAYGROUND.value:
            result = await run_playground_query(user_query=query, request_type=None)
        else:
            result, fallback_reason = await _run_real_agent_with_fallback(query, None, use_live_data)
            if fallback_reason is not None:
                result = await run_playground_query(user_query=query, request_type=None)
                result["agent_mode"] = AgentMode.PLAYGROUND.value
                result["modeFallback"] = True
                result["fallback_reason"] = fallback_reason
                _inject_mode_metadata(result, "PLAYGROUND", None, mode_fallback=True)
                logger.info("Request completed in mode: PLAYGROUND (fallback). reason=%s", fallback_reason)
                return MovieResponse(**result)

        result["agent_mode"] = mode
        _inject_mode_metadata(result, mode, None, mode_fallback=False)
        return MovieResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/stream")
async def search_movies_stream(query: MovieQuery):
    """
    Stream movie analysis response. REAL_AGENT streams tokens; PLAYGROUND returns one chunk.
    """
    from fastapi.responses import StreamingResponse
    import json

    mode = _effective_mode()
    logger.info("Executing stream request in mode: %s", mode)

    async def generate():
        try:
            if mode == AgentMode.PLAYGROUND.value:
                result = await run_playground_query(
                    user_query=query.query,
                    request_type=query.request_type,
                )
                _inject_mode_metadata(result, mode, query.requested_agent_mode, mode_fallback=False)
                payload = {"token": result.get("response", ""), "agent_mode": mode}
                payload["actualAgentMode"] = result.get("actualAgentMode")
                payload["requestedAgentMode"] = result.get("requestedAgentMode")
                payload["modeFallback"] = result.get("modeFallback", False)
                payload["toolsUsed"] = result.get("toolsUsed", [])
                yield f"data: {json.dumps(payload)}\n\n"
                yield "data: [DONE]\n\n"
            else:
                try:
                    agent = get_agent()
                    async for token in agent.stream_response(
                        query.query,
                        use_live_data=query.use_live_data,
                    ):
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    meta = {"agent_mode": mode, "actualAgentMode": mode, "requestedAgentMode": query.requested_agent_mode or mode, "modeFallback": False, "toolsUsed": []}
                    yield f"data: {json.dumps(meta)}\n\n"
                except Exception as e:
                    logger.exception("Real agent stream failed; falling back to PLAYGROUND.")
                    fallback = await run_playground_query(
                        user_query=query.query,
                        request_type=query.request_type,
                    )
                    _inject_mode_metadata(fallback, "PLAYGROUND", "REAL_AGENT", mode_fallback=True)
                    fallback["fallback_reason"] = str(e)
                    payload = {"token": fallback.get("response", ""), "agent_mode": "PLAYGROUND", "modeFallback": True, "fallback_reason": str(e)}
                    payload["actualAgentMode"] = fallback.get("actualAgentMode")
                    payload["requestedAgentMode"] = fallback.get("requestedAgentMode")
                    payload["toolsUsed"] = fallback.get("toolsUsed", [])
                    yield f"data: {json.dumps(payload)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Stream error")
            yield f"data: {json.dumps({'error': str(e), 'modeFallback': True})}\n\n"

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

