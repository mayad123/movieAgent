"""
Request tagging and classification for CineMind.
Hybrid three-layer classification system: Rules → LLM → Guardrails
"""

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Valid request types
REQUEST_TYPES = {
    "info": "General information request",
    "recs": "Recommendation request",
    "comparison": "Comparison between movies/directors/etc",
    "spoiler": "Request with spoilers",
    "release-date": "Release date inquiry",
    "fact-check": "Fact verification request",
}

# Valid outcomes
OUTCOMES = {
    "success": "Request was successfully answered",
    "unclear": "Response was unclear or ambiguous",
    "hallucination": "Response contained hallucinations or incorrect information",
    "user-corrected": "User provided corrections to the response",
}


@dataclass
class ClassificationResult:
    """Result of classification with metadata."""

    predicted_type: str
    rule_hit: str | None = None  # Which rule matched, or None if LLM was used
    llm_used: bool = False
    confidence: float = 1.0
    entities: list[str] = None  # Extracted entities (titles, persons)
    freshness_signal: bool = (
        False  # Weak signal: whether query might need fresh data (final decision made by ToolPlanner)
    )
    original_llm_type: str | None = None  # LLM prediction before guardrails

    def __post_init__(self):
        if self.entities is None:
            self.entities = []


class HybridClassifier:
    """
    Three-layer hybrid classification system:
    A) Fast deterministic rules (40-70% coverage)
    B) LLM classification for ambiguous cases
    C) Guardrails/overrides for edge cases
    """

    def __init__(self):
        # Layer A: Fast deterministic rules - optimized for obvious cases
        self.rules = {
            "recs": [
                # Strong signals
                r"\b(recommend|suggest|recommendation)\b",
                r"\b(similar to|like|similar|alike)\b",
                r"\b(should i watch|worth watching|watch next|what to watch)\b",
                r"\b(best|top|favorite|great|good)\s+(movie|film|movies|films)\b",
                r"\b(movies|films)\s+(like|similar to)\b",
            ],
            "spoiler": [
                # Strong signals
                r"\b(spoiler|spoilers)\b",
                r"\b(ending|endings|how does it end|how did it end)\b",
                r"\b(what happens|what happened|plot|twist|twists)\b",
                r"\b(explain the ending|explain the plot)\b",
                r"\b(dies|kills|death|deaths|killed)\b",
            ],
            "release-date": [
                # Strong signals
                r"\b(out yet|is it out|when is.*out|when does.*come out)\b",
                r"\b(release date|release dates|released|premiere|premieres)\b",
                r"\b(coming out|when.*coming out|debut)\b",
                r"\b(is.*out|was.*released|release)\b",
            ],
            "info": [
                # Strong signals - specific question patterns
                r"^(who directed|who starred|who stars|who wrote|who produced)\b",
                r"^(when was|when did|when is|when are)\b",
                r"^(what is|what are|what was|what were)\b",
                r"^(where was|where is|where are)\b",
                r"^(how many|how much|how long)\b",
            ],
            "comparison": [
                # Strong signals
                r"\b(compare|comparison|vs\.|versus|vs\s)\b",
                r"\b(difference|differences|different|better|worse)\b",
                r"\b(which is|which are|which one|which movie)\b",
                r"\b(similar|similarities|alike|same)\b",
            ],
            "fact-check": [
                # Strong signals
                r"\b(is it true|is this true|is that true)\b",
                r"\b(did.*really|does.*really|was.*really)\b",
                r"\b(verify|confirm|fact check|fact-check)\b",
                r"\b(accurate|correct|true|false)\b",
            ],
        }

        # Layer C: Guardrail patterns (override rules)
        self.guardrails = [
            # Override: If contains "similar" + "recommend" → recs (even if LLM says info)
            (
                lambda q: bool(
                    re.search(r"\b(similar|like)\b", q.lower()) and re.search(r"\b(recommend|suggest)\b", q.lower())
                ),
                "recs",
                "guardrail: similar+recommend",
            ),
            # Override: If "is it out yet" or "out yet" → release-date (even if LLM says info)
            (
                lambda q: bool(re.search(r"\b(is it out yet|out yet|is.*out yet)\b", q.lower())),
                "release-date",
                "guardrail: out yet",
            ),
            # Override: If "explain the ending" → spoiler (even if LLM says info)
            (
                lambda q: bool(re.search(r"\b(explain the ending|explain ending|ending of)\b", q.lower())),
                "spoiler",
                "guardrail: explain ending",
            ),
            # Override: If "movies in order" → info (even if LLM says recs)
            (
                lambda q: bool(re.search(r"\b(movies in order|order of|chronological order)\b", q.lower())),
                "info",
                "guardrail: movies in order",
            ),
        ]

    def classify_with_rules(self, query: str) -> tuple[str, str] | None:
        """
        Layer A: Fast deterministic rules.
        Returns (type, rule_name) if match found, None otherwise.
        """
        query_lower = _ = query.lower()

        # Check rules in priority order (most specific first)
        for req_type, patterns in self.rules.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return (req_type, f"rule:{pattern[:30]}")

        return None

    async def classify_with_llm(self, query: str, client) -> ClassificationResult:
        """
        Layer B: LLM classification for ambiguous cases.
        Returns structured JSON with type, entities, freshness_signal, confidence.
        """
        try:
            from config import CINEMIND_LLM_SUPPORTS_JSON_MODE, LLM_MODEL

            from ..llm.client import LLMClient

            if not isinstance(client, LLMClient):
                raise TypeError("classify_with_llm expects an LLMClient instance")

            classification_prompt = f"""Classify this movie-related query and extract information.

Query: "{query}"

Respond with ONLY valid JSON in this exact format:
{{
  "type": "one of: info, recs, comparison, spoiler, release-date, fact-check",
  "entities": ["movie title", "person name", ...],
  "freshness_signal": true or false,
  "confidence": 0.0 to 1.0
}}

Rules:
- type: The primary intent category
- entities: List of movie titles, director names, actor names mentioned (empty array if none)
- freshness_signal: true if query might need current/up-to-date data (this is a weak signal - final decision is made by tool planner based on intent and entity year)
- confidence: How confident you are (0.0-1.0)

Respond with ONLY the JSON, nothing else."""

            response_format = {"type": "json_object"} if CINEMIND_LLM_SUPPORTS_JSON_MODE else None
            try:
                llm_resp = await client.chat_completions_create(
                    LLM_MODEL,
                    [
                        {
                            "role": "system",
                            "content": "You are a query classifier. Respond with ONLY valid JSON, no other text.",
                        },
                        {"role": "user", "content": classification_prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                    response_format=response_format,
                )
            except Exception as e:
                if response_format:
                    logger.warning("LLM JSON mode failed, retrying without response_format: %s", e)
                    llm_resp = await client.chat_completions_create(
                        LLM_MODEL,
                        [
                            {
                                "role": "system",
                                "content": "You are a query classifier. Respond with ONLY valid JSON, no other text.",
                            },
                            {"role": "user", "content": classification_prompt},
                        ],
                        temperature=0.1,
                        max_tokens=200,
                    )
                else:
                    raise

            result_text = (llm_resp.content or "").strip()

            # Try to parse JSON (handle cases where LLM adds extra text)
            try:
                # Extract JSON if wrapped in markdown code blocks
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()

                result_json = json.loads(result_text)
            except json.JSONDecodeError:
                # Fallback: try to extract JSON object
                json_match = re.search(r"\{[^}]+\}", result_text)
                if json_match:
                    result_json = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found in response")

            predicted_type = result_json.get("type", "info").lower()
            entities = result_json.get("entities", [])
            freshness_signal = result_json.get("freshness_signal", False)
            confidence = float(result_json.get("confidence", 0.7))

            # Validate type
            if predicted_type not in REQUEST_TYPES:
                predicted_type = "info"

            return ClassificationResult(
                predicted_type=predicted_type,
                rule_hit=None,
                llm_used=True,
                confidence=confidence,
                entities=entities if isinstance(entities, list) else [],
                freshness_signal=bool(freshness_signal),
                original_llm_type=predicted_type,
            )

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to rules")
            # Fallback to rules
            rule_result = self.classify_with_rules(query)
            if rule_result:
                return ClassificationResult(
                    predicted_type=rule_result[0],
                    rule_hit=rule_result[1],
                    llm_used=False,
                    confidence=0.6,  # Lower confidence for fallback
                    freshness_signal=False,
                )
            return ClassificationResult(
                predicted_type="info",
                rule_hit="fallback:default",
                llm_used=False,
                confidence=0.3,
                freshness_signal=False,
            )

    def apply_guardrails(self, query: str, classification: ClassificationResult) -> ClassificationResult:
        """
        Layer C: Guardrails/overrides for edge cases.
        Applies overrides based on strong signals that contradict the classification.
        """
        _ = query.lower()

        for guardrail_func, override_type, reason in self.guardrails:
            if guardrail_func(query) and classification.predicted_type != override_type:
                logger.info(
                    f"Guardrail applied: {reason} - overriding {classification.predicted_type} → {override_type}"
                )
                classification.predicted_type = override_type
                classification.rule_hit = reason
                classification.confidence = min(classification.confidence + 0.2, 1.0)  # Boost confidence

        return classification

    async def classify(self, query: str, client=None, force_llm: bool = False) -> ClassificationResult:
        """
        Main classification method using three-layer hybrid approach.

        Args:
            query: User query
            client: OpenAI client (required if LLM classification needed)
            force_llm: If True, skip rules and use LLM directly

        Returns:
            ClassificationResult with all metadata
        """
        # Layer A: Try fast rules first (unless forced to use LLM)
        if not force_llm:
            rule_result = self.classify_with_rules(query)
            if rule_result:
                classification = ClassificationResult(
                    predicted_type=rule_result[0],
                    rule_hit=rule_result[1],
                    llm_used=False,
                    confidence=0.85,  # High confidence for clear rule matches
                    freshness_signal=False,  # Rules don't set freshness signal
                )
                # Apply guardrails even for rule-based results
                classification = self.apply_guardrails(query, classification)
                return classification

        # Layer B: Use LLM for ambiguous cases
        if client:
            classification = await self.classify_with_llm(query, client)
        else:
            # No client available, fallback to rules
            rule_result = self.classify_with_rules(query)
            if rule_result:
                classification = ClassificationResult(
                    predicted_type=rule_result[0],
                    rule_hit=rule_result[1],
                    llm_used=False,
                    confidence=0.7,
                    freshness_signal=False,
                )
            else:
                classification = ClassificationResult(
                    predicted_type="info",
                    rule_hit="fallback:no_client",
                    llm_used=False,
                    confidence=0.5,
                    freshness_signal=False,
                )

        # Layer C: Apply guardrails
        classification = self.apply_guardrails(query, classification)

        return classification


# Backward compatibility: Keep old RequestTagger class
class RequestTagger:
    """Legacy tagger - wraps HybridClassifier for backward compatibility."""

    def __init__(self):
        self.classifier = HybridClassifier()

    def classify_request_type(self, query: str) -> str:
        """
        Classify the request type based on query content (rules only, for speed).

        Returns the most likely request type or 'info' as default.
        """
        rule_result = self.classifier.classify_with_rules(query)
        if rule_result:
            return rule_result[0]
        return "info"

    def validate_request_type(self, request_type: str) -> bool:
        """Validate that request type is in allowed list."""
        return request_type.lower() in REQUEST_TYPES

    def validate_outcome(self, outcome: str) -> bool:
        """Validate that outcome is in allowed list."""
        return outcome.lower() in OUTCOMES

    def get_request_type_description(self, request_type: str) -> str:
        """Get description for a request type."""
        return REQUEST_TYPES.get(request_type.lower(), "Unknown type")

    def get_outcome_description(self, outcome: str) -> str:
        """Get description for an outcome."""
        return OUTCOMES.get(outcome.lower(), "Unknown outcome")


# Legacy function for backward compatibility
async def classify_with_llm(query: str, client) -> str:
    """
    Legacy function: Use LLM to classify request type (returns just the type string).
    """
    classifier = HybridClassifier()
    result = await classifier.classify(query, client, force_llm=True)
    return result.predicted_type
