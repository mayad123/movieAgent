"""
Response contract templates for CineMind.
Defines deterministic verbosity, structure, and style per request_type/intent.
"""
from dataclasses import dataclass, field


@dataclass
class ResponseTemplate:
    """Template defining response contract for a request type/intent."""
    # Identifier
    template_id: str

    # Verbosity constraints
    max_sentences: int | None = None
    max_words: int | None = None
    min_sentences: int | None = None

    # Required elements
    required_elements: list[str] = field(default_factory=list)  # e.g., "answer_first", "include_as_of_date"

    # Forbidden output terms (should not appear in user-facing responses)
    forbidden_terms: list[str] = field(default_factory=list)  # e.g., "Tier", "dataset", "confidence framework"

    # Citation style requirements
    citation_style: str = "natural"  # "natural", "minimal", "none"
    citation_examples: list[str] = field(default_factory=list)  # e.g., "according to IMDb", "per Wikipedia"

    # Structure requirements
    structure_hints: list[str] = field(default_factory=list)  # e.g., "direct_answer", "list_format"

    def to_instructions(self) -> str:
        """Convert template to instruction text for RESPONSE INSTRUCTIONS block."""
        instructions = []

        # Verbosity constraints
        if self.max_sentences or self.max_words:
            verbosity_parts = []
            if self.max_sentences:
                verbosity_parts.append(f"maximum {self.max_sentences} sentence{'s' if self.max_sentences > 1 else ''}")
            if self.max_words:
                verbosity_parts.append(f"maximum {self.max_words} words")
            if verbosity_parts:
                instructions.append(f"Length: {' or '.join(verbosity_parts)}. Be concise and direct.")

        if self.min_sentences:
            instructions.append(f"Minimum {self.min_sentences} sentence{'s' if self.min_sentences > 1 else ''}.")

        # Required elements
        if self.required_elements:
            elements_text = []
            for element in self.required_elements:
                if element == "answer_first":
                    elements_text.append("Provide the direct answer immediately (first sentence)")
                elif element == "include_as_of_date":
                    elements_text.append("Include current date/time context (e.g., 'as of [date]', 'currently', 'as of today')")
                elif element == "include_year":
                    elements_text.append("Include release year when mentioning movies")
                elif element == "numbered_list":
                    elements_text.append("Use numbered list format")
                elif element == "bullet_list":
                    elements_text.append("Use bullet list format")
                else:
                    elements_text.append(element.replace("_", " ").title())

            if elements_text:
                instructions.append("Required elements: " + "; ".join(elements_text) + ".")

        # Structure hints
        if self.structure_hints:
            for hint in self.structure_hints:
                if hint == "direct_answer":
                    instructions.append("Structure: Lead with direct answer, then brief context if needed.")
                elif hint == "list_format":
                    instructions.append(
                        "Structure: Use short paragraphs for explanations and bullet or numbered lists for multi-item outputs."
                    )
                elif hint == "comparison_table":
                    instructions.append("Structure: Use comparison format, clearly distinguishing between items.")
                else:
                    instructions.append(f"Structure: {hint}")

        # Citation style
        if self.citation_style == "natural":
            instructions.append("Citation style: Cite sources naturally (e.g., 'according to IMDb', 'per Wikipedia'). Avoid technical source names.")
        elif self.citation_style == "minimal":
            instructions.append("Citation style: Minimal citations, only when necessary for credibility.")
        elif self.citation_style == "none":
            instructions.append("Citation style: No explicit citations needed.")

        # Forbidden terms
        if self.forbidden_terms:
            forbidden_text = ", ".join([f'"{term}"' for term in self.forbidden_terms])
            instructions.append(f"Forbidden terms: Never use these terms in the response: {forbidden_text}.")

        instructions.append(
            "Plain text only: do not use markdown emphasis or dividers (no **, ***, __, or lines of only * or -). "
            "For lists use lines starting with 1. or 2. or with - ."
        )

        return "\n".join(instructions)


# Template registry by request_type/intent
RESPONSE_TEMPLATES: dict[str, ResponseTemplate] = {
    # Simple fact queries - very concise
    "director_info": ResponseTemplate(
        template_id="director_info",
        max_sentences=2,
        max_words=50,
        required_elements=["answer_first"],
        forbidden_terms=["Tier", "Tier A", "Tier B", "Tier C", "dataset", "Kaggle", "Tavily", "confidence framework", "source tier"],
        citation_style="natural",
        citation_examples=["according to IMDb", "per Wikipedia"],
        structure_hints=["direct_answer"]
    ),

    "cast_info": ResponseTemplate(
        template_id="cast_info",
        max_sentences=3,
        max_words=75,
        required_elements=["answer_first", "numbered_list"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily", "confidence framework"],
        citation_style="natural",
        structure_hints=["list_format"]
    ),

    "release_date": ResponseTemplate(
        template_id="release_date",
        max_sentences=2,
        max_words=40,
        required_elements=["answer_first", "include_year"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily"],
        citation_style="natural",
        structure_hints=["direct_answer"]
    ),

    "release_year": ResponseTemplate(
        template_id="release_year",
        max_sentences=2,
        max_words=40,
        required_elements=["answer_first", "include_year"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily"],
        citation_style="natural",
        structure_hints=["direct_answer"]
    ),

    "runtime": ResponseTemplate(
        template_id="runtime",
        max_sentences=2,
        max_words=30,
        required_elements=["answer_first"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily"],
        citation_style="minimal",
        structure_hints=["direct_answer"]
    ),

    # Freshness-sensitive queries
    "where_to_watch": ResponseTemplate(
        template_id="where_to_watch",
        max_sentences=4,
        max_words=100,
        required_elements=["answer_first", "include_as_of_date"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily", "confidence framework"],
        citation_style="natural",
        structure_hints=["list_format"]
    ),

    "availability": ResponseTemplate(
        template_id="availability",
        max_sentences=3,
        max_words=80,
        required_elements=["answer_first", "include_as_of_date"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily"],
        citation_style="natural",
        structure_hints=["direct_answer"]
    ),

    # Recommendations
    "recommendation": ResponseTemplate(
        template_id="recommendation",
        max_sentences=15,
        max_words=300,
        min_sentences=5,
        required_elements=["numbered_list", "include_year"],
        forbidden_terms=["Tier", "Tier A", "Tier B", "Tier C", "dataset", "Kaggle", "Tavily", "confidence framework"],
        citation_style="natural",
        structure_hints=["list_format"]
    ),

    "similar_movies": ResponseTemplate(
        template_id="similar_movies",
        max_sentences=12,
        max_words=250,
        required_elements=["numbered_list", "include_year"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily"],
        citation_style="minimal",
        structure_hints=["list_format"]
    ),

    # Comparison/analysis
    "comparison": ResponseTemplate(
        template_id="comparison",
        max_sentences=20,
        max_words=400,
        min_sentences=8,
        required_elements=["include_year"],
        forbidden_terms=["Tier", "Tier A", "Tier B", "Tier C", "dataset", "Kaggle", "Tavily", "confidence framework"],
        citation_style="natural",
        structure_hints=["comparison_table"]
    ),

    "filmography_overlap": ResponseTemplate(
        template_id="filmography_overlap",
        max_sentences=15,
        max_words=300,
        required_elements=["numbered_list", "include_year"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily", "confidence framework"],
        citation_style="natural",
        structure_hints=["list_format"]
    ),

    # General info - more flexible
    "general_info": ResponseTemplate(
        template_id="general_info",
        max_sentences=10,
        max_words=200,
        required_elements=["answer_first"],
        forbidden_terms=["Tier", "Tier A", "Tier B", "Tier C", "dataset", "Kaggle", "Tavily", "confidence framework"],
        citation_style="natural",
        structure_hints=["direct_answer"]
    ),

    "fact_check": ResponseTemplate(
        template_id="fact_check",
        max_sentences=3,
        max_words=80,
        required_elements=["answer_first"],
        forbidden_terms=["Tier", "dataset", "Kaggle", "Tavily", "confidence framework"],
        citation_style="natural",
        structure_hints=["direct_answer"]
    ),
}


def get_template(request_type: str, intent: str) -> ResponseTemplate:
    """
    Get response template for request_type/intent combination.

    Priority:
    1. Try intent first (more specific)
    2. Fall back to request_type
    3. Fall back to general_info template

    Args:
        request_type: Request type (e.g., "info", "recs", "comparison")
        intent: Intent (e.g., "director_info", "cast_info", "recommendation")

    Returns:
        ResponseTemplate
    """
    # Try intent first (more specific)
    if intent and intent in RESPONSE_TEMPLATES:
        return RESPONSE_TEMPLATES[intent]

    # Map request_type to intent-style keys
    request_type_to_template = {
        "info": "general_info",
        "recs": "recommendation",
        "comparison": "comparison",
        "fact-check": "fact_check",
        "release-date": "release_date",
        "spoiler": "general_info",
    }

    template_key = request_type_to_template.get(request_type)
    if template_key and template_key in RESPONSE_TEMPLATES:
        return RESPONSE_TEMPLATES[template_key]

    # Fallback to general_info
    return RESPONSE_TEMPLATES.get("general_info", ResponseTemplate(template_id="default"))


def list_all_templates() -> dict[str, ResponseTemplate]:
    """List all available templates."""
    return RESPONSE_TEMPLATES.copy()

