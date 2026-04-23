# LazyLoader

## What it is
- `LazyLoader` defers creation of an underlying value until it’s first used.
- It wraps a zero-argument `loader` callable and forwards common operations to the loaded value.

## Public API
- `class LazyLoader(loader: Callable)`
  - `__init__(loader)`
    - Stores the loader and marks the instance as not yet loaded.
  - `is_loaded() -> bool`
    - Returns whether the underlying value has been loaded.
  - `__getattr__(name)`
    - On first attribute access, calls `loader()` once, then forwards `getattr` to the loaded value.
  - `__iter__()`
    - Loads on first iteration, then returns `iter(loaded_value)`.
  - `__len__()`
    - Loads on first `len(...)`, then returns `len(loaded_value)`.
  - `__getitem__(key)`
    - Loads on first indexing, then returns `loaded_value[key]`.
  - `__repr__()`
    - Loads on first `repr(...)`, then returns `repr(loaded_value)`.

## Configuration/Dependencies
- Depends on Python’s standard library: `typing.Callable`, `typing.Any`.
- `loader` must be callable and is invoked as `loader()` (no arguments).

## Usage
```python
from naas_abi_core.utils.LazyLoader import LazyLoader

def load_data():
    return {"a": 1, "b": 2}

lazy = LazyLoader(load_data)

print(lazy.is_loaded())   # False
print(lazy["a"])          # Triggers load, then returns 1
print(lazy.is_loaded())   # True
print(repr(lazy))         # Uses loaded value
```

## Caveats
- Loading happens on first use of: attribute access, iteration, `len()`, indexing, or `repr()`.
- `repr(lazy)` triggers loading (it does not show an “unloaded” placeholder).
- The loader is called at most once; subsequent operations reuse the stored `value`.
