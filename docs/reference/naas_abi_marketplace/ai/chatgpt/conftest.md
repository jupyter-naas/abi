# `conftest.py` (pytest fixtures)

## What it is
- A `pytest` configuration module that provides a fixture to initialize and retrieve the ChatGPT `ABIModule` for tests.
- Ensures the `Engine` loads the module before the singleton `ABIModule` instance is accessed.

## Public API
- `module() -> ABIModule` (pytest fixture)
  - Creates an `Engine`, loads the module named `"src.core.chatgpt"`, then returns `ABIModule.get_instance()`.

## Configuration/Dependencies
- **pytest**: used for fixture declaration.
- **naas_abi_core.engine.Engine.Engine**: used to load modules.
- **naas_abi_marketplace.ai.chatgpt.ABIModule**: singleton module returned by the fixture.
- Module name loaded: `src.core.chatgpt` (must be loadable by `Engine.load`).

## Usage
```python
def test_module_available(module):
    # `module` is an instance of ABIModule provided by the fixture
    assert module is not None
```

## Caveats
- The fixture depends on `Engine.load(module_names=["src.core.chatgpt"])` succeeding; missing/incorrect module registration will cause setup failures.
- `ABIModule.get_instance()` implies singleton behavior; tests may share module state across runs unless the implementation isolates it.
