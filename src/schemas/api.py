"""API request/response Pydantic models (contract with clients)."""
from typing import Optional
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


class QueryRequest(BaseModel):
    """Request body for /query (UI contract: same as playground server)."""
    user_query: str = Field(..., description="User message")
    request_type: Optional[str] = Field(None, description="Optional request type")
    requested_agent_mode: Optional[str] = Field(None, alias="requestedAgentMode", description="UI hint: PLAYGROUND | REAL_AGENT")
