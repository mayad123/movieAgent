# Cursor hooks: pytest runs and session-log signals

This repo configures **Cursor IDE hooks** so that after the Agent or Tab edits a file, a **focused pytest** slice runs automatically and (separately) **session-log path signals** may be recorded. Configuration lives next to the runners:

- [`/.cursor/hooks.json`](../../.cursor/hooks.json) — registers `afterFileEdit` and `afterTabFileEdit` with timeouts for **pytest** and **session tracking**.
- [`/.cursor/hooks/path_map.json`](../../.cursor/hooks/path_map.json) — maps path prefixes under the repo root to `pytest` target paths.
- [`/.cursor/hooks/run-related-tests`](../../.cursor/hooks/run-related-tests) — reads hook JSON from stdin, resolves `file_path`, picks targets, runs `python -m pytest -q …`.
- [`/.cursor/hooks/track-scoped-work`](../../.cursor/hooks/track-scoped-work) — reads the same payload, appends debounced rows to **`docs/session_logs/.tracking/signals.jsonl`** (gitignored) when the path matches [`session_track_map.json`](../../.cursor/hooks/session_track_map.json). Use [`scripts/session_log_draft_from_signals.py`](../../scripts/session_log_draft_from_signals.py) to turn signals into a draft entry under `docs/session_logs/entries/` (then append [`MANIFEST.md`](../session_logs/MANIFEST.md) manually).

Official Cursor behavior and payload shapes: [Hooks | Cursor Docs](https://cursor.com/docs/hooks).

**Relationship to skills:** [CURSOR_SKILLS.md](CURSOR_SKILLS.md) is **online-first** for prompt and scenario workflows (live stack + [`tests/test_cases/`](../../tests/test_cases/)). Hooks only run **offline pytest** for quick feedback; they do not replace interactive/parallel runner validation. For a full visual flow of rules, skills, and hooks together, see [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md).

**Relationship to docs:** Edits under `docs/**` are **skipped** by **`run-related-tests`** `skip_prefixes`—no automatic pytest. The **session tracker** may still record selected doc prefixes (for example `docs/planning/` and `docs/AIbuilding/`) per `session_track_map.json`. Use [QUERYING.md](QUERYING.md) and planning/session manifests when investigating history.

## How mapping works

1. The script resolves the repo root (directory containing `pyproject.toml`).
2. It converts the edited absolute path to a path relative to the repo (POSIX `/`).
3. If the relative path starts with any prefix in `skip_prefixes` (for example `docs/`, `data/`, `tests/test_reports/`, `.cursor/`), it **does nothing** (avoids noise and recursion while editing hook files).
4. Otherwise it chooses pytest targets in this order:
   - **Edits under `tests/`** — special cases (for example a single `tests/unit/.../test_*.py` file, `tests/fixtures/scenarios/`, `tests/conftest.py`, `tests/helpers/`, etc.) are handled in the script.
   - **Everything else** — **longest matching** `prefix` in `path_map.json` `entries` wins; its `pytest_targets` list is passed as additional arguments to one `pytest` invocation.

Prompting and agent code intentionally include **`tests/test_scenarios_offline.py`** in their targets because template and validator changes must stay aligned with the YAML scenario matrix (see [TEST_COVERAGE_MAP](../practices/code-review/TEST_COVERAGE_MAP.md)).

## Debouncing

`debounce_seconds` in `path_map.json` (default 30) skips duplicate runs when the **same** pytest command was started recently. State is stored in `.cursor/hooks/.related_tests_last_run` (local only; safe to delete).

`session_track_map.json` has its own `debounce_seconds` (per **path**); state is stored in `.cursor/hooks/.session_track_last` (local only; gitignored companion).

## Session path recording (`track-scoped-work`)

1. Resolves repo root and relative `file_path` from the hook payload (same as pytest runner).
2. If the path matches a longest prefix in `session_track_map.json` `tracked_prefixes`, appends one JSON line to `docs/session_logs/.tracking/signals.jsonl`.
3. **YAML scenario fixtures** under `tests/fixtures/scenarios/` use topic tag `scenarios` (files are `.yaml`); the tracker keys off the directory prefix, not the extension alone.

To turn queued signals into a draft session file, run:

```bash
python scripts/session_log_draft_from_signals.py
python scripts/session_log_draft_from_signals.py --write --slug my-session-slug
```

Then edit the body, append [`MANIFEST.md`](../session_logs/MANIFEST.md), and commit.

## Exit behavior

**`run-related-tests`** always exits **0** so a failing test run does not block further agent edits. Failures still appear in **Cursor → Output → Hooks** and in the terminal stream from pytest.

**`track-scoped-work`** always exits **0** and only appends local signal lines; it never writes canonical entries under `docs/session_logs/entries/`.

The pytest runner uses **`python -m pytest`** (the same interpreter that executes the script) so hooks work when the `pytest` executable is not on `PATH`.

## Not the same as `tests/test_cases/`

The [`tests/test_cases/`](../../tests/test_cases/) package defines **`TestCase`** objects for **interactive / live-API** runners ([`tests/helpers/interactive_runner.py`](../../tests/helpers/interactive_runner.py), [`tests/helpers/parallel_runner.py`](../../tests/helpers/parallel_runner.py)). Those are **not** pytest modules. This hook layer only drives **pytest**. Edits under `tests/test_cases/` are mapped to `tests/test_scenarios_offline.py` as a lightweight offline regression signal.

## Changing the map

When you add a new top-level area under `src/cinemind/`, add a row to `entries` in `path_map.json` (mirror `tests/unit/<area>/` when that is the convention). For broader documentation on where tests live, see [TESTING_PRACTICES](../practices/TESTING_PRACTICES.md).

## See also

- [README.md](README.md) — AIbuilding index (mechanisms vs docs history)
- [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) — rules, skills, hooks diagrams
- [QUERYING.md](QUERYING.md) — manifests and `rg` for planning archive + session logs
