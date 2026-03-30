# CineMind Quick Start Guide

Get up and running with CineMind in 5 minutes!

## Step 1: Install Dependencies

Use a local virtualenv at **`.venv`** (already gitignored):

```bash
make venv
```

That creates `.venv`, upgrades pip, and runs `pip install -r requirements.txt`. The project **Makefile** uses `.venv/bin/python` automatically when `.venv` exists (`make demo`, `make test`, etc.).

Activate when running commands outside Make:

```bash
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows cmd/PowerShell
```

Optional editable install: `make install` or `make dev` (dev extras).

## Step 2: Set Up API Keys

1. Copy the example environment file:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` and add your LLM server + optional search keys:
   ```
   CINEMIND_LLM_BASE_URL=http://127.0.0.1:8000
   CINEMIND_LLM_MODEL=meta-llama/Llama-3.3-8B-Instruct
   CINEMIND_LLM_API_KEY=   # if your inference server requires a bearer token
   TAVILY_API_KEY=tvly-your-key-here  # Optional but recommended
   ```

   **LLM:** Run an OpenAI-compatible inference server (vLLM, llama.cpp, LM Studio, etc.) and point `CINEMIND_LLM_BASE_URL` at its `/v1` root.
   **Tavily:** https://tavily.com (free tier available)

## Step 3: Try It Out

### Option A: Command Line

```bash
python cinemind.py "What movies are coming out in 2025?"
```

### Option B: Interactive Mode

```bash
python cinemind.py
```

Then type your questions:
```
🎬 You: Tell me about the latest Christopher Nolan film
🎬 You: What's the best sci-fi movie from 2024?
🎬 You: exit
```

### Option C: REST API

1. Start the server:
   ```bash
   python api.py
   ```

2. In another terminal, test it:
   ```bash
   curl "http://localhost:8000/search?query=Tell me about Dune Part 2"
   ```

3. Visit API docs:
   - http://localhost:8000/docs (Swagger UI)
   - http://localhost:8000/redoc (ReDoc)

### Option D: Docker

```bash
docker-compose up -d
```

Then access the API at http://localhost:8000

## Example Queries

- "What's the latest news about Avatar 3?"
- "Recommend a good action movie from 2024"
- "Tell me about Denis Villeneuve's filmography"
- "What movies won Oscars in 2024?"
- "Compare Dune Part 1 and Part 2"

## Next Steps

- See [README.md](README.md) for full documentation
- See [OPERATIONALIZATION.md](OPERATIONALIZATION.md) for production deployment
- Check out `api.py` for API integration examples

## Troubleshooting

**"LLM not configured"**
- Set `CINEMIND_LLM_BASE_URL` and `CINEMIND_LLM_MODEL` in `.env` (see `.env.example`)
- Ensure the inference server is reachable from the API process

**"Tavily search failed"**
- Tavily is optional but recommended for better search
- The agent will work without it, using fallback search

**Import errors**
- Make sure all dependencies are installed: `pip install -r requirements.txt`

**Port already in use**
- Change the port in `api.py` or set `PORT` environment variable

