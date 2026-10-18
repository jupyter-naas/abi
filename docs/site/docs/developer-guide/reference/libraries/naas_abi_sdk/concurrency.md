# ConcurrentCalls

## What it is
A small asyncio utility to run subscription message handlers concurrently with a bounded parallelism limit. It wraps a single-message callback so each incoming message is executed in its own task, up to `limit` concurrent calls.

## Public API
- `DEFAULT_LIMIT: int`  
  Default maximum number of concurrent calls (`64`).

- `Callback = Callable[[Any], Awaitable[None]]`  
  Type alias for an async message handler.

- `class ConcurrentCalls(limit: int = DEFAULT_LIMIT)`  
  Concurrency controller.
  - `limit: int` — configured maximum concurrency.
  - `in_flight: int` — number of calls received and not finished yet (includes those waiting for a slot).

  Methods:
  - `callback(cb: Callback) -> Callback`  
    Wraps `cb` as a subscription callback so each message runs in its own `asyncio.Task`, constrained by `limit`.
  - `idle() -> Awaitable[None]`  
    Waits until every call received so far has finished (including those still waiting to acquire a slot).
  - `cancel() -> Awaitable[None]`  
    Cancels currently running tasks created by this instance and waits for them to finish (collecting exceptions).

## Configuration/Dependencies
- Requires `asyncio`.
- Uses `logging`:
  - Exceptions raised by `cb` are caught and logged at warning level; they are not re-raised to the caller.

## Usage
```python
import asyncio
from naas_abi_sdk.concurrency import ConcurrentCalls

async def handler(msg):
    await asyncio.sleep(0.1)
    print("handled:", msg)

async def main():
    cc = ConcurrentCalls(limit=2)
    receive = cc.callback(handler)

    # Simulate incoming messages
    for i in range(5):
        await receive(i)

    # Wait for all scheduled work to complete
    await cc.idle()

asyncio.run(main())
```

## Caveats
- `limit` must be `>= 1` or `ValueError` is raised.
- Handler exceptions are swallowed (logged) and do not propagate.
- `cancel()` only cancels tasks that have been created (i.e., messages that have already acquired a slot and started `_run`). Messages still waiting to acquire a slot are not represented as tasks.
