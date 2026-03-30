"""
Output validator for CineMind responses.
Checks generated responses against response contract templates.
"""
import logging
import re
from dataclasses import dataclass

from .templates import ResponseTemplate

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of response validation."""
    is_valid: bool
    violations: list[str]  # List of violation descriptions
    corrected_text: str | None = None  # Lightly corrected text (if auto-fix applied)
    requires_reprompt: bool = False  # Whether to re-prompt with strict correction

    def has_violations(self) -> bool:
        """Check if there are any violations."""
        return len(self.violations) > 0


class OutputValidator:
    """
    Validates generated responses against response contract templates.
    """

    def __init__(self, enable_auto_fix: bool = True):
        """
        Initialize output validator.

        Args:
            enable_auto_fix: If True, attempt to auto-fix violations (forbidden terms only).
                            If False, always require re-prompt for violations.
        """
        self.enable_auto_fix = enable_auto_fix

    def validate(
        self,
        response_text: str,
        template: ResponseTemplate,
        need_freshness: bool = False
    ) -> ValidationResult:
        """
        Validate response against template contract.

        Args:
            response_text: Generated response text
            template: ResponseTemplate with contract requirements
            need_freshness: Whether freshness/timestamp is required

        Returns:
            ValidationResult with violations and optional corrected text
        """
        violations = []
        corrected_text = response_text

        # Check forbidden terms and boilerplate
        forbidden_violations = self._check_forbidden_terms(response_text, template.forbidden_terms)
        violations.extend(forbidden_violations)

        # Auto-fix forbidden terms if enabled
        if self.enable_auto_fix and forbidden_violations:
            corrected_text = self._fix_forbidden_terms(corrected_text, template.forbidden_terms)
            logger.debug("Auto-fixed forbidden terms in response")

        # Check verbosity (max sentences/words)
        verbosity_violations = self._check_verbosity(response_text, template)
        violations.extend(verbosity_violations)

        # Check and normalize boilerplate/structure near the top of the response
        boilerplate_violations, corrected_text = self._check_and_fix_boilerplate(corrected_text)
        violations.extend(boilerplate_violations)

        markdown_violations, corrected_text = self._normalize_markdown_artifacts(corrected_text)
        violations.extend(markdown_violations)

        # Check freshness requirement
        freshness_violations = []
        if need_freshness and "include_as_of_date" in template.required_elements:
            freshness_violations = self._check_freshness(response_text)
            violations.extend(freshness_violations)

        # Determine if re-prompt is needed
        # Re-prompt if: verbosity violations OR (forbidden terms without auto-fix) OR freshness violations
        requires_reprompt = (
            bool(verbosity_violations) or
            (bool(forbidden_violations) and not self.enable_auto_fix) or
            bool(freshness_violations)
        )

        # Ship post-processed text whenever it differs (markdown/boilerplate/forbidden fix)
        text_changed = corrected_text != response_text

        return ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
            corrected_text=corrected_text if text_changed else None,
            requires_reprompt=requires_reprompt
        )

    def _check_forbidden_terms(self, text: str, forbidden_terms: list[str]) -> list[str]:
        """Check for forbidden terms in response."""
        violations = []
        text_lower = text.lower()

        for term in forbidden_terms:
            # Case-insensitive search (with word boundaries to avoid false positives)
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            if re.search(pattern, text_lower):
                violations.append(f"Forbidden term detected: '{term}'")

        return violations

    def _fix_forbidden_terms(self, text: str, forbidden_terms: list[str]) -> str:
        """
        Lightly rewrite text to remove forbidden terms.
        This is a simple replacement strategy - for complex cases, re-prompting is preferred.
        """
        corrected = text

        # Map forbidden terms to natural replacements (or remove context)
        replacements = {
            "tier a": "",
            "tier b": "",
            "tier c": "",
            "tier": "",
            "kaggle": "structured data",
            "tavily": "search results",
            "dataset": "data source",
            "confidence framework": "",
            "source tier": "",
        }

        # Apply replacements (case-insensitive)
        for forbidden, replacement in replacements.items():
            pattern = re.compile(re.escape(forbidden), re.IGNORECASE)
            if replacement:
                # Replace with natural alternative
                corrected = pattern.sub(replacement, corrected)
            else:
                # Remove the term and clean up surrounding whitespace
                corrected = pattern.sub("", corrected)
                corrected = re.sub(r'\s+', ' ', corrected)  # Clean up multiple spaces

        # Clean up any awkward phrasing
        corrected = re.sub(r'\s+', ' ', corrected)  # Multiple spaces
        corrected = corrected.strip()

        return corrected

    def _check_verbosity(self, text: str, template: ResponseTemplate) -> list[str]:
        """Check verbosity constraints (max sentences/words)."""
        violations = []

        # Count sentences
        sentences = self._count_sentences(text)

        # Count words
        words = len(text.split())

        # Check max sentences
        if template.max_sentences and sentences > template.max_sentences:
            violations.append(
                f"Exceeds max sentences: {sentences} > {template.max_sentences} "
                f"(template: {template.template_id})"
            )

        # Check max words
        if template.max_words and words > template.max_words:
            violations.append(
                f"Exceeds max words: {words} > {template.max_words} "
                f"(template: {template.template_id})"
            )

        # Check min sentences
        if template.min_sentences and sentences < template.min_sentences:
            violations.append(
                f"Below min sentences: {sentences} < {template.min_sentences} "
                f"(template: {template.template_id})"
            )

        return violations

    def _count_sentences(self, text: str) -> int:
        """Count sentences in text (simple heuristic)."""
        # Remove common abbreviations that end with periods
        text = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Jr|Sr|Inc|Ltd|etc|vs|e\.g|i\.e)\.', r'\1', text)

        # Count sentence-ending punctuation
        sentences = len(re.findall(r'[.!?]+', text))

        # If no punctuation found, treat as one sentence if non-empty
        if sentences == 0 and text.strip():
            sentences = 1

        return sentences

    def _check_freshness(self, text: str) -> list[str]:
        """Check if freshness/timestamp language is present when required."""
        violations = []

        # Check for freshness indicators
        freshness_patterns = [
            r'as of',
            r'as of \d{4}',  # "as of 2024"
            r'currently',
            r'as of today',
            r'latest',
            r'recent',
            r'\d{4}-\d{2}-\d{2}',  # ISO date
            r'(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}',  # "January 1, 2024"
        ]

        text_lower = text.lower()
        has_freshness = any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in freshness_patterns)

        if not has_freshness:
            violations.append(
                "Missing freshness/timestamp language (required: 'as of [date]', 'currently', etc.)"
            )

        return violations

    def _check_and_fix_boilerplate(self, text: str) -> tuple[list[str], str]:
        """
        Detect and lightly normalize common boilerplate and structural issues
        near the beginning of the response (e.g., \"As an AI model...\", duplicated greetings).
        """
        violations: list[str] = []
        corrected = text

        # Work on a limited prefix to avoid unnecessary processing on long answers
        head = corrected[:1000]

        # Detect and remove common AI self-references at the very start
        boilerplate_patterns = [
            r"^\s*as an ai[^.]*\.\s*",
            r"^\s*as an ai language model[^.]*\.\s*",
            r"^\s*i am an ai[^.]*\.\s*",
        ]
        for pattern in boilerplate_patterns:
            if re.search(pattern, head, flags=re.IGNORECASE):
                violations.append("Boilerplate AI self-reference removed from response opening.")
                corrected = re.sub(pattern, "", corrected, flags=re.IGNORECASE)
                head = corrected[:1000]
                break

        # Normalize list bullets: convert leading \"* \" or \"• \" to \"- \" for consistency
        lines = corrected.splitlines()
        normalized_lines = []
        list_bullet_changed = False
        for line in lines:
            stripped = line.lstrip()
            prefix_len = len(line) - len(stripped)
            if stripped.startswith("* ") or stripped.startswith("• "):
                normalized_lines.append(line[:prefix_len] + "- " + stripped[2:])
                list_bullet_changed = True
            else:
                normalized_lines.append(line)
        if list_bullet_changed:
            violations.append("Normalized list bullets (*, •) to '-' for frontend rendering consistency.")
        corrected = "\n".join(normalized_lines)

        # Collapse excessive blank lines (3+ → 2) to keep paragraph breaks tidy
        collapsed = re.sub(r"\n{3,}", "\n\n", corrected)
        if collapsed != corrected:
            violations.append("Collapsed excessive blank lines in response.")
            corrected = collapsed

        return violations, corrected

    def _normalize_markdown_artifacts(self, text: str) -> tuple[list[str], str]:
        """
        Strip common markdown the chat UI does not render (**, ***, horizontal rules).
        Unwraps **title**; removes decorative asterisks after list markers (e.g. 1. ***).
        """
        corrected = text

        corrected = re.sub(r"(?m)^\s*\*{3,}\s*$", "", corrected)
        corrected = re.sub(r"(?m)^\s*-{3,}\s*$", "", corrected)
        corrected = re.sub(r"\*\*\*([^*]+?)\*\*\*", r"\1", corrected)
        corrected = re.sub(r"\*\*([^*]+?)\*\*", r"\1", corrected)
        corrected = re.sub(r"(?m)^(\s*\d+\.\s*)\*{2,}\s*", r"\1", corrected)
        corrected = re.sub(r"(?m)^(\s*-\s*)\*{2,}\s*", r"\1", corrected)
        corrected = re.sub(r"\n{3,}", "\n\n", corrected)

        # Do not add violations (would trigger reprompt); this is a display/UX normalize only.
        return [], corrected

    def build_correction_instruction(self, violations: list[str], template: ResponseTemplate) -> str:
        """
        Build a strict correction instruction for re-prompting.

        Args:
            violations: List of violation descriptions
            template: ResponseTemplate with contract requirements

        Returns:
            Correction instruction text
        """
        instruction_parts = [
            "CORRECTION REQUIRED: The previous response violated the response contract.",
            "",
            "VIOLATIONS:"
        ]

        for i, violation in enumerate(violations, 1):
            instruction_parts.append(f"{i}. {violation}")

        instruction_parts.append("")
        instruction_parts.append("STRICT REQUIREMENTS:")
        instruction_parts.append(template.to_instructions())

        instruction_parts.append("")
        instruction_parts.append(
            "Please regenerate the response following ALL requirements above. "
            "Do not include any forbidden terms. Respect the length limits exactly."
        )

        return "\n".join(instruction_parts)

