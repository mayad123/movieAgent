# Running Scenario Tests and Viewing Results

Quick reference guide for running gold/explore scenario tests and viewing violations and failures.

## Running Tests

### Run All Scenarios (Gold + Explore)
```powershell
python -m pytest tests/test_scenarios_offline.py -v
```

### Run Only Gold Scenarios

**Using environment variable (Windows PowerShell):**
```powershell
$env:CINEMIND_SCENARIO_SET="gold"
python -m pytest tests/test_scenarios_offline.py -v
```

**Or as a one-liner (PowerShell):**
```powershell
$env:CINEMIND_SCENARIO_SET="gold"; python -m pytest tests/test_scenarios_offline.py -v
```

**Using environment variable (Windows CMD):**
```cmd
set CINEMIND_SCENARIO_SET=gold
python -m pytest tests/test_scenarios_offline.py -v
```

**Using pytest marker (no env var needed):**
```powershell
python -m pytest tests/test_scenarios_offline.py -m gold -v
```

### Run Only Explore Scenarios

**Using environment variable (Windows PowerShell):**
```powershell
$env:CINEMIND_SCENARIO_SET="explore"
python -m pytest tests/test_scenarios_offline.py -v
```

**Or as a one-liner (PowerShell):**
```powershell
$env:CINEMIND_SCENARIO_SET="explore"; python -m pytest tests/test_scenarios_offline.py -v
```

**Using environment variable (Windows CMD):**
```cmd
set CINEMIND_SCENARIO_SET=explore
python -m pytest tests/test_scenarios_offline.py -v
```

**Using pytest marker (no env var needed):**
```powershell
python -m pytest tests/test_scenarios_offline.py -m explore -v
```

### Quick Run (Less Verbose)
```powershell
# Gold only
python -m pytest tests/test_scenarios_offline.py -m gold -q

# Explore only
python -m pytest tests/test_scenarios_offline.py -m explore -q

# All scenarios
python -m pytest tests/test_scenarios_offline.py -q
```

## Viewing Test Report

### View Latest Report (JSON)
```bash
# Windows PowerShell
Get-Content tests\test_reports\latest.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Cross-platform (with Python)
python -m json.tool tests/test_reports/latest.json
```

### View Summary Statistics
```powershell
# Windows PowerShell - Quick summary
$report = Get-Content tests\test_reports\latest.json | ConvertFrom-Json
Write-Host "Total: $($report.summary.total)"
Write-Host "Passed: $($report.summary.passed)"
Write-Host "Failed: $($report.summary.failed)"
Write-Host "Pass Rate: $($report.summary.pass_rate)%"
Write-Host "Clean Passes: $($report.summary.passed_clean)"
Write-Host "Passes with Violations: $($report.summary.passed_with_violations)"
Write-Host "`nBy Scenario Set:"
$report.by_scenario_set | Format-Table
```

## Viewing Violations

Violations are recorded even when tests pass (for explore scenarios). They're stored in `tests/test_reports/violations/`.

### List All Violation Artifacts
```bash
# Windows PowerShell
Get-ChildItem tests\test_reports\violations\*.json | Select-Object Name

# Cross-platform
ls tests/test_reports/violations/*.json
```

### View Violations Index
```bash
# Windows PowerShell
Get-Content tests\test_reports\violations_index.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Cross-platform
python -m json.tool tests/test_reports/violations_index.json
```

### View a Specific Violation
```bash
# Windows PowerShell
Get-Content tests\test_reports\violations\forbidden_terms_violation.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Cross-platform
python -m json.tool tests/test_reports/violations/forbidden_terms_violation.json
```

### Count Violations by Type
```powershell
# Windows PowerShell - Count violations from report
$report = Get-Content tests\test_reports\latest.json | ConvertFrom-Json
Write-Host "Top Violations:"
$report.top_violations | Format-Table
```

### View All Violations with Details
```powershell
# Windows PowerShell - Show all violation files with summaries
Get-ChildItem tests\test_reports\violations\*.json | ForEach-Object {
    $violation = Get-Content $_.FullName | ConvertFrom-Json
    Write-Host "`n$($_.Name):"
    Write-Host "  Scenario: $($violation.scenario_name)"
    Write-Host "  Violations: $($violation.violations.Count)"
    Write-Host "  Types: $($violation.violation_types -join ', ')"
}
```

## Viewing Failures

Failures occur when tests fail (e.g., gold scenarios with violations or any scenario with other failures). They're stored in `tests/test_reports/failures/`.

### List All Failure Artifacts
```bash
# Windows PowerShell
Get-ChildItem tests\test_reports\failures\*.json | Select-Object Name

# Cross-platform
ls tests/test_reports/failures/*.json
```

### View a Specific Failure
```bash
# Windows PowerShell
Get-Content tests\test_reports\failures\director_matrix.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Cross-platform
python -m json.tool tests/test_reports/failures/director_matrix.json
```

### View All Failures with Details
```powershell
# Windows PowerShell - Show all failure files with summaries
Get-ChildItem tests\test_reports\failures\*.json | ForEach-Object {
    $failure = Get-Content $_.FullName | ConvertFrom-Json
    Write-Host "`n$($_.Name):"
    Write-Host "  Scenario: $($failure.scenario.name)"
    Write-Host "  Query: $($failure.scenario.user_query)"
    Write-Host "  Failures: $($failure.failures.Count)"
    $failure.failures | ForEach-Object { Write-Host "    - $_" }
}
```

### Count Failures by Template
```powershell
# Windows PowerShell - Group failures by template
$failures = Get-ChildItem tests\test_reports\failures\*.json
$grouped = $failures | ForEach-Object {
    $f = Get-Content $_.FullName | ConvertFrom-Json
    [PSCustomObject]@{
        Template = $f.template_id
        Scenario = $f.scenario.name
    }
} | Group-Object Template

$grouped | Format-Table Name, Count -AutoSize
```

## Common Workflows

### Check Gold Suite Status
```powershell
# Run gold tests
$env:CINEMIND_SCENARIO_SET="gold"
python -m pytest tests/test_scenarios_offline.py -q

# Check report
$report = Get-Content tests\test_reports\latest.json | ConvertFrom-Json
Write-Host "Gold Results:"
$report.by_scenario_set.gold | Format-List
```

### Check for Violations in Explore Suite
```powershell
# Run explore tests
$env:CINEMIND_SCENARIO_SET="explore"
python -m pytest tests/test_scenarios_offline.py -q

# Check violations
$report = Get-Content tests\test_reports\latest.json | ConvertFrom-Json
Write-Host "Explore Results:"
$report.by_scenario_set.explore | Format-List
Write-Host "`nPasses with Violations: $($report.by_scenario_set.explore.passed_with_violations)"
Write-Host "Top Violations:"
$report.top_violations | Format-Table
```

### Debug a Specific Failed Scenario
```powershell
# View failure artifact
$failure = Get-Content tests\test_reports\failures\YOUR_SCENARIO_NAME.json | ConvertFrom-Json

Write-Host "Scenario: $($failure.scenario.name)"
Write-Host "Query: $($failure.scenario.user_query)"
Write-Host "`nFailures:"
$failure.failures | ForEach-Object { Write-Host "  - $_" }

Write-Host "`nRequest Plan:"
$failure.request_plan | Format-List

Write-Host "`nMessages:"
$failure.messages | Format-List

Write-Host "`nValidator Result:"
$failure.validator | Format-List
```

### View Violations for a Specific Scenario
```powershell
# View violation artifact
$violation = Get-Content tests\test_reports\violations\YOUR_SCENARIO_NAME.json | ConvertFrom-Json

Write-Host "Scenario: $($violation.scenario_name)"
Write-Host "Template: $($violation.template_id)"
Write-Host "`nViolations:"
$violation.violations | ForEach-Object { Write-Host "  - $_" }

Write-Host "`nViolation Types: $($violation.violation_types -join ', ')"

if ($violation.corrected_text) {
    Write-Host "`nCorrected Text:"
    Write-Host $violation.corrected_text
}
```

## Report Structure

The `latest.json` report contains:

```json
{
  "timestamp": "2024-12-30T10:30:00",
  "summary": {
    "total": 70,
    "passed": 68,
    "failed": 2,
    "pass_rate": 97.14,
    "passed_clean": 65,
    "passed_with_violations": 3,
    "avg_time_ms": 2.85
  },
  "by_template_id": { ... },
  "by_scenario_set": {
    "gold": {
      "total": 28,
      "passed": 27,
      "failed": 1,
      "passed_clean": 27,
      "passed_with_violations": 0
    },
    "explore": {
      "total": 42,
      "passed": 41,
      "failed": 1,
      "passed_clean": 38,
      "passed_with_violations": 3
    }
  },
  "top_violations": [
    { "violation_type": "verbosity", "count": 2 },
    { "violation_type": "forbidden_terms", "count": 1 }
  ]
}
```

## Understanding Results

### Gold Scenarios
- **Must pass clean** (no violations allowed)
- Failures → Check `tests/test_reports/failures/`
- Failures will always include violation details if violations caused the failure

### Explore Scenarios
- **Can pass with violations**
- Violations → Check `tests/test_reports/violations/`
- Failures → Check `tests/test_reports/failures/`
- Both violations and failures are tracked separately

### Violation Types
- `forbidden_terms`: Response contains forbidden words (e.g., "Tier", "Kaggle")
- `verbosity`: Response exceeds/falls below sentence/word limits
- `freshness`: Missing freshness timestamp for time-sensitive queries
- `missing_required_section`: Required sections missing from response

