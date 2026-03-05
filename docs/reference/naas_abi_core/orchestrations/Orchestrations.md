# `Orchestrations`

## What it is
- A placeholder class intended to represent orchestration-related functionality.
- Currently unimplemented.

## Public API
- `class Orchestrations`
  - `@classmethod New(cls) -> Orchestrations`
    - Intended to create/return a new `Orchestrations` instance.
    - **Current behavior:** always raises `NotImplementedError("This method is not implemented")`.

## Configuration/Dependencies
- No configuration, external dependencies, or imports.

## Usage
```python
from naas_abi_core.orchestrations.Orchestrations import Orchestrations

try:
    Orchestrations.New()
except NotImplementedError as e:
    print(e)
```

## Caveats
- `Orchestrations.New()` is not implemented and will always raise `NotImplementedError`.
