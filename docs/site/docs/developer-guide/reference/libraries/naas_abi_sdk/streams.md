# `streams`

## What it is
Utilities for handling JetStream stream creation/update attempts made by a module logged in as broker user `module`. Modules are not permitted to create/update streams; such requests can time out. This module converts those timeouts into a clear error explaining what must create the stream.

## Public API
- **Constant**: `REFUSED`
  - Tuple of exception types that represent a broker refusal-by-silence (timeouts) when a module tries to create/update a stream:
    - `nats.errors.TimeoutError`
    - `asyncio.TimeoutError`

- **Exception**: `StreamNotCreated(RuntimeError)`
  - Raised/returned when a required stream is missing/out of date and the module cannot create/update it.

- **Function**: `not_created(kind: str, name: str, cause: BaseException) -> StreamNotCreated`
  - Builds a `StreamNotCreated` error with an operator-focused message that:
    - identifies the stream `kind` and `name`
    - notes the timeout/refusal cause type
    - explains that the engine (not the module) must create required streams

## Configuration/Dependencies
- Depends on:
  - `asyncio`
  - `nats.errors.TimeoutError` (imported as `NATSTimeoutError`)

## Usage
```python
import asyncio
from nats.errors import TimeoutError as NATSTimeoutError

from naas_abi_sdk.streams import REFUSED, not_created

try:
    # call that may time out when broker refuses stream create/update
    raise asyncio.TimeoutError()
except REFUSED as e:
    raise not_created("stream", "JOBS", e)
```

## Caveats
- `not_created(...)` **returns** an exception instance; it does not raise it. Use `raise not_created(...)`.
- Only timeout-like failures are classified as refusal-by-silence via `REFUSED`; other exception types should be handled separately.
