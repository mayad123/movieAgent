"""API request/response Pydantic models (contract with clients)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MovieQuery(BaseModel):
    query: str = Field(..., description="Movie-related question or search query")
    use_live_data: bool = Field(True, description="Whether to perform real-time searches")
    stream: bool = Field(False, description="Whether to stream the response")
    request_type: str | None = Field(
        None, description="Request type tag (info/recs/comparison/spoiler/release-date/fact-check)"
    )
    outcome: str | None = Field(None, description="Outcome tag (success/unclear/hallucination/user-corrected)")
    requested_agent_mode: str | None = Field(
        None, alias="requestedAgentMode", description="UI hint: PLAYGROUND | REAL_AGENT (backend may override)"
    )


class MovieResponse(BaseModel):
    agent: str
    version: str
    query: str
    response: str
    sources: list
    timestamp: str
    live_data_used: bool
    request_id: str | None = None
    token_usage: dict | None = None
    cost_usd: float | None = None
    request_type: str | None = None
    outcome: str | None = None
    agent_mode: str | None = None
    actualAgentMode: str | None = None
    requestedAgentMode: str | None = None
    modeFallback: bool | None = None
    toolsUsed: list | None = None
    fallback_reason: str | None = None
    # Optional: question-driven Movie Hub clusters for Sub-context hub view.
    # Uses the same shape as `/api/movies/{id}/similar`.
    movieHubClusters: list[SimilarCluster] | None = None
    responseEnvelopeVersion: str | None = None
    message_id: str | None = None
    thread_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    agent: str
    version: str
    agent_mode: str | None = None


class DiagnosticResponse(BaseModel):
    """Backend config and TMDB diagnostic; no secrets."""

    status: str
    config_loaded: bool
    tmdb_enabled: bool
    tmdb_token_present: bool
    tmdb_config_reachable: bool | None = None


class HubHistoryMessage(BaseModel):
    """One turn in sub-context Movie Hub multi-turn filtering (UI → /query)."""

    role: str = Field(..., description="user or assistant")
    content: str = Field(default="", description="Plain message text (no hub marker)")


class QueryRequest(BaseModel):
    """Request body for /query (UI contract: same as playground server)."""

    user_query: str = Field(..., description="User message")
    request_type: str | None = Field(None, description="Optional request type")
    requested_agent_mode: str | None = Field(
        None, alias="requestedAgentMode", description="UI hint: PLAYGROUND | REAL_AGENT"
    )
    hub_conversation_history: list[HubHistoryMessage] | None = Field(
        None,
        alias="hubConversationHistory",
        description="Prior sub-context hub chat turns (bounded server-side when building prompt)",
    )
    thread_id: str | None = Field(None, alias="threadId", description="Optional client thread identifier")
    message_id: str | None = Field(None, alias="messageId", description="Optional client message identifier")


class SimilarMovie(BaseModel):
    """Movie card shape for similar-movies clusters."""

    title: str
    year: int | None = None
    primary_image_url: str | None = None
    page_url: str | None = None
    tmdbId: int | None = None
    mediaType: str | None = None


class SimilarCluster(BaseModel):
    """Cluster of similar movies by genre/tone/cast."""

    kind: str
    label: str
    movies: list[SimilarMovie]


class SimilarMoviesResponse(BaseModel):
    """Response payload for /api/movies/{id}/similar."""

    clusters: list[SimilarCluster]


class RelatedMovie(BaseModel):
    """Minimal related-title shape used by the Movie Details modal."""

    movie_title: str | None = Field(None, description="Display title (preferred by frontend)")
    title: str | None = Field(None, description="Alternate display title")
    year: int | None = None
    tmdbId: int | None = None
    primary_image_url: str | None = None


class MovieDetailsResponse(BaseModel):
    """
    Normalized payload used by `web/js/modules/movie-details.js`.

    Fields are intentionally optional to allow graceful fallback when TMDB
    is missing/unavailable; the frontend can keep rendering the initial
    poster-derived payload.
    """

    tmdbId: int

    # Title/meta
    movie_title: str | None = None
    year: int | None = None
    tagline: str | None = None
    overview: str | None = None

    # Hero/meta
    runtime_minutes: int | None = None
    genres: list[str] | None = None
    release_date: str | None = None
    language: str | None = None
    country: str | None = None
    rating: float | None = None
    vote_count: int | None = None

    # Media
    primary_image_url: str | None = None
    backdrop_url: str | None = None

    # Credits
    directors: list[str] | None = None
    cast: list[str] | None = None

    # Related titles (optional enrichment)
    relatedMovies: list[RelatedMovie] | None = None


class ProjectAsset(BaseModel):
    """One saved movie asset in a project."""

    id: str
    title: str
    posterImageUrl: str | None = None
    pageUrl: str | None = None
    pageId: str | None = None
    conversationId: str | None = None
    subConversationId: str | None = None
    capturedAt: str
    storedRef: str | None = None


class ProjectSummary(BaseModel):
    """Summary row for project listings."""

    id: str
    name: str
    description: str | None = None
    contextFocus: str | None = None
    createdAt: str
    updatedAt: str
    assetCount: int = 0


class ProjectDetail(ProjectSummary):
    """Project detail payload with assets."""

    assets: list[ProjectAsset] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    """Request payload for creating a project."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=500)
    contextFocus: str | None = Field(None, max_length=200)


class ProjectAssetInput(BaseModel):
    """Input payload for adding an asset to a project."""

    title: str = Field(..., min_length=1, max_length=300)
    posterImageUrl: str | None = None
    pageUrl: str | None = None
    pageId: str | None = None
    conversationId: str | None = None
    subConversationId: str | None = None
    capturedAt: str | None = None
    storedRef: str | None = None


class ProjectAssetsAddRequest(BaseModel):
    """Bulk add payload for project assets."""

    assets: list[ProjectAssetInput] = Field(default_factory=list)


class ProjectAssetsAddResponse(BaseModel):
    """Bulk add result."""

    added: int
    skipped: int
    total: int
