# When to Run Which Tests

Use this page during PR review to pick the minimum useful test set based on what you changed.

## Common commands
All commands assume you run from the repo root.

```bash
# Unit tests (fast, isolated)
python -m pytest tests/unit/ -v

# Scenario regression harness (offline, YAML fixtures)
python -m pytest tests/test_scenarios_offline.py -v

# Smoke tests (playground server boot + core endpoints)
python -m pytest tests/smoke/test_playground_smoke.py -v

# Offline integration checks (agent end-to-end with FakeLLM)
python -m pytest tests/integration/test_agent_offline_e2e.py -v
```

## Change-based guidance (recommended sets)

### UI / frontend-only changes (`web/*`)
- Run: `python -m pytest tests/smoke/test_playground_smoke.py -v`
- Also run the offline playground server manually and load the UI in a browser.
  - `tests/playground/server.py` is the host that mounts `web/`.

### API wiring + response shape changes (`src/api/main.py`, `src/schemas/api.py`)
- Run: unit integration tests if they exist for that endpoint (under `tests/unit/integrations/`)
- Run: `python -m pytest tests/smoke/test_playground_smoke.py -v`

### Agent return / response-quality changes
(prompt templates, prompt builder/evidence formatting, output validator rules, repair behavior, media enrichment attached into responses)
- Run: `python -m pytest tests/integration/test_agent_offline_e2e.py -v`
- Run: `python -m pytest tests/test_scenarios_offline.py -v`

### Prompting-only changes (`src/cinemind/prompting/*`)
- Run: `python -m pytest tests/unit/prompting/ -v`
- Run: `python -m pytest tests/test_scenarios_offline.py -v` (because scenarios assert `template_id`, required sections, validator expectations)

### Media-only changes (`src/cinemind/media/*`)
- Run: `python -m pytest tests/unit/media/ -v`
- If “similar/attachments” impact response structure, also run: `python -m pytest tests/test_scenarios_offline.py -v`

### Planning / routing changes (`src/cinemind/planning/*`)
- Run: `python -m pytest tests/unit/planning/ -v`
- Run: `python -m pytest tests/test_scenarios_offline.py -v` (scenario expected template selection is sensitive to routing)

## Review phases (pragmatic checkpoints)
1. **Before merge (minimum bar):** run the unit tests for the touched module(s) + the smoke test if any API/UI contract could change.
2. **Before merging prompt/validator/template work:** run the scenario harness (`tests/test_scenarios_offline.py`).
3. **Before a release / major refactor:** run scenario harness + offline end-to-end integration tests together.

## How to pick "minimum useful"
- If the change affects the agent response structure, required sections, or validator rules: you need scenarios.
- If the change only affects deterministic internal helpers with unit coverage: unit tests may be sufficient.

