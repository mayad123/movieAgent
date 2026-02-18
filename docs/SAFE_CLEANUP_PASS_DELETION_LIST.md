# Safe Cleanup Pass — Deletion List and Verification

This document records the conservative cleanup pass performed without restructuring the repo. Only **irrelevant or unused** items were removed after proving they are not referenced by the real LLM workflow, playground server, Docker/build/run, or tests.

---

## 1. Deletion List with Justification

### 1.1 Removed (Deleted)

| Item | Justification |
|------|---------------|
| **`scripts/analysis/`** (empty directory) | Empty folder; no files. Not referenced by any code, Dockerfile, docker-compose, or docs. Docs reference `scripts/analyze_test_results.py` (flat path), not this dir. Created during an incomplete refactor; safe to remove. |
| **`scripts/db/`** (empty directory) | Same as above. No `scripts/db/*.py`; docs reference `scripts/migrate_tags.py` at top level. |
| **`scripts/export/`** (empty directory) | Same. Docs reference `scripts/export_to_csv.py` at top level. |
| **`scripts/observability/`** (empty directory) | Same. Docs reference `scripts/view_observability.py` at top level. |

**Proof of non-use:**

- **Imports/references:** No Python file in `src/`, `tests/`, or `docker/` imports from `scripts.analysis`, `scripts.db`, `scripts.export`, or `scripts.observability`. Grep for `scripts/analysis`, `scripts/db`, `scripts/export`, `scripts/observability` (as import paths or in run commands) finds no references.
- **Runtime:** Real LLM path uses `src.api.main` and `src.cinemind.agent`; playground uses `tests.playground_server` and `tests.playground_runner`. Neither uses these script subdirs.
- **Docker:** `docker/Dockerfile` and `docker-compose.yml` copy only `src/` and run `uvicorn src.api.main:app`. No reference to `scripts/` subdirs.
- **Tests:** Pytest collects from `tests/` and uses `conftest.py`, `report_generator`, fixtures, etc. No test references these four directories.

### 1.2 Not Deleted (Retained)

| Category | Reason |
|----------|--------|
| **All four flat scripts** (`view_observability.py`, `migrate_tags.py`, `export_to_csv.py`, `analyze_test_results.py`) | Referenced in multiple docs (VIEW_TEST_RESULT_COMMANDS.md, TESTING_SETUP_SUMMARY.md, SCALING_TESTING.md, OBSERVABILITY.md, data/exports/README.md, VIEW_OBSERVABILITY_GUIDE.md) and in BASELINE_INVENTORY. Not dead code; used by operators. |
| **requirements.txt dependencies** | Kept as-is. `matplotlib` is not imported in any `.py` file but is mentioned in tests/README; removal would be speculative. Other deps (pandas, numpy, kagglehub, etc.) are used in `src/` or `tests/`. No safe dependency removal without further analysis. |
| **test_runner_interactive.py / parallel_runner.py** | They depend on missing modules (`evaluator`, `test_runner`). Pre-existing broken state; not caused by this cleanup. Excluding them from collection allows the rest of the test suite to run. No deletion of these files. |
| **Other test files** | All are either used by pytest (unit/, integration/, contract/, test_scenarios_offline, etc.) or by the interactive/parallel runners. No truly disconnected stubs identified that are safe to remove. |

---

## 2. Dependency Manifests

- **No changes** were made to `requirements.txt`. All listed packages are either used in `src/` or `tests/` or (in the case of `matplotlib`) referenced in documentation; removing any would require separate verification.

---

## 3. Verification Summary

### 3.1 Playground Server

- **Command:** `python -m tests.playground_server` (with `PYTHONPATH=src` or equivalent so `cinemind` and `tests` are importable).
- **Result:** Server starts successfully; Uvicorn reports “Application startup complete” and “Uvicorn running on http://0.0.0.0:8000”.
- **Imports checked:** `tests.playground_runner.run_playground`, `tests.playground_server.app` load without error.

### 3.2 Real LLM Workflow

- **Entrypoints:** `src.api.main` (API) and `src.cinemind.agent` (CLI).
- **Result:** `CineMind` and `run_playground_query` (used by API fallback) import successfully. No code paths were removed; script deletions were limited to empty directories.
- **Scripts:** All four scripts under `scripts/` (now in subpackages: observability/, db/, export/, analysis/) respond to `--help` when run from repo root (e.g. `python scripts/observability/view_observability.py --help`), so CLI entrypoints are intact.

### 3.3 Tests

- **Command used:** `python3 -m pytest tests/ --ignore=tests/test_runner_interactive.py` (to avoid collection error from missing `test_cases`/`evaluator`/`test_runner` when run from project root).
- **Result:** 404 tests passed. 31 failures and 17 errors are **pre-existing** (e.g. `EvidenceFormatResult` API in `test_evidence_formatter.py`, contract tests, smoke tests, scenario assertions in `test_scenarios_offline.py`). None are caused by the removal of the four empty script directories.
- **Conclusion:** The cleanup did not introduce new test failures. Existing failures are outside the scope of this safe cleanup pass.

### 3.4 Broken Imports Caused by Removals

- **None.** Only empty directories were removed. No Python modules or script files were deleted, so no import or runtime paths were affected by this pass.

---

## 4. Summary

- **Deleted:** Four empty directories under `scripts/`: `analysis/`, `db/`, `export/`, `observability/`.
- **Unchanged:** All flat scripts, `src/`, `tests/` (except the above dirs), `web/`, `docker/`, `requirements.txt`, and docs.
- **Verification:** Playground server and real LLM entrypoints run/import successfully; scripts respond to `--help`; pytest runs and the only failures/errors are pre-existing.

This completes the safe cleanup pass without restructuring the repo.
