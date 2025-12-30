# Test Report Format

This directory contains JSON reports generated after running scenario tests. The report file `latest.json` is updated after each test run and provides machine-readable statistics for regression tracking and prompt/template evaluation.

## Failure Artifacts

When scenario tests fail, detailed failure artifacts are written to `failures/` subdirectory. See [Failure Artifacts](#failure-artifacts) section below for details on inspecting failed scenarios.

## Report Location

After running scenario tests, the report is written to:
```
tests/test_reports/latest.json
```

The directory is created automatically if it doesn't exist.

## Report Structure

```json
{
  "timestamp": "2024-12-30T10:30:00",
  "summary": {
    "total": 28,
    "passed": 27,
    "failed": 1,
    "pass_rate": 96.43,
    "avg_time_ms": 2.85
  },
  "by_template_id": {
    "director_info": {
      "total": 5,
      "passed": 5,
      "failed": 0
    },
    "recommendation": {
      "total": 5,
      "passed": 4,
      "failed": 1
    }
  },
  "top_violations": [
    {
      "violation_type": "verbosity",
      "count": 3
    },
    {
      "violation_type": "forbidden_terms",
      "count": 1
    }
  ],
  "evidence_stats": {
    "avg_evidence_items": 2.5,
    "avg_dedupe_reduction": 15.3,
    "max_snippet_length": 350
  }
}
```

## Field Descriptions

### `timestamp`
- **Type**: String (ISO 8601 format)
- **Description**: When the test run completed
- **Example**: `"2024-12-30T10:30:00"`

### `summary`
Overall test run statistics:
- **`total`**: Total number of scenario tests run
- **`passed`**: Number of tests that passed
- **`failed`**: Number of tests that failed
- **`pass_rate`**: Percentage of tests that passed (0-100)
- **`avg_time_ms`**: Average test execution time in milliseconds

### `by_template_id`
Breakdown of test results by response template:
- Each key is a `template_id` (e.g., "director_info", "recommendation", "comparison")
- Each value contains:
  - **`total`**: Number of scenarios using this template
  - **`passed`**: Number of scenarios that passed
  - **`failed`**: Number of scenarios that failed

Use this to identify which templates have the most issues.

### `top_violations`
Frequency of validator violation types across all tests:
- **`violation_type`**: Type of violation detected
  - `"forbidden_terms"`: Response contains forbidden terms (e.g., "Tier", "Kaggle")
  - `"verbosity"`: Response exceeds/falls below sentence/word limits
  - `"freshness"`: Missing freshness timestamp for time-sensitive queries
  - `"missing_required_section"`: Required sections missing from response
- **`count`**: Number of times this violation type occurred

Shows the top 10 most frequent violations, sorted by frequency (descending).

### `evidence_stats`
Statistics about evidence formatting:
- **`avg_evidence_items`**: Average number of evidence items per scenario (before deduplication)
- **`avg_dedupe_reduction`**: Average percentage reduction in evidence items after deduplication
  - Formula: `((original - deduped) / original) * 100`
  - Example: If 4 items become 3, reduction is 25%
- **`max_snippet_length`**: Maximum snippet length (in characters) found across all scenarios

## Usage Examples

### Check Overall Pass Rate

```python
import json
from pathlib import Path

report_path = Path("tests/test_reports/latest.json")
with open(report_path) as f:
    report = json.load(f)

pass_rate = report["summary"]["pass_rate"]
print(f"Pass rate: {pass_rate}%")
```

### Find Templates with Failures

```python
import json
from pathlib import Path

report_path = Path("tests/test_reports/latest.json")
with open(report_path) as f:
    report = json.load(f)

failed_templates = {
    template_id: stats
    for template_id, stats in report["by_template_id"].items()
    if stats["failed"] > 0
}

print("Templates with failures:")
for template_id, stats in failed_templates.items():
    print(f"  {template_id}: {stats['failed']}/{stats['total']} failed")
```

### Track Violation Trends

```python
import json
from pathlib import Path

report_path = Path("tests/test_reports/latest.json")
with open(report_path) as f:
    report = json.load(f)

print("Top violations:")
for violation in report["top_violations"]:
    print(f"  {violation['violation_type']}: {violation['count']} occurrences")
```

### Compare Reports (Regression Detection)

```python
import json
from pathlib import Path

def load_report(path):
    with open(path) as f:
        return json.load(f)

baseline = load_report("tests/test_reports/baseline.json")
latest = load_report("tests/test_reports/latest.json")

# Compare pass rates
baseline_rate = baseline["summary"]["pass_rate"]
latest_rate = latest["summary"]["pass_rate"]

if latest_rate < baseline_rate:
    print(f"⚠ Regression detected: Pass rate dropped from {baseline_rate}% to {latest_rate}%")
else:
    print(f"✓ Pass rate improved/stable: {latest_rate}% (was {baseline_rate}%)")
```

## CI/CD Integration

The report generation is designed to be non-blocking:
- If report writing fails, a warning is printed but tests continue
- The `test_reports/` directory is created automatically if missing
- Reports are deterministic (same input produces same output)

Example CI script:
```bash
# Run tests and generate report
pytest tests/test_scenarios_offline.py -v

# Check if report exists and parse it
if [ -f tests/test_reports/latest.json ]; then
    PASS_RATE=$(jq -r '.summary.pass_rate' tests/test_reports/latest.json)
    if (( $(echo "$PASS_RATE < 95" | bc -l) )); then
        echo "ERROR: Pass rate $PASS_RATE% is below 95% threshold"
        exit 1
    fi
fi
```

## Regression Tracking

To track regressions over time:

1. **Save baseline report** after a known-good state:
   ```bash
   cp tests/test_reports/latest.json tests/test_reports/baseline.json
   ```

2. **Compare after changes**:
   ```python
   # Load both reports and compare key metrics
   # Alert if pass_rate decreases or violations increase
   ```

3. **Archive reports** for historical tracking:
   ```bash
   # Add timestamp to filename
   cp tests/test_reports/latest.json "tests/test_reports/report_$(date +%Y%m%d_%H%M%S).json"
   ```

## Failure Artifacts

When a scenario test fails, a detailed JSON artifact is written to `failures/<scenario_name>.json` to aid in debugging.

### Location

Failure artifacts are written to:
```
tests/test_reports/failures/<scenario_name>.json
```

The directory is created automatically if it doesn't exist.

### Artifact Structure

Each failure artifact contains:

```json
{
  "scenario": {
    "name": "director_matrix",
    "user_query": "Who directed The Matrix?",
    "expected": { ... }
  },
  "request_plan": {
    "request_type": "info",
    "intent": "director_info",
    "entities_typed": { "movies": ["The Matrix"], "people": [] },
    "need_freshness": false,
    "freshness_ttl_hours": 168.0,
    "require_tier_a": true,
    "allowed_source_tiers": ["A"],
    "reject_tier_c": true
  },
  "template_id": "director_info",
  "messages": [
    {
      "role": "system",
      "content": "..."
    },
    {
      "role": "user",
      "content": "..."
    }
  ],
  "formatted_evidence": {
    "text": "...",
    "counts": { "before": 3, "after": 2 },
    "max_snippet_len": 350,
    "dedupe_removed": 1,
    "items_count": 2
  },
  "validator": {
    "is_valid": false,
    "violations": ["Forbidden term detected: 'Tier'"],
    "corrected_text": null,
    "requires_reprompt": true,
    "repair_instruction": "..."
  },
  "failures": [
    "Expected template_id 'director_info', got 'general_info'",
    "Formatted evidence must NOT contain 'Tier' but does"
  ],
  "timing_ms": 2.5,
  "timestamp": "2024-12-30T10:30:00"
}
```

### Inspecting a Failed Scenario

#### Quick Inspection

```bash
# View a specific failure artifact
cat tests/test_reports/failures/director_matrix.json | jq '.'

# View just the failures
cat tests/test_reports/failures/director_matrix.json | jq '.failures'

# View the prompt messages
cat tests/test_reports/failures/director_matrix.json | jq '.messages'

# View validator violations
cat tests/test_reports/failures/director_matrix.json | jq '.validator.violations'
```

#### Using Python

```python
import json
from pathlib import Path

artifact_path = Path("tests/test_reports/failures/director_matrix.json")
with open(artifact_path) as f:
    artifact = json.load(f)

# View failures
print("Failures:")
for failure in artifact["failures"]:
    print(f"  - {failure}")

# View prompt messages
print("\nPrompt Messages:")
for msg in artifact["messages"]:
    print(f"{msg['role']}: {msg['content'][:100]}...")

# View validator result
if artifact.get("validator"):
    print(f"\nValidator: valid={artifact['validator']['is_valid']}")
    print(f"Violations: {artifact['validator']['violations']}")
```

#### Common Debugging Workflows

**1. Check what template was selected:**
```bash
jq '.template_id' tests/test_reports/failures/director_matrix.json
```

**2. See the actual prompt that was built:**
```bash
jq '.messages[].content' tests/test_reports/failures/director_matrix.json
```

**3. Check evidence formatting:**
```bash
jq '.formatted_evidence' tests/test_reports/failures/director_matrix.json
```

**4. See validator violations:**
```bash
jq '.validator.violations' tests/test_reports/failures/director_matrix.json
```

**5. View all failure messages:**
```bash
jq -r '.failures[]' tests/test_reports/failures/director_matrix.json
```

### Notes

- Artifacts are overwritten on subsequent test runs (same scenario name = same file)
- Artifact writing failures are non-blocking (tests still fail for the real reason)
- Artifacts include the full prompt messages, making it easy to debug prompt construction issues
- Validator results show exactly what violations were detected
- Evidence formatting stats show deduplication and snippet length information

## Violation Artifacts

When a scenario produces validator violations (forbidden terms, verbosity issues, missing freshness timestamps, etc.), a detailed JSON artifact is written to `violations/<scenario_name>.json` **even if the test passes**. This allows tracking violations separately from test failures.

### Location

Violation artifacts are written to:
```
tests/test_reports/violations/<scenario_name>.json
```

The directory is created automatically if it doesn't exist.

### Violations Index

After all tests complete, a violations index is generated:
```
tests/test_reports/violations_index.json
```

This index lists all scenarios with violations, making it easy to see which scenarios had validator issues even if they passed.

### Artifact Structure

Each violation artifact contains:

```json
{
  "scenario_name": "director_matrix",
  "template_id": "director_info",
  "user_query": "Who directed The Matrix?",
  "violations": [
    {
      "type": "forbidden_terms",
      "message": "Forbidden term detected: 'Tier'"
    },
    {
      "type": "verbosity",
      "message": "Response exceeds maximum sentence limit of 2 sentences"
    }
  ],
  "violation_types": ["forbidden_terms", "verbosity"],
  "violation_count": 2,
  "offending_text": "The Matrix was directed by the Wachowskis according to Tier A sources.",
  "fixed_text": null,
  "repair_instruction": "CORRECTION REQUIRED: The previous response violated...",
  "timestamp": "2024-12-30T10:30:00"
}
```

### Violations Index Structure

The violations index contains:

```json
{
  "timestamp": "2024-12-30T10:30:00",
  "total_scenarios_with_violations": 5,
  "scenarios": [
    {
      "scenario_name": "director_matrix",
      "template_id": "director_info",
      "user_query": "Who directed The Matrix?",
      "violation_types": ["forbidden_terms"],
      "violation_count": 1,
      "artifact_path": "violations/director_matrix.json"
    }
  ]
}
```

### Inspecting Violations

#### Quick Inspection - View All Violations

```powershell
# PowerShell - View violations index
$index = Get-Content tests/test_reports/violations_index.json | ConvertFrom-Json
Write-Host "Total scenarios with violations: $($index.total_scenarios_with_violations)" -ForegroundColor Yellow
$index.scenarios | ForEach-Object {
    Write-Host "`n=== $($_.scenario_name) ===" -ForegroundColor Cyan
    Write-Host "Query: $($_.user_query)"
    Write-Host "Violations: $($_.violation_count) ($($_.violation_types -join ', '))"
}
```

```bash
# Linux/Mac
jq '.scenarios[] | "\(.scenario_name): \(.violation_count) violations (\(.violation_types | join(", ")))"' tests/test_reports/violations_index.json
```

#### View a Specific Violation Artifact

```powershell
# PowerShell - View full violation artifact
python -c "import json; print(json.dumps(json.load(open('tests/test_reports/violations/director_matrix.json')), indent=2))"
```

```bash
# Linux/Mac
cat tests/test_reports/violations/director_matrix.json | jq '.'
```

#### View Violations for a Scenario

```powershell
# PowerShell - View violations for a specific scenario
$art = Get-Content tests/test_reports/violations/director_matrix.json | ConvertFrom-Json
Write-Host "Scenario: $($art.scenario_name)" -ForegroundColor Cyan
Write-Host "Violations ($($art.violation_count)):" -ForegroundColor Yellow
$art.violations | ForEach-Object {
    Write-Host "  [$($_.type)] $($_.message)" -ForegroundColor Red
}
```

#### Common Debugging Workflows

**1. List all scenarios with violations:**
```powershell
# PowerShell
$index = Get-Content tests/test_reports/violations_index.json | ConvertFrom-Json
$index.scenarios | Select-Object scenario_name, violation_types, violation_count
```

**2. Find scenarios with specific violation types:**
```powershell
# PowerShell - Find scenarios with forbidden_terms violations
$index = Get-Content tests/test_reports/violations_index.json | ConvertFrom-Json
$index.scenarios | Where-Object { $_.violation_types -contains "forbidden_terms" } | Select-Object scenario_name, user_query
```

**3. View offending text and repair instruction:**
```powershell
# PowerShell
$art = Get-Content tests/test_reports/violations/director_matrix.json | ConvertFrom-Json
Write-Host "Offending Text:" -ForegroundColor Yellow
Write-Host $art.offending_text
if ($art.repair_instruction) {
    Write-Host "`nRepair Instruction:" -ForegroundColor Cyan
    Write-Host $art.repair_instruction
}
```

### Using the CLI to Inspect Violations

The easiest way to inspect violations is using the built-in CLI:

#### List All Violations

```bash
python -m cinemind.eval list-violations
```

Example output:
```
Found 3 scenario(s) with violations:

Scenario Name                              Template ID          Violations      Types
====================================================================================================
director_matrix                            director_info        2               forbidden_terms, verbosity
forbidden_terms_violation                  director_info        1               forbidden_terms
verbosity_violation                        director_info        1               verbosity

Use 'python -m cinemind.eval show-violation --scenario <name>' to see details.
```

#### Show Detailed Violation Information

```bash
python -m cinemind.eval show-violation --scenario director_matrix
```

Example output:
```
================================================================================
Scenario: director_matrix
================================================================================

User Query:
  Who directed The Matrix?

Template ID: director_info

Violations (2):
--------------------------------------------------------------------------------
  1. [forbidden_terms] Forbidden term detected: 'Tier'
  2. [verbosity] Response exceeds maximum sentence limit of 2 sentences

Offending Text:
--------------------------------------------------------------------------------
The Matrix was directed by the Wachowskis according to Tier A sources. This is a groundbreaking science fiction film that was released in 1999. It was written and directed by the Wachowskis, who are also known as Lana and Lilly Wachowski.
--------------------------------------------------------------------------------

Repair Instruction:
--------------------------------------------------------------------------------
CORRECTION REQUIRED: The previous response violated the response contract.

VIOLATIONS:
1. Forbidden term detected: 'Tier'
2. Response exceeds maximum sentence limit of 2 sentences

STRICT REQUIREMENTS:
[...]
```

#### CLI Notes

- The CLI reads from `tests/test_reports/violations_index.json`
- Works offline (no API calls required)
- Exits gracefully if no violations exist
- Use `list-violations` to discover which scenarios have violations
- Use `show-violation --scenario <name>` to see full details for fixing prompts/templates

### Notes

- Violation artifacts are written **even when tests pass** (unlike failure artifacts which are only written on failure)
- Artifact writing failures are non-blocking (tests continue normally)
- Violations are tracked separately from test failures - a scenario can pass but still have violations
- The violations index is regenerated after each test run
- Violation types include: `forbidden_terms`, `verbosity`, `freshness`, `missing_required_section`
- Use the CLI (`python -m cinemind.eval list-violations` and `python -m cinemind.eval show-violation`) for quick inspection

## Notes

- The report is generated **after** all tests complete, even if some tests fail
- Violation counts include all violations found, not just failed tests
- Evidence statistics only include scenarios with evidence (excludes scenarios with 0 evidence items)
- Dedupe reduction is calculated as: `((original_count - deduped_count) / original_count) * 100`

