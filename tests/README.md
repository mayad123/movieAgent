# CineMind Test Suite

Comprehensive testing framework for CineMind agent with real API evaluation.

## Features

- ✅ **Real APIs**: Uses actual OpenAI and Tavily APIs for accurate evaluation
- ✅ **Confirmation Prompt**: Asks before running to prevent accidental costs
- ✅ **Regression Tests**: Canonical test cases for major query types
- ✅ **Acceptance Criteria**: Flexible evaluation framework
- ✅ **Test Suites**: Organized by test type
- ✅ **Detailed Reporting**: JSON output with pass/fail details

## Quick Start

### Run All Tests

**Note: This will make real API calls and cost tokens!**

```bash
python tests/test_runner.py
```

You'll be prompted to confirm before tests run. The prompt shows estimated costs.

### Run Specific Test Suite

```bash
# Simple fact queries
python tests/test_runner.py --suite simple

# Recommendation queries
python tests/test_runner.py --suite recommendations

# Spoiler handling
python tests/test_runner.py --suite spoilers
```

### Skip Confirmation (for automation)

```bash
python tests/test_runner.py --yes
```

### Save Results

```bash
python tests/test_runner.py --output test_results.json
```

### Verbose Output

```bash
python tests/test_runner.py --verbose
```

## Test Suites

- **all**: All test cases
- **simple**: Simple fact queries
- **multi_hop**: Multi-hop reasoning queries
- **recommendations**: Recommendation requests
- **spoilers**: Spoiler handling tests
- **fact_check**: Fact-checking queries

## Test Cases

### Current Test Cases

1. **simple_fact_director**: "Who directed Prisoners?"
2. **simple_fact_release_date**: "When was The Matrix released?"
3. **multi_hop_actors**: "Name three movies with both Robert De Niro and Al Pacino"
4. **recommendations_similar_movies**: Recommendation based on liked movies
5. **release_date_future**: "Is Gladiator II already out?"
6. **spoiler_request**: "Explain the ending of Shutter Island (spoilers OK)"
7. **comparison_directors**: Compare Nolan and Villeneuve
8. **fact_check**: "Did Leonardo DiCaprio win an Oscar for The Revenant?"

## Adding New Test Cases

Edit `tests/test_cases.py`:

```python
TestCase(
    name="my_test",
    prompt="Your test query",
    expected_type="info",  # or "recs", "comparison", etc.
    acceptance_criteria=[
        contains_all_substrings("required", "terms"),
        min_length(100),
        contains_spoiler_warning()  # if needed
    ],
    mock_response="Expected mock response",
    mock_search_results=[
        {
            "title": "Mock Result",
            "url": "https://example.com",
            "content": "Mock content",
            "source": "mock"
        }
    ]
)
```

## Acceptance Criteria

Built-in criteria functions:

- `contains_all_substrings(*strings)`: Response must contain all substrings
- `contains_any_substring(*strings)`: Response must contain at least one
- `contains_spoiler_warning()`: Must include spoiler warning
- `min_length(chars)`: Minimum response length
- `contains_at_least_n_items(count, keyword)`: Count numbered/bulleted items
- `mentions_director(name)`: Must mention director
- `mentions_movie(title)`: Must mention movie

## Test Results

Results include:
- Pass/fail status
- Individual criterion results
- Actual response
- Request type classification
- Execution time
- Errors (if any)

## Using Tests for Regression

1. **Before changes**: Run tests and save baseline
   ```bash
   python tests/test_runner.py --output baseline.json
   ```

2. **After changes**: Run tests and compare
   ```bash
   python tests/test_runner.py --output after.json
   ```

3. **Compare results**: Check for regressions

## Integration with CI/CD

```bash
# Exit code 1 if tests fail
python tests/test_runner.py
```

Use in CI pipelines to catch regressions automatically.

## Custom Mock Responses

Each test case can specify:
- `mock_response`: Mock OpenAI response
- `mock_search_results`: Mock search results

This allows precise control over test scenarios without API costs.

