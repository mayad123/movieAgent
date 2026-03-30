"""
Mock implementations of OpenAI and Tavily APIs for testing without making real API calls.
"""
from unittest.mock import MagicMock


class MockOpenAIResponse:
    """Mock OpenAI API response."""

    def __init__(self, content: str, usage: dict | None = None):
        self.choices = [MagicMock()]
        self.choices[0].message.content = content
        self.usage = MagicMock()
        if usage:
            self.usage.prompt_tokens = usage.get("prompt_tokens", 0)
            self.usage.completion_tokens = usage.get("completion_tokens", 0)
            self.usage.total_tokens = usage.get("total_tokens", 0)
        else:
            self.usage.prompt_tokens = 100
            self.usage.completion_tokens = 50
            self.usage.total_tokens = 150
        # Make usage attributes accessible
        self.usage.__dict__.update({
            "prompt_tokens": self.usage.prompt_tokens,
            "completion_tokens": self.usage.completion_tokens,
            "total_tokens": self.usage.total_tokens
        })


class MockOpenAIClient:
    """Mock OpenAI client that returns predetermined responses."""

    def __init__(self, responses: dict[str, str] | None = None):
        """
        Initialize mock client.

        Args:
            responses: Dict mapping query patterns to responses
        """
        self.responses = responses or {}
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self._call_count = 0

    async def create_completion(self, messages: list[dict], **kwargs):
        """Create a mock completion."""
        # Extract user message
        user_message = None
        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        # Find matching response
        response_content = self._find_response(user_message)

        # Calculate mock usage
        prompt_tokens = len(str(messages).split()) // 2  # Rough estimate
        completion_tokens = len(response_content.split()) // 2

        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }

        self._call_count += 1

        return MockOpenAIResponse(response_content, usage)

    def _find_response(self, query: str) -> str:
        """Find matching response for query."""
        query_lower = query.lower()

        # Check exact matches first
        for pattern, response in self.responses.items():
            if pattern.lower() in query_lower:
                return response

        # Default response
        return "This is a test response. The query was: " + query[:100]

    async def create_completion_stream(self, messages: list[dict], **kwargs):
        """Create a mock streaming completion."""
        response_content = self._find_response(
            next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        )

        # Yield chunks
        words = response_content.split()
        for word in words:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = word + " "
            yield chunk


class MockTavilyClient:
    """Mock Tavily search client."""

    def __init__(self, search_results: dict[str, list[dict]] | None = None):
        """
        Initialize mock Tavily client.

        Args:
            search_results: Dict mapping query patterns to search results
        """
        self.search_results = search_results or {}
        self._call_count = 0

    def search(self, query: str, **kwargs) -> dict:
        """Mock search that returns predetermined results."""
        self._call_count += 1

        # Find matching results
        results = self._find_results(query)

        return {
            "results": results,
            "answer": f"Mock answer for: {query}" if not results else None
        }

    def _find_results(self, query: str) -> list[dict]:
        """Find matching search results."""
        query_lower = query.lower()

        # Check for matching patterns
        for pattern, results in self.search_results.items():
            if pattern.lower() in query_lower:
                return results

        # Default mock results
        return [
            {
                "title": f"Mock Result for {query}",
                "url": "https://example.com/mock",
                "content": f"This is mock search content for: {query}",
                "score": 0.9,
                "source": "mock"
            }
        ]


class MockSearchEngine:
    """Mock search engine for testing."""

    def __init__(self, tavily_api_key: str | None = None):
        self.tavily_api_key = tavily_api_key
        self.mock_results = {}

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Return mock search results."""
        if query in self.mock_results:
            return self.mock_results[query][:max_results]

        return [
            {
                "title": f"Mock: {query}",
                "url": "https://example.com",
                "content": f"Mock content for {query}",
                "source": "mock"
            }
        ]

    async def search_movie_specific(self, movie_title: str, year: int | None = None) -> list[dict]:
        """Return mock movie-specific results."""
        key = f"{movie_title} {year}" if year else movie_title
        return await self.search(key, max_results=10)

    def set_mock_results(self, query: str, results: list[dict]):
        """Set mock results for a specific query."""
        self.mock_results[query] = results

    async def async_close(self):
        """Mock close method."""
        pass

