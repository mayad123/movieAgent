# Test Results Directory

This directory automatically stores all test run results from the CineMind evaluation pipeline.

## Automatic Storage

When you run tests using `python tests/test_runner.py`, results are automatically saved here with timestamps:

- Format: `test_results_{suite}_{timestamp}.json`
- Example: `test_results_all_20241207_211415.json`
- Location: All results are stored in this directory

## Viewing Results

### Summary View (Default)
```bash
python tests/view_test_results.py
```

Shows a summary of all test runs with pass rates and execution times.

### Detailed View
```bash
python tests/view_test_results.py --detailed
```

Shows detailed results of the most recent test run, including individual test outcomes and responses.

### Compare Runs
```bash
python tests/view_test_results.py --compare 5
```

Compares the last 5 test runs side-by-side.

### Failure Analysis
```bash
python tests/view_test_results.py --failures
```

Shows which tests consistently fail across multiple runs.

### View Specific File
```bash
python tests/view_test_results.py --file test_results_all_20241207_211415.json
```

Shows detailed view of a specific result file.

## File Naming Convention

- `test_results_all_{timestamp}.json` - All test cases
- `test_results_simple_{timestamp}.json` - Simple test suite
- `test_results_recommendations_{timestamp}.json` - Recommendations suite
- `test_results_spoilers_{timestamp}.json` - Spoilers suite
- etc.

## Results Structure

Each result file contains:
- `timestamp`: When the test was run
- `summary`: Overall statistics (total, passed, failed, pass rate, avg time)
- `results`: Individual test results with:
  - Test name and pass/fail status
  - Criteria evaluation results
  - Actual response text
  - Request type classification
  - Execution time
  - Errors (if any)

## Best Practices

1. **Don't manually delete files** - They're automatically organized by timestamp
2. **Use the view utility** - Don't manually parse JSON files
3. **Compare before/after changes** - Run tests before and after code changes to track regressions
4. **Track trends** - Use `--compare` to see if performance is improving or degrading

## Integration with CI/CD

Results are automatically saved, so you can:
- Archive results for historical analysis
- Track performance trends over time
- Identify regressions quickly
- Compare different prompt versions or configurations

