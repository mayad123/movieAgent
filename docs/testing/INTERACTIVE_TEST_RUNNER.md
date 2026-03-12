# Interactive Test Runner

A streamlined test runner that allows you to select specific test cases and prompt versions from a single interface.

## Features

- **Flexible Test Selection**: Select individual test cases, entire suites, or all tests
- **Multiple Prompt Versions**: Test one or more prompt versions in a single run
- **Combination Testing**: Automatically runs all combinations of selected tests × versions
- **Interactive Mode**: Menu-based selection for easy use
- **Command-Line Mode**: Automation-friendly CLI interface
- **Parallel Execution**: Optional parallel test execution for faster runs
- **Comprehensive Results**: Saves results per version and generates comparison summaries

## Usage

### Interactive Mode (Recommended)

Simply run without arguments for an interactive menu:

```bash
python tests/test_runner_interactive.py
```

The interactive mode will:
1. Show all available test cases grouped by suite
2. Let you select tests (individual names, suite names, or "all")
3. Show all available prompt versions
4. Let you select versions (comma-separated or "all")
5. Ask for additional options (verbose, parallel execution)
6. Run all combinations and show results

### Command-Line Mode

For automation or quick runs, use command-line arguments:

#### Select Specific Test Cases and Versions

```bash
# Run specific test cases with specific prompt versions
python tests/test_runner_interactive.py \
    --tests simple_fact_director,simple_fact_release_date \
    --versions v1,v2_optimized
```

#### Select Test Suites

```bash
# Run an entire test suite with all versions
python tests/test_runner_interactive.py \
    --tests suite:simple \
    --versions all
```

#### Multiple Suites and Versions

```bash
# Run multiple suites with multiple versions
python tests/test_runner_interactive.py \
    --tests simple,multi_hop \
    --versions v1,v4,v5
```

#### All Tests, Specific Versions, Parallel Execution

```bash
# Run all tests with specific versions in parallel
python tests/test_runner_interactive.py \
    --tests all \
    --versions v1,v4 \
    --parallel \
    --max-concurrent 5 \
    --verbose
```

## Test Case Selection Syntax

- **Individual names**: `simple_fact_director,simple_fact_release_date`
- **Suite names**: `simple,multi_hop,recommendations`
- **Suite prefix**: `suite:simple` (explicit suite selector)
- **All tests**: `all`

### Available Test Suites

- `simple` - Simple fact queries
- `multi_hop` - Multi-hop reasoning questions
- `recommendations` - Recommendation requests
- `comparisons` - Comparison queries
- `spoilers` - Spoiler-related queries
- `fact_check` - Fact-checking queries
- `all` - All test cases

## Prompt Version Selection

- **Specific versions**: `v1,v2_optimized,v4`
- **All versions**: `all`

### Available Prompt Versions

- `v1` - Initial version - basic structure
- `v2_optimized` - Optimized version - concise while maintaining precision
- `v4` - Highly optimized - condensed format, maximum efficiency
- `v5` - Ultra-concise - minimal format, maximum efficiency

## Options

- `--tests` - Test cases to run (see syntax above)
- `--versions` - Prompt versions to test (comma-separated or "all")
- `--output` - Output directory (default: auto-generated with timestamp)
- `--verbose` / `-v` - Show detailed output for each test
- `--parallel` - Run tests in parallel (faster, uses more API quota)
- `--max-concurrent` - Max concurrent tests when using `--parallel` (default: 3)
- `--yes` / `-y` - Skip confirmation prompt (for automation)

## Output

Results are saved to `data/test_results/interactive_<timestamp>/` with:

- Individual version results: `{version}_results.json`
- Comparison summary: `summary.json`

Each version result includes:
- Test results for each test case
- Pass/fail status
- Execution times
- Detailed criteria evaluations

The summary includes:
- Pass rates per version
- Best performing version
- Comparison statistics

## Examples

### Quick Test: Single Test Case, Single Version

```bash
python tests/test_runner_interactive.py \
    --tests simple_fact_director \
    --versions v1 \
    --yes
```

### Full Comparison: All Tests, All Versions

```bash
python tests/test_runner_interactive.py \
    --tests all \
    --versions all \
    --parallel \
    --max-concurrent 3
```

### Suite Comparison: Compare Versions on Specific Suite

```bash
python tests/test_runner_interactive.py \
    --tests suite:simple \
    --versions v1,v2_optimized,v4,v5 \
    --verbose
```

## Tips

1. **Start Small**: Test with a few test cases and versions first to verify everything works
2. **Use Parallel Execution**: For large test runs, enable `--parallel` to speed things up
3. **Check Costs**: The tool estimates costs before running - be mindful of API usage
4. **Review Summaries**: The final summary shows which version performs best
5. **Save Output**: Results are automatically saved with timestamps for later comparison

## Integration with Existing Tools

This runner is compatible with:
- `test_runner.py` - Uses the same test execution engine (imports `run_test_suite_real_apis`)
- `test_prompt_versions.py` - Focused prompt version comparison script (better for viewing prompts)
- Existing test results viewing tools (`view_test_results.py`, `view_test_results_graphical.py`)
- All existing test infrastructure (evaluator, parallel runner, etc.)

**When to use which tool:**
- **`test_runner_interactive.py`**: When you want flexible test case selection AND prompt version comparison
- **`test_prompt_versions.py`**: When you want to focus specifically on comparing prompt versions and viewing prompt text
- **`test_runner.py`**: Simple test runs with a single prompt version

