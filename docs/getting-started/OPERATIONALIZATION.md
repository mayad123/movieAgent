# CineMind Operationalization Guide

This document outlines how to deploy and operate CineMind in production.

## Deployment Options

### 1. Docker Deployment

**Build and run:**
```bash
docker build -t cinemind .
docker run -p 8000:8000 --env-file .env cinemind
```

**Using Docker Compose:**
```bash
docker-compose up -d
```

### 2. Cloud Deployment

#### AWS (EC2/ECS/Lambda)
- **EC2**: Deploy Docker container on EC2 instance
- **ECS**: Use Fargate for serverless container deployment
- **Lambda**: For serverless API (requires adaptation)

#### Google Cloud (Cloud Run)
```bash
gcloud run deploy cinemind \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=$OPENAI_API_KEY,TAVILY_API_KEY=$TAVILY_API_KEY
```

#### Azure (Container Instances)
```bash
az container create \
  --resource-group myResourceGroup \
  --name cinemind \
  --image cinemind:latest \
  --environment-variables OPENAI_API_KEY=$OPENAI_API_KEY TAVILY_API_KEY=$TAVILY_API_KEY
```

### 3. API Endpoints

Once deployed, the API is available at:

- **Health Check**: `GET /health`
- **Search (POST)**: `POST /search` with JSON body
- **Search (GET)**: `GET /search?query=movie+title`
- **Stream**: `POST /search/stream` for streaming responses

### 4. Production Considerations

#### Environment Variables
- Set `OPENAI_API_KEY` (required)
- Set `TAVILY_API_KEY` (recommended)
- Set `PORT` if different from 8000

#### Security
- Add API authentication (API keys, JWT tokens)
- Use HTTPS/TLS
- Configure CORS properly (update `api.py`)
- Rate limiting (add middleware)
- Input validation and sanitization

#### Monitoring
- Add logging aggregation (ELK, CloudWatch, Datadog)
- Set up health checks
- Monitor API response times
- Track API usage and costs

#### Caching
- Implement Redis for search result caching
- Cache frequent queries
- Set appropriate TTLs based on data freshness needs

#### Scaling
- Use load balancer (nginx, ALB, Cloud Load Balancing)
- Horizontal scaling with multiple instances
- Consider async task queues for heavy operations

### 5. Recommended Additions

#### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/search")
@limiter.limit("10/minute")
async def search_movies(...):
    ...
```

#### Authentication
```python
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

@app.post("/search")
async def search_movies(
    api_key: str = Security(api_key_header),
    ...
):
    # Validate API key
    ...
```

#### Caching with Redis
```python
import redis
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(ttl=3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator
```

### 6. Monitoring & Logging

#### Structured Logging
```python
import structlog

logger = structlog.get_logger()

logger.info("movie_search", query=query, results_count=len(results))
```

#### Metrics
- Request count
- Response time (p50, p95, p99)
- Error rate
- Search success rate
- API costs tracking

### 7. Cost Management

- Monitor OpenAI API usage
- Implement query caching to reduce API calls
- Set usage limits per user/API key
- Use cheaper models for simple queries when appropriate

### 8. Testing

Create test suite:
```bash
pytest tests/
```

Test endpoints, error handling, and search functionality.

