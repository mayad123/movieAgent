# Error Tracking (Failures vs Violations)

Scenario tests do not only report pass/fail. They also write JSON artifacts so you can understand *what broke* and *how it was repaired*.

## Where artifacts are written
- `tests/test_reports/latest.json`: overall scenario run summary (pass rate + top violation types)
- `tests/test_reports/failures/`: scenario failures (assertion mismatches)
- `tests/test_reports/violations/`: validator violations (even if auto-repair happens)
- `tests/test_reports/violations_index.json`: index/summary across all `violations/*.json`

See also:
- `tests/test_reports/README.md` (report structure)
- `tests/helpers/failure_artifact_writer.py` and `tests/helpers/violation_artifact_writer.py` (artifact schemas)

## How to interpret artifacts
- If `latest.json` shows failures, open the corresponding `failures/<scenario>.json` artifact.
  - Failures include details about request_plan, prompt builder messages, evidence formatting stats, and validator outcomes.
- If a scenario fails due to missing required sections or forbidden terms but the system performs auto-repair:
  - the validator violation details will generally be present under `violations/<scenario>.json`.
- Use `violations_index.json` when you need to review violation frequency or quickly jump to the relevant scenario artifacts.

## When you change validator / violation behavior
Two places must stay in sync:

1. **Violation-type classification**
   - `tests/helpers/violation_artifact_writer.py` maps validator violation messages into `violation_type` buckets (e.g. `forbidden_terms`, `verbosity`, `freshness`, `missing_required_section`).

2. **Scenario expected violation types**
   - `tests/test_scenarios_offline.py` derives expected violation-type buckets from violation message text (used to check `validator_checks.expected_violation_types`).

If you add a new violation type or change the wording/patterns of existing violation messages:
- update both classifiers
- update any scenario fixtures that assert expected violation types

## How to update “what gets logged”
- If you change which fields appear on failure/violation artifacts, update:
  - `tests/helpers/failure_artifact_writer.py`
  - `tests/helpers/violation_artifact_writer.py`
  - any report generator logic that reads them (if applicable)
- If you change artifact naming or directory paths:
  - update any code that enumerates those directories (report writer/index logic)

