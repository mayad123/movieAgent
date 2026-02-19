"""
REST API wrapper for CineMind agent.
For operationalization and deployment.
"""
import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
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
    from config import REAL_AGENT_TIMEOUT_SECONDS, is_watchmode_configured
    from cinemind.database import Database
    from cinemind.observability import Observability
    from cinemind.tagging import RequestTagger, OUTCOMES
    from workflows import run_real_agent_with_fallback as run_real_agent_workflow, run_playground
    from schemas import MovieQuery, MovieResponse, QueryRequest, HealthResponse, DiagnosticResponse
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
        tools_used = ["tmdb"]  # Playground uses TMDB for media/posters
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
        from config import is_tmdb_enabled, get_tmdb_access_token
        config_loaded = True
        tmdb_enabled = is_tmdb_enabled()
        token = get_tmdb_access_token()
        tmdb_token_present = bool((token or "").strip())
    except Exception as e:
        logger.debug("Diagnostic config load failed: %s", e)

    tmdb_config_reachable: Optional[bool] = None
    if tmdb_enabled and config_loaded and tmdb_token_present:
        try:
            from config import get_tmdb_access_token as _get_token
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


def _watchmode_500_missing_key():
    """Structured 500 for Watchmode routes when API key is not configured."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={
            "error": "missing_key",
            "message": "Where to Watch is not configured. Set WATCHMODE_API_KEY in the server environment (e.g. .env or secrets manager). Get an API key from https://watchmode.com.",
        },
    )


def _watchmode_error_response(status_code: int, error: str, message: str):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content={"error": error, "message": message})


@app.get("/api/watch/where-to-watch")
async def where_to_watch_by_tmdb(
    tmdbId: Optional[str] = Query(None, alias="tmdbId", description="TMDB movie or TV id (optional if title provided)"),
    mediaType: str = Query("movie", alias="mediaType", description="movie or tv"),
    country: str = Query("US", description="Country code (e.g. US, GB)"),
    title: Optional[str] = Query(None, description="Movie title (used when tmdbId missing; also display name)"),
    year: Optional[str] = Query(None, description="Release year (optional, improves title lookup)"),
):
    """
    Where to Watch: by TMDB id or by title. Returns availability by access type (subscription/free/rent/buy/tve).
    Provide either tmdbId or title; when only title is provided, Watchmode autocomplete-search is used.
    """
    from fastapi.responses import JSONResponse
    if not is_watchmode_configured():
        logger.warning("Where-to-watch called but WATCHMODE_API_KEY is not set.")
        return _watchmode_500_missing_key()
    mt = (mediaType or "movie").strip().lower()
    if mt not in ("movie", "tv"):
        return _watchmode_error_response(400, "invalid_media_type", "mediaType must be movie or tv")
    title_name = (title or "").strip() or None
    year_val = None
    if year and str(year).strip().isdigit():
        try:
            year_val = int(year)
        except (TypeError, ValueError):
            pass
    use_tmdb = bool((tmdbId or "").strip())
    if not use_tmdb and not title_name:
        return _watchmode_error_response(400, "missing_params", "Provide tmdbId or title to find where to watch.")

    from integrations.watchmode import get_watchmode_client
    from integrations.where_to_watch_normalizer import normalize_where_to_watch_response

    client = get_watchmode_client()
    if not client:
        return _watchmode_500_missing_key()
    if use_tmdb:
        err, data = await client.get_availability((tmdbId or "").strip(), mt, (country or "US").strip())
    else:
        err, data = await client.get_availability_by_title(title_name, year_val, mt, (country or "US").strip())
    if err:
        if "not found" in err.lower() or "title not found" in err.lower():
            return _watchmode_error_response(404, "not_found", err)
        if "rate limit" in err.lower():
            return _watchmode_error_response(429, "rate_limit_exceeded", err)
        return _watchmode_error_response(500, "service_error", err)
    request_region = (country or "US").strip().upper()
    response_data = data or {"movie": {}, "region": request_region, "groups": []}
    title_id_for_response = (tmdbId or "").strip() or (response_data.get("_resolved_tmdb_id") if isinstance(response_data, dict) else None)
    payload = normalize_where_to_watch_response(
        response_data,
        title_id=title_id_for_response or None,
        title_name=title_name,
        year=year_val,
        media_type=mt,
    )
    payload["region"] = request_region
    return JSONResponse(status_code=200, content=payload)


@app.get("/api/where-to-watch")
async def where_to_watch(
    title: str = Query(..., description="Movie title"),
    year: Optional[int] = Query(None),
    pageUrl: Optional[str] = Query(None, alias="pageUrl"),
    pageId: Optional[str] = Query(None, alias="pageId"),
):
    """
    Where to Watch (legacy): title-based. Prefer GET /api/watch/where-to-watch?tmdbId=&mediaType=&country= for TMDB-based lookup.
    """
    if not is_watchmode_configured():
        logger.warning("Where-to-watch called but WATCHMODE_API_KEY is not set.")
        return _watchmode_500_missing_key()
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=501,
        content={
            "error": "not_implemented",
            "message": "Use GET /api/watch/where-to-watch?tmdbId=<id>&mediaType=movie|tv&country=US for availability.",
        },
    )


@app.post("/search", response_model=MovieResponse)
async def search_movies(query: MovieQuery):
    """
    Search and analyze movie information.
    Dispatches to PLAYGROUND (TMDB media) or REAL_AGENT based on backend config.
    """
    try:
        if not query.query or not query.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        mode = _effective_mode(query.requested_agent_mode)
        logger.info("Executing request in mode: %s (query: %s...)", mode, query.query[:80])

        if mode == AgentMode.PLAYGROUND.value:
            result = await run_playground(
                user_query=query.query,
                request_type=query.request_type,
            )
        else:
            result, fallback_reason = await run_real_agent_workflow(
                query.query, query.request_type, query.use_live_data,
                REAL_AGENT_TIMEOUT_SECONDS, get_agent(),
            )
            if fallback_reason is not None:
                result = await run_playground(
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
            result = await run_playground(
                user_query=req.user_query,
                request_type=req.request_type,
            )
        else:
            result, fallback_reason = await run_real_agent_workflow(
                req.user_query, req.request_type, True,
                REAL_AGENT_TIMEOUT_SECONDS, get_agent(),
            )
            if fallback_reason is not None:
                result = await run_playground(
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
            result = await run_playground(user_query=query, request_type=None)
        else:
            result, fallback_reason = await run_real_agent_workflow(
                query, None, use_live_data, REAL_AGENT_TIMEOUT_SECONDS, get_agent(),
            )
            if fallback_reason is not None:
                result = await run_playground(user_query=query, request_type=None)
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
                result = await run_playground(
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
                    fallback = await run_playground(
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

