# How to Use view_observability.py

A guide to viewing and analyzing your CineMind observability data.

## Basic Usage

### 1. View Recent Requests (Default)

Shows the most recent 10 requests:

```bash
python view_observability.py
```

**Output shows:**
- Request ID (first 8 characters)
- Query text (truncated to 60 chars)
- Request type and outcome
- Status and response time

**Customize limit:**
```bash
python view_observability.py --limit 20
```

### 2. View Detailed Request Information

Get complete details for a specific request:

```bash
python view_observability.py --request-id <request-id>
```

**Example:**
```bash
python view_observability.py --request-id efd11844-483a-49c4-8568-8491a646452b
```

**Shows:**
- Full request metadata
- Complete response text
- All sources (URLs)
- Token usage breakdown
- Cost information
- All metrics (timings, etc.)
- Search operation details

### 3. View Statistics

Get aggregated statistics:

```bash
python view_observability.py --stats
```

**Shows:**
- Total requests
- Successful vs failed requests
- Average response time
- Total cost

**Filter by time period:**
```bash
python view_observability.py --stats --days 30
```

**Filter by request type:**
```bash
python view_observability.py --stats --type recs
```

**Filter by outcome:**
```bash
python view_observability.py --stats --outcome success
```

**Combine filters:**
```bash
python view_observability.py --stats --days 7 --type recs --outcome success
```

### 4. View Tag Distribution

See how requests are distributed by type and outcome:

```bash
python view_observability.py --tags
```

**Shows:**
- Count of each request type (info, recs, comparison, etc.)
- Count of each outcome (success, unclear, hallucination, etc.)

**For specific time period:**
```bash
python view_observability.py --tags --days 30
```

## Common Use Cases

### Find a Request ID

First, list recent requests:
```bash
python view_observability.py
```

Copy the request ID (first 8 chars) and use it:
```bash
python view_observability.py --request-id <full-id>
```

### Check Performance

View stats to see average response times and costs:
```bash
python view_observability.py --stats --days 7
```

### Analyze Request Types

See what types of requests are most common:
```bash
python view_observability.py --tags
```

### Find Failed Requests

Look for errors:
```bash
python view_observability.py --stats --outcome error
```

Or check recent requests for failed status:
```bash
python view_observability.py --limit 50
# Look for requests with status: error
```

### Calculate Costs

View total costs over time:
```bash
python view_observability.py --stats --days 30
```

View costs for specific request type:
```bash
python view_observability.py --stats --days 30 --type recs
```

## Advanced Usage

### Using Custom Database Location

If your database is in a different location:

```bash
python view_observability.py --db "C:/data/cinemind.db"
```

### Complete Request Trace

Get everything about a request:
```bash
python view_observability.py --request-id <id>
```

This shows:
- Request metadata (query, type, outcome, timestamps)
- Full response text
- All sources used
- Token usage (prompt, completion, total)
- API cost
- All metrics (response times, search times, etc.)
- Search operations (provider, results count, duration)

## Examples

### Example 1: Quick Overview
```bash
# See last 5 requests
python view_observability.py --limit 5

# Then get details on one
python view_observability.py --request-id <id-from-above>
```

### Example 2: Weekly Report
```bash
# Weekly statistics
python view_observability.py --stats --days 7

# Tag distribution
python view_observability.py --tags --days 7
```

### Example 3: Analyze Recommendations
```bash
# Stats for recommendation requests only
python view_observability.py --stats --type recs

# Tag distribution
python view_observability.py --tags
```

### Example 4: Debugging
```bash
# Find request ID from recent requests
python view_observability.py --limit 20

# Get full trace
python view_observability.py --request-id <id>
```

## Understanding the Output

### Request Details Include:

**Request Section:**
- `Request ID`: Unique identifier
- `Query`: What the user asked
- `Status`: success/error/pending
- `Type`: info/recs/comparison/spoiler/release-date/fact-check
- `Outcome`: success/unclear/hallucination/user-corrected
- `Model`: Which OpenAI model was used
- `Response Time`: Total time in milliseconds
- `Created`: Timestamp

**Response Section:**
- `Text`: Full response (first 200 chars shown)
- `Sources`: List of URLs used
- `Token Usage`: Prompt, completion, and total tokens
- `Cost`: Cost in USD

**Metrics Section:**
- `search_time_ms`: Time spent searching
- `openai_llm_time_ms`: Time for LLM response
- `prompt_tokens`: Tokens in the prompt
- `completion_tokens`: Tokens in the response
- `cost_usd`: API cost
- `total_response_time_ms`: End-to-end time

**Search Operations:**
- Provider (e.g., tavily)
- Results count
- Search duration

## Tips

1. **Start with recent requests**: Always start with `view_observability.py` to see what's there
2. **Use request IDs**: Copy the full request ID from recent requests to get details
3. **Filter wisely**: Use `--type` and `--outcome` to narrow down results
4. **Time periods**: Use `--days` to analyze different time ranges
5. **Combine flags**: Mix and match flags for powerful queries

