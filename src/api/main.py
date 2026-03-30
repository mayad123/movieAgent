"""
REST API wrapper for CineMind agent.
For operationalization and deployment.
"""
import logging
import json
import os
import re
import time
import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Path as ApiPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

try:
    import sys
    from pathlib import Path
    # Add src to path for imports
    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from cinemind.agent import CineMind
    from cinemind.agent import AgentMode, get_configured_mode, resolve_effective_mode
    from config import REAL_AGENT_TIMEOUT_SECONDS, is_watchmode_configured, is_llm_configured
    from cinemind.infrastructure import Database
    from cinemind.infrastructure import Observability
    from cinemind.infrastructure import ProjectsStore
    from cinemind.infrastructure.tagging import RequestTagger, OUTCOMES
    from workflows import run_real_agent_with_fallback as run_real_agent_workflow, run_playground
    from schemas import (
        MovieQuery,
        MovieResponse,
        QueryRequest,
        HealthResponse,
        DiagnosticResponse,
        SimilarMoviesResponse,
        MovieDetailsResponse,
        ProjectSummary,
        ProjectDetail,
        ProjectCreateRequest,
        ProjectAssetsAddRequest,
        ProjectAssetsAddResponse,
    )
    from cinemind.media.media_enrichment import enrich_batch, build_similar_movie_clusters
    from cinemind.media.movie_hub_genre_parsing import parse_movie_hub_genre_buckets
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
_projects_store: Optional[ProjectsStore] = None


@app.on_event("startup")
def _log_agent_mode_at_startup():
    """Log whether Real Agent is available so you can confirm the right server and env."""
    llm_ok = is_llm_configured()
    effective = resolve_effective_mode(AgentMode.REAL_AGENT).value
    logger.info(
        "CineMind API startup: LLM configured=%s, Real Agent when requested=%s",
        llm_ok,
        effective,
    )
    if not llm_ok:
        logger.info(
            "To use Real Agent, set CINEMIND_LLM_BASE_URL and CINEMIND_LLM_MODEL "
            "(OpenAI-compatible server, e.g. local Llama / vLLM) and run this API (src.api.main)."
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


def get_projects_store() -> ProjectsStore:
    """Get or create projects store instance."""
    global _projects_store
    if _projects_store is None:
        _projects_store = ProjectsStore()
    return _projects_store


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
            from integrations.tmdb.image_config import fetch_config
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
    from integrations.watchmode.normalizer import normalize_where_to_watch_response

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


@app.get(
    "/api/movies/{movie_id}/similar",
    response_model=SimilarMoviesResponse,
)
async def get_similar_movies(
    movie_id: str = ApiPath(..., description="Backend movie identifier (typically TMDB id)"),
    by: str = Query("genre,tone,cast", description="Comma-separated cluster kinds to request"),
    title: Optional[str] = Query(None, description="Optional movie title hint"),
    year: Optional[int] = Query(None, description="Optional release year"),
    mediaType: Optional[str] = Query(None, description="Optional media type (movie/tv)"),
) -> SimilarMoviesResponse:
    """
    Similar movies endpoint for the Sub-context Movie Hub.

    Phase 3 MVP: returns empty-but-well-structured genre/tone/cast clusters so the
    frontend can rely on a stable contract. Future work will populate these using
    TMDB similar/recommendations and enriched metadata.
    """
    try:
        tmdb_id = int(movie_id) if movie_id.isdigit() else None
    except ValueError:
        tmdb_id = None

    payload = build_similar_movie_clusters(
        title=title or "",
        year=year,
        tmdb_id=tmdb_id,
        media_type=mediaType,
        max_results=20,
    )
    return SimilarMoviesResponse(**payload)


@app.get(
    "/api/movies/{tmdbId}/details",
    response_model=MovieDetailsResponse,
)
async def get_movie_details(
    tmdbId: str = ApiPath(..., description="TMDB movie id"),
) -> MovieDetailsResponse:
    """
    On-demand TMDB-backed details for the full-screen Movie Details modal.

    Graceful fallback:
    - When TMDB is missing/unavailable, return a minimal response (tmdbId-only)
      so the frontend can keep rendering poster-derived fields.
    """
    try:
        from config import get_tmdb_access_token, is_tmdb_enabled
        from integrations.tmdb.movie_details import build_movie_details_payload

        mid = int((tmdbId or "").strip())
        if not is_tmdb_enabled():
            return MovieDetailsResponse(tmdbId=mid)

        token = (get_tmdb_access_token() or "").strip()
        payload = build_movie_details_payload(mid, token=token, timeout=6.0, include_related=True)
        return MovieDetailsResponse(**payload)
    except ValueError:
        raise HTTPException(status_code=400, detail="tmdbId must be an integer")
    except Exception as e:
        logger.debug("Movie details endpoint failed: %s", e)
        try:
            mid = int((tmdbId or "").strip())
        except Exception:
            mid = 0
        # Never fail hard: keep response contract stable for the frontend.
        return MovieDetailsResponse(tmdbId=mid)


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


@app.get("/api/projects", response_model=List[ProjectSummary])
async def list_projects():
    """List all projects."""
    store = get_projects_store()
    return store.list_projects()


@app.post("/api/projects", response_model=ProjectSummary)
async def create_project(req: ProjectCreateRequest):
    """Create a new project."""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")
    store = get_projects_store()
    return store.create_project(
        name=name,
        description=req.description,
        context_focus=req.contextFocus,
    )


@app.get("/api/projects/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str):
    """Fetch one project with assets."""
    store = get_projects_store()
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/api/projects/{project_id}/assets", response_model=ProjectAssetsAddResponse)
async def add_project_assets(project_id: str, req: ProjectAssetsAddRequest):
    """Add assets to a project, skipping duplicates."""
    if not req.assets:
        return ProjectAssetsAddResponse(added=0, skipped=0, total=0)
    store = get_projects_store()
    result = store.add_assets(project_id, [asset.model_dump() for asset in req.assets])
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.delete("/api/projects/{project_id}/assets/{asset_ref}")
async def delete_project_asset(project_id: str, asset_ref: str):
    """Delete one project asset by id or legacy index."""
    store = get_projects_store()
    result = store.delete_asset(project_id, asset_ref)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not result:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": True}


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


def _format_hub_conversation_history_block(history: Optional[list], *, max_per_message: int = 2000, max_block_total: int = 12000) -> str:
    """
    Bounded prior-turn block for sub-context Movie Hub multi-turn prompts.
    """
    if not history:
        return ""
    parts: list[str] = []
    total = 0
    for item in history:
        if item is None:
            continue
        if isinstance(item, dict):
            role = str(item.get("role") or "").strip().lower()
            raw = str(item.get("content") or "").strip()
        else:
            role = str(getattr(item, "role", "") or "").strip().lower()
            raw = str(getattr(item, "content", "") or "").strip()
        if role not in ("user", "assistant"):
            continue
        if not raw:
            continue
        if len(raw) > max_per_message:
            raw = raw[: max_per_message - 3] + "..."
        line = f"{role.capitalize()}: {raw}"
        if total + len(line) + 1 > max_block_total:
            break
        parts.append(line)
        total += len(line) + 1
    if not parts:
        return ""
    return (
        "Sub-context Movie Hub — prior conversation (same anchor movie; use for continuity when interpreting follow-ups):\n"
        + "\n".join(parts)
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

        # Optional Sub-context Movie Hub context marker:
        # When present, we parse it and use it to build + filter `movieHubClusters`,
        # while stripping the marker before sending text to the agent.
        context_movie: Optional[dict] = None
        candidate_titles: list[str] = []
        hub_marker_re = re.compile(
            r"\[\[CINEMIND_HUB_CONTEXT\]\](.*?)\[\[\/CINEMIND_HUB_CONTEXT\]\]",
            re.DOTALL,
        )
        stripped_user_query = (req.user_query or "").strip()
        m = hub_marker_re.search(stripped_user_query)
        if m:
            payload_raw = (m.group(1) or "").strip()
            try:
                payload = json.loads(payload_raw) if payload_raw else None
                if isinstance(payload, dict):
                    context_movie = payload
                    maybe_candidates = payload.get("candidateTitles") or payload.get("candidate_titles")
                    if isinstance(maybe_candidates, list):
                        # Candidate titles are passed from the UI as "Title (Year)" strings.
                        # Keep it bounded to avoid oversized prompts.
                        for it in maybe_candidates[:30]:
                            if it is None:
                                continue
                            s = str(it).strip()
                            if s:
                                candidate_titles.append(s)
            except Exception:
                context_movie = None
            # Remove marker block; keep the user's natural-language question.
            stripped_user_query = hub_marker_re.sub("", stripped_user_query).strip()

        # Effective prompt sent to the agent (marker stripped, plus optional
        # candidate-title injection for sub-context hub filtering).
        agent_user_query = stripped_user_query
        hub_history_block = _format_hub_conversation_history_block(
            req.hub_conversation_history if req.hub_conversation_history is not None else None
        )
        if candidate_titles:
            # The UI already enforces a strict output contract; we add an
            # additional instruction so the model filters within the loaded
            # poster universe.
            candidates_text = "\n".join(candidate_titles)
            hub_contract = (
                "Return the Movie Hub structured format (strict contract):\n"
                + "- Return exactly 4 genre blocks.\n"
                + "- Each block MUST start with: Genre: <GenreName>\n"
                + "- Then provide exactly 5 numbered lines formatted exactly as: \"1. Title (Year)\"\n"
                + "- Total titles: 20.\n"
                + "- You MUST output exactly 20 titles (4 * 5), even if the Candidate Titles list contains fewer than 20 unique titles.\n"
                + "- Prefer titles from the Candidate Titles list first. If needed, you MAY add closely similar titles, but any title you add must still follow \"Title (Year)\" format and stay consistent with the anchor movie context.\n"
                + "- Return ONLY the genre blocks. No commentary. No markdown."
            )
            question_section = (
                stripped_user_query
                if not hub_history_block
                else ("Current user question:\n" + stripped_user_query.strip())
            )
            prefix = (hub_history_block + "\n\n") if hub_history_block else ""
            agent_user_query = (
                prefix
                + question_section
                + "\n\n"
                + "Candidate Titles (movies currently shown in the hub; prefer filtering from this set first):\n"
                + candidates_text
                + "\n\n"
                + hub_contract
            )

        def build_filtered_candidate_movie_hub_clusters() -> Optional[list[dict]]:
            """
            Deterministic filtering for candidateTitles-based hub queries.

            This prevents fragile LLM structured output parsing from causing
            poster-card under-renders (e.g., falling back to the small
            poster-derived relatedMovies set).
            """
            if not candidate_titles:
                return None
            try:
                from cinemind.media.movie_hub_filtering import filter_movie_hub_clusters_by_question

                max_total = 20
                bounded_titles = list(candidate_titles[:max_total])
                if not bounded_titles:
                    return None

                # Enrich titles into poster-ready movie cards.
                try:
                    hub_max_concurrent = int(os.getenv("HUB_ENRICH_MAX_CONCURRENT", "4"))
                except Exception:
                    hub_max_concurrent = 4
                if hub_max_concurrent < 1:
                    hub_max_concurrent = 1
                if hub_max_concurrent > 12:
                    hub_max_concurrent = 12

                enriched_cards = enrich_batch(
                    bounded_titles,
                    max_titles=min(len(bounded_titles), max_total),
                    max_concurrent=hub_max_concurrent,
                ) or []

                base_title = "this movie"
                if isinstance(context_movie, dict):
                    bt = (context_movie.get("title") or "").strip()
                    by = context_movie.get("year")
                    if bt:
                        base_title = bt + (f" ({by})" if by is not None else "")

                flat_movies: list[dict] = []
                for card in enriched_cards:
                    if not isinstance(card, dict):
                        continue
                    tmdb_id = card.get("tmdb_id")
                    try:
                        tmdb_id_int = int(tmdb_id) if tmdb_id is not None else None
                    except Exception:
                        tmdb_id_int = None

                    primary_image_url = card.get("primary_image_url")

                    title = (card.get("movie_title") or card.get("title") or "").strip()
                    if not title:
                        continue

                    flat_movies.append(
                        {
                            "title": title,
                            "year": card.get("year"),
                            "primary_image_url": primary_image_url if (primary_image_url or "").strip() else None,
                            "page_url": (card.get("page_url") or "").strip() or "#",
                            "tmdbId": tmdb_id_int,
                            "mediaType": "movie",
                        }
                    )

                clusters: list[dict] = [
                    {
                        "kind": "genre",
                        "label": "Similar by genre to " + base_title,
                        "movies": flat_movies,
                    }
                ]

                # Apply deterministic constraints extracted from the question.
                filtered = filter_movie_hub_clusters_by_question(clusters, stripped_user_query)
                return filtered
            except Exception as e:
                logger.debug("Deterministic candidate filtering failed: %s", e)
                return None

        def _normalize_movie_hub_title(value: object) -> str:
            return re.sub(r"\s+", " ", str(value or "").strip()).lower()

        def _normalize_movie_hub_year(value: object) -> Optional[int]:
            if value is None:
                return None
            try:
                y = int(str(value).strip())
            except Exception:
                return None
            return y if 1800 <= y <= 2100 else None

        def _movie_hub_key(movie: object) -> Optional[str]:
            """
            Canonical identity order for sub-context dedupe:
            1) tmdbId
            2) normalized title + year
            3) normalized title
            """
            if not isinstance(movie, dict):
                return None
            tmdb_id = movie.get("tmdbId")
            if tmdb_id is not None:
                try:
                    tmdb_id_int = int(str(tmdb_id).strip())
                    return f"tmdb:{tmdb_id_int}"
                except Exception:
                    pass

            title_raw = movie.get("title") or movie.get("movie_title") or ""
            title = _normalize_movie_hub_title(title_raw)
            if not title:
                return None
            year_val = _normalize_movie_hub_year(movie.get("year"))
            if year_val is not None:
                return f"title_year:{title}|{year_val}"
            return f"title:{title}"

        def dedupe_movie_hub_clusters(clusters: object, *, max_total: int = 20) -> list[dict]:
            """
            Remove duplicate movies across all clusters while preserving first-seen order.
            """
            if not isinstance(clusters, list):
                return []
            seen: set[str] = set()
            total = 0
            out: list[dict] = []
            for cluster in clusters:
                if total >= max_total:
                    break
                if not isinstance(cluster, dict):
                    continue
                movies = cluster.get("movies")
                if not isinstance(movies, list):
                    continue
                kept_movies: list[dict] = []
                for movie in movies:
                    if total >= max_total:
                        break
                    if not isinstance(movie, dict):
                        continue
                    key = _movie_hub_key(movie)
                    if key and key in seen:
                        continue
                    if key:
                        seen.add(key)
                    kept_movies.append(movie)
                    total += 1
                if kept_movies:
                    next_cluster = dict(cluster)
                    next_cluster["movies"] = kept_movies
                    out.append(next_cluster)
            return out

        def maybe_add_movie_hub_clusters(result_dict: dict) -> None:
            t0 = time.perf_counter()
            if not context_movie or not isinstance(result_dict, dict):
                return
            try:
                if not stripped_user_query:
                    return

                response_text = result_dict.get("response") or result_dict.get("answer") or ""
                response_text = str(response_text or "").strip()
                if not response_text:
                    return

                parsed_buckets = parse_movie_hub_genre_buckets(
                    response_text,
                    expected_genres=4,
                    expected_items_per_genre=5,
                    min_total_items=20,
                    min_genre_items_signal=5,
                )

                if not parsed_buckets:
                    return

                # Standardize "fallback bucket" output:
                # `parse_movie_hub_genre_buckets(...)` may return a single bucket like
                # {"genre":"Similar by genre","items":[...up to 20 titles...]} when the
                # structured "Genre:" signals are too weak.
                #
                # Downstream we assume 4 buckets x 5 items. Without this, the
                # per-bucket truncation (`items = items[:5]`) yields only ~5 movies.
                try:
                    expected_genres = 4
                    expected_items_per_genre = 5
                    max_total = 20
                    total_items = sum(
                        len((b or {}).get("items") or [])
                        for b in (parsed_buckets or [])
                        if isinstance(b, dict)
                    )
                    if (
                        isinstance(parsed_buckets, list)
                        and len(parsed_buckets) == 1
                        and isinstance(parsed_buckets[0], dict)
                        and total_items >= max_total
                    ):
                        base_genre = str(parsed_buckets[0].get("genre") or "").strip() or "Similar by genre"
                        all_items = [str(it or "").strip() for it in (parsed_buckets[0].get("items") or []) if str(it or "").strip()]
                        all_items = all_items[:max_total]
                        rebucketed: list[dict] = []
                        for i in range(expected_genres):
                            start = i * expected_items_per_genre
                            end = start + expected_items_per_genre
                            items_i = all_items[start:end]
                            if not items_i:
                                break
                            rebucketed.append({"genre": base_genre, "items": items_i})
                        if len(rebucketed) == expected_genres:
                            parsed_buckets = rebucketed
                except Exception:
                    # Graceful degrade: keep parsed_buckets as-is.
                    pass

                max_total = 20
                # Performance guard:
                # Enriching via TMDB resolution can be slow and occasionally time out.
                # We keep the full item set (via parsed LLM titles), and only fetch posters/IDs
                # for a prefix so the hub renders quickly and consistently.
                try:
                    enrich_posters_limit = int(os.getenv("HUB_ENRICH_POSTERS_LIMIT", str(max_total)))
                except Exception:
                    enrich_posters_limit = max_total
                if enrich_posters_limit < 0:
                    enrich_posters_limit = 0
                enrich_posters_limit = min(enrich_posters_limit, max_total)

                flat_enrich_titles: list[str] = []
                bucket_sizes: list[int] = []
                bucket_genres: list[str] = []

                year_tail_re = re.compile(r"^\s*.+?\(\s*(\d{4})\s*\)\s*$")
                year_parse_re = re.compile(r"\(\s*(\d{4})\s*\)\s*$")

                def strip_year_tail(item: str) -> str:
                    if not item:
                        return ""
                    return re.sub(r"\s*\(\s*\d{4}\s*\)\s*$", "", str(item or "").strip()).strip()

                flat_items: list[str] = []
                for b in parsed_buckets:
                    genre = str(b.get("genre") or "").strip()
                    items = b.get("items") or []
                    if not genre or not isinstance(items, list):
                        continue
                    items = [str(it or "").strip() for it in items if str(it or "").strip()]
                    if not items:
                        continue

                    items = items[:5]
                    bucket_genres.append(genre)
                    bucket_sizes.append(len(items))

                    for it in items:
                        flat_items.append(it)
                        # Keep the `Title (Year)` so the TMDB resolver can extract year.
                        flat_enrich_titles.append(str(it or "").strip())
                        if len(flat_enrich_titles) >= max_total:
                            break
                    if len(flat_enrich_titles) >= max_total:
                        break

                if not flat_enrich_titles:
                    return

                enrich_titles = flat_enrich_titles[:enrich_posters_limit] if enrich_posters_limit else []
                # TMDB poster/id enrichment (not TMDB "similar" endpoint).
                try:
                    hub_max_concurrent = int(os.getenv("HUB_ENRICH_MAX_CONCURRENT", "4"))
                except Exception:
                    hub_max_concurrent = 4
                if hub_max_concurrent < 1:
                    hub_max_concurrent = 1
                if hub_max_concurrent > 12:
                    hub_max_concurrent = 12

                enriched_cards = (
                    enrich_batch(
                        enrich_titles,
                        max_titles=enrich_posters_limit,
                        max_concurrent=hub_max_concurrent,
                    )
                    if enrich_posters_limit
                    else []
                )
                # We allow `enriched_cards` to be empty: hub placeholders will still render.
                enriched_cards = enriched_cards or []

                # Align enriched cards back to the input order.
                aligned_cards: list[Optional[dict]] = []
                if not enrich_titles:
                    aligned_cards = []
                elif len(enriched_cards) == len(enrich_titles):
                    aligned_cards = enriched_cards
                else:
                    # enrich_batch may dedupe titles when TMDB is enabled.
                    # Replicate the same dedupe rule to align indices safely.
                    seen: set[str] = set()
                    unique: list[str] = []
                    for t in enrich_titles:
                        n = (t or "").strip().lower()
                        if n and n not in seen:
                            seen.add(n)
                            unique.append((t or "").strip())

                    if len(enriched_cards) == len(unique):
                        card_by_norm: dict[str, dict] = {}
                        for i, ut in enumerate(unique):
                            card_by_norm[(ut or "").strip().lower()] = enriched_cards[i]
                        aligned_cards = [card_by_norm.get((t or "").strip().lower()) for t in enrich_titles]
                    else:
                        # Last resort: keep positional for whatever came back.
                        aligned_cards = list(enriched_cards[: len(enrich_titles)])
                        while len(aligned_cards) < len(enrich_titles):
                            aligned_cards.append(None)

                # Map enriched cards into the SimilarMovie contract shape.
                flat_movies: list[dict] = []
                for idx, item in enumerate(flat_items[:max_total]):
                    card = aligned_cards[idx] if idx < len(aligned_cards) else None
                    card = card if isinstance(card, dict) else None

                    fallback_title = (strip_year_tail(item) or item or "").strip()
                    fallback_year = None
                    m = year_parse_re.search(str(item or ""))
                    if m:
                        try:
                            fallback_year = int(m.group(1))
                        except Exception:
                            fallback_year = None

                    title = (card.get("movie_title") if card else None) or fallback_title
                    title = (title or "").strip()

                    year = card.get("year") if card else None
                    if year is None:
                        year = fallback_year

                    primary_image_url = (card.get("primary_image_url") if card else None) or None
                    page_url = (card.get("page_url") if card else None) or ""
                    tmdb_id = (card.get("tmdb_id") if card else None) or None

                    flat_movies.append(
                        {
                            "title": title,
                            "year": year,
                            "primary_image_url": primary_image_url,
                            "page_url": page_url,
                            "tmdbId": tmdb_id,
                            "mediaType": "movie",
                        }
                    )

                # Re-bucket by the parsed genre categories.
                clusters: list[dict] = []
                pos = 0
                for genre, sz in zip(bucket_genres, bucket_sizes):
                    if pos >= len(flat_movies):
                        break
                    movies = flat_movies[pos : pos + sz]
                    pos += sz
                    if movies:
                        clusters.append(
                            {
                                "kind": "genre",
                                "label": genre,
                                "movies": movies,
                            }
                        )

                deduped_clusters = dedupe_movie_hub_clusters(clusters, max_total=max_total)
                if deduped_clusters and any(c.get("movies") for c in deduped_clusters):
                    result_dict["movieHubClusters"] = deduped_clusters
                logger.debug("hub_parse_enrich_ms=%.1f", (time.perf_counter() - t0) * 1000)
            except Exception as e:
                logger.debug("Failed to build filtered movieHubClusters: %s", e)

        def _count_total_moviehub_items(clusters: object) -> int:
            """
            Count total movies across all hub clusters.
            Used to avoid overwriting LLM-parsed hubs with underfilled deterministic
            candidate-only hubs (which can collapse the UX below 20 titles).
            """
            if not isinstance(clusters, list):
                return 0
            total = 0
            for c in clusters:
                if not isinstance(c, dict):
                    continue
                movies = c.get("movies")
                if isinstance(movies, list):
                    total += len(movies)
            return total

        def attach_movie_hub_clusters(result_dict: dict) -> None:
            """
            Build movieHubClusters with minimal duplicate work:
            - Prefer deterministic candidate path when sufficiently complete.
            - Fall back to parse/enrich path for quality or when deterministic is missing/underfilled.
            """
            if not isinstance(result_dict, dict):
                return
            t_attach = time.perf_counter()
            deterministic_clusters: Optional[list[dict]] = None
            deterministic_total = 0
            try:
                t_det = time.perf_counter()
                deterministic_clusters = build_filtered_candidate_movie_hub_clusters()
                logger.debug("hub_deterministic_ms=%.1f", (time.perf_counter() - t_det) * 1000)
                if deterministic_clusters:
                    deterministic_total = _count_total_moviehub_items(deterministic_clusters)
            except Exception:
                deterministic_clusters = None
                deterministic_total = 0

            # If deterministic path is already good enough, skip parse/enrich path to save latency.
            min_deterministic = max(1, int(os.getenv("HUB_DETERMINISTIC_MIN_ITEMS", "12")))
            if deterministic_clusters and deterministic_total >= min_deterministic:
                result_dict["movieHubClusters"] = dedupe_movie_hub_clusters(
                    deterministic_clusters, max_total=20
                )
                logger.debug(
                    "hub_attach_strategy=deterministic total_items=%s total_ms=%.1f",
                    deterministic_total,
                    (time.perf_counter() - t_attach) * 1000,
                )
                return

            maybe_add_movie_hub_clusters(result_dict)
            existing = result_dict.get("movieHubClusters")
            existing_total = _count_total_moviehub_items(existing)
            if deterministic_clusters and (not existing or existing_total < 20):
                result_dict["movieHubClusters"] = dedupe_movie_hub_clusters(
                    deterministic_clusters, max_total=20
                )
            logger.debug(
                "hub_attach_strategy=parse_then_merge existing_items=%s deterministic_items=%s total_ms=%.1f",
                existing_total,
                deterministic_total,
                (time.perf_counter() - t_attach) * 1000,
            )

        if mode == AgentMode.PLAYGROUND.value:
            result = await run_playground(
                user_query=agent_user_query,
                request_type=req.request_type,
            )
        else:
            result, fallback_reason = await run_real_agent_workflow(
                agent_user_query, req.request_type, True,
                REAL_AGENT_TIMEOUT_SECONDS, get_agent(),
            )
            if fallback_reason is not None:
                result = await run_playground(
                    user_query=agent_user_query,
                    request_type=req.request_type,
                )
                result["agent_mode"] = AgentMode.PLAYGROUND.value
                result["modeFallback"] = True
                result["fallback_reason"] = fallback_reason
                rid = result.get("request_id") or str(uuid.uuid4())
                result["request_id"] = rid
                result["responseEnvelopeVersion"] = "v1"
                result["message_id"] = req.message_id or str(uuid.uuid4())
                result["thread_id"] = req.thread_id or (f"sub-{rid}" if context_movie else f"main-{rid}")
                _inject_mode_metadata(result, "PLAYGROUND", req.requested_agent_mode, mode_fallback=True)
                logger.info("Request completed in mode: PLAYGROUND (fallback). reason=%s", fallback_reason)
                attach_movie_hub_clusters(result)
                return result

        result["agent_mode"] = mode
        rid = result.get("request_id") or str(uuid.uuid4())
        result["request_id"] = rid
        result["responseEnvelopeVersion"] = "v1"
        result["message_id"] = req.message_id or str(uuid.uuid4())
        result["thread_id"] = req.thread_id or (f"sub-{rid}" if context_movie else f"main-{rid}")
        mode_override_reason = None
        if (
            mode == AgentMode.PLAYGROUND.value
            and req.requested_agent_mode == "REAL_AGENT"
            and not is_llm_configured()
        ):
            mode_override_reason = "LLM not configured (CINEMIND_LLM_BASE_URL + CINEMIND_LLM_MODEL); Real Agent unavailable."
        _inject_mode_metadata(
            result, mode, req.requested_agent_mode, mode_fallback=False, mode_override_reason=mode_override_reason
        )

        # If hub context marker was provided, generate question-filtered clusters for the UI.
        attach_movie_hub_clusters(result)

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
    global _agent, _observability, _projects_store
    if _agent:
        await _agent.close()
        _agent = None
    if _observability and hasattr(_observability, 'db'):
        _observability.db.close()
        _observability = None
    _projects_store = None


# Serve the web frontend (must be the LAST mount so API routes take priority)
_web_dir = Path(__file__).resolve().parent.parent.parent / "web"
if _web_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dir), html=True), name="web")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    run_server(port=port)

