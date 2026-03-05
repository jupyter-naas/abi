# `conftest` (pytest fixtures)

## What it is
- A `pytest` configuration module that provides a single fixture returning a YAML configuration string for tests.

## Public API
- `test_configuration()` (pytest fixture)
  - Returns a multi-line YAML string containing workspace, API, CORS, and service configuration used by tests.

## Configuration/Dependencies
- Depends on `pytest`:
  - `from pytest import fixture`
- Fixture content includes references typical of a templating/secret system (e.g., `{{ secret.OXIGRAPH_URL }}`) but this file only returns the string; it does not resolve templates.

## Usage
```python
# test_example.py

def test_config_is_provided(test_configuration):
    assert "workspace_id" in test_configuration
    assert "services:" in test_configuration
```

## Caveats
- The fixture returns raw YAML text; it is not parsed or validated in this module.
- Any placeholders (e.g., `{{ secret.OXIGRAPH_URL }}`) are not interpolated here.
