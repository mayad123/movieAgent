# Scenario Fixtures Schema

This directory contains YAML/JSON scenario fixtures for offline testing of CineMind's routing, prompt construction, evidence formatting, and validator behavior.

## Schema

Each scenario file must follow this structure:

```yaml
name: "scenario_name"
user_query: "Who directed The Matrix?"

request_plan:
  intent: "director_info"
  request_type: "info"
  entities_typed:
    movies: ["The Matrix"]
    people: []
  need_freshness: false
  freshness_ttl_hours: 168.0
  require_tier_a: true
  allowed_source_tiers: ["A"]
  reject_tier_c: true
  response_format: "short_fact"
  constraints: {}

evidence_input:
  - source: "kaggle_imdb"
    url: "https://www.imdb.com/title/tt0133093/"
    title: "The Matrix"
    content: "The Matrix is a 1999 science fiction action film written and directed by the Wachowskis..."
    year: 1999
    tier: "A"

expected:
  template_id: "director_info"
  prompt_checks:
    required_sections: ["system", "developer", "user"]
    must_contain: ["director", "The Matrix"]
    must_not_contain: ["Tier A", "Kaggle", "dataset"]
  evidence_checks:
    dedupe_expected_count: 1
    max_snippet_len: 400
    must_not_contain_terms: ["Tier", "kaggle_imdb"]
  validator_checks:
    expected_valid: true
    expected_violation_types: []
  sample_model_output: "The Matrix was directed by the Wachowskis (Lana and Lilly Wachowski)."
```

## Field Descriptions

### Top-level Fields

- **name** (string, required): Unique identifier for the scenario
- **user_query** (string, required): The user's input query
- **request_plan** (object, required): Minimal fields to construct a `RequestPlan` object
- **evidence_input** (array, required): List of evidence items from search results
- **expected** (object, required): Expected outcomes for validation

### request_plan Fields

- **intent** (string, required): Intent type (e.g., "director_info", "cast_info", "release_date", "recommendation")
- **request_type** (string, required): Request classification (e.g., "info", "recs", "comparison")
- **entities_typed** (object, required): Typed entities with "movies" and "people" arrays
- **need_freshness** (boolean, default: false): Whether fresh data is required
- **freshness_ttl_hours** (float, default: 24.0): TTL in hours for freshness
- **require_tier_a** (boolean, default: false): Must have at least one Tier A source
- **allowed_source_tiers** (array, default: ["A", "B"]): Which source tiers are allowed
- **reject_tier_c** (boolean, default: true): Reject Tier C sources
- **response_format** (string, default: "short_fact"): Response format enum value
- **constraints** (object, default: {}): Additional constraints (format, order_by, min_count, etc.)

### evidence_input Item Fields

- **source** (string, required): Source identifier (e.g., "kaggle_imdb", "tavily", "wikipedia")
- **url** (string, required): Source URL
- **title** (string, optional): Result title
- **content** (string, optional): Result content/snippet
- **year** (integer, optional): Year associated with the result
- **tier** (string, optional): Source tier ("A", "B", or "C")

### expected Fields

- **template_id** (string, required): Expected template ID that should be selected
- **prompt_checks** (object, required): Checks for prompt construction
- **evidence_checks** (object, required): Checks for evidence formatting
- **validator_checks** (object, required): Checks for output validation
- **sample_model_output** (string, optional): Sample LLM output to validate

### prompt_checks Fields

- **required_sections** (array, required): List of required message sections (e.g., ["system", "developer", "user"])
- **must_contain** (array, optional): Strings that must appear in the prompt
- **must_not_contain** (array, optional): Strings that must NOT appear in the prompt

### evidence_checks Fields

- **dedupe_expected_count** (integer, required): Expected count after deduplication
- **max_snippet_len** (integer, required): Maximum snippet length per item
- **must_not_contain_terms** (array, optional): Terms that must NOT appear in formatted evidence

### validator_checks Fields

- **expected_valid** (boolean, required): Whether the response should be valid
- **expected_violation_types** (array, optional): List of expected violation types (e.g., ["forbidden_terms", "verbosity"])
- **enforce_clean** (boolean, optional): Whether to require zero violations for this scenario to pass. Overrides default policy:
  - `gold` scenarios default to `true` (must pass clean)
  - `explore` scenarios default to `false` (can pass with violations)
  - If specified, this value takes precedence over the set default

## Example Scenarios

See the YAML files in this directory for complete examples covering:
- Simple facts (director, cast, year, runtime)
- Recommendations
- Freshness-sensitive queries (where to watch, availability)
- Edge cases (punctuation titles, multi-movie, ambiguity)

## Folder Structure

Scenarios are organized into two sets:

- **`gold/`**: Core regression tests (13 scenarios)
  - 9 simple fact cases (director, cast, release date, runtime)
  - 2 freshness cases (where-to-watch, availability)
  - 2 recommendation cases

- **`explore/`**: Extended test coverage (14 scenarios)
  - Additional recommendation types
  - Edge cases (punctuation, special characters, ambiguity)
  - Multi-movie comparisons
  - Deduplication and violation tests

## Usage

Scenarios are automatically loaded by `tests/test_scenarios_offline.py`:

```bash
# Run all scenarios
pytest tests/test_scenarios_offline.py -v

# Run only gold scenarios (via env var)
CINEMIND_SCENARIO_SET=gold pytest tests/test_scenarios_offline.py -v

# Run only gold scenarios (via marker)
pytest tests/test_scenarios_offline.py -m gold -v

# Run only explore scenarios
CINEMIND_SCENARIO_SET=explore pytest tests/test_scenarios_offline.py -v
```

All scenarios run offline without calling external APIs, completing in <2-3 seconds.

