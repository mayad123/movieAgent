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

## Offline Scenario Tests

The offline scenario harness (`tests/test_scenarios_offline.py`) tests routing, prompt construction, evidence formatting, and validator behavior using YAML/JSON fixtures without calling external APIs.

### Scenario Sets: Gold vs Explore

Scenarios are organized into two sets:

#### Gold Scenarios
**Purpose**: Core regression tests that must pass before any release.

- **9 simple fact cases**: Director, cast, release date, and runtime queries covering fundamental functionality
- **2 freshness cases**: Where-to-watch and availability queries requiring fresh data
- **2 recommendation cases**: Movie recommendation queries

**Strictness Policy**: Gold scenarios **must pass with zero validator violations** (clean pass). Any violation will cause the test to fail.

These are the essential tests that validate core functionality and should be run frequently (e.g., on every commit, in CI/CD).

#### Explore Scenarios
**Purpose**: Extended test coverage for edge cases, advanced features, and exploratory testing.

Includes scenarios for:
- Additional recommendation types
- Edge cases (punctuation in titles, special characters, ambiguous queries)
- Multi-movie comparisons
- Deduplication tests
- Violation handling (forbidden terms, verbosity)

**Strictness Policy**: Explore scenarios **can pass with violations**. Violations are still recorded in reports and artifacts, but do not cause test failure.

These scenarios provide broader coverage but may be run less frequently (e.g., nightly, before releases).

### Running Scenario Tests

By default, all scenarios from both sets are loaded:

```bash
pytest tests/test_scenarios_offline.py -v
```

#### Run Only Gold Scenarios

Using environment variable:
```bash
CINEMIND_SCENARIO_SET=gold pytest tests/test_scenarios_offline.py -v
```

Using pytest marker:
```bash
pytest tests/test_scenarios_offline.py -m gold -v
```

#### Run Only Explore Scenarios

Using environment variable:
```bash
CINEMIND_SCENARIO_SET=explore pytest tests/test_scenarios_offline.py -v
```

Using pytest marker:
```bash
pytest tests/test_scenarios_offline.py -m explore -v
```

### Test Reports

Test reports include statistics broken out by `scenario_set`:
- Total counts per set (gold vs explore)
- Pass/fail rates per set
- **Clean passes** vs **passes with violations**
- Execution times per set

The report distinguishes between:
- **`passed_clean`**: Tests that passed with zero validator violations
- **`passed_with_violations`**: Tests that passed but had validator violations (explore scenarios only)

View the latest report at `tests/test_reports/latest.json`.

### Strictness Policy Override

You can override the default strictness policy on a per-scenario basis by adding `enforce_clean` to the scenario's `expected.validator_checks`:

```yaml
expected:
  validator_checks:
    expected_valid: true
    enforce_clean: false  # Allow violations (overrides gold default)
```

This is useful for testing violation handling or relaxing requirements for specific scenarios.

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

### Viewing Test Results

#### Text-Based View

```bash
# View summary of all test runs
python tests/view_test_results.py

# View detailed results of most recent run
python tests/view_test_results.py --detailed

# Compare last 5 test runs
python tests/view_test_results.py --compare 5

# Show failure analysis
python tests/view_test_results.py --failures

# View specific result file
python tests/view_test_results.py --file test_results_all_20241207_211415.json
```

#### Graphical Visualization

View test results in a graphical format with charts and dashboards:

```bash
# Show comprehensive dashboard (opens interactive window)
python tests/view_test_results_graphical.py

# Save dashboard as PNG
python tests/view_test_results_graphical.py --output dashboard.png

# Compare last 5 test runs graphically
python tests/view_test_results_graphical.py --compare 5

# Save comparison chart
python tests/view_test_results_graphical.py --compare 5 --output comparison.png
```

The graphical viewer provides:
- **Pass Rate Trends**: See how pass rates change over time
- **Execution Time Trends**: Monitor performance over time
- **Test-by-Test Analysis**: Individual test pass rates across all runs
- **Criteria Failure Breakdown**: Which criteria fail most often
- **Comparison Charts**: Side-by-side comparison of multiple test runs
- **Latest Run Details**: Detailed breakdown of the most recent test run

**Note**: Requires `matplotlib` (install with `pip install matplotlib`)

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

