# CSV Exports

This directory contains CSV exports of database and test data for analysis.

## Export Script

Use the export script to generate CSV files:

```bash
# Export all data (database + test results)
python scripts/export/export_to_csv.py

# Export specific tables/data
python scripts/export/export_to_csv.py --table requests
python scripts/export/export_to_csv.py --table responses
python scripts/export/export_to_csv.py --table metrics
python scripts/export/export_to_csv.py --table search_operations
python scripts/export/export_to_csv.py --table test_results
python scripts/export/export_to_csv.py --table prompt_comparison

# Custom output directory
python scripts/export/export_to_csv.py --output-dir my_exports

# Custom database file
python scripts/export/export_to_csv.py --db my_database.db
```

## Available CSV Files

- **requests.csv** - All requests from the database (includes prompts, query, type, status, etc.)
- **responses.csv** - All responses (includes response text, sources, token usage, cost)
- **metrics.csv** - All metrics (response times, token counts, costs, etc.)
- **search_operations.csv** - All search operations (queries, providers, results count, timing)
- **test_results.csv** - Test results from JSON files (includes all test runs)
- **prompt_comparison.csv** - Prompt version comparison results

## CSV Structure

### requests.csv
- request_id, user_query, prompt, timestamp, status, request_type, outcome, response_time_ms, etc.

### responses.csv
- request_id, response_text, sources (JSON), token_usage (JSON), cost_usd, created_at

### metrics.csv
- request_id, metric_type, metric_name, metric_value, metric_data (JSON), timestamp

### search_operations.csv
- request_id, search_query, search_provider, results_count, search_time_ms, timestamp

### test_results.csv
- file, timestamp, type (summary/test_result), test_name, passed, failed, pass_rate, prompt_version, model_version, etc.

### prompt_comparison.csv
- version, timestamp, type, test_name, passed, failed, pass_rate, prompt_length, model_version, etc.

## Analysis Tips

1. **Open in Excel/Google Sheets** - CSV files can be opened directly in spreadsheet applications
2. **Filter by prompt_version** - Compare performance across different prompt versions
3. **Group by test_name** - See which tests consistently pass/fail
4. **Sort by execution_time_ms** - Identify slow tests
5. **Filter by request_type** - Analyze performance by query type (info, recs, comparison, etc.)

