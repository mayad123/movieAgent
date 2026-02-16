# CineMind Offline Playground Server

A minimal local HTTP server that exposes the offline playground runner over HTTP for UI development.

## Features

- **Completely Offline**: No OpenAI, no Tavily, no internet access
- **Uses FakeLLM**: Deterministic responses for development
- **CORS Enabled**: Ready for local UI development
- **OpenAPI Docs**: Automatic API documentation at `/docs`

## Usage

### Starting the Server

```bash
python -m tests.playground_server
```

The server will start on `http://localhost:8000` by default.

### Endpoints

#### GET /health

Health check endpoint for sanity checks.

**Response:**
```json
{
  "status": "ok",
  "service": "cinemind-offline-playground"
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

#### POST /query

Execute a user query through the offline playground runner.

**Request Body:**
```json
{
  "user_query": "Who directed The Matrix?",
  "request_type": "info"  // Optional: "info", "recs", "comparison", "release-date"
}
```

**Response:**
Returns the full structured result from the CineMind agent, unchanged.

**Example:**
```bash
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"user_query": "Who directed The Matrix?", "request_type": "info"}'
```

**PowerShell Example:**
```powershell
$body = @{
    user_query = "Who directed The Matrix?"
    request_type = "info"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/query -Method POST -Body $body -ContentType "application/json"
```

### Interactive API Documentation

Once the server is running, visit `http://localhost:8000/docs` in your browser for interactive API documentation powered by Swagger UI.

## Behavior

This server:
- Mirrors offline test behavior exactly
- Uses `FakeLLMClient` (no OpenAI API calls)
- Always disables live data (no Tavily/external API calls)
- Returns the agent's result unchanged
- Does not modify CineMind internals

## Purpose

This server exists solely to support UI development. It allows frontend developers to:
- Test UI components against real agent responses
- Develop without external API dependencies
- Use deterministic responses for consistent testing
- Work completely offline

## Web UI

The canonical UI is in `web/` (index.html + css/app.css + js/app.js). The server serves it at the root.

**Usage:**
1. Start the server: `python -m tests.playground_server`
2. Open `http://localhost:8000/` in your browser
3. Enter queries in the composer and send messages

The UI provides:
- Chat interface with message history
- Media strip (poster images) when available
- "Did you mean…?" candidate strip for ambiguous queries
- Raw response toggle for debugging

## Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

