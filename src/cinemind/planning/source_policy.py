"""
Source policy and ranking system for CineMind.
Implements Tier A/B/C source ranking with strict enforcement.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SourceTier(Enum):
    """Source quality tiers."""
    TIER_A = "A"  # Authoritative/structured
    TIER_B = "B"  # Reputable editorial
    TIER_C = "C"  # Low-trust
    UNKNOWN = "UNKNOWN"


@dataclass
class SourceMetadata:
    """Metadata about a source."""
    url: str
    domain: str
    tier: SourceTier
    title: str
    content: str
    score: float = 0.0
    published_date: str | None = None
    last_updated: str | None = None
    is_structured: bool = False  # True for APIs/structured data
    source_name: str = "unknown"  # Original source name (tavily, kaggle_imdb, etc.)


@dataclass
class SourceConstraints:
    """
    Constraints for source filtering and ranking derived from RequestPlan.
    """
    allowed_source_tiers: list[str] = field(default_factory=lambda: ["A", "B"])  # Which tiers are allowed
    require_tier_a: bool = False  # Must have at least one Tier A source
    reject_tier_c: bool = True  # Reject Tier C sources
    need_freshness: bool = False  # Whether query needs fresh data (affects ranking)
    request_type: str = "info"  # Request type (for fallback behavior)

    @classmethod
    def from_request_plan(cls, plan) -> "SourceConstraints":
        """
        Create SourceConstraints from RequestPlan.

        Args:
            plan: RequestPlan instance

        Returns:
            SourceConstraints
        """
        return cls(
            allowed_source_tiers=getattr(plan, 'allowed_source_tiers', ["A", "B"]),
            require_tier_a=getattr(plan, 'require_tier_a', False),
            reject_tier_c=getattr(plan, 'reject_tier_c', True),
            need_freshness=getattr(plan, 'need_freshness', False),
            request_type=getattr(plan, 'request_type', 'info')
        )


class SourcePolicy:
    """
    Source policy with tier-based ranking and filtering.
    """

    # Tier A: Authoritative/structured sources
    TIER_A_DOMAINS = {
        # IMDb
        "imdb.com",
        "www.imdb.com",

        # Wikipedia
        "en.wikipedia.org",
        "wikipedia.org",

        # Wikidata
        "wikidata.org",
        "www.wikidata.org",

        # TMDb (if using API)
        "themoviedb.org",
        "www.themoviedb.org",
    }

    # Tier B: Reputable editorial sources
    TIER_B_DOMAINS = {
        # Trade publications
        "variety.com",
        "www.variety.com",
        "deadline.com",
        "www.deadline.com",
        "hollywoodreporter.com",
        "www.hollywoodreporter.com",
        "indiewire.com",
        "www.indiewire.com",
        "entertainmentweekly.com",
        "www.entertainmentweekly.com",

        # Established film sites
        "rottentomatoes.com",
        "www.rottentomatoes.com",
        "metacritic.com",
        "www.metacritic.com",
        "empireonline.com",
        "www.empireonline.com",
    }

    # Tier C: Low-trust sources (auto-reject for facts)
    TIER_C_DOMAINS = {
        "quora.com",
        "www.quora.com",
        "facebook.com",
        "www.facebook.com",
        "reddit.com",
        "www.reddit.com",
        "blogspot.com",
        "wordpress.com",
        "medium.com",
        "tumblr.com",
    }

    # Patterns for Tier A identification
    TIER_A_PATTERNS = [
        r"imdb\.com/title/tt\d+",  # IMDb title pages
        r"wikipedia\.org/wiki/.*film",  # Wikipedia film pages
        r"wikidata\.org/wiki/Q\d+",  # Wikidata entities
    ]

    def __init__(self):
        """Initialize source policy."""
        pass

    def classify_source(self, url: str, title: str = "", content: str = "", source_name: str = "") -> SourceTier:
        """
        Classify a source into Tier A, B, C, or UNKNOWN.

        Args:
            url: Source URL
            title: Source title
            content: Source content (for pattern matching)
            source_name: Original source name (kaggle_imdb, tavily, etc.)

        Returns:
            SourceTier
        """
        # Kaggle IMDB dataset is Tier A (authoritative structured data)
        if source_name == "kaggle_imdb":
            return SourceTier.TIER_A

        if not url:
            return SourceTier.UNKNOWN

        # Parse domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            return SourceTier.UNKNOWN

        # Check Tier A
        if domain in self.TIER_A_DOMAINS:
            return SourceTier.TIER_A

        # Check Tier A patterns
        url_lower = url.lower()
        for pattern in self.TIER_A_PATTERNS:
            if re.search(pattern, url_lower):
                return SourceTier.TIER_A

        # Check Tier B
        if domain in self.TIER_B_DOMAINS:
            return SourceTier.TIER_B

        # Check Tier C
        if domain in self.TIER_C_DOMAINS:
            return SourceTier.TIER_C

        # Check for Tier C patterns in content
        content_lower = (title + " " + content).lower()
        if any(tier_c in content_lower for tier_c in ["quora", "facebook post", "reddit thread"]):
            return SourceTier.TIER_C

        return SourceTier.UNKNOWN

    def rank_and_filter(self, results: list[dict],
                       plan_or_constraints: SourceConstraints | str | None = None,
                       request_type: str | None = None,
                       need_freshness: bool = False) -> tuple[list[SourceMetadata], dict[str, Any]]:
        """
        Rank and filter search results by tier using RequestPlan or SourceConstraints.

        Args:
            results: Raw search results from search engine
            plan_or_constraints: RequestPlan, SourceConstraints, or request_type string (for backward compatibility)
            request_type: Request type (only used if plan_or_constraints is a string, for backward compatibility)
            need_freshness: Whether query needs fresh data (only used if plan_or_constraints is a string, for backward compatibility)

        Returns:
            Tuple of (filtered_sources: List[SourceMetadata], metadata: Dict) where metadata contains:
            - tiers_present_in_candidates: Dict[str, int] - Count of each tier in input results
            - tiers_used_in_evidence: Dict[str, int] - Count of each tier in final results
            - filtering_reasons: List[str] - Reasons why results were filtered out (e.g., "tier_not_allowed", "tier_c_rejected")
            - missing_required_tier: bool - True if require_tier_a=True but no Tier A sources found
        """
        # Handle backward compatibility: if plan_or_constraints is a string, treat it as request_type
        if isinstance(plan_or_constraints, str):
            request_type = plan_or_constraints
            constraints = SourceConstraints(
                allowed_source_tiers=["A", "B"],
                require_tier_a=False,
                reject_tier_c=True,
                need_freshness=need_freshness,
                request_type=request_type or "info"
            )
        elif plan_or_constraints is None:
            # Fallback to old behavior if nothing provided
            constraints = SourceConstraints(
                allowed_source_tiers=["A", "B"],
                require_tier_a=False,
                reject_tier_c=True,
                need_freshness=need_freshness,
                request_type=request_type or "info"
            )
        elif isinstance(plan_or_constraints, SourceConstraints):
            # It's already a SourceConstraints
            constraints = plan_or_constraints
        elif hasattr(plan_or_constraints, 'allowed_source_tiers'):
            # It's a RequestPlan-like object - convert to SourceConstraints
            constraints = SourceConstraints.from_request_plan(plan_or_constraints)
        else:
            # Unknown type, fallback to default
            constraints = SourceConstraints(
                allowed_source_tiers=["A", "B"],
                require_tier_a=False,
                reject_tier_c=True,
                need_freshness=need_freshness,
                request_type=request_type or "info"
            )

        # Classify all sources
        sources = []
        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")

            source_name = result.get("source", "unknown")
            tier = self.classify_source(url, title, content, source_name)

            # Extract domain
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
            except Exception:
                domain = ""
                # For Kaggle sources, set domain to indicate it's from IMDB dataset
                if source_name == "kaggle_imdb":
                    domain = "imdb.com (via Kaggle dataset)"

            source = SourceMetadata(
                url=url,
                domain=domain,
                tier=tier,
                title=title,
                content=content,
                score=result.get("score", 0.0),
                published_date=result.get("published_date"),
                last_updated=result.get("last_updated"),
                is_structured=result.get("source") in ["tavily_answer", "kaggle_imdb"],  # Structured data sources
                source_name=source_name
            )
            sources.append(source)

        # Log tiers present in candidates
        tiers_present = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
        for source in sources:
            tiers_present[source.tier.value] = tiers_present.get(source.tier.value, 0) + 1

        # Initialize missing_required_tier flag
        missing_required_tier = False

        # Step 1: Filter by allowed_source_tiers
        filtering_reasons = []
        removed_by_tier = {}  # Track removals by tier for detailed diagnostics
        filtered_sources = []
        for s in sources:
            if s.tier.value in constraints.allowed_source_tiers:
                filtered_sources.append(s)
            else:
                tier_value = s.tier.value
                if tier_value not in removed_by_tier:
                    removed_by_tier[tier_value] = []
                removed_by_tier[tier_value].append("tier_not_allowed")

        # Add detailed filtering reasons for tier_not_allowed
        if removed_by_tier:
            for tier_value, reasons in removed_by_tier.items():
                count = len(reasons)
                filtering_reasons.append(f"Removed {count} sources with tier {tier_value} (tier_not_allowed: not in allowed_source_tiers {constraints.allowed_source_tiers})")

        # Step 2: Filter by reject_tier_c (apply after allowed_source_tiers to ensure Tier C is removed even if in allowed set)
        if constraints.reject_tier_c:
            tier_c_before = [s for s in filtered_sources if s.tier == SourceTier.TIER_C]
            tier_c_count = len(tier_c_before)
            if tier_c_count > 0:
                filtering_reasons.append(f"Removed {tier_c_count} sources with tier C (tier_c_rejected: reject_tier_c=True)")
            filtered_sources = [s for s in filtered_sources if s.tier != SourceTier.TIER_C]

        # Step 3: Group by tier for require_tier_a logic
        tier_a_sources = [s for s in filtered_sources if s.tier == SourceTier.TIER_A]
        [s for s in filtered_sources if s.tier == SourceTier.TIER_B]
        [s for s in filtered_sources if s.tier == SourceTier.TIER_C]

        # Step 4: Apply require_tier_a logic
        if constraints.require_tier_a:
            if not tier_a_sources:
                # If Tier A is required but none exist, return empty list and set missing_required_tier
                missing_required_tier = True
                logger.warning("require_tier_a=True but no Tier A sources found - returning empty set")
                filtering_reasons.append("No Tier A sources found (require_tier_a=True)")
                tiers_used = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
                return ([], {
                    "tiers_present_in_candidates": tiers_present,
                    "tiers_used_in_evidence": tiers_used,
                    "filtering_reasons": filtering_reasons,
                    "missing_required_tier": True
                })
            # Only use Tier A sources if required
            filtered_sources = tier_a_sources

        # Step 6: Apply freshness-based ranking if needed
        if constraints.need_freshness:
            # Weight recency higher - rank by recency (newer first), then score
            filtered_sources = self._rank_by_freshness(filtered_sources)
        else:
            # Standard ranking: tier first, then score
            filtered_sources = sorted(filtered_sources,
                                    key=lambda x: (
                                        {"A": 0, "B": 1, "C": 2, "UNKNOWN": 3}.get(x.tier.value, 3),
                                        -x.score
                                    ))

        # Log tiers used in evidence
        tiers_used = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
        for source in filtered_sources:
            tiers_used[source.tier.value] = tiers_used.get(source.tier.value, 0) + 1

        logger.info(f"Source filtering: present={tiers_present}, used={tiers_used}, reasons={filtering_reasons}")

        return (filtered_sources, {
            "tiers_present_in_candidates": tiers_present,
            "tiers_used_in_evidence": tiers_used,
            "filtering_reasons": filtering_reasons,
            "missing_required_tier": missing_required_tier
        })

    def _rank_by_freshness(self, sources: list[SourceMetadata]) -> list[SourceMetadata]:
        """
        Rank sources by freshness (newer first) when need_freshness=True.

        Args:
            sources: List of sources to rank

        Returns:
            Sorted list of sources (newer first, then by score)
        """
        def freshness_score(source: SourceMetadata) -> tuple[int, float]:
            """
            Calculate freshness score for ranking.
            Returns: (days_old: int, -score: float) for sorting (lower days_old = newer = better)
            """
            score = source.score or 0.0

            # Try to extract date from published_date
            days_old = 999999  # Default: very old (sorts last)

            if source.published_date:
                try:
                    # Try parsing ISO format dates
                    date_str = str(source.published_date)
                    # Handle timezone-aware dates
                    if date_str.endswith('Z'):
                        date_str = date_str.replace('Z', '+00:00')
                    try:
                        date_obj = datetime.fromisoformat(date_str)
                        # Handle timezone-aware dates
                        if date_obj.tzinfo:
                            now = datetime.now(date_obj.tzinfo)
                            days_old = (now - date_obj).days
                        else:
                            days_old = (datetime.now() - date_obj).days
                        if days_old < 0:
                            days_old = 0  # Future dates count as 0 days old
                    except ValueError:
                        # Try extracting year from string if ISO parsing fails
                        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
                        if year_match:
                            year = int(year_match.group(0))
                            days_old = (datetime.now().year - year) * 365  # Approximate
                except (ValueError, AttributeError, TypeError):
                    pass

            return (days_old, -score)

        return sorted(sources, key=freshness_score)

    def filter_tier_c(self, sources: list[SourceMetadata],
                     allow_tier_c: bool = False) -> list[SourceMetadata]:
        """
        Filter out Tier C sources unless explicitly allowed.

        Args:
            sources: List of sources
            allow_tier_c: Whether to allow Tier C sources

        Returns:
            Filtered list
        """
        if allow_tier_c:
            return sources

        return [s for s in sources if s.tier != SourceTier.TIER_C]

    def get_source_summary(self, sources: list[SourceMetadata]) -> dict:
        """
        Get summary of source tiers used.

        Returns:
            Dict with tier counts and metadata
        """
        tier_counts = {"A": 0, "B": 0, "C": 0, "UNKNOWN": 0}
        tier_a_domains = set()
        tier_b_domains = set()
        tier_c_domains = set()

        for source in sources:
            tier_counts[source.tier.value] = tier_counts.get(source.tier.value, 0) + 1

            if source.tier == SourceTier.TIER_A:
                tier_a_domains.add(source.domain)
            elif source.tier == SourceTier.TIER_B:
                tier_b_domains.add(source.domain)
            elif source.tier == SourceTier.TIER_C:
                tier_c_domains.add(source.domain)

        return {
            "tier_counts": tier_counts,
            "tier_a_domains": list(tier_a_domains),
            "tier_b_domains": list(tier_b_domains),
            "tier_c_domains": list(tier_c_domains),
            "total_sources": len(sources),
            "has_tier_a": tier_counts["A"] > 0,
            "has_tier_c_only": tier_counts["A"] == 0 and tier_counts["B"] == 0 and tier_counts["C"] > 0
        }

