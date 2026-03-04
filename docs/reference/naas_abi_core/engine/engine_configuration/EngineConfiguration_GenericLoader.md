# `GenericLoader`

## What it is
- A small Pydantic model that **dynamically imports** a Python module, **retrieves** a named callable (class or function), and **instantiates/calls** it using a configuration dict as keyword arguments.

## Public API
- `class GenericLoader(pydantic.BaseModel)`
  - Fields:
    - `python_module: str | None` — fully qualified module path to import.
    - `module_callable: str | None` — attribute name in the module to call.
    - `custom_config: Dict[str, Any] | None` — keyword arguments passed to the callable.
  - Methods:
    - `load() -> Any`
      - Imports `python_module` via `importlib.import_module`.
      - Retrieves the callable via `getattr(module, module_callable)`.
      - Calls it as `callable_obj(**custom_config)` and returns the result.

## Configuration/Dependencies
- Dependencies:
  - Standard library: `importlib`
  - Third-party: `pydantic.BaseModel`
- Required inputs (enforced at runtime via `assert` in `load()`):
  - `python_module` must be non-`None`
  - `module_callable` must be non-`None`
  - `custom_config` must be non-`None`

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import GenericLoader

# Example: call a standard library callable (datetime.datetime)
loader = GenericLoader(
    python_module="datetime",
    module_callable="datetime",
    custom_config={"year": 2024, "month": 1, "day": 2},
)

dt = loader.load()
print(dt)  # 2024-01-02 00:00:00
```

## Caveats
- `load()` uses `assert` statements; missing fields raise `AssertionError`.
- The target attribute must exist on the imported module; otherwise `getattr` raises `AttributeError`.
- `custom_config` must match the callable’s expected keyword arguments; otherwise a `TypeError` may be raised.
- Only supports callables invoked with keyword arguments (`callable_obj(**custom_config)`).
