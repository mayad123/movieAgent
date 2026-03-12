# Scaling Testing Infrastructure

Guide for managing large-scale testing with many test cases.

## Recommended Setup

### 1. Modular Test Organization ✅

**Structure:**
```
tests/
├── test_cases/
│   ├── base.py              # TestCase class and criteria functions
│   ├── simple_facts.py      # Simple fact queries
│   ├── multi_hop.py         # Multi-hop reasoning
│   ├── recommendations.py  # Recommendation queries
│   ├── comparisons.py       # Comparison queries
│   ├── spoilers.py          # Spoiler handling
│   └── fact_checking.py     # Fact-check queries
└── ...
```

**Benefits:**
- Easy to add new test categories
- Better organization with many tests
- Can import specific categories
- Easier code review

**Usage:**
```python
# Import all tests
from test_cases import TEST_CASES, TEST_SUITES

# Or import specific categories
from test_cases.simple_facts import SIMPLE_FACT_TESTS
```

### 2. Test Results Database ✅

**Why Database?**
- Fast queries across thousands of test runs
- Easy filtering by date, version, test name
- Better analytics and trend analysis
- Can link to request/response data
- SQL queries for complex analysis

**Usage:**
```bash
# Tests automatically save to database
python tests/test_runner.py

# Query test results
python scripts/analysis/analyze_test_results.py --pass-rates
python scripts/analysis/analyze_test_results.py --test simple_fact_director
python scripts/analysis/analyze_test_results.py --flaky
python scripts/analysis/analyze_test_results.py --compare-versions v1 v4 v5
```

**Database Schema:**
- `test_runs` - Summary of each test run
- `test_results` - Individual test results
- `criteria_results` - Criteria evaluations
- `test_search_results` - Search information

### 3. Parallel Test Execution ✅

**Benefits:**
- Much faster test execution
- Can run 3-5 tests concurrently
- Respects API rate limits with semaphore

**Usage:**
```bash
# Run tests in parallel (3 concurrent by default)
python tests/test_runner.py --parallel

# Custom concurrency limit
python tests/test_runner.py --parallel --max-concurrent 5
```

**Considerations:**
- Higher API quota usage
- May hit rate limits if too high
- Recommended: 3-5 concurrent tests

### 4. Enhanced Analysis Tools ✅

**Available Tools:**

1. **CSV Export** - Export all data to CSV
   ```bash
   python scripts/export/export_to_csv.py
   ```

2. **Database Analysis** - SQL-like queries
   ```bash
   python scripts/analysis/analyze_test_results.py --pass-rates
   python scripts/analysis/analyze_test_results.py --flaky
   ```

3. **Graphical Visualization**
   ```bash
   python tests/view_test_results_graphical.py
   ```

### 5. Test Data Management

**Best Practices:**

1. **Version Control Test Cases**
   - Keep test cases in git
   - Review test additions
   - Tag test case versions

2. **Test Result Archival**
   - Keep last N days in active database
   - Archive older results to separate database
   - Export to CSV for long-term storage

3. **Configuration Management**
   - Track prompt versions
   - Track model versions
   - Track agent config versions
   - All stored in test results

### 6. Adding New Test Cases

**Process:**

1. **Choose Category** - Add to appropriate file in `tests/test_cases/`
2. **Define Test Case** - Use TestCase dataclass
3. **Set Criteria** - Use acceptance criteria functions
4. **Add to Suite** - Update `__init__.py` if new category

**Example:**
```python
# tests/test_cases/simple_facts.py
from .base import TestCase, contains_all_substrings, min_length

SIMPLE_FACT_TESTS = [
    # ... existing tests ...
    
    TestCase(
        name="simple_fact_actor",
        prompt="Who starred in Inception?",
        expected_type="info",
        acceptance_criteria=[
            contains_all_substrings("leonardo", "dicaprio"),
            min_length(50)
        ]
    ),
]
```

### 7. CI/CD Integration (Future)

**Recommended Setup:**

```yaml
# .github/workflows/tests.yml
name: Run Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          python tests/test_runner.py --yes --parallel
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: test-results
          path: data/test_results/
```

### 8. Performance Optimization

**For Large Test Suites:**

1. **Use Parallel Execution**
   ```bash
   python tests/test_runner.py --parallel --max-concurrent 5
   ```

2. **Run Specific Suites**
   ```bash
   python tests/test_runner.py --suite simple
   ```

3. **Skip Database** (if just testing)
   ```bash
   python tests/test_runner.py --no-db
   ```

4. **Batch Test Runs**
   - Run different suites at different times
   - Use cron/scheduled tasks
   - Monitor API costs

### 9. Cost Management

**Tracking:**
- Database stores cost per test run
- CSV exports include cost data
- Analysis tools show cost trends

**Optimization:**
- Cache test results when possible
- Run regression tests less frequently
- Use parallel execution to reduce total time (but increases concurrent API calls)

### 10. Querying Test Results

**SQL Queries (via analyze script):**

```bash
# Pass rates by version
python scripts/analysis/analyze_test_results.py --pass-rates

# Specific test history
python scripts/analysis/analyze_test_results.py --test simple_fact_director

# Find flaky tests
python scripts/analysis/analyze_test_results.py --flaky

# Compare versions
python scripts/analysis/analyze_test_results.py --compare-versions v1 v4 v5
```

**Direct Database Access:**
```python
from cinemind.test_results_db import TestResultsDB

db = TestResultsDB()
runs = db.get_test_runs(prompt_version="v4", limit=10)
stats = db.get_test_statistics(days=7)
db.close()
```

## Migration Path

### Phase 1: Current Setup ✅
- Modular test organization
- Test results database
- Parallel execution
- Enhanced analysis tools

### Phase 2: Scale Up
- Add more test categories
- Implement test result archival
- Add automated regression detection
- Set up scheduled test runs

### Phase 3: Production
- CI/CD integration
- Automated reporting
- Cost monitoring alerts
- Performance benchmarking

## Quick Reference

```bash
# Run all tests (sequential)
python tests/test_runner.py

# Run tests in parallel
python tests/test_runner.py --parallel

# Run specific suite
python tests/test_runner.py --suite simple

# Export to CSV
python scripts/export/export_to_csv.py

# Analyze results
python scripts/analysis/analyze_test_results.py --pass-rates

# View graphically
python tests/view_test_results_graphical.py
```

