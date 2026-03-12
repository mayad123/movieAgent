# Source Policy and Verification System

## Overview

The source policy system implements strict tier-based source ranking, intent-specific search optimization, and fact verification to ensure high-quality, authoritative responses.

## Key Components

### 1. Source Policy (`source_policy.py`)

**Tier-Based Ranking:**
- **Tier A (Authoritative/Structured)**: IMDb, Wikipedia, Wikidata, TMDb
- **Tier B (Reputable Editorial)**: Variety, Deadline, Hollywood Reporter, Rotten Tomatoes, Metacritic
- **Tier C (Low-Trust)**: Quora, Facebook, Reddit, blogs

**Enforcement Rules:**
- **Facts (info, fact-check)**: Tier A only, unless no Tier A exists
- **Release dates**: Tier A preferred, Tier B allowed for news
- **Recommendations**: All tiers allowed, ranked by tier
- **Spoilers**: Tier A preferred (Wikipedia plot summaries)

**Auto-Rejection:**
- Tier C sources are automatically filtered for fact-based queries
- Quora and Facebook posts are rejected for confirmed facts

### 2. Intent Extraction (`intent_extraction.py`)

**Structured Intent Schema:**
```json
{
  "intent": "filmography_overlap|director_info|release_date|cast_info|comparison|recommendation",
  "entities": ["person name", "movie title", ...],
  "constraints": {
    "min_count": 3,
    "order_by": "release_year",
    "format": "list"
  }
}
```

**Extraction Methods:**
- Pattern-based (fast, fallback)
- LLM-based (accurate, uses GPT for better entity extraction)

### 3. Verification (`verification.py`)

**Extraction + Verification Pass:**
1. Extract candidate facts from search results
2. Verify each candidate against Tier A sources (IMDb, Wikipedia)
3. Only include verified facts in final answer
4. Resolve conflicts using conflict resolution rules

**Conflict Resolution:**
- Same title, different years: Use most common year from Tier A
- Release year vs premiere: Use first public release year
- Cast overlaps: Use credited cast only (from IMDb/Wikipedia)

### 4. Intent-Specific Search Queries (`search_engine.py`)

**Optimized Queries by Intent:**

**Filmography Overlap:**
```
site:imdb.com "Robert De Niro" "Al Pacino" film
site:wikipedia.org Robert De Niro Al Pacino film
```

**Director Info:**
```
site:imdb.com "The Matrix" director
site:wikipedia.org "The Matrix" film director
```

**Release Date:**
```
site:imdb.com "The Matrix" release date
site:wikipedia.org "The Matrix" film release
```

These queries bias search results toward Tier A sources.

## Agent Integration

### Flow:

1. **Classification**: Request is classified (info, recs, etc.)
2. **Intent Extraction**: Query is converted to structured intent + entities + constraints
3. **Intent-Specific Search**: Search queries are optimized based on intent
4. **Source Ranking**: Results are ranked and filtered by tier
5. **Verification**: Facts are extracted and verified against Tier A sources
6. **Response Generation**: LLM uses verified facts and Tier A sources
7. **Source Transparency**: All source tiers are logged

### Example: Filmography Overlap Query

**Query**: "Name three movies with both Robert De Niro and Al Pacino, ordered by release year"

**Process:**
1. **Intent Extraction**: 
   - Intent: `filmography_overlap`
   - Entities: `["Robert De Niro", "Al Pacino"]`
   - Constraints: `{min_count: 3, order_by: "release_year", format: "list"}`

2. **Search Queries**:
   - `site:imdb.com "Robert De Niro" "Al Pacino" film`
   - `site:wikipedia.org Robert De Niro Al Pacino film`

3. **Source Ranking**:
   - Tier A sources (IMDb, Wikipedia) prioritized
   - Tier C sources (Quora, Facebook) filtered out

4. **Verification**:
   - Extract candidate titles from results
   - Verify each title against IMDb/Wikipedia
   - Confirm both actors are in cast

5. **Response**:
   - Use only verified facts
   - Format: "Title (Year)" in ascending order
   - Add: "Verified via IMDb/Wikipedia"

## Source Transparency Logging

All source usage is logged:

- `source_tier_counts`: Count of sources by tier (A/B/C)
- `has_tier_a_sources`: Whether Tier A sources were used
- `has_tier_c_only`: Whether only Tier C sources were available (warning flag)

This enables metrics like:
- "% of info answers using Tier A sources"
- "% of answers relying on Tier C"
- "average source age for release-status questions"

## Standardized Output Format

For list-based queries (e.g., "Name three movies..."):

**Format:**
```
1. Title (Year)
2. Title (Year)
3. Title (Year)

Verified via IMDb/Wikipedia
```

**Validation:**
- Substring match for year
- Correct ordering (ascending by year)
- At least N items (from constraints)

## Benefits

1. **Accuracy**: Tier A sources ensure authoritative facts
2. **Reliability**: Verification prevents hallucination from low-quality sources
3. **Efficiency**: Intent-specific queries reduce noise
4. **Transparency**: Full source attribution and tier tracking
5. **Testability**: Standardized output format enables reliable testing

## Configuration

### Adding New Tier A Sources

Edit `src/cinemind/source_policy.py`:
```python
TIER_A_DOMAINS = {
    "imdb.com",
    "wikipedia.org",
    "your-new-source.com",  # Add here
}
```

### Adjusting TTL by Request Type

Edit `src/cinemind/source_policy.py`:
```python
TTL_BY_TYPE = {
    "release-date": 12,  # hours
    "info": {...},
    # ...
}
```

### Similarity Threshold

Edit `src/cinemind/cache.py`:
```python
SEMANTIC_SIMILARITY_THRESHOLD = 0.90  # 0.88-0.93 recommended
```

## Future Enhancements

- Direct API integration (IMDb API, TMDb API, Wikidata SPARQL)
- Source freshness tracking (check Wikipedia page last updated)
- Entity-aware caching (cache by movie/person, not just query)
- Advanced NER for better entity extraction
- Multi-source consensus (require 2+ Tier A sources for critical facts)

