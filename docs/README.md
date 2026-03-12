# CineMind Documentation

## Documentation Structure

```
docs/
├── README.md                   ← You are here
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
└── AI_CONTEXT.md               ← Start here when using AI assistance
```

## Quick Navigation

| I want to... | Go to |
|-------------|-------|
| Set up the project | [Getting Started](getting-started/QUICKSTART.md) |
| Understand the system | [Feature Docs Index](features/README.md) |
| Use AI to make changes | [AI Context Guide](AI_CONTEXT.md) |
| Follow coding standards | [Best Practices](practices/README.md) |
| Understand a specific feature | [Feature Docs](features/README.md#documentation-index) |
| Add a new module | [Directory Structure Guide](practices/DIRECTORY_STRUCTURE.md) |
