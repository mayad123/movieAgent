"""
Evidence formatter for CineMind.
Standardizes evidence formatting: deduplication, snippet length limits, user-friendly source labels.
"""

import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class FormattedEvidenceItem:
    """Metadata for a single formatted evidence item."""

    url: str
    title: str
    source_label: str
    year: int | None
    snippet_len: int
    index: int  # 1-based index in the formatted output


@dataclass
class EvidenceFormatResult:
    """Structured result from evidence formatting."""

    text: str  # The formatted evidence string (for backward compatibility)
    items: list[FormattedEvidenceItem] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"before": 0, "after": 0})
    max_snippet_len: int = 0
    dedupe_removed: int = 0

    def __str__(self) -> str:
        """Return the formatted text for backward compatibility."""
        return self.text

    def __len__(self) -> int:
        """Return length of formatted text."""
        return len(self.text)


class EvidenceFormatter:
    """
    Formats evidence for presentation to the generation model.
    Deduplicates, limits snippet length, and labels sources in user-friendly terms.
    """

    def __init__(self, max_snippet_length: int = 400, max_items: int = 10):
        """
        Initialize evidence formatter.

        Args:
            max_snippet_length: Maximum characters per snippet (default: 400)
            max_items: Maximum number of evidence items to include (default: 10)
        """
        self.max_snippet_length = max_snippet_length
        self.max_items = max_items

    def format(self, evidence_bundle) -> EvidenceFormatResult:
        """
        Format evidence bundle for user message.

        Args:
            evidence_bundle: EvidenceBundle with search_results and verified_facts

        Returns:
            EvidenceFormatResult with formatted text and metadata
        """
        if not evidence_bundle.search_results:
            return EvidenceFormatResult(
                text="", items=[], counts={"before": 0, "after": 0}, max_snippet_len=0, dedupe_removed=0
            )

        # Track counts before deduplication
        before_count = len(evidence_bundle.search_results)

        # Deduplicate and format search results
        deduplicated_results = self._deduplicate(evidence_bundle.search_results)
        after_count = len(deduplicated_results)
        dedupe_removed = before_count - after_count

        # Format each item with length limits and user-friendly labels
        formatted_item_strings = []
        formatted_item_metadata = []
        max_snippet_len = 0

        for i, result in enumerate(deduplicated_results[: self.max_items], 1):
            formatted_item_text, item_metadata = self._format_item_with_metadata(result, i)
            if formatted_item_text and item_metadata:
                formatted_item_strings.append(formatted_item_text)
                formatted_item_metadata.append(item_metadata)
                max_snippet_len = max(max_snippet_len, item_metadata.snippet_len)

        if not formatted_item_strings:
            return EvidenceFormatResult(
                text="",
                items=[],
                counts={"before": before_count, "after": 0},
                max_snippet_len=0,
                dedupe_removed=dedupe_removed,
            )

        # Build evidence section
        evidence_text = "\n\nEVIDENCE:\n"
        evidence_text += "=" * 60 + "\n"
        evidence_text += "\n".join(formatted_item_strings)

        # Add verified facts if available
        if evidence_bundle.verified_facts:
            verified_items = [f.value for f in evidence_bundle.verified_facts if hasattr(f, "verified") and f.verified]
            if verified_items:
                evidence_text += "\n\nVERIFIED INFORMATION:\n"
                for item in verified_items[:5]:  # Limit to top 5
                    evidence_text += f"- {item}\n"

        return EvidenceFormatResult(
            text=evidence_text,
            items=formatted_item_metadata,
            counts={"before": before_count, "after": len(formatted_item_metadata)},
            max_snippet_len=max_snippet_len,
            dedupe_removed=dedupe_removed,
        )

    def _deduplicate(self, search_results: list[dict]) -> list[dict]:
        """
        Deduplicate search results by url/title/year.
        Keeps first occurrence of each unique item, preferring items with content.

        Deduplication rules:
        - Items with the same normalized URL are considered duplicates (regardless of title/year)
        - Items with the same title and year are considered duplicates (regardless of URL)
        - When duplicates are found, prefer items with content over items without content

        Args:
            search_results: List of search result dicts

        Returns:
            Deduplicated list
        """
        seen_urls: dict[str, dict] = {}  # normalized_url -> result (with content preferred)
        seen_title_year: dict[str, dict] = {}  # title|year -> result (with content preferred)
        deduplicated = []

        for result in search_results:
            # Extract fields
            url = result.get("url", "").strip()
            title = result.get("title", "").strip()
            year = result.get("year") or result.get("release_year")
            content = result.get("content", "").strip()
            has_content = bool(content)

            # Normalize URL (remove query params, fragments, trailing slashes)
            if url:
                parsed = urlparse(url)
                normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/").lower()
            else:
                normalized_url = ""

            # Check if duplicate by URL
            is_duplicate = False
            if normalized_url:
                if normalized_url in seen_urls:
                    # Prefer item with content
                    existing = seen_urls[normalized_url]
                    existing_has_content = bool(existing.get("content", "").strip())
                    if has_content and not existing_has_content:
                        # Replace existing with this one (has content)
                        seen_urls[normalized_url] = result
                        # Remove old one from deduplicated list if it's there
                        if existing in deduplicated:
                            deduplicated.remove(existing)
                        deduplicated.append(result)
                    # Otherwise, skip this one (existing is better or equal)
                    is_duplicate = True
                else:
                    seen_urls[normalized_url] = result

            # Check if duplicate by title+year (if not already duplicate by URL)
            if not is_duplicate and title and year:
                title_year_key = f"{title.lower().strip()}|{year}"
                if title_year_key in seen_title_year:
                    # Prefer item with content
                    existing = seen_title_year[title_year_key]
                    existing_has_content = bool(existing.get("content", "").strip())
                    if has_content and not existing_has_content:
                        # Replace existing with this one (has content)
                        seen_title_year[title_year_key] = result
                        # Remove old one from deduplicated list if it's there
                        if existing in deduplicated:
                            deduplicated.remove(existing)
                        deduplicated.append(result)
                    # Otherwise, skip this one
                    is_duplicate = True
                else:
                    seen_title_year[title_year_key] = result

            # Skip items with no identifying information
            if not normalized_url and not (title and year):
                continue

            # Add if not duplicate
            if not is_duplicate:
                deduplicated.append(result)

        logger.debug(f"Deduplicated {len(search_results)} -> {len(deduplicated)} evidence items")
        return deduplicated

    def _format_item(self, result: dict, index: int) -> str:
        """
        Format a single evidence item with length limits and user-friendly labels.

        Args:
            result: Search result dict
            index: Item index (1-based)

        Returns:
            Formatted string for this item, or empty string if invalid

        Note: This is a backward compatibility wrapper around _format_item_with_metadata
        """
        formatted_text, _ = self._format_item_with_metadata(result, index)
        return formatted_text

    def _format_item_with_metadata(self, result: dict, index: int) -> tuple[str, FormattedEvidenceItem | None]:
        """
        Format a single evidence item with length limits and user-friendly labels.

        Args:
            result: Search result dict
            index: Item index (1-based)

        Returns:
            Tuple of (formatted_string, FormattedEvidenceItem metadata)
            Returns ("", None) if item is invalid (no content)
        """
        title = result.get("title", "Unknown").strip()
        url = result.get("url", "").strip()
        content = result.get("content", "").strip()
        source = result.get("source", "unknown")
        year = result.get("year") or result.get("release_year")

        # Skip items with no content - return None for metadata
        if not content:
            return "", None

        # Limit snippet length
        content_snippet = self._truncate_snippet(content, self.max_snippet_length)
        snippet_len = len(content_snippet)

        # Add user-friendly source label
        source_label = self._format_source_label(source, url)

        # Create metadata
        metadata = FormattedEvidenceItem(
            url=url, title=title, source_label=source_label, year=year, snippet_len=snippet_len, index=index
        )

        # Format item
        item_lines = []
        item_lines.append(f"\n[{index}] {title}")

        # Add URL if available
        if url:
            item_lines.append(f"URL: {url}")

        # Add user-friendly source label
        if source_label:
            item_lines.append(f"Source: {source_label}")

        # Add content snippet
        item_lines.append(f"Content:\n{content_snippet}")
        item_lines.append("-" * 60)

        formatted_text = "\n".join(item_lines)
        return formatted_text, metadata

    def _truncate_snippet(self, content: str, max_length: int) -> str:
        """
        Truncate content snippet to max_length, trying to break at sentence boundaries.

        Args:
            content: Content text
            max_length: Maximum length

        Returns:
            Truncated content
        """
        if len(content) <= max_length:
            return content

        # Try to truncate at sentence boundary
        truncated = content[:max_length]
        last_period = truncated.rfind(".")
        last_exclamation = truncated.rfind("!")
        last_question = truncated.rfind("?")

        # Find last sentence-ending punctuation
        last_sentence_end = max(last_period, last_exclamation, last_question)

        if last_sentence_end > max_length * 0.7:  # Only use sentence boundary if not too short
            truncated = truncated[: last_sentence_end + 1]
        else:
            # Truncate at word boundary
            last_space = truncated.rfind(" ")
            truncated = truncated[:last_space] + "..." if last_space > max_length * 0.8 else truncated.rstrip() + "..."

        return truncated

    def _format_source_label(self, source: str, url: str = "") -> str:
        """
        Format source name to user-friendly label.
        Avoids technical terms like "Tier A", "Kaggle", etc.
        If source is from Tavily, infers label from URL.

        Args:
            source: Source identifier (e.g., "kaggle_imdb", "tavily", "imdb")
            url: URL of the source (used to infer source name for Tavily results)

        Returns:
            User-friendly source label, or empty string to skip
        """
        if not source:
            # Try to infer from URL
            return self._infer_source_from_url(url)

        source_lower = source.lower()
        url.lower() if url else ""

        # Map technical source names to user-friendly labels
        source_mapping = {
            "kaggle_imdb": "Structured IMDb dataset",
            "kaggle": "Structured dataset",
            "imdb": "IMDb",
            "imdb.com": "IMDb",
            "wikipedia": "Wikipedia",
            "wikipedia.org": "Wikipedia",
            "tavily": "",  # Don't show "Tavily" - infer from URL
            "tavily_answer": "",  # Don't show technical source name
        }

        # Check exact matches first
        if source_lower in source_mapping:
            label = source_mapping[source_lower]
            # If label is empty and we have a URL, try to infer from URL
            if not label and url:
                return self._infer_source_from_url(url)
            return label

        # Check partial matches (e.g., "imdb" in "kaggle_imdb")
        for key, label in source_mapping.items():
            if key in source_lower:
                # If label is empty and we have a URL, try to infer from URL
                if not label and url:
                    return self._infer_source_from_url(url)
                return label

        # Default: capitalize and replace underscores
        # But avoid showing raw technical terms
        if any(tech_term in source_lower for tech_term in ["tier", "kaggle", "tavily", "dataset"]):
            # Try to infer from URL if available
            if url:
                return self._infer_source_from_url(url)
            return ""  # Skip technical sources

        return source.replace("_", " ").title()

    def _infer_source_from_url(self, url: str) -> str:
        """
        Infer user-friendly source name from URL.

        Args:
            url: Source URL

        Returns:
            User-friendly source label, or empty string
        """
        if not url:
            return ""

        url_lower = url.lower()

        # Common source domains
        if "wikipedia.org" in url_lower:
            return "Wikipedia"
        elif "imdb.com" in url_lower:
            return "IMDb"
        elif "rottentomatoes.com" in url_lower:
            return "Rotten Tomatoes"
        elif "variety.com" in url_lower:
            return "Variety"
        elif "deadline.com" in url_lower:
            return "Deadline"
        elif "metacritic.com" in url_lower:
            return "Metacritic"
        elif "boxofficemojo.com" in url_lower:
            return "Box Office Mojo"
        elif "themoviedb.org" in url_lower or "tmdb.org" in url_lower:
            return "TMDb"

        # If we can't infer, return empty to avoid showing technical source name
        return ""
