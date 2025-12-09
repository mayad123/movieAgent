# Testing Quick Start Guide

## Running Tests

### Basic Usage
```bash
# Run all tests (sequential)
python tests/test_runner.py

# Run tests in parallel (faster)
python tests/test_runner.py --parallel

# Run specific test suite
python tests/test_runner.py --suite simple
```

### Advanced Options
```bash
# Parallel with custom concurrency (3-5 recommended)
python tests/test_runner.py --parallel --max-concurrent 5

# Skip database saving
python tests/test_runner.py --no-db

# Verbose output
python tests/test_runner.py --verbose

# Skip confirmation (for automation)
python tests/test_runner.py --yes
```

## Analyzing Results

### Database Analysis
```bash
# View pass rates and statistics
python scripts/analyze_test_results.py --pass-rates

# View history of specific test
python scripts/analyze_test_results.py --test simple_fact_director

# Find flaky tests
python scripts/analyze_test_results.py --flaky

# Compare prompt versions
python scripts/analyze_test_results.py --compare-versions v1 v4 v5
```

### Graphical View
```bash
# View test results graphically
python tests/view_test_results_graphical.py
```

## Adding New Tests

1. Choose the appropriate category file in `tests/test_cases/`
2. Add your test case:
   ```python
   TestCase(
       name="my_test",
       prompt="Your query",
       expected_type="info",
       acceptance_criteria=[
           contains_all_substrings("required", "terms"),
           min_length(100)
       ]
   )
   ```
3. Test is automatically included!

## Test Suites

- `all` - All test cases
- `simple` - Simple fact queries
- `multi_hop` - Multi-hop reasoning
- `recommendations` - Recommendation queries
- `comparisons` - Comparison queries
- `spoilers` - Spoiler handling
- `fact_check` - Fact-checking queries

## Key Features

✅ **Modular Organization** - Tests organized by category  
✅ **Database Storage** - Fast queries and analysis  
✅ **Parallel Execution** - Run tests concurrently  
✅ **Rich Analysis** - Pass rates, trends, flaky test detection  
✅ **Version Tracking** - Track prompt/model/agent versions  

For more details, see:
- `docs/TESTING_SETUP_SUMMARY.md` - Setup overview
- `docs/SCALING_TESTING.md` - Scaling guide
- `docs/TESTING_INFRASTRUCTURE.md` - Detailed documentation

