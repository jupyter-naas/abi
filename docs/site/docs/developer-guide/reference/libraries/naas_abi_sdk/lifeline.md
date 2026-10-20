# lifeline

## What it is
Utilities to stop (or log about) a process when a dependent NATS connection closes permanently. Designed to avoid a “healthy but non-functional” process after `nats-py` gives up reconnecting.

## Public API
- `HARD_EXIT_SECONDS: float`
  - Grace period for shutdown before forcing process exit (default `20.0` seconds).
- `stop_process() -> None`
  - Sends `SIGTERM` to the current process and forces `os._exit(1)` if it hasn’t stopped within `HARD_EXIT_SECONDS`.
- `exit_on_connection_loss(stop: Callable[[], None] | None = stop_process) -> Callable[[], None]`
  - Configures what happens when a watched connection is reported lost:
    - `stop` callable: invoked once on first loss.
    - `None`: only logs an error; does not stop the process.
  - Returns `restore()` to revert to the previous behavior.
- `stopping_on_loss(stop: Callable[[], None] | None = stop_process) -> AsyncIterator[None]`
  - Async context manager that applies `exit_on_connection_loss(stop)` for the duration of the `async with` block.
- `connection_lost(name: str) -> None`
  - Reports that connection `name` closed unexpectedly:
    - Logs `error` if no stop function is configured.
    - Logs `critical` and calls the configured stop function once (first loss only).
- `class Lifeline`
  - Per-connection helper intended to be used as the NATS client `closed_cb`.
  - `__init__(name: str)`
    - `name`: connection identifier used in logs.
    - `closing`: boolean flag (default `False`) to distinguish intentional closes.
  - `closed() -> None` (async)
    - Should be used as `closed_cb`; triggers `connection_lost(name)` unless `closing` is `True`.
  - `close(nc: Any) -> None` (async)
    - Intentionally closes `nc` (if not already closed) by setting `closing=True` then awaiting `nc.close()`.

## Configuration/Dependencies
- Uses standard library modules: `logging`, `os`, `signal`, `threading`, `contextlib`.
- Expects a NATS-like client object in `Lifeline.close(nc)` with:
  - `nc.is_closed` boolean attribute
  - `await nc.close()` coroutine method

## Usage
```python
import asyncio
from naas_abi_sdk.lifeline import Lifeline, exit_on_connection_loss

class FakeNC:
    def __init__(self):
        self.is_closed = False
    async def close(self):
        self.is_closed = True

async def main():
    # Configure process stop behavior on first unexpected connection loss.
    restore = exit_on_connection_loss()  # default uses stop_process()

    life = Lifeline("main-nats")
    nc = FakeNC()

    # Intentional close: should not be treated as a loss.
    await life.close(nc)
    await life.closed()  # no-op due to life.closing == True

    restore()  # revert to previous behavior

asyncio.run(main())
```

## Caveats
- `connection_lost()` only calls the configured stop function once per configuration; additional losses only log.
- `stop_process()` sends `SIGTERM` and may forcefully exit with `os._exit(1)` after `HARD_EXIT_SECONDS`, bypassing normal cleanup.
- If the underlying NATS client closes first (already `is_closed`), `Lifeline.close()` will not set `closing=True`; a later `closed_cb` may still be treated as a loss (as noted in the docstring).
