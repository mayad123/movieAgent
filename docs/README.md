# CineMind Documentation

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I want to... | Start with |
|-------------|-----------|
| Use AI to modify code | [AI_CONTEXT.md](AI_CONTEXT.md) |
| Add a new feature | [ADD_FEATURE_CONTEXT.md](ADD_FEATURE_CONTEXT.md) |
| Fix / change existing code | [CHANGE_FEATURE_CONTEXT.md](CHANGE_FEATURE_CONTEXT.md) |
| Understand a specific feature | [features/README.md](features/README.md) |
| Follow coding conventions | [practices/README.md](practices/README.md) |
| Set up the project | [getting-started/QUICKSTART.md](getting-started/QUICKSTART.md) |

</details>

## Documentation Structure

```
docs/
├── README.md                   ← You are here
├── AI_CONTEXT.md               ← Start here when using AI assistance
├── ADD_FEATURE_CONTEXT.md      ← AI context for adding new features
├── CHANGE_FEATURE_CONTEXT.md   ← AI context for modifying existing code
├── getting-started/            ← Setup & deployment
│   ├── QUICKSTART.md
│   ├── ENV_AND_SECRETS.md
│   └── OPERATIONALIZATION.md
├── features/                   ← Feature documentation (by domain)
│   ├── README.md               ← Index + system architecture diagram
│   ├── agent/                  ← Agent core, modes, pipeline
│   ├── api/                    ← REST API endpoints
│   ├── config/                 ← Configuration, schemas, env vars
│   ├── extraction/             ← NLP extraction pipeline
│   ├── infrastructure/         ← Cache, DB, observability, tagging
│   ├── integrations/           ← TMDB, Watchmode
│   ├── llm/                    ← LLM client abstraction
│   ├── media/                  ← Media enrichment & attachments
│   ├── planning/               ← Request planning & routing
│   ├── prompting/              ← Prompt building & validation
│   ├── search/                 ← Search engine & data retrieval
│   ├── verification/           ← Fact verification
│   ├── web/                    ← Frontend architecture
│   └── workflows/              ← Orchestration layer
├── practices/                  ← Engineering best practices
│   ├── README.md               ← Index
│   ├── BACKEND_PATTERNS.md     ← Python/backend conventions
│   ├── FRONTEND_PATTERNS.md    ← JS/CSS/HTML conventions
│   ├── CSS_STYLE_GUIDE.md      ← CSS architecture & naming
│   ├── DIRECTORY_STRUCTURE.md  ← How to add new modules
│   └── TESTING_PRACTICES.md    ← Testing conventions
```

## Quick Navigation

| I want to... | Go to |
|-------------|-------|
| Set up the project | [Getting Started](getting-started/QUICKSTART.md) |
| Understand the system | [Feature Docs Index](features/README.md) |
| Use AI to make changes | [AI Context Guide](AI_CONTEXT.md) |
| Use AI to **add** a feature | [AI_CONTEXT.md](AI_CONTEXT.md) + [ADD_FEATURE_CONTEXT.md](ADD_FEATURE_CONTEXT.md) |
| Use AI to **modify** existing code | [AI_CONTEXT.md](AI_CONTEXT.md) + [CHANGE_FEATURE_CONTEXT.md](CHANGE_FEATURE_CONTEXT.md) |
| Follow coding standards | [Best Practices](practices/README.md) |
| Understand a specific feature | [Feature Docs](features/README.md#documentation-index) |
| Add a new module | [Directory Structure Guide](practices/DIRECTORY_STRUCTURE.md) |
