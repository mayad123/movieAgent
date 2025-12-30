"""
Evidence formatter for CineMind.
Standardizes evidence formatting: deduplication, snippet length limits, user-friendly source labels.
"""
import logging
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


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
    
    def format(self, evidence_bundle) -> str:
        """
        Format evidence bundle for user message.
        
        Args:
            evidence_bundle: EvidenceBundle with search_results and verified_facts
        
        Returns:
            Formatted evidence string for inclusion in user message
        """
        if not evidence_bundle.search_results:
            return ""
        
        # Deduplicate and format search results
        deduplicated_results = self._deduplicate(evidence_bundle.search_results)
        
        # Format each item with length limits and user-friendly labels
        formatted_items = []
        for i, result in enumerate(deduplicated_results[:self.max_items], 1):
            formatted_item = self._format_item(result, i)
            if formatted_item:
                formatted_items.append(formatted_item)
        
        if not formatted_items:
            return ""
        
        # Build evidence section
        evidence_text = "\n\nEVIDENCE:\n"
        evidence_text += "=" * 60 + "\n"
        evidence_text += "\n".join(formatted_items)
        
        # Add verified facts if available
        if evidence_bundle.verified_facts:
            verified_items = [
                f.value for f in evidence_bundle.verified_facts 
                if hasattr(f, 'verified') and f.verified
            ]
            if verified_items:
                evidence_text += "\n\nVERIFIED INFORMATION:\n"
                for item in verified_items[:5]:  # Limit to top 5
                    evidence_text += f"- {item}\n"
        
        return evidence_text
    
    def _deduplicate(self, search_results: List[Dict]) -> List[Dict]:
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
        seen_urls: Dict[str, Dict] = {}  # normalized_url -> result (with content preferred)
        seen_title_year: Dict[str, Dict] = {}  # title|year -> result (with content preferred)
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
                normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/').lower()
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
    
    def _format_item(self, result: Dict, index: int) -> str:
        """
        Format a single evidence item with length limits and user-friendly labels.
        
        Args:
            result: Search result dict
            index: Item index (1-based)
        
        Returns:
            Formatted string for this item, or empty string if invalid
        """
        title = result.get("title", "Unknown").strip()
        url = result.get("url", "").strip()
        content = result.get("content", "").strip()
        source = result.get("source", "unknown")
        
        # Skip items with no content
        if not content:
            return ""
        
        # Limit snippet length
        content_snippet = self._truncate_snippet(content, self.max_snippet_length)
        
        # Format item
        item_lines = []
        item_lines.append(f"\n[{index}] {title}")
        
        # Add URL if available
        if url:
            item_lines.append(f"URL: {url}")
        
        # Add user-friendly source label
        source_label = self._format_source_label(source, url)
        if source_label:
            item_lines.append(f"Source: {source_label}")
        
        # Add content snippet
        item_lines.append(f"Content:\n{content_snippet}")
        item_lines.append("-" * 60)
        
        return "\n".join(item_lines)
    
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
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        # Find last sentence-ending punctuation
        last_sentence_end = max(last_period, last_exclamation, last_question)
        
        if last_sentence_end > max_length * 0.7:  # Only use sentence boundary if not too short
            truncated = truncated[:last_sentence_end + 1]
        else:
            # Truncate at word boundary
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.8:
                truncated = truncated[:last_space] + "..."
            else:
                truncated = truncated.rstrip() + "..."
        
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
        url_lower = url.lower() if url else ""
        
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

