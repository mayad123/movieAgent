# Semantic Cache System

## Overview

The semantic cache system implements a two-tier caching strategy with freshness gates to reduce API calls and costs while maintaining data accuracy.

## Architecture

### Two-Tier Cache

**Tier 1: Exact Cache (Hash-based)**
- Fast, high-precision matching
- Key: `normalized_prompt_hash + classifier_type + tool_config_version`
- Instant lookup for identical queries
- No embedding computation needed

**Tier 2: Semantic Cache (Embedding-based)**
- Approximate matching for similar queries
- Uses OpenAI embeddings (text-embedding-3-small)
- Cosine similarity threshold: 0.90 (configurable)
- Finds semantically similar queries even with different wording

### Freshness Gates

TTL (Time To Live) varies by request type:

- **release-date**: 12 hours (frequently changing)
- **info** (old films): 30 days (historical data)
- **info** (recent films): 7 days
- **recs**: 14 days (taste doesn't change much)
- **comparison**: 7 days
- **spoiler**: 30 days (plot doesn't change)
- **fact-check**: 7 days

The `need_freshness` flag from classification can override TTL to force shorter cache times.

## Prompt Normalization

Before caching, prompts are normalized:

1. **Lowercase** conversion
2. **Strip punctuation** (keep basic sentence structure)
3. **Normalize whitespace**
4. **Map common variants**:
   - "release date" → "released"
   - "out yet" → "release status"
   - "premiere" → "release status"
5. **Entity normalization**:
   - Extract years: "The Matrix (1999)" → "the matrix 1999"
   - Remove articles: "the matrix" → "matrix"

## Cache Schema

Each cache entry stores:

- `prompt_original`: Original user query
- `prompt_normalized`: Normalized version
- `prompt_hash`: SHA256 hash for exact matching
- `prompt_embedding`: Vector embedding for semantic matching
- `predicted_type`: Request classification type
- `entities`: Extracted movie titles, person names
- `response_text`: Cached agent response
- `sources`: List of source URLs with metadata
- `created_at`: Cache entry creation time
- `expires_at`: Expiration timestamp (TTL-based)
- `agent_version`: Agent version
- `prompt_version`: Prompt version
- `tool_config_version`: Tool configuration version
- `cost_metrics`: Cost savings tracking
- `cache_tier`: "exact" or "semantic"
- `similarity_score`: Similarity score for semantic matches

## Usage

The cache is automatically integrated into the agent flow:

1. **Classification**: Request is classified to determine type and freshness needs
2. **Cache Lookup**: 
   - First checks exact cache (Tier 1)
   - If miss, checks semantic cache (Tier 2)
3. **Cache Hit**: Returns cached response immediately (no API calls)
4. **Cache Miss**: Proceeds with normal API calls, then stores result in cache

## Metrics

Cache performance is tracked:

- `cache_hit`: 1.0 if cache hit, 0.0 if miss
- `cache_tier`: "exact" or "semantic"
- `cache_similarity`: Similarity score (for semantic hits)
- `cache_savings_usd`: Cost saved by using cache

## Configuration

### Similarity Threshold

Default: 0.90 (90% similarity required)

Can be adjusted in `src/cinemind/cache.py`:
```python
SEMANTIC_SIMILARITY_THRESHOLD = 0.90
```

### TTL Configuration

TTL values can be adjusted in `src/cinemind/cache.py`:
```python
TTL_BY_TYPE = {
    "release-date": 12,  # hours
    "recs": 14 * 24,  # hours
    # ...
}
```

## Database

Cache entries are stored in the `cache_entries` table with indexes on:
- `prompt_hash` (for exact lookups)
- `expires_at` (for freshness checks)
- `predicted_type` (for semantic filtering)

## Benefits

1. **Cost Reduction**: Avoids redundant API calls for similar queries
2. **Speed**: Cache hits return instantly (no network latency)
3. **Accuracy**: Freshness gates ensure data doesn't get stale
4. **Intelligence**: Semantic matching finds similar queries even with different wording
5. **Observability**: Full tracking of cache performance and savings

## Example

**Query 1**: "Who directed The Matrix?"
- Cache miss → API call → Response cached
- Cost: $0.002

**Query 2**: "who directed the matrix" (same query, different case)
- Exact cache hit → Instant response
- Cost: $0.00 (saved $0.002)

**Query 3**: "What is the director of The Matrix movie?"
- Semantic cache hit (similarity: 0.92) → Instant response
- Cost: $0.00 (saved $0.002)

## Future Enhancements

- Source freshness tracking (check if Wikipedia page updated)
- Entity-aware caching (cache by movie/person, not just query)
- Cache warming strategies
- Distributed cache support
- Cache analytics dashboard

