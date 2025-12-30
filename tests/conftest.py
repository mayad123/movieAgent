"""
Pytest configuration and fixtures for CineMind tests.
"""
import pytest
from tests.report_generator import get_collector


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
