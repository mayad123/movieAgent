# Adding New Test Scenarios

This guide explains how to add new test scenarios to the CineMind test suite.

## Scenario Format

Test scenarios are stored as JSON or YAML files in `tests/fixtures/scenarios/`. Each scenario file defines a test case with input data and expected outcomes.

## Scenario File Structure

### JSON Format Example

Create a file `tests/fixtures/scenarios/simple_director_query.json`:

```json
{
  "name": "simple_director_query",
  "description": "Test query for director information",
  "input": {
    "prompt": "Who directed Prisoners?",
    "request_plan": {
      "intent": "director_info",
      "request_type": "info",
      "entities": ["Prisoners"],
      "entities_typed": {
        "movies": ["Prisoners"],
        "people": []
      }
    }
  },
  "expected": {
    "response_contains": ["Denis Villeneuve"],
    "request_type": "info"
  },
  "metadata": {
    "category": "simple_facts",
    "tags": ["director", "factual"]
  }
}
```

### YAML Format Example

Create a file `tests/fixtures/scenarios/recommendation_query.yaml`:

```yaml
name: recommendation_query
description: Test query for movie recommendations
input:
  prompt: "Recommend movies similar to Inception"
  request_plan:
    intent: recommendation
    request_type: recs
    entities: ["Inception"]
    entities_typed:
      movies: ["Inception"]
      people: []
expected:
  response_contains: ["movie", "similar"]
  request_type: recs
  min_length: 100
metadata:
  category: recommendations
  tags: ["recommendation", "similarity"]
```

## Loading Scenarios in Tests

Use the `load_scenario` function from `tests.fixtures.loader`:

```python
import pytest
from tests.fixtures.loader import load_scenario

def test_director_query():
    """Test director information query."""
    scenario = load_scenario("simple_director_query", format="json")
    
    # Access scenario data
    prompt = scenario["input"]["prompt"]
    expected = scenario["expected"]
    
    # Use in your test
    # ... your test logic here ...
```

## Scenario Fields

### Required Fields

- `name`: Unique identifier for the scenario
- `input`: Input data for the test
  - `prompt`: User query string
  - `request_plan`: RequestPlan structure (optional, can be generated)

### Optional Fields

- `description`: Human-readable description
- `expected`: Expected outcomes
  - `response_contains`: List of strings that should appear in response
  - `request_type`: Expected request type classification
  - `min_length`: Minimum response length
  - `max_length`: Maximum response length
- `metadata`: Additional metadata
  - `category`: Test category (e.g., "simple_facts", "recommendations")
  - `tags`: List of tags for filtering

## Best Practices

1. **Naming**: Use descriptive, lowercase names with underscores (e.g., `simple_director_query.json`)
2. **Organization**: Group related scenarios by category in their metadata
3. **Minimal Data**: Only include necessary data in scenarios
4. **Reusability**: Design scenarios to be reusable across different test types
5. **Documentation**: Add descriptions to explain the purpose of each scenario

## Listing Available Scenarios

To see all available scenarios:

```python
from tests.fixtures.loader import list_scenarios

scenarios = list_scenarios()
print(f"Available scenarios: {scenarios}")
```

## Example Test Using Scenarios

```python
import pytest
from tests.fixtures.loader import load_scenario
from cinemind.agent import CineMind

@pytest.mark.asyncio
async def test_scenario_based_query():
    """Test using a scenario file."""
    scenario = load_scenario("simple_director_query")
    
    agent = CineMind()
    result = await agent.search_and_analyze(scenario["input"]["prompt"])
    
    # Verify expected outcomes
    response = result.get("response", "")
    for expected_text in scenario["expected"]["response_contains"]:
        assert expected_text.lower() in response.lower()
```

