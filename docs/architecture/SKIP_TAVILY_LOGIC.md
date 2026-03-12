# Skip Tavily Logic Explanation

The "Skip Tavily" decision is made in **TWO different places** with different logic:

## 1. Tool Plan Based (Hardcoded Logic - NOT correlation-based)

**Location**: `src/cinemind/tool_plan.py` → `plan_tools()`

**Logic**: If the query has a "stable intent" (like `director_info`, `cast_info`, etc.) and doesn't need fresh data, Tavily is skipped.

```python
stable_intents = ["director_info", "cast_info", "filmography_overlap", "general_info", "comparison"]
is_stable_intent = intent in stable_intents

if not need_freshness:
    return ToolPlan(
        use_tavily=requires_disambiguation,  # Only if ambiguous title
        skip_reason="no freshness needed, using cache/structured sources"
    )
```

**When it triggers**:
- Intent type is in `stable_intents` list
- AND `need_freshness = False`
- AND `requires_disambiguation = False`

**Log message**: `"Skipping Tavily based on tool plan: no freshness needed, using cache/structured sources"`

---

## 2. Correlation Based (Automatic when Kaggle has high correlation)

**Location**: `src/cinemind/search_engine.py` → `search()`

**Logic**: If Kaggle returns highly correlated results (above threshold), Tavily is automatically skipped.

```python
if is_highly_correlated:
    logger.info(f"Using Kaggle dataset results (correlation: {max_correlation:.3f})")
    results.extend(kaggle_results)
    # If we have highly correlated results, skip Tavily API call
    return results[:max_results]
```

**When it triggers**:
- Kaggle correlation score > `KAGGLE_CORRELATION_THRESHOLD` (default: 0.7)
- This happens BEFORE checking the `skip_tavily` flag

**Log message**: `"Using Kaggle dataset results (correlation: 0.XXX)"` (and function returns early, so Tavily is never called)

---

## 3. Flag-Based (When skip_tavily flag is True from tool plan)

**Location**: `src/cinemind/search_engine.py` → `search()` (line 159)

**Logic**: If the `skip_tavily` flag is passed from the agent (based on tool plan), Tavily is skipped even if Kaggle correlation is low.

```python
elif skip_tavily:
    logger.info(f"Skipping Tavily API (as requested), using only Kaggle results")
```

**When it triggers**:
- `skip_tavily=True` is passed from `agent.py` (which got it from tool plan)
- AND Kaggle correlation is below threshold (otherwise it would have returned early)

**Log message**: `"Skipping Tavily API (as requested), using only Kaggle results"`

---

## Current Behavior for "Who directed Prisoners?"

1. **Tool Plan Decision**: Intent = `director_info` (stable) → `use_tavily=False` → `should_skip_tavily=True`
2. **Log**: `"Skipping Tavily based on tool plan: stable metadata"`
3. **Kaggle Search**: Correlation = 0.571 (< 0.7 threshold) → NOT highly correlated
4. **Log**: `"Kaggle results not highly correlated (0.571), skipping Tavily"`
5. **Skip Tavily**: Because `skip_tavily=True` flag is set
6. **Log**: `"Skipping Tavily API (as requested), using only Kaggle results"`

**Result**: Tavily is skipped because of the **tool plan decision**, NOT because of correlation.

---

## To Make It Correlation-Only

If you want Tavily to be skipped ONLY when Kaggle has high correlation, you would need to:

1. Remove or modify the tool plan logic that sets `use_tavily=False` for stable intents
2. Always allow Tavily unless Kaggle correlation is high

This would mean calling Tavily even for stable queries if Kaggle doesn't have good results.

