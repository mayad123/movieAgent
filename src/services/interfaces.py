"""Service interfaces used by workflows. Workflows depend on these, not on concrete implementations."""
from typing import Any, Dict, Optional, Protocol


class IAgentRunner(Protocol):
    """Contract for running the real agent pipeline (search + LLM + response)."""

    async def search_and_analyze(
        self,
        user_query: str,
        use_live_data: bool = True,
        request_id: Optional[str] = None,
        request_type: Optional[str] = None,
        outcome: Optional[str] = None,
        playground_mode: bool = False,
    ) -> Dict[str, Any]:
        """Run the full agent pipeline and return the result dict."""
        ...
