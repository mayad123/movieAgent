# Kaggle Behavior Testing in Offline Scenarios

This document describes how to test Kaggle-first behavior in the offline scenario test framework.

## Overview

The offline scenario test framework now supports testing Kaggle behavior without requiring:
- Kaggle dataset downloads
- Network access
- Real KaggleDatasetSearcher

Kaggle behavior is tracked and can be asserted in scenarios, similar to how validator violations are handled.

## Scenario Format

Add a `kaggle_checks` section to the `expected` block in your scenario YAML:

```yaml
expected:
  kaggle_checks:
    expected_attempted: true          # Whether Kaggle should be attempted
    expected_evidence_used: true     # Whether Kaggle evidence should be present
    min_evidence_count: 1             # Minimum number of Kaggle evidence items
```

### Kaggle Checks Fields

- **`expected_attempted`** (optional, bool): Whether Kaggle retrieval should be attempted. If `true` and no Kaggle evidence is found, the test fails. If `false` and Kaggle evidence is found, a warning is recorded.

- **`expected_evidence_used`** (optional, bool): Whether Kaggle evidence should be present in the evidence bundle. If `true` and no Kaggle evidence is found, the test fails. If `false` and Kaggle evidence is found, a warning is recorded (but test still passes).

- **`min_evidence_count`** (optional, int): Minimum number of Kaggle evidence items expected. If the actual count is less, the test fails.

## Behavior Classification

### Kaggle Miss (No Evidence)

- **Not a hard failure** unless `expected_evidence_used: true` is set
- If `expected_evidence_used: true` and no evidence found → **test fails**
- If `expected_evidence_used: false` or not set → **test passes** (fallback works)

### Kaggle Timeout/Error

- Recorded as a **warning/violation artifact** (similar to validator violations)
- Test **still passes** if fallback works (unless explicitly expected)
- Warnings are visible in artifacts for debugging

### Kaggle Success

- If `expected_evidence_used: true` and evidence found → **test passes**
- If `min_evidence_count` is set and count is met → **test passes**
- If count is below minimum → **test fails**

## Example Scenarios

### Scenario Expecting Kaggle Evidence

```yaml
name: recommendation_with_kaggle
user_query: Recommend top 10 sci-fi movies
request_plan:
  intent: recommendation
  request_type: recs
  entities_typed:
    movies: []
    people: []
evidence_input:
  - source: kaggle_imdb
    title: The Matrix
    content: Director: The Wachowskis\nYear: 1999\nGenre: Sci-Fi, Action
    year: 1999
expected:
  kaggle_checks:
    expected_attempted: true
    expected_evidence_used: true
    min_evidence_count: 1
  evidence_checks:
    dedupe_expected_count: 1
```

### Scenario Not Expecting Kaggle (Fallback Works)

```yaml
name: simple_director_query
user_query: Who directed The Matrix?
request_plan:
  intent: director_info
  request_type: info
  entities_typed:
    movies:
    - The Matrix
    people: []
evidence_input:
  - source: tavily
    title: The Matrix - IMDb
    content: Directed by The Wachowskis
expected:
  kaggle_checks:
    expected_attempted: false  # Simple queries don't need Kaggle
    expected_evidence_used: false
  evidence_checks:
    dedupe_expected_count: 1
```

### Scenario with Kaggle Warning (Unexpected Evidence)

```yaml
name: query_with_unexpected_kaggle
user_query: Who directed The Matrix?
request_plan:
  intent: director_info
  request_type: info
evidence_input:
  - source: kaggle_imdb  # Unexpected - simple queries shouldn't use Kaggle
    title: The Matrix
    content: Director: The Wachowskis
expected:
  kaggle_checks:
    expected_evidence_used: false  # Warning recorded, but test passes
```

## Artifacts

Kaggle warnings are written to violation artifacts (similar to validator violations):

- **Location**: `tests/test_reports/violations/{scenario_name}_kaggle.json`
- **Format**: Same as violation artifacts
- **Visibility**: Kaggle behavior is visible in artifacts without breaking tests

## Test Results

Kaggle outcomes are included in test reports:

```json
{
  "scenario_name": "recommendation_with_kaggle",
  "kaggle_outcome": {
    "attempted": true,
    "evidence_used": true,
    "evidence_count": 1,
    "warnings": []
  }
}
```

## Integration with Existing Framework

- **Violations vs Failures**: Kaggle warnings follow the same pattern as validator violations
- **Gold vs Explore**: Same strictness policy applies (gold requires clean passes)
- **Artifacts**: Kaggle warnings are written to violation artifacts for visibility
- **Reports**: Kaggle outcomes are included in test reports for analysis

## Best Practices

1. **Explicit Expectations**: Always set `expected_evidence_used` when you expect Kaggle evidence
2. **Minimum Counts**: Use `min_evidence_count` to ensure sufficient evidence
3. **Warning Tolerance**: Allow warnings for unexpected Kaggle usage (explore scenarios)
4. **Clean Passes**: Gold scenarios should explicitly expect or reject Kaggle evidence

