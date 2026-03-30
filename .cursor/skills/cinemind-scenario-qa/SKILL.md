---
name: cinemind-scenario-qa
description: >-
  Maintains online scenario quality for CineMind: curated prompts, acceptance criteria,
  and real-API evaluation via tests/test_cases and interactive or parallel runners. Use
  when editing tests/test_cases/, adding TestCase definitions, suites, or acceptance
  checks, or when running or debugging live stack scenario runs (not offline YAML pytest).
---

# CineMind scenario QA (online scenarios)

**Scope:** This skill treats **online** scenarios as authoritative: real model + provider stack, [`tests/test_cases/`](../../../tests/test_cases/) (`TestCase`, `TEST_SUITES`), and the helpers below. The **offline** YAML harness (`tests/fixtures/scenarios/`, `tests/test_scenarios_offline.py`) is for CI/determinism and is documented in [TEST_COVERAGE_MAP](../../../docs/practices/code-review/TEST_COVERAGE_MAP.md)—do not use it as the primary definition of “scenario QA” when following this skill.

## Canonical references

- **Acceptance patterns:** [`tests/test_cases/base.py`](../../../tests/test_cases/base.py) — `TestCase`, criteria helpers
- **Module index:** [`tests/test_cases/__init__.py`](../../../tests/test_cases/__init__.py) — `TEST_CASES`, `TEST_SUITES`
- **Test policy (offline vs live):** [`docs/practices/TESTING_PRACTICES.md`](../../../docs/practices/TESTING_PRACTICES.md)

## Online runners

- **Interactive selection / combos:** [`tests/helpers/interactive_runner.py`](../../../tests/helpers/interactive_runner.py) — execute with the same Python path and env as your normal agent runs (e.g. `CINEMIND_LLM_*` and related config); entrypoint is `__main__` in that file.
- **Batch / parallel:** [`tests/helpers/parallel_runner.py`](../../../tests/helpers/parallel_runner.py)
- **Eval helper:** `TestEvaluator` / real-API paths as wired from `interactive_runner` (imports `test_runner` / `CineMind` per that module).

## Workflow

1. **Define or adjust scenarios** — Add or edit `TestCase` entries in the category modules under `tests/test_cases/`; keep `name`, `prompt`, and `acceptance_criteria` explicit.
2. **Suite organization** — Update `TEST_SUITES` in `__init__.py` when grouping changes.
3. **Validate online** — Run the interactive or parallel runner against the suites you touched; confirm criteria pass on the live stack.
4. **Stay deterministic in code** — Unit and integration tests without network remain in `tests/unit/` / `tests/integration/` per project rules; they complement but do not replace online scenario passes for this skill.

## Out of scope for this skill

- Editing offline gold/explore YAML or `test_scenarios_offline.py` as the main task — use repo docs and CI; mention offline updates only when keeping parity after an online-proven behavior change.
