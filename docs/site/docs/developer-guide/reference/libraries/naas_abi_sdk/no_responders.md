# `no_responders`

## What it is
Utilities for safely retrying NATS requests that temporarily fail with **“no responders”** during engine handover/restart. Retries are only applied to subjects served by the *current serving engine* (queue group), where re-sending is safe.

## Public API
- `engine_served(subject: str) -> bool`
  - Returns `True` when the given NATS `subject` is expected to be served by the serving engine via a queue group.
  - Rules:
    - `abi.svc.*` → served
    - `abi.discovery.*` → served unless it contains `.presence.`

- `transfer_open(subject: str) -> bool`
  - Returns `True` if `subject` ends with `.transfer.open`.
  - Used to identify transfer “open” calls, which go to the serving engine queue group.

- `async request(nc, subject, payload, *, headers, timeout, retry_seconds=RETRY_SECONDS) -> Any`
  - Wrapper around `nc.request(...)` that retries on `nats.errors.NoRespondersError`:
    - Retries only if `engine_served(subject)` is `True`.
    - Retries up to `retry_seconds`, but stops before the caller’s `timeout` (deadline margin is applied).
    - Uses exponential backoff from `_FIRST_DELAY_SECONDS` up to `_MAX_DELAY_SECONDS`.
  - Re-raises `NoRespondersError` if the retry window expires.

## Configuration/Dependencies
- Depends on:
  - `asyncio`
  - `nats.errors.NoRespondersError`
- Constants:
  - `RETRY_SECONDS = 5.0` (default retry window)
  - Backoff timing:
    - `_FIRST_DELAY_SECONDS = 0.05`
    - `_MAX_DELAY_SECONDS = 0.5`
  - `_DEADLINE_MARGIN_SECONDS = 0.5` (stops retrying slightly before `timeout`)

## Usage
```python
import asyncio
from naas_abi_sdk.no_responders import request

async def main(nc):
    msg = await request(
        nc,
        "abi.svc.example.ping",
        b"ping",
        headers={},
        timeout=2.0,
        retry_seconds=5.0,
    )
    print(msg.data)

# asyncio.run(main(nc))  # nc must be a connected NATS client with .request()
```

## Caveats
- Retries happen **only** for subjects classified by `engine_served(...)`. Other subjects are requested once (a “no responders” there is treated as definitive).
- The retry window is capped by `timeout - _DEADLINE_MARGIN_SECONDS`; if `timeout` is too small, retries may effectively be disabled.
