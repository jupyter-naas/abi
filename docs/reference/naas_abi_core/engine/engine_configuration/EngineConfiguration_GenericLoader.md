# GenericLoader

## What it is
- A small Pydantic model that **dynamically imports** a Python module, **retrieves a named callable** (class or function), and **instantiates/calls it** using a provided configuration dict as `**kwargs`.

## Public API
- `class GenericLoader(BaseModel)`
  - Fields:
    - `python_module: str | None` — fully qualified module path to import.
    - `module_callable: str | None` — name of the callable inside the module.
    - `custom_config: Dict[str, Any] | None` — keyword arguments to pass to the callable.
  - Methods:
    - `load() -> Any`
      - Imports `python_module`, fetches `module_callable` via `getattr`, and returns `callable_obj(**custom_config)`.
      - Uses `assert` to require all three fields are non-`None`.

## Configuration/Dependencies
- Dependencies:
  - Standard library: `importlib`
  - Third-party: `pydantic.BaseModel`
- Required configuration (must be set before calling `load()`):
  - `python_module`
  - `module_callable`
  - `custom_config`

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import GenericLoader

loader = GenericLoader(
    python_module="collections",
    module_callable="Counter",
    custom_config={"iterable": "abca"},
)

obj = loader.load()
print(obj)  # Counter({'a': 2, 'b': 1, 'c': 1})
```

## Caveats
- Missing `python_module`, `module_callable`, or `custom_config` triggers an `AssertionError`.
- Import and attribute failures will raise standard Python errors:
  - `ModuleNotFoundError` (module import fails)
  - `AttributeError` (callable not found)
  - `TypeError` (kwargs don’t match the callable signature)
- `assert` statements can be disabled with Python optimization (`-O`), which removes these checks.
