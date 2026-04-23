# `conftest.py` (pytest fixtures)

## What it is
- A `pytest` configuration module that provides a reusable fixture returning a YAML-like configuration string for tests.

## Public API
- `test_configuration()` (pytest fixture)
  - Returns a multiline string containing test configuration data (workspace, CORS, and service adapter settings).

## Configuration/Dependencies
- Depends on:
  - `pytest` (`from pytest import fixture`)
- Intended usage:
  - Discovered automatically by `pytest` when placed in a test directory tree (as `conftest.py`).

## Usage
```python
# test_example.py
import yaml

def test_can_load_config(test_configuration):
    cfg = yaml.safe_load(test_configuration)
    assert cfg["workspace_id"] == "1234567890"
    assert "services" in cfg
```

## Caveats
- The fixture returns a raw string; parsing/validation is the responsibility of the test.
- The string includes a templated secret reference (`{{ secret.OXIGRAPH_URL }}`) that may require additional processing in the system under test.
