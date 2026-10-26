# cancellation

## What it is
- Stopping a tool call its caller gave up on, on the side that runs it (`call_id` and `CancelToolRequest` in `abi.tool.v1` and `abi.tool_registry.v1`; `docs/adr/20261026_tool-call-cancellation.md`).
- Stdlib only. Used by `ToolHost` (a module's tools) and by core's `EngineToolInvoker` (the engine's).

## Public API
- `new_call_id() -> str`, `valid_call_id(value) -> bool`: ids are 1..128 characters of letters, digits, `_` and `-`.
- `ToolCancellation`: `cancelled`, `cancel()`, `wait(timeout=None) -> bool` (`True` when cancelled; use it in place of `time.sleep`), `raise_if_cancelled()` (raises `ToolCancelled`). Safe from any thread.
- `current_cancellation() -> ToolCancellation`: the cancellation of the tool call running in this context (a handler's thread included); one that is never set outside a call.
- `ActiveCalls`: the running calls by `(identity, call_id)`, for one event loop. `register(identity, call_id) -> Registration` (`CallIdInUse` when it already runs), `cancel(identity, call_id) -> bool` (`False` for another identity's, an unknown or a finished call; a cancel that comes before its call is kept 30 s, 1024 at most). `Registration.on_cancel(callback)` runs at once if already cancelled.

## Usage
```python
async def import_rows(arguments, call):
    try:
        async for batch in source(arguments["url"]):   # cancelled at its next await
            await store(batch)
    finally:
        await release_lock()                           # runs on a cancel too

def slow_report(arguments, call):                      # a thread: cooperate
    for page in range(100):
        if call.cancellation.wait(0.1):                # sleeps, wakes on a cancel
            return None
        render(page)
```

## Caveats
- A synchronous handler that never looks at its cancellation runs on, and keeps its slot, after the caller is answered.
- Only the identity that started a call can cancel it; a cancel is best effort and is not a rollback.
- A caller whose process dies sends nothing: the deadline (at most 300 s) bounds the call.
