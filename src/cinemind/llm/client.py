"""
LLM client interface and implementations for CineMind.
Supports dependency injection for testing with FakeLLM.
Production: OpenAI-compatible HTTP API (e.g. local Llama / vLLM) via httpx.
"""
import json
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class LLMResponse:
    """Response from LLM client."""
    content: str
    usage: dict[str, int] | None = None
    metadata: dict[str, Any] | None = None  # e.g. similar_movies for batch enrichment


class LLMClient(ABC):
    """Abstract interface for LLM clients."""

    @abstractmethod
    async def chat_completions_create(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """
        Generate a chat completion.

        Args:
            model: Model id on the inference server
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional OpenAI-style {"type": "json_object"} when supported

        Returns:
            LLMResponse with content and usage
        """
        pass

    async def chat_completions_create_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncGenerator[str, None]:
        """Stream text deltas (OpenAI-style SSE). Default: single chunk from non-streaming call."""
        resp = await self.chat_completions_create(model, messages, temperature, max_tokens)
        if resp.content:
            yield resp.content


class FakeLLMClient(LLMClient):
    """
    Deterministic fake LLM client for offline testing.

    Returns predetermined responses based on intent and messages.
    """

    def __init__(self) -> None:
        """Initialize fake LLM client."""
        pass

    async def chat_completions_create(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """
        Generate a fake response based on messages.

        Detects:
        - Intent from messages (director_info, cast_info, etc.)
        - Whether this is a repair/correction request
        - Entity names from messages
        """
        # Combine all messages to analyze
        full_text = "\n".join([msg.get("content", "") for msg in messages])
        full_text_lower = full_text.lower()

        # Extract user query from messages (look for user message or "User Question:")
        user_query = ""
        for msg in messages:
            content = msg.get("content", "")
            if msg.get("role") == "user":
                # Extract just the question part (before "EVIDENCE:" if present)
                if "EVIDENCE:" in content:
                    user_query = content.split("EVIDENCE:")[0].strip()
                elif "User Question:" in content:
                    user_query = content.split("User Question:")[1].strip()
                else:
                    user_query = content.strip()
                break

        # Check if this is a correction/repair request
        is_repair = any(
            "correction" in msg.get("content", "").lower() or
            "fix" in msg.get("content", "").lower() or
            "violation" in msg.get("content", "").lower() or
            "error" in msg.get("content", "").lower()
            for msg in messages
        )

        # Extract entities (movie titles, director names) from full text
        movie_title = self._extract_movie_title(full_text)
        director_name = self._extract_director_name(full_text)

        # Detect intent from user query (more reliable than full text)
        intent = self._detect_intent(user_query.lower() if user_query else full_text_lower, messages)

        # Generate response based on intent and context
        if is_repair:
            # For repair requests, return a minimal corrected response
            return self._generate_repair_response(intent, movie_title, director_name, full_text_lower)
        elif intent == "director_info":
            return self._generate_director_response(movie_title, director_name)
        elif intent == "cast_info":
            return self._generate_cast_response(movie_title, full_text_lower)
        elif intent == "release_date":
            return self._generate_release_date_response(movie_title, full_text_lower)
        elif intent == "runtime":
            return self._generate_runtime_response(movie_title, full_text_lower)
        elif intent == "where_to_watch" or intent == "availability":
            return self._generate_availability_response(movie_title, full_text_lower, intent)
        elif intent == "recommendation":
            return self._generate_recommendation_response(movie_title, full_text_lower)
        elif intent == "comparison":
            return self._generate_comparison_response(movie_title, full_text_lower)
        elif intent == "forbidden_test":
            # Negative test: return response with forbidden terms
            return self._generate_forbidden_terms_response(movie_title, director_name)
        elif intent == "verbosity_test":
            # Negative test: return overly verbose response
            return self._generate_verbose_response(movie_title, director_name)
        elif intent == "freshness_missing":
            # Negative test: return response missing freshness timestamp
            return self._generate_freshness_missing_response(movie_title, full_text_lower)
        else:
            # Default response
            return LLMResponse(
                content=f"{movie_title or 'The movie'} information is available.",
                usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
            )

    def _detect_intent(self, text_lower: str, messages: list[dict[str, str]]) -> str:
        """Detect intent from message content."""
        # Extract user query from messages (usually in user message)
        user_query_lower = ""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Extract just the question part (before "EVIDENCE:" if present)
                if "EVIDENCE:" in content:
                    user_query_lower = content.split("EVIDENCE:")[0].strip().lower()
                elif "User Question:" in content:
                    user_query_lower = content.split("User Question:")[1].strip().lower()
                else:
                    user_query_lower = content.strip().lower()
                break

        # Use user query for intent detection (more reliable than full text)
        text_to_check = user_query_lower if user_query_lower else text_lower

        # Check for test markers FIRST (before intent detection)
        if "freshness_test" in text_to_check:
            return "freshness_missing"
        elif "forbidden_test" in text_to_check:
            return "forbidden_test"
        elif "verbosity_test" in text_to_check:
            return "verbosity_test"

        # Check for specific intents in user query (priority order matters)
        if "compare" in text_to_check:
            return "comparison"
        elif (
            "recommend" in text_to_check
            or ("similar" in text_to_check and ("movie" in text_to_check or "movies" in text_to_check))
            or ("like" in text_to_check and ("movie" in text_to_check or "movies" in text_to_check))
        ):
            return "recommendation"
        elif "where" in text_to_check and ("watch" in text_to_check or "stream" in text_to_check):
            return "where_to_watch"
        elif "available" in text_to_check or ("streaming" in text_to_check and "where" not in text_to_check):
            return "availability"
        elif "director" in text_to_check or "directed by" in text_to_check or "directed" in text_to_check:
            return "director_info"
        elif "cast" in text_to_check or "starred" in text_to_check or "who was in" in text_to_check:
            return "cast_info"
        elif "release" in text_to_check or "when was" in text_to_check or "came out" in text_to_check:
            return "release_date"
        elif "runtime" in text_to_check or "how long" in text_to_check or "length" in text_to_check:
            return "runtime"

        # Fallback to general_info
        return "general_info"

    def _extract_movie_title(self, text: str) -> str | None:
        """Extract movie title from text."""
        # Common movie titles in test scenarios
        titles = [
            "The Matrix", "Inglourious Basterds", "Dune", "Inception",
            "Pulp Fiction", "Avatar", "Interstellar", "The Godfather",
            "Parasite", "Fight Club", "Dr. Strangelove", "It's a Wonderful Life",
            "King Kong", "The Grand Budapest Hotel", "Get Out"
        ]
        for title in titles:
            if title.lower() in text.lower():
                return title
        return None

    def _extract_director_name(self, text: str) -> str | None:
        """Extract director name from evidence or context."""
        # Common directors in test scenarios
        directors = {
            "matrix": "the Wachowskis",
            "pulp fiction": "Quentin Tarantino",
            "parasite": "Bong Joon-ho",
            "fight club": "David Fincher",
            "dr. strangelove": "Stanley Kubrick",
            "it's a wonderful life": "Frank Capra",
            "godfather": "Francis Ford Coppola",
            "dune": "Denis Villeneuve",
            "inception": "Christopher Nolan",
            "interstellar": "Christopher Nolan",
        }
        text_lower = text.lower()
        for key, director in directors.items():
            if key in text_lower:
                return director
        return None

    def _generate_director_response(self, movie_title: str | None, director_name: str | None) -> LLMResponse:
        """Generate director_info response."""
        if movie_title and director_name:
            content = f"{movie_title} was directed by {director_name}."
        elif movie_title:
            content = f"{movie_title} was directed by the director."
        else:
            content = "The movie was directed by the director."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 150, "completion_tokens": 30, "total_tokens": 180}
        )

    def _generate_cast_response(self, movie_title: str | None, text_lower: str) -> LLMResponse:
        """Generate cast_info response."""
        # Extract cast from evidence if available
        cast_members = []
        if "brad pitt" in text_lower:
            cast_members.append("Brad Pitt")
        if "christoph waltz" in text_lower:
            cast_members.append("Christoph Waltz")
        if "sam worthington" in text_lower:
            cast_members.append("Sam Worthington")

        if movie_title and cast_members:
            content = f"{movie_title} stars {', '.join(cast_members)}."
        elif movie_title:
            content = f"{movie_title} features a talented cast."
        else:
            content = "The movie features a talented cast."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 200, "completion_tokens": 40, "total_tokens": 240}
        )

    def _generate_release_date_response(self, movie_title: str | None, text_lower: str) -> LLMResponse:
        """Generate release_date response."""
        # Extract year from evidence if available
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', text_lower)
        year = year_match.group(1) if year_match else None

        if movie_title and year:
            content = f"{movie_title} was released in {year}."
        elif movie_title:
            content = f"{movie_title} was released in the past."
        else:
            content = "The movie was released previously."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 180, "completion_tokens": 25, "total_tokens": 205}
        )

    def _generate_runtime_response(self, movie_title: str | None, text_lower: str) -> LLMResponse:
        """Generate runtime response."""
        # Extract runtime from evidence if available
        runtime_match = re.search(r'(\d+)\s*minutes?', text_lower)
        runtime = runtime_match.group(1) if runtime_match else None

        if movie_title and runtime:
            content = f"{movie_title} has a runtime of {runtime} minutes."
        elif movie_title:
            content = f"{movie_title} has a runtime of approximately 120 minutes."
        else:
            content = "The movie has a runtime of approximately 120 minutes."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 170, "completion_tokens": 25, "total_tokens": 195}
        )

    def _generate_availability_response(
        self,
        movie_title: str | None,
        text_lower: str,
        intent: str
    ) -> LLMResponse:
        """Generate availability/where_to_watch response (always includes timestamp for freshness)."""
        # Always include freshness timestamp for availability queries
        platforms = []
        if "netflix" in text_lower:
            platforms.append("Netflix")
        if "hulu" in text_lower:
            platforms.append("Hulu")
        if "hbo max" in text_lower or "hbo" in text_lower:
            platforms.append("HBO Max")
        if "prime video" in text_lower or "amazon" in text_lower:
            platforms.append("Amazon Prime Video")

        if movie_title:
            # Always include timestamp for availability queries
            content = f"As of December 2024, {movie_title} is available on {', '.join(platforms) if platforms else 'various streaming platforms'}."
        else:
            content = "As of December 2024, the movie is available on various streaming platforms."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}
        )

    def _generate_recommendation_response(self, movie_title: str | None, text_lower: str) -> LLMResponse:
        """Generate recommendation response (must be at least 5 sentences)."""
        similar_movies: list[str] = []
        if "matrix" in text_lower:
            similar_movies = ["Inception", "Blade Runner", "The Terminator"]
        elif "pulp fiction" in text_lower:
            similar_movies = ["Reservoir Dogs", "Kill Bill", "Django Unchained"]
        elif "avatar" in text_lower:
            similar_movies = ["Dune (2021)", "Interstellar (2014)", "The Last Airbender (2010)", "District 9 (2009)"]

        if movie_title and similar_movies:
            content = f"Movies similar to {movie_title} include {', '.join(similar_movies)}. These films share similar themes and styles. Each offers a unique perspective on storytelling. They are perfect for fans of {movie_title}'s distinctive approach. If you enjoyed {movie_title}, these films will likely appeal to you."
        elif movie_title:
            content = f"Movies similar to {movie_title} include several films with similar themes and styles. These films share common elements that make them appealing. Each offers a unique perspective on storytelling. They are perfect for fans of {movie_title}'s distinctive approach. If you enjoyed {movie_title}, these films will likely appeal to you."
        else:
            content = "There are several movies with similar themes and styles. These films share common elements that make them appealing. Each offers a unique perspective on storytelling. They are perfect for fans seeking similar experiences. If you enjoyed the original film, these will likely appeal to you."
        metadata: dict[str, Any] | None = {"similar_movies": similar_movies} if similar_movies else None
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 250, "completion_tokens": 80, "total_tokens": 330},
            metadata=metadata
        )

    def _generate_comparison_response(self, movie_title: str | None, text_lower: str) -> LLMResponse:
        """Generate comparison response (must be at least 8 sentences)."""
        movies = []
        if "matrix" in text_lower:
            movies.append("The Matrix")
        if "inception" in text_lower:
            movies.append("Inception")

        if len(movies) >= 2:
            content = f"{movies[0]} and {movies[1]} are both science fiction films. {movies[0]} was directed by one director. {movies[1]} was directed by another director. Both films feature innovative visual effects. They explore complex themes and narratives. Each film represents a significant achievement in cinema. They have influenced subsequent science fiction films. Both are considered classics of the genre."
        elif movie_title:
            # Fallback: generate 8+ sentences even with one movie
            content = f"{movie_title} compares favorably with other films in its genre. It demonstrates unique storytelling techniques. The film features innovative visual effects. It explores complex themes and narratives. The movie represents a significant achievement in cinema. It has influenced subsequent films in the genre. The film is considered a classic. It continues to inspire filmmakers today."
        else:
            content = "These films compare favorably with each other. They demonstrate unique storytelling techniques. The films feature innovative visual effects. They explore complex themes and narratives. Each represents a significant achievement in cinema. They have influenced subsequent films. Both are considered classics. They continue to inspire filmmakers today."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 300, "completion_tokens": 100, "total_tokens": 400}
        )

    def _generate_forbidden_terms_response(
        self,
        movie_title: str | None,
        director_name: str | None
    ) -> LLMResponse:
        """Generate response with forbidden terms (for negative testing)."""
        if movie_title and director_name:
            content = f"{movie_title} was directed by {director_name} according to Tier A Kaggle dataset."
        elif movie_title:
            content = f"{movie_title} was directed by the director according to Tier A Kaggle dataset."
        else:
            content = "The movie was directed by the director according to Tier A Kaggle dataset."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 150, "completion_tokens": 35, "total_tokens": 185}
        )

    def _generate_verbose_response(
        self,
        movie_title: str | None,
        director_name: str | None
    ) -> LLMResponse:
        """Generate overly verbose response (for negative testing)."""
        if movie_title and director_name:
            content = f"{movie_title} is a groundbreaking film that was directed by {director_name}. This film represents a significant achievement in cinema. It features innovative storytelling techniques. The director's vision is clearly evident throughout. The film has had a lasting impact on the industry. It continues to influence filmmakers today. Many consider it one of the greatest films ever made."
        elif movie_title:
            content = f"{movie_title} is a groundbreaking film directed by an acclaimed director. This film represents a significant achievement in cinema."
        else:
            content = "The movie is a groundbreaking film directed by an acclaimed director."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 150, "completion_tokens": 120, "total_tokens": 270}
        )

    def _generate_freshness_missing_response(
        self,
        movie_title: str | None,
        text_lower: str
    ) -> LLMResponse:
        """Generate response missing freshness timestamp (for negative testing)."""
        platforms = []
        if "netflix" in text_lower:
            platforms.append("Netflix")
        if "hulu" in text_lower:
            platforms.append("Hulu")

        if movie_title:
            content = f"{movie_title} is available on {', '.join(platforms) if platforms else 'various streaming platforms'}."
        else:
            content = "The movie is available on various streaming platforms."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 200, "completion_tokens": 30, "total_tokens": 230}
        )

    def _generate_repair_response(
        self,
        intent: str,
        movie_title: str | None,
        director_name: str | None,
        text_lower: str
    ) -> LLMResponse:
        """Generate minimal corrected response for repair requests."""
        if intent == "director_info":
            if movie_title and director_name:
                content = f"{movie_title} was directed by {director_name}."
            elif movie_title:
                content = f"{movie_title} was directed by the director."
            else:
                content = "The movie was directed by the director."
        elif intent == "availability" or intent == "where_to_watch":
            platforms = []
            if "netflix" in text_lower:
                platforms.append("Netflix")
            if "hulu" in text_lower:
                platforms.append("Hulu")
            if movie_title:
                content = f"As of December 2024, {movie_title} is available on {', '.join(platforms) if platforms else 'various streaming platforms'}."
            else:
                content = "As of December 2024, the movie is available on various streaming platforms."
        else:
            content = f"{movie_title or 'The movie'} information."
        return LLMResponse(
            content=content,
            usage={"prompt_tokens": 200, "completion_tokens": 30, "total_tokens": 230}
        )


class HttpChatLLMClient(LLMClient):
    """OpenAI-compatible Chat Completions over HTTP (Llama, vLLM, LM Studio, etc.)."""

    def __init__(self, http_client: httpx.AsyncClient, api_key: str = "") -> None:
        self._http = http_client
        self._api_key = (api_key or "").strip()

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    async def chat_completions_create(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        try:
            r = await self._http.post("chat/completions", json=body, headers=self._headers())
        except httpx.TimeoutException as e:
            raise RuntimeError(f"LLM request timed out: {e}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"LLM connection error: {e}") from e

        if r.status_code == 401:
            raise ValueError("LLM returned 401 Unauthorized. Check CINEMIND_LLM_API_KEY if the server requires it.")
        if r.status_code == 404:
            raise ValueError(
                f"LLM returned 404. Check CINEMIND_LLM_BASE_URL and that the server exposes "
                f"/v1/chat/completions. Response: {r.text[:500]}"
            )
        if r.status_code >= 400:
            raise ValueError(f"LLM error HTTP {r.status_code}: {r.text[:800]}")

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned non-JSON: {r.text[:500]}") from e

        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"LLM response missing choices: {str(data)[:800]}")

        message = (choices[0].get("message") or {})
        content = message.get("content")
        if content is None:
            content = ""
        usage_raw = data.get("usage")
        usage: dict[str, int] | None = None
        if isinstance(usage_raw, dict):
            usage = {k: int(v) for k, v in usage_raw.items() if isinstance(v, (int, float))}

        return LLMResponse(content=content, usage=usage)

    async def chat_completions_create_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncGenerator[str, None]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with self._http.stream(
                "POST",
                "chat/completions",
                json=body,
                headers=self._headers(),
            ) as response:
                if response.status_code == 401:
                    raise ValueError(
                        "LLM returned 401 Unauthorized. Check CINEMIND_LLM_API_KEY if the server requires it."
                    )
                if response.status_code >= 400:
                    text = (await response.aread()).decode(errors="replace")
                    raise ValueError(f"LLM stream error HTTP {response.status_code}: {text[:800]}")

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    for choice in obj.get("choices") or []:
                        delta = choice.get("delta") or {}
                        piece = delta.get("content") or ""
                        if piece:
                            yield piece
        except httpx.TimeoutException as e:
            raise RuntimeError(f"LLM stream timed out: {e}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"LLM stream connection error: {e}") from e

