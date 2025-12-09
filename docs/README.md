# CineMind - Real-time Movie Analysis Agent 🎬

CineMind is an expert movie analysis and discovery agent that provides real-time, up-to-date information about films, directors, actors, and everything related to cinema.

## Features

- 🎥 **Real-time Movie Data**: Uses live web searches to get the latest information
- 🔍 **Multiple Sources**: Aggregates data from IMDb, Rotten Tomatoes, Wikipedia, Variety, Deadline, and more
- 🧠 **AI-Powered Analysis**: Leverages GPT-4 for intelligent movie analysis and recommendations
- 📊 **Current Information**: Prioritizes recent updates (cast confirmations, release schedules, awards)
- 🎯 **Movie-Only Domain**: Focused exclusively on cinema-related topics

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add:
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `TAVILY_API_KEY`: Your Tavily API key (optional, for enhanced search)

Get your Tavily API key at [https://tavily.com](https://tavily.com)

### 3. Run CineMind

**Interactive Mode:**
```bash
python cinemind.py
```

**Single Query Mode:**
```bash
python cinemind.py "What's the latest news about Dune Part 2?"
```

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp env.example .env
   # Edit .env and add your API keys
   ```

3. **Run the CLI:**
   ```bash
   python cinemind.py
   ```

4. **Or start the API server:**
   ```bash
   python api.py
   ```

## Usage

### Command Line Interface

**Interactive mode:**
```bash
python cinemind.py
```

**Single query:**
```bash
python cinemind.py "What's the latest Christopher Nolan movie?"
```

### REST API

Start the API server:
```bash
python api.py
# Server runs on http://localhost:8000
```

**Search movies:**
```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "Tell me about Dune Part 2", "use_live_data": true}'
```

**Health check:**
```bash
curl http://localhost:8000/health
```

**API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### As a Python Module

```python
import asyncio
from cinemind import CineMind

async def main():
    agent = CineMind()
    
    # Get movie analysis with real-time data
    result = await agent.search_and_analyze(
        "Tell me about the latest Christopher Nolan film",
        use_live_data=True
    )
    
    print(result["response"])
    print("\nSources:")
    for source in result["sources"]:
        print(f"- {source['title']}: {source['url']}")
    
    # Stream response
    async for token in agent.stream_response("Recommend a good sci-fi movie from 2024"):
        print(token, end="", flush=True)
    
    await agent.close()

asyncio.run(main())
```

### Docker Deployment

**Build and run:**
```bash
docker build -t cinemind .
docker run -p 8000:8000 --env-file .env cinemind
```

**Using Docker Compose:**
```bash
docker-compose up -d
```

See [OPERATIONALIZATION.md](OPERATIONALIZATION.md) for detailed deployment guides.

## Architecture

```
cinemind.py          # Main agent with OpenAI integration
search_engine.py     # Real-time web search functionality
config.py            # Configuration and system prompts
requirements.txt     # Python dependencies
```

## Real-time Data Sources

CineMind searches across:
- **IMDb** - Cast, crew, ratings, trivia
- **Rotten Tomatoes** - Reviews and scores
- **Wikipedia** - General film information
- **Variety** - Industry news and updates
- **Deadline** - Production and release news
- **Metacritic** - Critical reception
- **YouTube** - Interviews and behind-the-scenes

## Operationalization Roadmap

For production deployment:

1. **API Layer**: Add FastAPI/Flask REST API
2. **Caching**: Implement Redis for search result caching
3. **Rate Limiting**: Add request throttling
4. **Monitoring**: Integrate logging and metrics (Prometheus, Grafana)
5. **Containerization**: Dockerize for easy deployment
6. **Database**: Optional storage for search history and user preferences
7. **Authentication**: Add API key management for multi-user access

## Requirements

- Python 3.8+
- OpenAI API key (required)
- Tavily API key (optional but recommended for better search)

## Operationalization

CineMind is production-ready and can be:

1. ✅ **Deployed via Docker** (Dockerfile included)
2. ✅ **Exposed as REST API** (FastAPI with auto-docs)
3. **Deployed to cloud** (AWS, GCP, Azure - see OPERATIONALIZATION.md)
4. **Integrated into applications** (Python SDK, REST API)
5. **Extended with features** (authentication, caching, rate limiting)

For production deployment guidance, see [OPERATIONALIZATION.md](OPERATIONALIZATION.md).

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or pull request.

