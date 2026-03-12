# Scripts Restructure — Deliverable (Prompt 4)

After cleanup and validation, `scripts/` was reorganized into logical subpackages. Behavior is unchanged; only layout and references were updated.

---

## 1. Proposed New Structure

```
scripts/
├── __init__.py
├── db/                          # Database maintenance
│   ├── __init__.py
│   └── migrate_tags.py
├── observability/               # Observability inspection
│   ├── __init__.py
│   └── view_observability.py
├── export/                      # Data export
│   ├── __init__.py
│   └── export_to_csv.py
└── analysis/                    # Test/analytics analysis
    ├── __init__.py
    └── analyze_test_results.py
```

**Top-level directories preserved:** `docker/`, `docs/`, `src/`, `web/`, `tests/` — unchanged.

---

## 2. Justification for Groupings

| Subpackage       | Responsibility / domain              | Script(s)                | Justification |
|------------------|--------------------------------------|--------------------------|----------------|
| **db**           | Database schema and maintenance      | `migrate_tags.py`        | One-off schema migrations; clear boundary from app runtime. |
| **observability**| Inspecting observability data        | `view_observability.py`  | Queries CineMind DB and observability layer; single concern. |
| **export**       | Exporting data to files (CSV, etc.)  | `export_to_csv.py`       | All export targets (DB tables, test results, prompt comparison) share the same “export” concern. |
| **analysis**     | Analyzing test/run data              | `analyze_test_results.py`| Uses test_results DB for pass rates, flaky tests, version comparison; distinct from export. |

- **Separation of concerns:** DB ops, observability inspection, export, and analysis are separate.
- **Maintainability:** New scripts (e.g. another migration or export) have a clear place.
- **Testability:** Subpackages can be tested or stubbed by domain.
- **Dependency boundaries:** Only `observability/`, `export/`, and `analysis/` add `src` to `sys.path` for `cinemind`; `db/` uses only stdlib sqlite3.

---

## 3. Naming and Conventions

- **Subpackage names:** `db`, `observability`, `export`, `analysis` — short, lowercase, one word where possible.
- **Script names:** Unchanged (`migrate_tags`, `view_observability`, `export_to_csv`, `analyze_test_results`) so CLI usage stays recognizable.
- **Run commands:** From repo root, run the script file directly (recommended in docs):
  - `python scripts/db/migrate_tags.py`
  - `python scripts/observability/view_observability.py [options]`
  - `python scripts/export/export_to_csv.py [options]`
  - `python scripts/analysis/analyze_test_results.py [options]`
- **Path handling:** Scripts under a subpackage use `Path(__file__).resolve().parent.parent.parent` to get repo root, then `repo_root / "src"` for `sys.path`, so they work when run from any cwd.

---

## 4. Changes Made

- Added `scripts/__init__.py` and `scripts/{db,observability,export,analysis}/__init__.py`.
- Moved each script into its subpackage and fixed `sys.path` for those that import `cinemind`.
- Removed the four flat scripts from `scripts/` (no duplicate entrypoints).
- Updated all references in:
  - `README.md`, `docs/VIEW_TEST_RESULT_COMMANDS.md`, `docs/VIEW_OBSERVABILITY_GUIDE.md`, `docs/OBSERVABILITY.md`, `docs/TESTING_GUIDE.md`, `docs/TESTING_SETUP_SUMMARY.md`, `docs/SCALING_TESTING.md`, `docs/BASELINE_INVENTORY_AND_PROTECTED_LIST.md`, `docs/SAFE_CLEANUP_PASS_DELETION_LIST.md`, `data/exports/README.md`.

---

## 5. Confirmation: Playground + Real Workflow + Tests

- **Playground server:** `python -m tests.playground_server` — imports and app load successfully; server starts (Uvicorn on port 8000).
- **Real LLM workflow:** `CineMind`, `run_playground_query`, and API entrypoints import successfully. No code under `src/` or `tests/` was changed; only `scripts/` layout and doc references were updated.
- **Scripts:** All four scripts execute from their new paths and respond to `--help` when run from repo root (e.g. `python scripts/observability/view_observability.py --help`). `scripts/db/migrate_tags.py` runs correctly against the default DB.
- **Tests:** `pytest tests/ --ignore=tests/test_runner_interactive.py` — **404 passed**. The same 31 failures and 17 errors as before the restructure (evidence formatter, contract, smoke); no new failures introduced by this restructure.

---

## 6. Summary

- **New structure:** `scripts/` split into `db/`, `observability/`, `export/`, `analysis/` with one script per subpackage.
- **Justification:** Grouping by responsibility/domain improves separation of concerns, maintainability, testability, and dependency boundaries.
- **Behavior:** Identical; only structure and documentation references were changed.
- **Confirmation:** Playground and real workflow both run; all four scripts work from new paths; test pass count unchanged (404 passed).
