# Smoke Tests and Run Commands (Pre-Refactor Guardrails)

Minimal smoke checks to run **before** any src/ refactor. No file moves; no behavior changes.

---

## 1. Exact Commands

Run from **repository root**.

### 1.1 Playground smoke (server boot + one basic request)

Single command (no env required):

```bash
PYTHONPATH=src pytest tests/smoke/test_playground_smoke.py -v
```

- Uses FastAPI `TestClient`; no real server process.
- Asserts: app imports, GET /health returns 200 and `status == "ok"`, POST /query with one minimal body returns 200 and response shape (`response`, `agent_mode`).

### 1.2 Real LLM workflow smoke (minimal input)

Single command (**requires** `OPENAI_API_KEY`; skips if unset):

```bash
OPENAI_API_KEY=sk-your-key PYTHONPATH=src pytest tests/smoke/test_real_workflow_smoke.py -v
```

- Runs `CineMind.search_and_analyze("What year was The Matrix released?")` with real OpenAI (timeout 90s).
- Asserts: dict result with non-empty `response`. Skips if `OPENAI_API_KEY` is not set.

### 1.3 Full test suite (ensure tests currently pass)

```bash
PYTHONPATH=src pytest tests/ --ignore=tests/test_runner_interactive.py -q
```

- Excludes `test_runner_interactive.py` (broken imports: missing `evaluator`, `test_runner`).
- Use `-q` for quiet; drop it for more output.
- **Current baseline:** hundreds of tests pass; some existing failures/errors (e.g. evidence formatter, contract, smoke fixtures) are pre-existing. Use the same command before and after refactor; the **smoke tests** (playground + optional real) are the guardrails for refactor.

### 1.4 Run both smokes in one go

```bash
PYTHONPATH=src pytest tests/smoke/ -v
```

- Playground smoke always runs; real workflow smoke runs only if `OPENAI_API_KEY` is set.

---

## 2. What Was Added (Tiny Additions)

| Item | Purpose |
|------|--------|
| **tests/smoke/__init__.py** | Marks `smoke` as a package. |
| **tests/smoke/test_playground_smoke.py** | Three tests: app import, GET /health, POST /query with one minimal body. Uses `TestClient`; no real server. |
| **tests/smoke/test_real_workflow_smoke.py** | One test: real agent minimal query; `@pytest.mark.skipif(not OPENAI_API_KEY)`. |
| **docs/SMOKE_TESTS_AND_RUN_COMMANDS.md** | This file: exact commands and usage. |

No changes to application code, routes, or behavior. Only new tests and this doc.

---

## 3. Before Any Refactor

1. Run playground smoke:  
   `PYTHONPATH=src pytest tests/smoke/test_playground_smoke.py -v`
2. (Optional) Run real workflow smoke if you have a key:  
   `OPENAI_API_KEY=... PYTHONPATH=src pytest tests/smoke/test_real_workflow_smoke.py -v`
3. Run full suite:  
   `PYTHONPATH=src pytest tests/ --ignore=tests/test_runner_interactive.py -q`
4. After refactor, run 1–3 again; fix any regressions before proceeding.
