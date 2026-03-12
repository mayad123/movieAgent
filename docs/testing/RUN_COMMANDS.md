# Running Tests to Generate Reports

This document shows how to run the scenario tests and generate the JSON report.

## Important: Working Directory

**You must run pytest from the project root directory** (where `src/` and `tests/` folders are located).

The project root is: `C:\Users\MDN26\Desktop\Movie Agent\`

## Setting Up Python Path

The tests need to import the `cinemind` module from `src/`. You have two options:

### Option 1: Use PYTHONPATH Environment Variable (Recommended)

```powershell
# Windows PowerShell
$env:PYTHONPATH = "src"; python -m pytest tests/test_scenarios_offline.py -v

# Or set it for the session
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -v
```

```bash
# Linux/Mac
export PYTHONPATH=src
python -m pytest tests/test_scenarios_offline.py -v
```

### Option 2: Use pytest with pythonpath option

```bash
python -m pytest tests/test_scenarios_offline.py -v --pythonpath=src
```

### Option 3: Install package in development mode (one-time setup)

```bash
# From project root
pip install -e .
```

## Basic Commands

### Run All Scenario Tests (Generates Report Automatically)

```powershell
# From project root directory
# Set PYTHONPATH first, then run tests
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -v
```

Or using pytest's pythonpath option:
```powershell
python -m pytest tests/test_scenarios_offline.py -v --pythonpath=src
```

### Quick Run (Minimal Output)

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -q
```

### Verbose Output (See Each Test)

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -v
```

## Complete Example Workflow

```powershell
# 1. Navigate to project root (if not already there)
cd "C:\Users\MDN26\Desktop\Movie Agent"

# 2. Set PYTHONPATH and run tests
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -v

# 3. Check if report was generated
Test-Path tests/test_reports/latest.json

# 4. View the report summary
$report = Get-Content tests/test_reports/latest.json | ConvertFrom-Json
Write-Host "Pass rate: $($report.summary.pass_rate)%"
Write-Host "Total: $($report.summary.total), Passed: $($report.summary.passed), Failed: $($report.summary.failed)"
```

## Verify Report Generation

After running tests, you should see a message at the end:
```
[OK] Test report written to: tests/test_reports/latest.json
```

## View the Report

### Using PowerShell (Windows)

```powershell
# View full report
Get-Content tests/test_reports/latest.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# View summary only
(Get-Content tests/test_reports/latest.json | ConvertFrom-Json).summary

# View pass rate
(Get-Content tests/test_reports/latest.json | ConvertFrom-Json).summary.pass_rate
```

### Using Python

```bash
python -c "import json; report = json.load(open('tests/test_reports/latest.json')); print(f\"Pass rate: {report['summary']['pass_rate']}%\"); print(f\"Total tests: {report['summary']['total']}\"); print(f\"Passed: {report['summary']['passed']}, Failed: {report['summary']['failed']}\")"
```

### Using jq (if installed)

```bash
# View summary
jq '.summary' tests/test_reports/latest.json

# View pass rate
jq -r '.summary.pass_rate' tests/test_reports/latest.json

# View templates with failures
jq '.by_template_id | to_entries | map(select(.value.failed > 0))' tests/test_reports/latest.json

# View top violations
jq '.top_violations' tests/test_reports/latest.json
```

## Viewing Violations

Violations are validator errors detected during tests (e.g., forbidden terms, verbosity issues, missing freshness timestamps). Violations are tracked in the test report even if tests pass (since some scenarios may have violations that don't cause failures).

### View Violations from Test Report

```powershell
# PowerShell - View top violations summary
$report = Get-Content tests/test_reports/latest.json | ConvertFrom-Json
Write-Host "`nTop Violations:" -ForegroundColor Cyan
$report.top_violations | ForEach-Object {
    Write-Host "  $($_.violation_type): $($_.count) occurrences" -ForegroundColor Yellow
}

# View full violations data
$report.top_violations | Format-Table -AutoSize
```

```bash
# Linux/Mac - View top violations
jq '.top_violations' tests/test_reports/latest.json

# Pretty formatted
jq -r '.top_violations[] | "\(.violation_type): \(.count) occurrences"' tests/test_reports/latest.json
```

### View Violations from Failure Artifacts (Detailed)

If tests failed, you can view detailed violation information from the failure artifacts:

```powershell
# PowerShell - View violations from all failure artifacts
if (Test-Path tests/test_reports/failures) {
    Get-ChildItem tests/test_reports/failures/*.json | ForEach-Object {
        $art = Get-Content $_.FullName | ConvertFrom-Json
        if ($art.validator) {
            Write-Host "`n=== $($art.scenario.name) ===" -ForegroundColor Yellow
            Write-Host "Valid: $($art.validator.is_valid)" -ForegroundColor $(if ($art.validator.is_valid) { "Green" } else { "Red" })
            Write-Host "Violations:" -ForegroundColor Cyan
            $art.validator.violations | ForEach-Object { Write-Host "  ✗ $_" -ForegroundColor Red }
        }
    }
} else {
    Write-Host "No failures found. Check latest.json for violation summary." -ForegroundColor Green
}
```

```bash
# Linux/Mac - View violations from failure artifacts
if [ -d tests/test_reports/failures ]; then
    for file in tests/test_reports/failures/*.json; do
        echo "=== $(jq -r '.scenario.name' "$file") ==="
        jq -r '.validator.violations[]?' "$file" | sed 's/^/  ✗ /'
        echo
    done
fi
```

### View Violations for a Specific Failed Scenario

```powershell
# PowerShell - View violations for a specific scenario
if (Test-Path tests/test_reports/failures/director_matrix.json) {
    $art = Get-Content tests/test_reports/failures/director_matrix.json | ConvertFrom-Json
    Write-Host "Scenario: $($art.scenario.name)" -ForegroundColor Cyan
    Write-Host "Valid: $($art.validator.is_valid)"
    Write-Host "`nViolations:" -ForegroundColor Yellow
    $art.validator.violations | ForEach-Object { Write-Host "  - $_" }
    
    # View repair instruction if available
    if ($art.validator.repair_instruction) {
        Write-Host "`nRepair Instruction:" -ForegroundColor Cyan
        Write-Host $art.validator.repair_instruction
    }
}
```

```bash
# Linux/Mac - View violations for a specific scenario
jq '.validator | {is_valid, violations}' tests/test_reports/failures/director_matrix.json

# View violations only
jq -r '.validator.violations[]' tests/test_reports/failures/director_matrix.json
```

### Quick Violation Summary

**Recommended:** Use the CLI for the easiest way to inspect violations:
```bash
# List all scenarios with violations
python -m cinemind.eval list-violations

# Show detailed information for a specific scenario
python -m cinemind.eval show-violation --scenario director_matrix
```

**PowerShell/Manual approach:**
```powershell
# PowerShell - Quick summary of all violations
$report = Get-Content tests/test_reports/latest.json | ConvertFrom-Json
Write-Host "`n=== Violation Summary ===" -ForegroundColor Cyan
Write-Host "Total tests: $($report.summary.total)"
Write-Host "Passed: $($report.summary.passed)" -ForegroundColor Green
Write-Host "Failed: $($report.summary.failed)" -ForegroundColor $(if ($report.summary.failed -gt 0) { "Red" } else { "Green" })
Write-Host "`nTop Violations:" -ForegroundColor Yellow
$report.top_violations | ForEach-Object {
    Write-Host "  $($_.violation_type): $($_.count)"
}
```

## Viewing Failure Artifacts

When tests fail, detailed artifacts are written to `tests/test_reports/failures/`. These contain the full prompt messages, validator results, and evidence for each failed scenario.

**Note:** The `failures/` directory is only created if at least one test fails. If all tests pass, this directory won't exist.

### Check if Any Tests Failed

```powershell
# PowerShell - Check the test report for failures
$report = Get-Content tests/test_reports/latest.json | ConvertFrom-Json
Write-Host "Total: $($report.summary.total), Passed: $($report.summary.passed), Failed: $($report.summary.failed)"
if ($report.summary.failed -gt 0) {
    Write-Host "There are $($report.summary.failed) failed tests. Check tests/test_reports/failures/ for artifacts." -ForegroundColor Yellow
} else {
    Write-Host "All tests passed! No failure artifacts." -ForegroundColor Green
}
```

```bash
# Linux/Mac
jq '.summary | "Total: \(.total), Passed: \(.passed), Failed: \(.failed)"' tests/test_reports/latest.json
```

### List All Failure Artifacts

```powershell
# PowerShell - Check if failures directory exists first
if (Test-Path tests/test_reports/failures) {
    Get-ChildItem tests/test_reports/failures/*.json | Select-Object Name
} else {
    Write-Host "No failures directory found. All tests passed!" -ForegroundColor Green
}
```

```bash
# Linux/Mac
if [ -d tests/test_reports/failures ]; then
    ls tests/test_reports/failures/*.json
else
    echo "No failures directory found. All tests passed!"
fi
```

### View a Specific Failure Artifact

```powershell
# PowerShell - View full artifact (formatted)
Get-Content tests/test_reports/failures/director_matrix.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Or using Python
python -c "import json; print(json.dump(json.load(open('tests/test_reports/failures/director_matrix.json')), indent=2, ensure_ascii=False))"
```

```bash
# Linux/Mac - Using jq (recommended)
cat tests/test_reports/failures/director_matrix.json | jq '.'

# View just the failures
cat tests/test_reports/failures/director_matrix.json | jq '.failures'

# View prompt messages
cat tests/test_reports/failures/director_matrix.json | jq '.messages'

# View validator violations
cat tests/test_reports/failures/director_matrix.json | jq '.validator.violations'
```

### Quick Inspection Commands

```powershell
# PowerShell - View failures from all artifacts
Get-ChildItem tests/test_reports/failures/*.json | ForEach-Object {
    $art = Get-Content $_.FullName | ConvertFrom-Json
    Write-Host "`n=== $($art.scenario.name) ==="
    $art.failures | ForEach-Object { Write-Host "  - $_" }
}
```

```bash
# Linux/Mac - View failures from all artifacts
for file in tests/test_reports/failures/*.json; do
    echo "=== $(jq -r '.scenario.name' "$file") ==="
    jq -r '.failures[]' "$file" | sed 's/^/  - /'
    echo
done
```

### Common Debugging Workflows

**1. Check which scenarios failed (with error handling):**
```powershell
# PowerShell
if (Test-Path tests/test_reports/failures) {
    Get-ChildItem tests/test_reports/failures/*.json | Select-Object Name
} else {
    Write-Host "No failures. All tests passed!" -ForegroundColor Green
}
```

**2. View failures for a specific scenario:**
```powershell
# PowerShell
if (Test-Path tests/test_reports/failures/director_matrix.json) {
    $art = Get-Content tests/test_reports/failures/director_matrix.json | ConvertFrom-Json
    $art.failures
} else {
    Write-Host "No failure artifact found for director_matrix" -ForegroundColor Yellow
}
```

**3. View the prompt that was built:**
```powershell
# PowerShell
if (Test-Path tests/test_reports/failures/director_matrix.json) {
    $art = Get-Content tests/test_reports/failures/director_matrix.json | ConvertFrom-Json
    $art.messages | ForEach-Object { 
        Write-Host "`n--- $($_.role) ---" -ForegroundColor Cyan
        Write-Host $_.content
    }
}
```

**4. View validator violations:**
```powershell
# PowerShell
if (Test-Path tests/test_reports/failures/director_matrix.json) {
    $art = Get-Content tests/test_reports/failures/director_matrix.json | ConvertFrom-Json
    if ($art.validator) {
        $art.validator.violations
    }
}
```

**5. Check evidence formatting stats:**
```powershell
# PowerShell
if (Test-Path tests/test_reports/failures/director_matrix.json) {
    $art = Get-Content tests/test_reports/failures/director_matrix.json | ConvertFrom-Json
    $art.formatted_evidence
}
```

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'cinemind'"

**Solution:** Make sure you're in the project root and set PYTHONPATH:

```powershell
# Verify you're in the right directory
Get-Location
# Should show: C:\Users\MDN26\Desktop\Movie Agent

# Set PYTHONPATH
$env:PYTHONPATH = "src"

# Run tests
python -m pytest tests/test_scenarios_offline.py -v
```

Or use the pythonpath option:
```powershell
python -m pytest tests/test_scenarios_offline.py -v --pythonpath=src
```

## Run Specific Tests

### Run a Single Scenario Test

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py::test_scenario[director_matrix] -v
```

### Run Only the Count Test

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py::test_scenario_count -v
```

## Run with Different Options

### Stop on First Failure

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -x
```

### Show Local Variables on Failure

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -l
```

### No Output (Silent Mode)

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_scenarios_offline.py -q --tb=no
```

## CI/CD Integration

The report generation is non-blocking - if report writing fails, tests still complete successfully.

Example CI script:
```bash
#!/bin/bash
# Set PYTHONPATH
export PYTHONPATH=src

# Run tests
python -m pytest tests/test_scenarios_offline.py -v

# Check pass rate (fail if below threshold)
PASS_RATE=$(python -c "import json; print(json.load(open('tests/test_reports/latest.json'))['summary']['pass_rate'])")
if (( $(echo "$PASS_RATE < 95" | bc -l) )); then
    echo "ERROR: Pass rate $PASS_RATE% is below 95% threshold"
    exit 1
fi
```

## Notes

- The report is **automatically generated** after all tests complete
- The `test_reports/` directory is created automatically if it doesn't exist
- The report overwrites `latest.json` each time (you can copy it with a timestamp for history)
- Report generation failures are non-blocking (tests still pass)
- **Always run from the project root directory** where `src/` and `tests/` folders are located
