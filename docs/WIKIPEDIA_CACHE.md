# Wikipedia Cache — Operational Limits and TTL Defaults

In-memory TTL cache for Wikipedia API calls to avoid repeated requests on keystroke/query repetition and to improve rate-limit resilience.

## Cache Strategy

| Call Type      | Cache Key              | TTL    | Notes                                |
|----------------|------------------------|--------|--------------------------------------|
| Search         | Normalized query       | 1h     | Search results change slowly         |
| Categories     | Sorted pipe-joined titles | 1h  | Category metadata is stable          |
| Page images    | Normalized page title  | 24h    | Poster images rarely change          |
| Enrich result  | Normalized user query  | 30m    | Full result for duplicate queries    |

## Key Normalization

- **Search**: Lowercase, collapse whitespace, trim
- **Page title**: Spaces → underscores, trim
- **Categories**: Sorted list of normalized titles, pipe-joined
- **Enrich**: Lowercase, collapse whitespace, trim

## TTL Overrides (Environment)

```bash
CINEMIND_WIKI_CACHE_TTL_SEARCH=3600      # seconds, default 1h
CINEMIND_WIKI_CACHE_TTL_CATEGORIES=3600  # 1h
CINEMIND_WIKI_CACHE_TTL_PAGEIMAGE=86400  # 24h
CINEMIND_WIKI_CACHE_TTL_ENRICH=1800      # 30m
CINEMIND_WIKI_CACHE_MAX_ENTRIES=500      # max cache entries (LRU eviction)
```

## Failure Handling

- **Timeouts / Wikipedia errors**: Not cached. Next request will retry.
- **No image found**: Cached as "no image" to avoid repeated failed lookups.
- **Main response path**: Never breaks. Failures degrade to placeholder (movie_title only, no image).

## Recommended Defaults

| Setting | Value  | Rationale                              |
|---------|--------|----------------------------------------|
| Search TTL  | 3600   | Balance freshness vs API load          |
| Categories  | 3600   | Same as search                         |
| Page image  | 86400  | Images almost never change             |
| Enrich      | 1800   | Typing repetition within session       |
| Max entries | 500    | ~10–20 MB in-memory for typical usage  |
