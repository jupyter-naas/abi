# GenericLoader

## What it is
- A small utility module providing:
  - `config_model(...)`: normalize/validate a config object into a specific Pydantic model.
  - `GenericLoader`: a Pydantic model that dynamically imports a module, retrieves a named callable, and invokes it with `**custom_config`.

## Public API
- `config_model(model: type[ConfigModel], config: Any) -> ConfigModel`
  - Adapts `config` into an instance of the given Pydantic `model`.
  - Behavior:
    - If `config` is already an instance of `model`, returns it.
    - If `config` is another `BaseModel`, converts it via `model_dump()`.
    - Validates with `model.model_validate(config or {})`.

- `class GenericLoader(pydantic.BaseModel)`
  - Fields:
    - `python_module: str | None` — module path passed to `importlib.import_module(...)`.
    - `module_callable: str | None` — attribute name to fetch via `getattr(module, ...)`.
    - `custom_config: dict[str, Any] | None` — kwargs passed to the callable.
    - `shared_storage: bool` — defaults to `False` (used for storage-location reporting).
  - Methods:
    - `local_storage() -> str | None`
      - Abstract by design; always raises `NotImplementedError`.
    - `custom_local_storage() -> str | None`
      - Returns `None` if `shared_storage` is `True`, otherwise a fixed explanatory string.
    - `load() -> Any`
      - Asserts `python_module`, `module_callable`, and `custom_config` are not `None`.
      - Imports the module, resolves the callable, and returns `callable_obj(**custom_config)`.

## Configuration/Dependencies
- Dependencies:
  - Standard library: `importlib`, `typing` (`Any`, `TypeVar`)
  - Third-party: `pydantic.BaseModel`
- Required fields for `GenericLoader.load()`:
  - `python_module`, `module_callable`, `custom_config`

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)

loader = GenericLoader(
    python_module="collections",
    module_callable="Counter",
    custom_config={"iterable": "abca"},
)

obj = loader.load()
print(obj)  # Counter({'a': 2, 'b': 1, 'c': 1})
```

## Caveats
- `GenericLoader.load()` uses `assert` checks:
  - Missing required fields raises `AssertionError`.
  - Running Python with optimizations (`-O`) can disable `assert` checks.
- Import/lookup/call failures raise standard Python errors:
  - `ModuleNotFoundError`, `AttributeError`, `TypeError`.
- `GenericLoader.local_storage()` is not implemented and always raises `NotImplementedError`.
