"""
Prompt building pipeline for CineMind.
Consumes RequestPlan and EvidenceBundle to produce structured chat messages.
"""
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from ..planning.request_plan import RequestPlan, ResponseFormat
from config import PROMPT_VERSION
from .templates import get_template, ResponseTemplate
from .evidence_formatter import EvidenceFormatter

logger = logging.getLogger(__name__)


@dataclass
class PromptArtifacts:
    """Metadata about the prompt that was built."""
    prompt_version: str
    instruction_template_id: str  # Based on request_type/intent
    verbosity_budget: Optional[Dict[str, Any]] = None  # Sentences/words used
    messages_count: int = 0
    system_tokens: int = 0
    developer_tokens: int = 0
    user_tokens: int = 0


@dataclass
class EvidenceBundle:
    """Bundle of evidence from search results."""
    search_results: List[Dict]
    verified_facts: Optional[List] = None
    
    def format_for_user_message(self) -> str:
        """
        Format evidence for inclusion in user message.
        Keeps evidence neutral, no behavioral instructions.
        """
        if not self.search_results:
            return ""
        
        evidence_text = "\n\nEVIDENCE:\n"
        evidence_text += "=" * 60 + "\n"
        
        for i, result in enumerate(self.search_results[:10], 1):  # Limit to top 10
            title = result.get("title", "Unknown")
            url = result.get("url", "")
            content = result.get("content", "")
            source = result.get("source", "unknown")
            tier = result.get("tier", "UNKNOWN")
            
            evidence_text += f"\n[{i}] {title}\n"
            if url:
                evidence_text += f"URL: {url}\n"
            if source:
                # Don't expose "Tier A" terminology to user output
                source_display = source.replace("_", " ").title()
                if source == "kaggle_imdb":
                    source_display = "IMDB Dataset"
                evidence_text += f"Source: {source_display}\n"
            evidence_text += f"Content:\n{content}\n"
            evidence_text += "-" * 60 + "\n"
        
        # Add verified facts if available
        if self.verified_facts:
            verified_items = [f.value for f in self.verified_facts if hasattr(f, 'verified') and f.verified]
            if verified_items:
                evidence_text += "\nVERIFIED INFORMATION:\n"
                for item in verified_items[:5]:  # Limit to top 5
                    evidence_text += f"- {item}\n"
        
        return evidence_text


class PromptBuilder:
    """
    Builds structured chat messages from RequestPlan and EvidenceBundle.
    
    Message structure:
    - System: Fixed identity + hard rules (thin, stable)
    - Developer: Dynamic RESPONSE INSTRUCTIONS from RequestPlan
    - User: User question + EVIDENCE section (neutral, no behavioral instructions)
    """
    
    # Thin, stable system prompt (identity + hard rules only)
    SYSTEM_PROMPT = """You are CineMind, a movie analysis agent.

DOMAIN: Films, filmmakers, actors, genres, box office, awards, trivia, comparisons, recommendations. Film-only domain.

HARD RULES:
- Movies-only domain (no non-film topics)
- No spoilers unless explicitly requested (use spoiler warning if requested)
- Never mention internal metadata (Tier A/B/C, Kaggle, Tavily, etc.) in responses
- Follow the RESPONSE INSTRUCTIONS provided in the developer message
- Cite sources naturally without technical details"""
    
    def __init__(self, prompt_version: str = None):
        """
        Initialize prompt builder.
        
        Args:
            prompt_version: Prompt version identifier (default: from config)
        """
        self.prompt_version = prompt_version or PROMPT_VERSION
        self.evidence_formatter = EvidenceFormatter(max_snippet_length=400, max_items=10)
    
    def build_messages(
        self,
        request_plan: RequestPlan,
        evidence: EvidenceBundle,
        user_query: str,
        structured_intent = None
    ) -> tuple[List[Dict[str, str]], PromptArtifacts]:
        """
        Build structured chat messages from RequestPlan and evidence.
        
        Args:
            request_plan: RequestPlan with routing and behavior instructions
            evidence: EvidenceBundle with search results
            user_query: Original user query
        
        Returns:
            (messages: List[Dict], artifacts: PromptArtifacts)
        """
        # Build developer message with RESPONSE INSTRUCTIONS
        developer_message = self._build_response_instructions(request_plan, structured_intent)
        
        # Build user message with query + evidence
        user_message = self._build_user_message(user_query, evidence)
        
        # Construct messages list
        # Note: OpenAI API doesn't support "developer" role, so we combine
        # system prompt + developer instructions into system message
        combined_system = f"{self.SYSTEM_PROMPT}\n\n{developer_message}"
        
        messages = [
            {"role": "system", "content": combined_system},
            {"role": "user", "content": user_message}
        ]
        
        # Build instruction template ID
        instruction_template_id = self._build_template_id(request_plan)
        
        # Build artifacts
        artifacts = PromptArtifacts(
            prompt_version=self.prompt_version,
            instruction_template_id=instruction_template_id,
            verbosity_budget=self._estimate_verbosity_budget(request_plan),
            messages_count=len(messages)
        )
        
        logger.debug(f"Built prompt with template_id={instruction_template_id}, version={self.prompt_version}")
        
        return messages, artifacts
    
    def _build_response_instructions(self, request_plan: RequestPlan, structured_intent = None) -> str:
        """
        Build RESPONSE INSTRUCTIONS block from RequestPlan.
        This is dynamic and derived from request plan fields.
        """
        instructions = ["RESPONSE INSTRUCTIONS:", "=" * 60]
        
        # Request type / intent
        intent = request_plan.intent
        request_type = request_plan.request_type
        instructions.append(f"Request Type: {request_type}")
        if intent and intent != request_type:
            instructions.append(f"Intent: {intent}")
        
        instructions.append("")
        
        # Get response template for request_type/intent
        response_template = get_template(request_plan.request_type, request_plan.intent)
        
        # Add template-based instructions (verbosity, structure, citations, forbidden terms)
        template_instructions = response_template.to_instructions()
        if template_instructions:
            instructions.append(template_instructions)
            instructions.append("")
        
        # Response format (only if not already covered by template)
        response_format = request_plan.response_format
        if isinstance(response_format, ResponseFormat):
            format_value = response_format.value
        else:
            format_value = str(response_format)
        
        # Note: Format instructions are now primarily handled by ResponseTemplate
        # but we can still add format-specific hints if needed
        format_instructions = self._get_format_instructions(format_value, request_plan)
        if format_instructions:
            instructions.append("Format Requirements:")
            instructions.append(format_instructions)
            instructions.append("")
        
        # Spoiler policy
        spoiler_policy = self._get_spoiler_policy(request_plan)
        if spoiler_policy:
            instructions.append("Spoiler Policy:")
            instructions.append(spoiler_policy)
            instructions.append("")
        
        # Freshness / timestamp language
        freshness_instructions = self._get_freshness_instructions(request_plan)
        if freshness_instructions:
            instructions.append("Freshness/Timestamp Requirements:")
            instructions.append(freshness_instructions)
            instructions.append("")
        
        # Constraints (format, order_by, min_count)
        constraints_instructions = self._get_constraints_instructions(request_plan, structured_intent)
        if constraints_instructions:
            instructions.append("Constraints:")
            instructions.append(constraints_instructions)
            instructions.append("")
        
        # Source quality requirements (without exposing Tier terminology)
        source_instructions = self._get_source_instructions(request_plan)
        if source_instructions:
            instructions.append("Source Quality Requirements:")
            instructions.append(source_instructions)
            instructions.append("")
        
        return "\n".join(instructions)
    
    def _get_format_instructions(self, format_value: str, request_plan: RequestPlan) -> str:
        """Get format-specific instructions."""
        format_map = {
            "short_fact": "Provide a concise 1-2 sentence answer. No fluff, no elaboration unless necessary.",
            "list": "Provide a numbered or bulleted list of items.",
            "comparison": "Provide a side-by-side comparison format, clearly distinguishing between items.",
            "detailed": "Provide a comprehensive, detailed response with context and examples.",
            "verified_list": "Provide a list with verification/sources clearly indicated for each item.",
            "spoiler_warning": "Include a prominent spoiler warning before revealing plot details."
        }
        return format_map.get(format_value, "")
    
    def _get_verbosity_instructions(self, request_plan: RequestPlan) -> str:
        """
        Get verbosity/length instructions based on intent.
        Note: This is now handled by ResponseTemplate, but kept for backward compatibility.
        """
        # Verbosity is now handled by ResponseTemplate.to_instructions()
        # This method is kept for backward compatibility but should not be called
        return ""
    
    def _get_spoiler_policy(self, request_plan: RequestPlan) -> str:
        """Get spoiler policy instructions."""
        request_type = request_plan.request_type
        
        if request_type == "spoiler":
            return "User has explicitly requested spoilers. Include a clear spoiler warning and provide detailed plot information."
        else:
            return "Default: No spoilers. Focus on themes, setup, and non-plot details unless user explicitly requests spoilers."
    
    def _get_freshness_instructions(self, request_plan: RequestPlan) -> str:
        """Get freshness/timestamp instructions."""
        if not request_plan.need_freshness:
            return ""
        
        ttl_hours = request_plan.freshness_ttl_hours or 24.0
        freshness_reason = request_plan.freshness_reason or "recent information requested"
        
        instructions = [
            f"User requires current/up-to-date information ({freshness_reason}).",
            f"Emphasize recent information and use timestamp language when relevant.",
            f"Example: 'As of [current year]', 'Recently', 'Latest updates indicate'"
        ]
        
        # For very short TTL (e.g., < 12 hours), emphasize recency more
        if ttl_hours < 12:
            instructions.append("Critical: This query requires very recent information. Highlight any time-sensitive details.")
        
        return "\n".join(instructions)
    
    def _get_constraints_instructions(self, request_plan: RequestPlan, structured_intent = None) -> str:
        """Get constraints instructions (order_by, min_count, etc.)."""
        constraints_list = []
        
        # Extract constraints from structured_intent if available
        if structured_intent and hasattr(structured_intent, 'constraints'):
            constraints_dict = structured_intent.constraints
            if isinstance(constraints_dict, dict):
                # order_by constraint
                order_by = constraints_dict.get("order_by")
                if order_by:
                    if order_by == "release_year_asc":
                        constraints_list.append("Sort results by release year (oldest first).")
                    elif order_by == "release_year_desc":
                        constraints_list.append("Sort results by release year (newest first).")
                    elif order_by == "chronological":
                        constraints_list.append("Sort results in chronological order.")
                
                # min_count constraint
                min_count = constraints_dict.get("min_count")
                if min_count and isinstance(min_count, int):
                    constraints_list.append(f"Provide at least {min_count} items.")
        
        if constraints_list:
            return "\n".join(constraints_list)
        return ""
    
    def _get_source_instructions(self, request_plan: RequestPlan) -> str:
        """
        Get source quality requirements WITHOUT exposing Tier terminology.
        """
        instructions = []
        
        # require_tier_a -> emphasize authoritative sources
        if request_plan.require_tier_a:
            instructions.append(
                "Prioritize authoritative sources (IMDb, Wikipedia, official sites) for factual claims. "
                "Be cautious with unverified sources."
            )
        
        # reject_tier_c -> avoid low-trust sources
        if request_plan.reject_tier_c:
            instructions.append(
                "Avoid relying on low-trust sources for factual claims. "
                "Use them only for context or speculation."
            )
        
        # allowed_source_tiers -> guide source selection (without mentioning tiers)
        if request_plan.allowed_source_tiers:
            if "A" in request_plan.allowed_source_tiers:
                instructions.append("Prefer authoritative sources (IMDb, Wikipedia, official sites).")
            if "B" in request_plan.allowed_source_tiers:
                instructions.append("Reputable editorial sources (Variety, Deadline) are acceptable.")
            if "C" not in request_plan.allowed_source_tiers:
                instructions.append("Avoid low-trust sources for facts.")
        
        return "\n".join(instructions) if instructions else ""
    
    def _build_user_message(self, user_query: str, evidence: EvidenceBundle) -> str:
        """
        Build user message with query + evidence section.
        Evidence is neutral, no behavioral instructions.
        Uses EvidenceFormatter for standardized formatting.
        """
        message_parts = [user_query]
        
        # Use EvidenceFormatter for standardized formatting
        evidence_result = self.evidence_formatter.format(evidence)
        if evidence_result.text:
            message_parts.append(evidence_result.text)
        
        return "\n\n".join(message_parts)
    
    def _build_template_id(self, request_plan: RequestPlan) -> str:
        """Build instruction template ID based on request_type/intent."""
        # Get template to use its template_id
        response_template = get_template(request_plan.request_type or "info", request_plan.intent or "general_info")
        return f"{response_template.template_id}_{self.prompt_version}"
    
    def _estimate_verbosity_budget(self, request_plan: RequestPlan) -> Dict[str, Any]:
        """Estimate verbosity budget (sentences/words) based on template."""
        response_template = get_template(request_plan.request_type, request_plan.intent)
        
        budget = {
            "template_id": response_template.template_id
        }
        
        if response_template.max_sentences:
            budget["max_sentences"] = response_template.max_sentences
        if response_template.min_sentences:
            budget["min_sentences"] = response_template.min_sentences
        if response_template.max_words:
            budget["max_words"] = response_template.max_words
        
        return budget

