# Test Coverage Map (UI / API / Agent Returns)

## Quick rules
- `tests/unit/` mirrors `src/cinemind/*` for fast, isolated contract checks.
- `tests/unit/integrations/` and `tests/smoke/` validate API wiring / request-response shapes.
- `tests/integration/` and `tests/test_scenarios_offline.py` validate "agent returns" behavior (prompting, evidence formatting, validator repair expectations, and response constraints) using offline fakes and YAML/fixtures.

## UI (web/)
**What we test automatically**
- `tests/smoke/test_playground_smoke.py` checks the offline FastAPI playground server boots and that core UI-facing endpoints (`/health`, `/query`) return the expected JSON shape.

**What we do manually**
- Since the frontend is vanilla JS (no bundler/test runner here), UI behavior is validated by running the playground server and checking the UI in a browser.

## API (src/api/main.py + related schemas)

**What we test automatically**
- `tests/unit/integrations/` covers FastAPI endpoints and error cases.
  - Example: `tests/unit/integrations/test_where_to_watch_api.py` validates `GET /api/watch/where-to-watch` happy path, not-found, rate limit, and missing key behavior.
- Some API contracts are validated indirectly via unit tests that exercise the API entrypoints with `fastapi.testclient.TestClient`.
  - Example: `tests/unit/media/test_media_alignment.py` calls the "similar movies" endpoint contract.

**Note**
- There is currently no full end-to-end API test suite that runs against the real external services. Instead, API + agent behavior is validated offline with fakes and scenario fixtures.

## Agent returns (offline, response-quality oriented)

### Offline end-to-end (FakeLLM)
- `tests/integration/test_agent_offline_e2e.py` runs the full agent path with `FakeLLMClient` and checks response structure and repair behavior.
  - Examples of what is asserted today: response text presence, forbidden-term repair, verbosity repair, freshness timestamp inclusion.

### Scenario matrix harness (YAML/JSON fixtures)
- `tests/test_scenarios_offline.py` is the main "agent returns" regression harness.
- Scenario inputs come from:
  - `tests/fixtures/scenarios/gold/` (must pass; regression)
  - `tests/fixtures/scenarios/explore/` (may fail; informational for new features)
- Scenario expected behavior is evaluated in a consistent order:
  1. prompt construction checks (`prompt_checks`)
  2. template selection checks (`expected.template_id` vs `get_template(...)`)
  3. evidence formatting checks (`evidence_checks`)
  4. output validation checks (`validator_checks`, including expected violation types)

## Unit module mapping (src -> tests)

This is the current (repo tree) mapping. Keep new unit tests under the corresponding `tests/unit/<feature>/` directory.

| src/cinemind area | tests/unit directory (if present) | Notes |
|---|---|---|
| `src/cinemind/extraction/` | `tests/unit/extraction/` | Extraction + intent/entity matching |
| `src/cinemind/media/` | `tests/unit/media/` | Enrichment, alignment, attachments, cache |
| `src/cinemind/planning/` | `tests/unit/planning/` | Routing and tool-plan logic |
| `src/cinemind/prompting/` | `tests/unit/prompting/` | Evidence formatting + output validator |
| `src/cinemind/search/` | `tests/unit/search/` | Retrieval adapter and search engine unit behavior |
| `src/cinemind/workflows/` | `tests/unit/workflows/` | Orchestration-level logic (unit-scoped) |
| `src/cinemind/infrastructure/` | (no `tests/unit/infrastructure/` directory yet) | Add if observability/cache/DB logic needs unit coverage |
| `src/cinemind/verification/` | (no `tests/unit/verification/` directory yet) | Add if fact verification logic gets refactored or expanded |

## How template / validator changes flow into tests
- If you change `cinemind/prompting/templates.py`, update:
  - unit tests under `tests/unit/prompting/` (where applicable)
  - scenario fixtures in `tests/fixtures/scenarios/*` (so expected `template_id` and constraints remain accurate)
- If you change `cinemind/prompting/output_validator.py`, update:
  - unit tests under `tests/unit/prompting/test_output_validator.py`
  - scenario fixtures by adjusting expected violation types / repair expectations

## How to change tests (agent-return scenarios)
Scenario behavior is driven by YAML fixtures in `tests/fixtures/scenarios/`.

### Add/modify a scenario
1. Create or edit a YAML file under `tests/fixtures/scenarios/gold/` (regression) or `tests/fixtures/scenarios/explore/` (informational).
2. Update these keys as needed:
   - `expected.template_id` (must match the template chosen by `get_template(request_plan.request_type, request_plan.intent)`)
   - `expected.prompt_checks` (required sections, must contain / must not contain)
   - `expected.evidence_checks` (dedupe counts, snippet limits, forbidden evidence terms)
   - `expected.validator_checks` (expected valid vs invalid, expected violation types)
   - `sample_model_output` if you need to validate a specific response text path
3. Re-run:
   - `python -m pytest tests/test_scenarios_offline.py -v`

### Run only part of the matrix
- `gold` scenarios:
  - `CINEMIND_SCENARIO_SET=gold python -m pytest tests/test_scenarios_offline.py -v`
  - or `python -m pytest tests/test_scenarios_offline.py -m gold -v`
- `explore` scenarios:
  - `CINEMIND_SCENARIO_SET=explore python -m pytest tests/test_scenarios_offline.py -v`

