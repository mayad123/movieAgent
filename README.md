# CineMind - Movie Analysis Agent

Real-time movie analysis and discovery agent powered by OpenAI and Tavily.

## Project Structure

```
Movie Agent/
├── src/                    # Source code
│   ├── cinemind/          # Core agent package
│   │   ├── agent.py       # Main CineMind agent
│   │   ├── config.py      # Configuration
│   │   ├── database.py    # Database models
│   │   ├── observability.py # Monitoring
│   │   ├── search_engine.py # Search functionality
│   │   ├── tagging.py     # Request classification
│   │   └── prompts/       # Prompt versions
│   │       └── versions.py
│   └── api/               # API server
│       └── main.py
├── tests/                  # Test suite
│   ├── test_cases.py
│   ├── evaluator.py
│   ├── test_runner.py
│   └── ...
├── scripts/                # Utility scripts
│   ├── view_observability.py
│   └── migrate_tags.py
├── docs/                   # Documentation
│   ├── README.md
│   ├── QUICKSTART.md
│   └── ...
├── data/                   # Data files
│   ├── test_results/
│   └── prompt_comparison/
├── docker/                 # Docker files
│   ├── Dockerfile
│   └── docker-compose.yml
└── requirements.txt
```

## Quick Start

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed setup instructions.

## Installation

Use a virtual environment (recommended):

```bash
# Create and activate (macOS/Linux)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

On Windows: `.venv\Scripts\activate` then `pip install -r requirements.txt`.

## Usage

### Run the Agent

```bash
python -m src.cinemind.agent
```

### Run the API Server

```bash
python -m uvicorn src.api.main:app --reload
```

### Run Tests

```bash
python tests/test_runner.py
```

## Documentation

- [Quick Start Guide](docs/QUICKSTART.md)
- [Testing Guide](docs/TESTING_GUIDE.md)
- [Observability Guide](docs/OBSERVABILITY.md)
- [Operationalization Guide](docs/OPERATIONALIZATION.md)

## License

MIT

