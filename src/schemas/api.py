"""API request/response Pydantic models (contract with clients)."""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


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
    agent_mode: Optional[str] = None
    actualAgentMode: Optional[str] = None
    requestedAgentMode: Optional[str] = None
    modeFallback: Optional[bool] = None
    toolsUsed: Optional[list] = None
    fallback_reason: Optional[str] = None
    # Optional: question-driven Movie Hub clusters for Sub-context hub view.
    # Uses the same shape as `/api/movies/{id}/similar`.
    movieHubClusters: Optional[List["SimilarCluster"]] = None
    responseEnvelopeVersion: Optional[str] = None
    message_id: Optional[str] = None
    thread_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    agent: str
    version: str
    agent_mode: Optional[str] = None


class DiagnosticResponse(BaseModel):
    """Backend config and TMDB diagnostic; no secrets."""
    status: str
    config_loaded: bool
    tmdb_enabled: bool
    tmdb_token_present: bool
    tmdb_config_reachable: Optional[bool] = None


class HubHistoryMessage(BaseModel):
    """One turn in sub-context Movie Hub multi-turn filtering (UI → /query)."""

    role: str = Field(..., description="user or assistant")
    content: str = Field(default="", description="Plain message text (no hub marker)")


class QueryRequest(BaseModel):
    """Request body for /query (UI contract: same as playground server)."""
    user_query: str = Field(..., description="User message")
    request_type: Optional[str] = Field(None, description="Optional request type")
    requested_agent_mode: Optional[str] = Field(None, alias="requestedAgentMode", description="UI hint: PLAYGROUND | REAL_AGENT")
    hub_conversation_history: Optional[List[HubHistoryMessage]] = Field(
        None,
        alias="hubConversationHistory",
        description="Prior sub-context hub chat turns (bounded server-side when building prompt)",
    )
    thread_id: Optional[str] = Field(None, alias="threadId", description="Optional client thread identifier")
    message_id: Optional[str] = Field(None, alias="messageId", description="Optional client message identifier")


class SimilarMovie(BaseModel):
    """Movie card shape for similar-movies clusters."""

    title: str
    year: Optional[int] = None
    primary_image_url: Optional[str] = None
    page_url: Optional[str] = None
    tmdbId: Optional[int] = None
    mediaType: Optional[str] = None


class SimilarCluster(BaseModel):
    """Cluster of similar movies by genre/tone/cast."""

    kind: str
    label: str
    movies: List[SimilarMovie]


class SimilarMoviesResponse(BaseModel):
    """Response payload for /api/movies/{id}/similar."""

    clusters: List[SimilarCluster]


class RelatedMovie(BaseModel):
    """Minimal related-title shape used by the Movie Details modal."""

    movie_title: Optional[str] = Field(None, description="Display title (preferred by frontend)")
    title: Optional[str] = Field(None, description="Alternate display title")
    year: Optional[int] = None
    tmdbId: Optional[int] = None
    primary_image_url: Optional[str] = None


class MovieDetailsResponse(BaseModel):
    """
    Normalized payload used by `web/js/modules/movie-details.js`.

    Fields are intentionally optional to allow graceful fallback when TMDB
    is missing/unavailable; the frontend can keep rendering the initial
    poster-derived payload.
    """

    tmdbId: int

    # Title/meta
    movie_title: Optional[str] = None
    year: Optional[int] = None
    tagline: Optional[str] = None
    overview: Optional[str] = None

    # Hero/meta
    runtime_minutes: Optional[int] = None
    genres: Optional[List[str]] = None
    release_date: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    rating: Optional[float] = None
    vote_count: Optional[int] = None

    # Media
    primary_image_url: Optional[str] = None
    backdrop_url: Optional[str] = None

    # Credits
    directors: Optional[List[str]] = None
    cast: Optional[List[str]] = None

    # Related titles (optional enrichment)
    relatedMovies: Optional[List[RelatedMovie]] = None


class ProjectAsset(BaseModel):
    """One saved movie asset in a project."""

    id: str
    title: str
    posterImageUrl: Optional[str] = None
    pageUrl: Optional[str] = None
    pageId: Optional[str] = None
    conversationId: Optional[str] = None
    subConversationId: Optional[str] = None
    capturedAt: str
    storedRef: Optional[str] = None


class ProjectSummary(BaseModel):
    """Summary row for project listings."""

    id: str
    name: str
    description: Optional[str] = None
    contextFocus: Optional[str] = None
    createdAt: str
    updatedAt: str
    assetCount: int = 0


class ProjectDetail(ProjectSummary):
    """Project detail payload with assets."""

    assets: List[ProjectAsset] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    """Request payload for creating a project."""

    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    contextFocus: Optional[str] = Field(None, max_length=200)


class ProjectAssetInput(BaseModel):
    """Input payload for adding an asset to a project."""

    title: str = Field(..., min_length=1, max_length=300)
    posterImageUrl: Optional[str] = None
    pageUrl: Optional[str] = None
    pageId: Optional[str] = None
    conversationId: Optional[str] = None
    subConversationId: Optional[str] = None
    capturedAt: Optional[str] = None
    storedRef: Optional[str] = None


class ProjectAssetsAddRequest(BaseModel):
    """Bulk add payload for project assets."""

    assets: List[ProjectAssetInput] = Field(default_factory=list)


class ProjectAssetsAddResponse(BaseModel):
    """Bulk add result."""

    added: int
    skipped: int
    total: int
