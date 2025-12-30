"""
Pytest configuration and shared fixtures for CineMind tests.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cinemind.request_plan import RequestPlan, ResponseFormat, ToolType
from cinemind.prompting.prompt_builder import EvidenceBundle


@pytest.fixture
def frozen_time():
    """
    Deterministic time fixture that freezes time to a fixed point.
    
    Usage:
        def test_something(frozen_time):
            # Time is frozen to 2024-01-01 12:00:00
            # The fixture automatically enters the context
            now = datetime.now()
            # Your test code here
    """
    with freeze_time("2024-01-01 12:00:00"):
        yield


@pytest.fixture
def fixed_now():
    """
    Provides a fixed "now" datetime string for deterministic tests.
    
    Returns:
        ISO format datetime string: "2024-01-01T12:00:00"
    """
    return "2024-01-01T12:00:00"


@pytest.fixture
def minimal_request_plan():
    """
    Helper to build a minimal RequestPlan object.
    
    Returns:
        RequestPlan with default values
    """
    return RequestPlan(
        intent="general_info",
        request_type="info",
        original_query="test query"
    )


@pytest.fixture
def request_plan_factory():
    """
    Factory fixture to create RequestPlan objects with custom parameters.
    
    Usage:
        def test_something(request_plan_factory):
            plan = request_plan_factory(
                intent="director_info",
                request_type="info",
                entities=["Christopher Nolan"]
            )
    """
    def _create_plan(**kwargs) -> RequestPlan:
        """Create a RequestPlan with given parameters."""
        defaults = {
            "intent": "general_info",
            "request_type": "info",
            "original_query": kwargs.get("original_query", "test query")
        }
        defaults.update(kwargs)
        return RequestPlan(**defaults)
    
    return _create_plan


@pytest.fixture
def minimal_evidence_bundle():
    """
    Helper to build a minimal EvidenceBundle object.
    
    Returns:
        EvidenceBundle with empty search results
    """
    return EvidenceBundle(search_results=[])


@pytest.fixture
def evidence_bundle_factory():
    """
    Factory fixture to create EvidenceBundle objects with custom data.
    
    Usage:
        def test_something(evidence_bundle_factory):
            bundle = evidence_bundle_factory(
                search_results=[
                    {
                        "title": "Test Result",
                        "url": "https://example.com",
                        "content": "Test content",
                        "source": "test",
                        "tier": "A"
                    }
                ]
            )
    """
    def _create_bundle(
        search_results: Optional[List[Dict[str, Any]]] = None,
        verified_facts: Optional[List] = None
    ) -> EvidenceBundle:
        """Create an EvidenceBundle with given parameters."""
        if search_results is None:
            search_results = []
        return EvidenceBundle(
            search_results=search_results,
            verified_facts=verified_facts
        )
    
    return _create_bundle


@pytest.fixture
def sample_search_result():
    """
    Provides a sample search result dictionary for testing.
    
    Returns:
        Dictionary with typical search result structure
    """
    return {
        "title": "Sample Movie Title",
        "url": "https://example.com/movie",
        "content": "This is sample content about a movie.",
        "source": "kaggle_imdb",
        "tier": "A"
    }


@pytest.fixture
def sample_evidence_bundle(sample_search_result, evidence_bundle_factory):
    """
    Provides a sample EvidenceBundle with one search result.
    
    Returns:
        EvidenceBundle with one sample search result
    """
    return evidence_bundle_factory(search_results=[sample_search_result])

