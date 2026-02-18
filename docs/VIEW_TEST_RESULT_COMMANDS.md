# Commands to View Test Results from Database

## Quick Reference

### View the Multi-Hop Test Result (from our test run)

```bash
python scripts/observability/view_observability.py --request-id 0abf162b-5e24-43a4-93a8-aabc224a8e98
```

## Finding Request IDs

### 1. View Recent Requests

To see the most recent requests and find a request ID:

```bash
python scripts/observability/view_observability.py
```

Or with a custom limit:

```bash
python scripts/observability/view_observability.py --limit 20
```

**Output shows:**
- Request ID (first 8 characters)
- Query text (truncated)
- Request type and outcome
- Status and response time

### 2. View Specific Request Details

Once you have a request ID, view full details:

```bash
python scripts/observability/view_observability.py --request-id <request-id>
```

**Shows:**
- Full request metadata (query, type, status, model, response time)
- **Classification Metadata** (NEW!):
  - Predicted Type
  - Rule Hit (which rule matched)
  - LLM Used (whether LLM classification was used)
  - Confidence score
  - Entities extracted
  - Need Freshness flag
- Response text
- Sources (URLs)
- Token usage breakdown
- Cost information
- All metrics (timings, etc.)
- Search operation details

## Example: Viewing the Multi-Hop Test

```bash
# View the specific test result
python scripts/observability/view_observability.py --request-id 0abf162b-5e24-43a4-93a8-aabc224a8e98
```

**Expected Output:**
- Request information (query, type, status, model, response time)
- **Classification Metadata** showing:
  - Predicted Type: release-date (incorrect - should be info)
  - Rule Hit: rule:\b(is.*out|was.*released|relea
  - LLM Used: False
  - Confidence: 0.85
- Metrics (search time, LLM time, tokens, cost)
- Search operations

## Other Useful Commands

### View Statistics

```bash
# Last 7 days
python scripts/observability/view_observability.py --stats

# Last 30 days
python scripts/observability/view_observability.py --stats --days 30

# Filter by request type
python scripts/observability/view_observability.py --stats --type info

# Filter by outcome
python scripts/observability/view_observability.py --stats --outcome success
```

### View Tag Distribution

```bash
# Distribution of request types and outcomes
python scripts/observability/view_observability.py --tags

# For specific time period
python scripts/observability/view_observability.py --tags --days 30
```

### Custom Database Location

If your database is in a different location:

```bash
python scripts/observability/view_observability.py --db "path/to/cinemind.db" --request-id <id>
```

## Understanding Classification Metadata

The classification metadata shows how the hybrid classifier worked:

- **Predicted Type**: Final classification result
- **Rule Hit**: Which rule pattern matched (if any), or guardrail applied
- **LLM Used**: Whether the LLM was used for classification (False = rules only)
- **Confidence**: Confidence score (0.0-1.0)
- **Entities**: Extracted movie titles, person names (if LLM was used)
- **Need Freshness**: Whether query needs up-to-date data

## Notes

- The script automatically shows classification metadata if available
- Request IDs can be found from recent requests or from test output
- All times are in milliseconds
- Costs are in USD

