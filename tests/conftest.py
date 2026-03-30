"""
Pytest configuration and fixtures for CineMind tests.
"""

import pytest
from freezegun import freeze_time

from cinemind.planning.request_plan import RequestPlan
from cinemind.prompting.prompt_builder import EvidenceBundle
from tests.helpers.report_generator import get_collector


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "gold: marks tests as gold scenarios")
    config.addinivalue_line("markers", "explore: marks tests as explore scenarios")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to mark test results."""
    # Execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # Set a report attribute for each phase of a call, which can
    # be "setup", "call", "teardown"
    setattr(item, "rep_" + rep.when, rep)


def pytest_sessionstart(session):
    """Called after the Session object has been created and before performing collection."""
    collector = get_collector()
    collector.start_test_run()


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished, right before returning the exit status."""
    collector = get_collector()
    collector.end_test_run()

    # Write the report
    try:
        report_file = collector.write_report()
        print(f"\n[OK] Test report written to: {report_file}")
    except Exception as e:
        # Don't fail the test run if report writing fails
        print(f"\n[WARNING] Failed to write test report: {e}")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_request_plan():
    """A minimal ``RequestPlan`` suitable for most unit tests."""
    return RequestPlan(
        intent="general_info",
        request_type="info",
        original_query="Tell me about movies",
    )


@pytest.fixture()
def minimal_evidence_bundle():
    """An empty ``EvidenceBundle`` (no search results)."""
    return EvidenceBundle(search_results=[])


@pytest.fixture()
def request_plan_factory():
    """Factory fixture — call with keyword overrides to build a ``RequestPlan``.

    Usage::

        plan = request_plan_factory(intent="director_info", request_type="info")
    """

    def _factory(**overrides) -> RequestPlan:
        defaults = dict(
            intent="general_info",
            request_type="info",
            original_query="",
        )
        defaults.update(overrides)
        return RequestPlan(**defaults)

    return _factory


@pytest.fixture()
def evidence_bundle_factory():
    """Factory fixture — call with keyword overrides to build an ``EvidenceBundle``."""

    def _factory(**overrides) -> EvidenceBundle:
        defaults = dict(search_results=[])
        defaults.update(overrides)
        return EvidenceBundle(**defaults)

    return _factory


@pytest.fixture()
def sample_search_result():
    """A single realistic search-result dict for use in evidence bundles."""
    return {
        "title": "Sample Movie Title",
        "url": "https://www.imdb.com/title/tt0000001/",
        "content": "A sample movie entry used for testing purposes.",
        "source": "kaggle_imdb",
        "tier": "A",
    }


@pytest.fixture()
def frozen_time():
    """Freeze time to 2024-01-01 12:00:00 UTC for deterministic tests."""
    with freeze_time("2024-01-01 12:00:00") as ft:
        yield ft
