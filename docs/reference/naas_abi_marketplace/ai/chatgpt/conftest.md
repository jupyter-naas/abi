# `conftest.py` (pytest fixture: `module`)

## What it is
- A `pytest` configuration module that defines a fixture to load the ChatGPT ABI module via the core `Engine` and return the singleton `ABIModule` instance for tests.

## Public API
- `module() -> ABIModule` (pytest fixture)
  - Instantiates `Engine`.
  - Calls `engine.load(module_names=["src.core.chatgpt"])`.
  - Returns `ABIModule.get_instance()`.

## Configuration/Dependencies
- **pytest**: provides `@pytest.fixture`.
- **naas_abi_core.engine.Engine.Engine**: used to load modules.
- **naas_abi_marketplace.ai.chatgpt.ABIModule**: singleton module returned.
- **Module name loaded**: `"src.core.chatgpt"` must be resolvable by `Engine.load`.

## Usage
```python
def test_chatgpt_module_loaded(module):
    assert module is not None
```

## Caveats
- If `Engine.load(module_names=["src.core.chatgpt"])` fails (e.g., module not registered/available), fixture setup will fail.
- The fixture returns a singleton (`ABIModule.get_instance()`), so state may be shared across tests depending on `ABIModule` implementation.
