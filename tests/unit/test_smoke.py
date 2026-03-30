"""
Smoke test to verify the pytest test harness is working correctly.
"""

from cinemind.planning.request_plan import RequestPlan
from cinemind.prompting.prompt_builder import EvidenceBundle
from tests.fixtures.loader import list_scenarios


def test_harness_imports():
    """Test that all required imports work."""
    assert RequestPlan is not None
    assert EvidenceBundle is not None


def test_fixtures_available(minimal_request_plan, minimal_evidence_bundle):
    """Test that basic fixtures are available and functional."""
    assert minimal_request_plan is not None
    assert isinstance(minimal_request_plan, RequestPlan)
    assert minimal_request_plan.intent == "general_info"

    assert minimal_evidence_bundle is not None
    assert isinstance(minimal_evidence_bundle, EvidenceBundle)
    assert minimal_evidence_bundle.search_results == []


def test_request_plan_factory(request_plan_factory):
    """Test RequestPlan factory fixture."""
    plan = request_plan_factory(intent="director_info", request_type="info", entities=["Christopher Nolan"])
    assert plan.intent == "director_info"
    assert plan.request_type == "info"
    assert "Christopher Nolan" in plan.entities


def test_evidence_bundle_factory(evidence_bundle_factory, sample_search_result):
    """Test EvidenceBundle factory fixture."""
    bundle = evidence_bundle_factory(search_results=[sample_search_result])
    assert len(bundle.search_results) == 1
    assert bundle.search_results[0]["title"] == "Sample Movie Title"


def test_frozen_time(frozen_time):
    """Test that time fixture works."""
    from datetime import datetime

    # The frozen_time fixture automatically enters the context
    now = datetime.now()
    assert now.year == 2024, f"Expected year 2024, got {now.year}"
    assert now.month == 1, f"Expected month 1, got {now.month}"
    assert now.day == 1, f"Expected day 1, got {now.day}"
    assert now.hour == 12, f"Expected hour 12, got {now.hour}"


def test_fixture_loader():
    """Test that fixture loader can list scenarios (even if none exist yet)."""
    scenarios = list_scenarios()
    # Should not raise, even if no scenarios exist
    assert isinstance(scenarios, list)


def test_pytest_runs():
    """Simple test to verify pytest is working."""
    assert True
