---
name: cinemind-prompt-engineer
description: >-
  Maintains CineMind prompt construction, response templates, evidence formatting,
  and output validation. Use when changing system or user prompts, template registry,
  forbidden terms, verbosity or freshness rules, EvidenceFormatter, PromptBuilder, or
  OutputValidator behavior. Treat online scenario runs as the authoritative check for
  end-to-end prompt quality; offline pytest supports CI only.
---

# CineMind prompt engineer

## Scope

- **Authoritative for behavior:** **Online** runs using [`tests/test_cases/`](../../../tests/test_cases/) and [`tests/helpers/interactive_runner.py`](../../../tests/helpers/interactive_runner.py) / [`parallel_runner.py`](../../../tests/helpers/parallel_runner.py) with real credentials—prove templates and validator behavior the way users hit the stack.
- **Supporting:** `tests/unit/prompting/` for fast, deterministic contracts; offline YAML in `tests/fixtures/scenarios/` + `tests/test_scenarios_offline.py` for regression automation (update when CI expectations must track a change already validated online).

## Canonical references

- **Pipeline map and change impact:** [`docs/features/prompting/PROMPT_PIPELINE.md`](../../../docs/features/prompting/PROMPT_PIPELINE.md)
- **Coverage map (incl. offline harness):** [`docs/practices/code-review/TEST_COVERAGE_MAP.md`](../../../docs/practices/code-review/TEST_COVERAGE_MAP.md)
- **Online scenario definitions:** [`tests/test_cases/`](../../../tests/test_cases/)

## Code touchpoints (`src/cinemind/prompting/`)

| Area | Modules |
|------|---------|
| Message assembly | `prompt_builder.py`, `versions.py` (`PROMPT_VERSIONS`) |
| Evidence text | `evidence_formatter.py` (`EvidenceFormatResult` contract) |
| Per-intent output | `templates.py` (`get_template`, `ResponseTemplate`) |
| Post-generation checks | `output_validator.py` |

## Workflow

1. **Classify the change** — System prompt vs user prompt vs evidence block vs template vs validator; use PROMPT_PIPELINE “Example changes and where to look”.
2. **Keep contracts coherent** — Template changes must stay consistent with validator assumptions (length, required sections, markdown).
3. **Unit tests** — Adjust `tests/unit/prompting/` for formatter/validator edge cases.
4. **Validate online** — Run relevant `TEST_SUITES` / cases via the interactive or parallel runner; extend or tighten `acceptance_criteria` on `TestCase` objects when behavior shifts.
5. **CI parity (optional follow-up)** — If the repo’s offline scenario matrix encodes the same expectations, update YAML + run `tests/test_scenarios_offline.py` so CI stays green (see TEST_COVERAGE_MAP).
6. **Docs** — Sync `PROMPT_PIPELINE.md` or linked feature docs when behavior is non-trivial.

## Coordination

Intent or routing changes may need extraction/planning tests; online scenarios should still reflect user-visible outcomes first.
