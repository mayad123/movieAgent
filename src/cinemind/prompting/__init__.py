"""
Prompt building pipeline for CineMind.
"""

from .evidence_formatter import EvidenceFormatResult, EvidenceFormatter, FormattedEvidenceItem
from .output_validator import OutputValidator, ValidationResult
from .prompt_builder import EvidenceBundle, PromptArtifacts, PromptBuilder
from .templates import RESPONSE_TEMPLATES, ResponseTemplate, get_template, list_all_templates
from .versions import PROMPT_VERSIONS, compare_versions, get_prompt_version, list_versions

__all__ = [
    "PROMPT_VERSIONS",
    "RESPONSE_TEMPLATES",
    "EvidenceBundle",
    "EvidenceFormatResult",
    "EvidenceFormatter",
    "FormattedEvidenceItem",
    "OutputValidator",
    "PromptArtifacts",
    "PromptBuilder",
    "ResponseTemplate",
    "ValidationResult",
    "compare_versions",
    "get_prompt_version",
    "get_template",
    "list_all_templates",
    "list_versions",
]
