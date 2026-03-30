"""Service interfaces used by workflows. Workflows depend on these, not on concrete implementations."""
from typing import Any, Protocol


class IAgentRunner(Protocol):
    """Contract for running the real agent pipeline (search + LLM + response)."""

    async def search_and_analyze(
        self,
        user_query: str,
        use_live_data: bool = True,
        request_id: str | None = None,
        request_type: str | None = None,
        outcome: str | None = None,
        playground_mode: bool = False,
    ) -> dict[str, Any]:
        """Run the full agent pipeline and return the result dict."""
        ...
