# CineMind Documentation

> Navigation index for all project documentation.

---

## Getting Started

| Document | Description |
|----------|-------------|
| [Quickstart](getting-started/QUICKSTART.md) | 5-minute setup: install, configure API keys, run |
| [Environment & Secrets](getting-started/ENV_AND_SECRETS.md) | All environment variables and where they're used |
| [Operationalization](getting-started/OPERATIONALIZATION.md) | Deployment (Docker, Cloud Run, AWS), health checks, scaling |

## Architecture

| Document | Description |
|----------|-------------|
| [Observability](architecture/OBSERVABILITY.md) | Request tracking, metrics, SQLite/Postgres storage, structured logging |
| [Observability Guide](architecture/VIEW_OBSERVABILITY_GUIDE.md) | How to use the `view_observability.py` CLI |
| [Source Policy](architecture/SOURCE_POLICY.md) | Tier-based source ranking (A/B/C), fact verification, auto-rejection |
| [Semantic Cache](architecture/SEMANTIC_CACHE.md) | Two-tier cache (exact hash + embedding), freshness gates, TTLs |
| [Attachment Pipeline](architecture/ATTACHMENT_PIPELINE_TRACE.md) | Call graph for how titles become media attachments |
| [Attachments Schema](architecture/ATTACHMENTS_SCHEMA.md) | `attachments.sections[]` contract: primary movie, lists, scenes |
| [Attachment Intent Classifier](architecture/ATTACHMENT_INTENT_CLASSIFIER.md) | Deterministic classifier: outputs intent + titles + rationale |
| [Batch Enrichment](architecture/BATCH_ENRICHMENT.md) | `enrich_batch()` API, throttling, graceful degradation |
| [Title Extraction Contract](architecture/TITLE_EXTRACTION_CONTRACT.md) | Deterministic title extraction patterns and intent gating |
| [Kaggle Integration](architecture/KAGGLE_INTEGRATION.md) | IMDB dataset search, correlation threshold, config |
| [Skip Tavily Logic](architecture/SKIP_TAVILY_LOGIC.md) | When and why Tavily search is skipped |
| [Wikipedia Cache](architecture/WIKIPEDIA_CACHE.md) | In-memory TTL cache for Wikipedia API |

## Testing

| Document | Description |
|----------|-------------|
| [Testing Guide](testing/TESTING_GUIDE.md) | **Start here** — running, writing, and analyzing tests |
| [Interactive Test Runner](testing/INTERACTIVE_TEST_RUNNER.md) | Interactive mode with test/version selection and parallel execution |
| [Scaling Testing](testing/SCALING_TESTING.md) | Strategies for large test suites, parallel execution, analysis tools |
| [Run Commands](testing/RUN_COMMANDS.md) | Exact pytest commands for every test category |
| [Run Commands (Scenarios)](testing/RUN_COMMANDS_SCENARIOS.md) | Gold vs explore scenario commands |
| [Scenarios](testing/SCENARIOS.md) | YAML scenario format and conventions |
| [Playground Server](testing/PLAYGROUND_SERVER.md) | Offline playground server for testing |
| [Tests README](testing/TESTS_README.md) | Legacy test suite overview |

## API Contracts

| Document | Description |
|----------|-------------|
| [UI Response Contract](api-contracts/UI_RESPONSE_CONTRACT.md) | API response shape: hero media, attachments, agent mode |
| [Data Contracts](api-contracts/DATA_CONTRACTS.md) | Message, media strip, and conversation data shapes |
| [Where to Watch Contract](api-contracts/WHERE_TO_WATCH_CONTRACT.md) | Where-to-Watch UX and backend event contract |

## Migration & Restructuring

| Document | Description |
|----------|-------------|
| [Restructure Plan](migration/RESTRUCTURE_PLAN.md) | Master plan: current state, target structure, 7 migration phases |
| [Dependency Registry](migration/DEPENDENCY_REGISTRY.md) | Every external package, env var, and internal import mapped per file |
| [Source Reality Map](migration/SRC_REALITY_MAP_AND_MIGRATION_PLAN.md) | Entrypoints, module dependency map, earlier migration notes |
| [Baseline Inventory](migration/BASELINE_INVENTORY_AND_PROTECTED_LIST.md) | Protected files/folders before restructuring |
| [Cleanup Deletion List](migration/SAFE_CLEANUP_PASS_DELETION_LIST.md) | Items removed and retained with justification |
| [Scripts Restructure](migration/SCRIPTS_RESTRUCTURE_DELIVERABLE.md) | Proposed `scripts/` layout and rationale |
