# LazyLoader

## What it is
- A small utility class that defers creation of an underlying value until it is first accessed.
- Wraps a `loader: Callable` and proxies common operations to the loaded value.

## Public API
- `class LazyLoader(loader: Callable)`
  - Holds:
    - `loaded: bool` — whether the value has been loaded.
    - `loader: Callable` — function used to compute/load the value.
    - `value: Any` — cached loaded value (set on first use).
- `LazyLoader.__init__(loader: Callable)`
  - Initializes in an unloaded state.
- `LazyLoader.is_loaded() -> bool`
  - Returns whether the underlying value has been loaded.
- `LazyLoader.__getattr__(name)`
  - Loads the value on first attribute access and forwards `getattr(...)`.
- `LazyLoader.__iter__()`
  - Loads on first iteration and returns `iter(value)`.
- `LazyLoader.__len__()`
  - Loads on first `len(...)` and returns `len(value)`.
- `LazyLoader.__getitem__(key)`
  - Loads on first indexing and returns `value[key]`.
- `LazyLoader.__repr__()`
  - Loads on first `repr(...)` and returns `repr(value)`.

## Configuration/Dependencies
- Depends on:
  - `typing.Callable`, `typing.Any` (type annotations only).
- No external configuration.

## Usage
```python
from naas_abi_core.utils.LazyLoader import LazyLoader

def load_data():
    print("loading...")
    return {"a": 1, "b": 2}

lazy = LazyLoader(load_data)

print(lazy.is_loaded())  # False
print(lazy["a"])         # triggers load, prints "loading...", then 1
print(lazy.is_loaded())  # True
print(repr(lazy))        # uses cached value
```

## Caveats
- Accessing `repr(lazy)` will load the value (because `__repr__` triggers loading).
- Only a subset of operations are proxied (`__getattr__`, iteration, length, indexing, repr). Other operations may not behave like the underlying value unless they route through these methods.
