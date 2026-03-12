# CineMind Observability Guide

CineMind includes comprehensive observability features for production monitoring, debugging, and analytics.

## Features

### 1. Request Tracking
- Every request gets a unique `request_id` for end-to-end tracing
- Request lifecycle tracking (pending → success/error)
- Timestamp tracking
- **Request Type Tagging**: Auto-classification of request types
- **Outcome Tagging**: Track response quality and user feedback

### 2. Metrics Collection
- **Response Times**: Total response time, search time, LLM time
- **Token Usage**: Prompt tokens, completion tokens, total tokens
- **Cost Tracking**: Calculated API costs per request
- **Search Metrics**: Search provider, results count, search duration
- **Error Tracking**: Error types and messages

### 3. Data Storage
- **SQLite** (default): Local development and testing
- **PostgreSQL** (production): For production deployments
- Automatic table creation and migrations

### 4. Structured Logging
- Request-scoped logging with request IDs
- Log file: `cinemind.log`
- Structured JSON-compatible format

## Database Schema

### Requests Table
Stores request metadata:
- `request_id` (unique identifier)
- `user_query`
- `timestamp`
- `use_live_data`
- `model`
- `status` (pending/success/error)
- `response_time_ms`
- `error_message`
- `request_type` (info/recs/comparison/spoiler/release-date/fact-check)
- `outcome` (success/unclear/hallucination/user-corrected)

### Responses Table
Stores response data:
- `request_id` (foreign key)
- `response_text`
- `sources` (JSON)
- `token_usage` (JSON)
- `cost_usd`

### Metrics Table
Stores metrics:
- `request_id` (foreign key)
- `metric_type` (gauge/counter/error)
- `metric_name`
- `metric_value`
- `metric_data` (JSON)

### Search Operations Table
Stores search operation details:
- `request_id` (foreign key)
- `search_query`
- `search_provider`
- `results_count`
- `search_time_ms`

## Request Tagging

### Request Types

Requests are automatically classified into categories:

- **info**: General information request
- **recs**: Recommendation request
- **comparison**: Comparison between movies/directors/actors
- **spoiler**: Request asking for spoilers or plot details
- **release-date**: Release date or premiere inquiry
- **fact-check**: Fact verification request

### Outcomes

Track response quality:

- **success**: Request was successfully answered
- **unclear**: Response was unclear or ambiguous
- **hallucination**: Response contained hallucinations or incorrect information
- **user-corrected**: User provided corrections to the response

### Auto-Classification

Request types are automatically classified using:
1. **LLM-based classification** (more accurate, uses GPT)
2. **Pattern matching fallback** (faster, rule-based)

Outcomes can be:
- Auto-set to "success" on successful completion
- Manually set via API endpoint
- Updated by users/admin

## Usage

### Enable Observability

Observability is **enabled by default**. To disable:

```python
agent = CineMind(enable_observability=False)
```

### Manual Tagging

You can manually specify request type and outcome:

```python
result = await agent.search_and_analyze(
    "What's the best sci-fi movie?",
    request_type="recs",
    outcome="success"
)
```

### Update Outcome After Request

```bash
PUT /observability/requests/{request_id}/outcome?outcome=hallucination
```

### Access Request Data

#### Via API Endpoints

**Get request trace:**
```bash
GET /observability/requests/{request_id}
```

**Get recent requests:**
```bash
GET /observability/requests?limit=100
```

**Get statistics:**
```bash
GET /observability/stats?days=7
GET /observability/stats?days=7&request_type=recs
GET /observability/stats?days=7&outcome=hallucination
```

**Get tag distribution:**
```bash
GET /observability/tags?days=7
```

**Update outcome:**
```bash
PUT /observability/requests/{request_id}/outcome?outcome=hallucination
```

#### Via Python Code

```python
from database import Database
from observability import Observability

db = Database()
obs = Observability(db)

# Get request trace
trace = obs.get_request_trace("request-id-here")

# Get recent requests
requests = obs.db.get_recent_requests(limit=50)

# Get statistics
stats = obs.db.get_stats(days=7)
```

### Query Examples

**Get all successful requests:**
```python
cursor = db.conn.cursor()
cursor.execute("SELECT * FROM requests WHERE status = 'success'")
```

**Calculate total cost:**
```python
cursor.execute("SELECT SUM(cost_usd) FROM responses")
```

**Get average response time:**
```python
cursor.execute("SELECT AVG(response_time_ms) FROM requests WHERE status = 'success'")
```

**Get error rate:**
```python
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
    FROM requests
""")
```

## Migration

If you have an existing database, run the migration script:

```bash
python scripts/db/migrate_tags.py
```

This adds the `request_type` and `outcome` columns to existing databases.

## Configuration

### SQLite (Default)
```python
db = Database()  # Uses cinemind.db
```

### PostgreSQL
```python
db = Database(
    db_path="postgresql://user:pass@localhost/cinemind",
    use_postgres=True
)
```

Or via environment variable:
```bash
export DATABASE_URL="postgresql://user:pass@localhost/cinemind"
```

## API Response Format

When observability is enabled, responses include:

```json
{
    "agent": "CineMind",
    "version": "1.0.0",
    "request_id": "abc123...",
    "query": "user question",
    "response": "agent response",
    "sources": [...],
    "timestamp": "2024-12-07T20:00:00",
    "live_data_used": true,
    "token_usage": {
        "prompt_tokens": 150,
        "completion_tokens": 300,
        "total_tokens": 450
    },
    "cost_usd": 0.0015,
    "request_type": "recs",
    "outcome": "success"
}
```

## Monitoring & Analytics

### Key Metrics to Monitor

1. **Request Volume**: Total requests per day/hour
2. **Success Rate**: Percentage of successful requests
3. **Response Times**: P50, P95, P99 response times
4. **Cost**: Daily/weekly/monthly API costs
5. **Error Rate**: Error frequency and types
6. **Token Usage**: Average tokens per request
7. **Search Performance**: Search latency and success rate

### Example Queries

**Daily statistics:**
```sql
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_requests,
    AVG(response_time_ms) as avg_response_time,
    SUM(cost_usd) as total_cost
FROM requests r
LEFT JOIN responses res ON r.request_id = res.request_id
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

**Error analysis:**
```sql
SELECT 
    error_message,
    COUNT(*) as count
FROM requests
WHERE status = 'error'
GROUP BY error_message
ORDER BY count DESC;
```

**Cost breakdown by model:**
```sql
SELECT 
    model,
    COUNT(*) as requests,
    SUM(cost_usd) as total_cost,
    AVG(cost_usd) as avg_cost
FROM requests r
LEFT JOIN responses res ON r.request_id = res.request_id
GROUP BY model;
```

**Request type distribution:**
```sql
SELECT 
    request_type,
    COUNT(*) as count,
    AVG(response_time_ms) as avg_response_time
FROM requests
WHERE request_type IS NOT NULL
GROUP BY request_type
ORDER BY count DESC;
```

**Outcome analysis:**
```sql
SELECT 
    outcome,
    COUNT(*) as count,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM requests WHERE outcome IS NOT NULL) as percentage
FROM requests
WHERE outcome IS NOT NULL
GROUP BY outcome;
```

**Hallucination tracking:**
```sql
SELECT 
    user_query,
    response_text,
    created_at
FROM requests r
JOIN responses res ON r.request_id = res.request_id
WHERE r.outcome = 'hallucination'
ORDER BY r.created_at DESC;
```

## Production Considerations

### Database Maintenance

- **Backup**: Regularly backup your database
- **Cleanup**: Consider archiving old requests (>90 days)
- **Indexing**: Add indexes on frequently queried columns

### Performance

- **Connection Pooling**: Use connection pooling for PostgreSQL
- **Read Replicas**: Use read replicas for analytics queries
- **Caching**: Cache statistics queries

### Security

- **Access Control**: Restrict database access
- **Encryption**: Encrypt sensitive data (API keys in error messages)
- **Audit Logs**: Enable database audit logging

## Log Files

Logs are written to `cinemind.log` with format:
```
2024-12-07 20:00:00 - cinemind - INFO - [request-id] - Message
```

Logs include:
- Request IDs for correlation
- Timestamps
- Log levels (INFO, WARNING, ERROR)
- Structured metadata

## Cost Calculation

Cost calculation uses current OpenAI pricing:
- `gpt-3.5-turbo`: $0.0015/$0.002 per 1K tokens (input/output)
- `gpt-4`: $0.03/$0.06 per 1K tokens
- `gpt-4-turbo`: $0.01/$0.03 per 1K tokens
- `gpt-4o`: $0.005/$0.015 per 1K tokens

Prices are updated in `observability.py` - adjust as needed.

## Troubleshooting

**Database connection errors:**
- Check database URL/credentials
- Ensure database exists
- Check network connectivity

**Missing metrics:**
- Verify observability is enabled
- Check database permissions
- Review logs for errors

**Performance issues:**
- Add database indexes
- Use connection pooling
- Archive old data

