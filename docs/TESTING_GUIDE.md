# CineMind Testing Guide

Complete guide to testing and evaluating your movie agent.

## Overview

The test suite provides:
- ✅ **Real API Evaluation**: Uses actual OpenAI and Tavily APIs for accurate results
- ✅ **Confirmation Prompt**: Asks before running to prevent accidental costs
- ✅ **Regression Testing**: Catch breaking changes before deployment
- ✅ **A/B Testing**: Compare different prompt versions
- ✅ **Acceptance Criteria**: Flexible evaluation framework

## Quick Start

### Run All Tests

**⚠️ WARNING: This will make real API calls and cost tokens!**

```bash
python tests/test_runner.py
```

You'll see a confirmation prompt with estimated costs before tests run.

### Run Specific Test Suite

```bash
# Simple fact queries
python tests/test_runner.py --suite simple

# Recommendations
python tests/test_runner.py --suite recommendations

# Spoiler handling
python tests/test_runner.py --suite spoilers
```

### Save Results

```bash
python tests/test_runner.py --output test_results.json
```

## Test Suites

| Suite | Description | Test Cases |
|-------|-------------|------------|
| `all` | All test cases | 8 tests |
| `simple` | Simple fact queries | 2 tests |
| `multi_hop` | Multi-step reasoning | 1 test |
| `recommendations` | Recommendation requests | 1 test |
| `spoilers` | Spoiler handling | 1 test |
| `fact_check` | Fact verification | 1 test |

## Current Test Cases

1. **simple_fact_director**: "Who directed Prisoners?"
   - Checks: Mentions Denis Villeneuve
   
2. **simple_fact_release_date**: "When was The Matrix released?"
   - Checks: Mentions 1999

3. **multi_hop_actors**: "Name three movies with both Robert De Niro and Al Pacino"
   - Checks: Mentions both actors, lists 3+ movies

4. **recommendations_similar_movies**: "I liked Arrival and Annihilation, recommend 5 movies"
   - Checks: Recommends 5 movies, explains connections

5. **release_date_future**: "Is Gladiator II already out?"
   - Checks: Mentions release date/status

6. **spoiler_request**: "Explain the ending of Shutter Island (spoilers OK)"
   - Checks: Contains spoiler warning, explains ending

7. **comparison_directors**: "Compare Nolan and Villeneuve"
   - Checks: Mentions both directors, compares styles

8. **fact_check**: "Did DiCaprio win an Oscar for The Revenant?"
   - Checks: Confirms Oscar win

## Adding New Test Cases

Edit `tests/test_cases.py`:

```python
TestCase(
    name="my_new_test",
    prompt="Your test query here",
    expected_type="info",  # or recs, comparison, spoiler, etc.
    acceptance_criteria=[
        contains_all_substrings("required", "terms"),
        min_length(100),
        contains_spoiler_warning()  # if needed
    ],
    mock_response="Expected mock response text",
    mock_search_results=[
        {
            "title": "Mock Search Result",
            "url": "https://example.com",
            "content": "Mock content here",
            "source": "mock"
        }
    ]
)
```

## Acceptance Criteria

Built-in criteria functions:

### `contains_all_substrings(*strings)`
Response must contain all specified strings:
```python
contains_all_substrings("nolan", "villeneuve")
```

### `contains_any_substring(*strings)`
Response must contain at least one:
```python
contains_any_substring("2024", "2025", "coming soon")
```

### `contains_spoiler_warning()`
Must include spoiler warning:
```python
contains_spoiler_warning()
```

### `min_length(chars)`
Minimum response length:
```python
min_length(200)
```

### `contains_at_least_n_items(count, keyword)`
Count numbered/bulleted items:
```python
contains_at_least_n_items(5, "movie")
```

### `mentions_director(name)` / `mentions_movie(title)`
Must mention specific director/movie:
```python
mentions_director("Christopher Nolan")
mentions_movie("Inception")
```

## Prompt Version Testing

### Compare Prompt Versions

**Option 1: Dedicated Prompt Comparison Script** (recommended for prompt-focused comparisons)

```bash
# Compare all prompt versions
python tests/test_prompt_versions.py

# Compare specific versions
python tests/test_prompt_versions.py --versions v1 v2_optimized v4

# Compare on specific test suite
python tests/test_prompt_versions.py --suite simple --versions v1 v4

# Skip confirmation
python tests/test_prompt_versions.py --yes
```

This script saves:
- Individual results per version (with full prompt text)
- `comparison.json` (includes all prompts)
- `prompts.json` (just the prompt texts for easy viewing)

**Option 2: Interactive Test Runner** (for flexible test case + version selection)

```bash
# Interactive mode
python tests/test_runner_interactive.py

# Command-line - compare all versions with all tests
python tests/test_runner_interactive.py --tests all --versions all

# Compare specific versions with specific tests
python tests/test_runner_interactive.py --tests simple_fact_director --versions v1,v2_optimized
```

### Available Prompt Versions

- **v1**: Initial version - basic structure
- **v2**: Modular structure with clear sections
- **v3**: Enhanced with detailed guidelines and examples

### Switch Prompt Version

Set environment variable:
```bash
export PROMPT_VERSION=v2
python cinemind.py "test query"
```

Or edit `config.py`:
```python
PROMPT_VERSION = "v2"
```

## Regression Testing Workflow

### 1. Baseline Before Changes

```bash
# Run tests and save baseline
python tests/test_runner.py --output baseline.json
```

### 2. Make Changes

- Modify system prompt
- Update agent logic
- Change API usage

### 3. Test After Changes

```bash
# Run tests again
python tests/test_runner.py --output after.json
```

### 4. Compare Results

Check for:
- New failures
- Performance regressions
- Changed responses

## Using Tests in Development

### Before Committing

```bash
# Run all tests
python tests/test_runner.py

# Exit code 1 if tests fail (for CI/CD)
if [ $? -ne 0 ]; then
    echo "Tests failed - fix before committing"
    exit 1
fi
```

### Iterative Improvement

1. Identify issue from logs/observability
2. Create test case for the issue
3. Fix the issue
4. Run test to verify fix
5. Add to regression suite

## Test Results Structure

```json
{
  "timestamp": "2024-12-07T20:54:00",
  "summary": {
    "total_tests": 8,
    "passed": 8,
    "failed": 0,
    "pass_rate": 1.0,
    "avg_execution_time_ms": 600.0
  },
  "results": [
    {
      "test_name": "simple_fact_director",
      "passed": true,
      "criteria_results": [
        ["criterion_1", true, "All required substrings found"]
      ],
      "actual_response": "...",
      "actual_type": "info",
      "execution_time_ms": 500.0,
      "errors": []
    }
  ]
}
```

## Best Practices

### 1. Test Coverage

Aim for test cases covering:
- ✅ All request types (info, recs, comparison, spoiler, release-date, fact-check)
- ✅ Edge cases (vague queries, missing data, conflicting info)
- ✅ Common user queries (from observability logs)

### 2. Mock Data Quality

Use realistic mock responses and search results that match real API behavior.

### 3. Regular Testing

Run tests:
- Before each commit
- After prompt changes
- Before releases
- When fixing bugs

### 4. Version Control

Keep test cases and results in version control:
```bash
git add tests/
git commit -m "Add test cases for recommendation queries"
```

## Integration with Observability

Use observability data to improve tests:

1. **Find Common Queries**: Use `scripts/observability/view_observability.py` to see frequent queries
2. **Identify Issues**: Look for failed requests or unclear responses
3. **Create Tests**: Add test cases for issues found
4. **Verify Fixes**: Run tests to ensure issues are resolved

## Troubleshooting

### Tests Failing Unexpectedly

1. Check mock responses match expected format
2. Verify acceptance criteria aren't too strict
3. Ensure mock search results are realistic

### Import Errors

Make sure you're running from project root:
```bash
cd "C:\Users\MDN26\Desktop\Movie Agent"
python tests/test_runner.py
```

### Mock Not Working

Verify mocks are properly set up:
- Check `test_case.mock_response` is set
- Verify `test_case.mock_search_results` is set
- Ensure agent is using mocked dependencies

## Advanced Usage

### Custom Test Runner

```python
from tests.test_cases import TEST_CASES
from tests.evaluator import run_test_suite

# Run specific tests
my_tests = [tc for tc in TEST_CASES if "spoiler" in tc.name]
report = await run_test_suite(my_tests)
```

### Programmatic Evaluation

```python
from tests.evaluator import TestEvaluator
from tests.test_cases import TEST_CASES

evaluator = TestEvaluator()
result = await evaluator.run_test(TEST_CASES[0])
print(f"Passed: {result.passed}")
```

## Next Steps

1. **Add More Test Cases**: Based on real user queries
2. **Improve Mocks**: Make them more realistic
3. **Automate**: Add to CI/CD pipeline
4. **Monitor**: Track test results over time
5. **Iterate**: Use test feedback to improve prompts

