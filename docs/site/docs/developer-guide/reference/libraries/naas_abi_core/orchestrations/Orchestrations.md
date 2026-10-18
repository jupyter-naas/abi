# Orchestrations

## What it is
- A placeholder `Orchestrations` class intended to provide orchestration-related functionality.
- Currently unimplemented.

## Public API
- `class Orchestrations`
  - `@classmethod New(cls) -> Orchestrations`
    - Intended factory/constructor method.
    - **Current behavior:** always raises `NotImplementedError`.

## Configuration/Dependencies
- None.

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
