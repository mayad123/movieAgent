"""
Test report generator for scenario matrix tests.

Collects statistics during test runs and generates a JSON report.
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict, field


@dataclass
class ScenarioResult:
    """Result for a single scenario test."""
    scenario_name: str
    template_id: Optional[str]
    passed: bool
    duration_ms: float
    failure_count: int
    failures: List[str] = field(default_factory=list)
    violation_types: List[str] = field(default_factory=list)
    evidence_items: int = 0
    evidence_deduped_count: int = 0
    evidence_max_snippet_len: int = 0
    scenario_set: Optional[str] = None
    passed_clean: bool = True  # True if passed with zero violations
    has_violations: bool = False  # True if validation found violations
    kaggle_outcome: Optional[Dict[str, Any]] = None  # Kaggle behavior outcome


class ScenarioReportCollector:
    """Collects statistics during scenario test runs."""
    
    def __init__(self):
        self.results: List[ScenarioResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def start_test_run(self):
        """Mark the start of a test run."""
        self.start_time = time.time()
        self.results = []
    
    def record_scenario_result(
        self,
        scenario_name: str,
        template_id: Optional[str],
        passed: bool,
        duration_ms: float,
        failures: List[str],
        violation_types: List[str] = None,
        evidence_items: int = 0,
        evidence_deduped_count: int = 0,
        evidence_max_snippet_len: int = 0,
        scenario_set: Optional[str] = None,
        passed_clean: bool = True,
        has_violations: bool = False,
        kaggle_outcome: Optional[Dict[str, Any]] = None
    ):
        """
        Record the result of a single scenario test.
        
        Args:
            scenario_name: Name of the scenario
            template_id: Template ID used
            passed: Whether the test passed
            duration_ms: Test duration in milliseconds
            failures: List of failure messages
            violation_types: List of violation type strings
            evidence_items: Number of evidence items before deduplication (from counts.before)
            evidence_deduped_count: Number of evidence items after deduplication (from counts.after)
            evidence_max_snippet_len: Maximum snippet length (from max_snippet_len)
        """
        result = ScenarioResult(
            scenario_name=scenario_name,
            template_id=template_id,
            passed=passed,
            duration_ms=duration_ms,
            failure_count=len(failures),
            failures=failures,
            violation_types=violation_types or [],
            evidence_items=evidence_items,
            evidence_deduped_count=evidence_deduped_count,
            evidence_max_snippet_len=evidence_max_snippet_len,
            scenario_set=scenario_set,
            passed_clean=passed_clean,
            has_violations=has_violations,
            kaggle_outcome=kaggle_outcome
        )
        self.results.append(result)
    
    def end_test_run(self):
        """Mark the end of a test run."""
        self.end_time = time.time()
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a JSON report from collected results."""
        if not self.results:
            return {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "pass_rate": 0.0,
                    "passed_clean": 0,
                    "passed_with_violations": 0,
                    "avg_time_ms": 0.0
                },
                "by_template_id": {},
                "by_scenario_set": {},
                "top_violations": [],
                "evidence_stats": {
                    "avg_evidence_items": 0.0,
                    "avg_dedupe_reduction": 0.0,
                    "max_snippet_length": 0
                }
            }
        
        # Calculate summary statistics
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        passed_clean = sum(1 for r in self.results if r.passed and r.passed_clean)
        passed_with_violations = sum(1 for r in self.results if r.passed and r.has_violations)
        avg_time_ms = sum(r.duration_ms for r in self.results) / total if total > 0 else 0.0
        
        # Group by template_id
        by_template: Dict[str, Dict[str, int]] = defaultdict(lambda: {"passed": 0, "failed": 0, "total": 0})
        for result in self.results:
            template_key = result.template_id or "unknown"
            by_template[template_key]["total"] += 1
            if result.passed:
                by_template[template_key]["passed"] += 1
            else:
                by_template[template_key]["failed"] += 1
        
        # Group by scenario_set
        by_scenario_set: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "passed": 0, 
            "failed": 0, 
            "total": 0,
            "passed_clean": 0,
            "passed_with_violations": 0
        })
        for result in self.results:
            set_key = result.scenario_set or "unknown"
            by_scenario_set[set_key]["total"] += 1
            if result.passed:
                by_scenario_set[set_key]["passed"] += 1
                if result.passed_clean:
                    by_scenario_set[set_key]["passed_clean"] += 1
                if result.has_violations:
                    by_scenario_set[set_key]["passed_with_violations"] += 1
            else:
                by_scenario_set[set_key]["failed"] += 1
        
        # Calculate top violations
        violation_counts: Dict[str, int] = defaultdict(int)
        for result in self.results:
            for violation_type in result.violation_types:
                violation_counts[violation_type] += 1
        
        # Sort violations by frequency (descending)
        top_violations = [
            {"violation_type": v_type, "count": count}
            for v_type, count in sorted(violation_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Calculate evidence statistics
        evidence_items_list = [r.evidence_items for r in self.results if r.evidence_items > 0]
        avg_evidence_items = sum(evidence_items_list) / len(evidence_items_list) if evidence_items_list else 0.0
        
        # Calculate dedupe reduction (percentage reduction from original to deduped)
        dedupe_reductions = []
        for result in self.results:
            if result.evidence_items > 0 and result.evidence_deduped_count >= 0:
                reduction = ((result.evidence_items - result.evidence_deduped_count) / result.evidence_items * 100)
                dedupe_reductions.append(reduction)
        avg_dedupe_reduction = sum(dedupe_reductions) / len(dedupe_reductions) if dedupe_reductions else 0.0
        
        max_snippet_length = max((r.evidence_max_snippet_len for r in self.results), default=0)
        
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": round(pass_rate, 2),
                "passed_clean": passed_clean,
                "passed_with_violations": passed_with_violations,
                "avg_time_ms": round(avg_time_ms, 2)
            },
            "by_template_id": dict(by_template),
            "by_scenario_set": dict(by_scenario_set),
            "top_violations": top_violations[:10],  # Top 10 violations
            "evidence_stats": {
                "avg_evidence_items": round(avg_evidence_items, 2),
                "avg_dedupe_reduction": round(avg_dedupe_reduction, 2),
                "max_snippet_length": max_snippet_length
            }
        }
        
        return report
    
    def write_report(self, report_dir: Path = None):
        """Write the report to test_reports/latest.json and generate violations index."""
        if report_dir is None:
            # Default to tests/test_reports/
            report_dir = Path(__file__).parent.parent / "test_reports"
        
        # Create directory if it doesn't exist
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / "latest.json"
        
        report = self.generate_report()
        
        # Write JSON report with indentation for readability
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            # Generate violations index after writing report
            try:
                from tests.helpers.violation_artifact_writer import generate_violations_index
                violations_dir = report_dir / "violations"
                index_path = generate_violations_index(violations_dir)
                if index_path:
                    print(f"[OK] Violations index written to: {index_path}")
            except Exception as e:
                # Don't fail report writing if index generation fails
                print(f"Warning: Failed to generate violations index: {e}")
            
            return report_file
        except Exception as e:
            print(f"Warning: Failed to write test report to {report_file}: {e}")
            return None


# Global collector instance
_collector = ScenarioReportCollector()


def get_collector() -> ScenarioReportCollector:
    """Get the global scenario report collector."""
    return _collector

