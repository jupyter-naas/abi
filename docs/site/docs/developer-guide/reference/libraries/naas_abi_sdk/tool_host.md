# ToolHost

## What it is
- Serves a module's tools on instance-addressed NATS subjects: `abi.mod.<project>.<instance>.tool.<name>.invoke`. One unary `InvokeToolRequest` per call, one attempt, never replayed.
- Needs the optional `jsonschema` (`pip install naas-abi-sdk[tools]`); `run_module` starts it when the module declares tools, after `on_initialized`, and drains it with the module.

## Public API
- `ToolHost(session, tools: dict[str, tuple[ToolDescriptor, handler]], authorize, *, max_concurrency=64, user_callers={"api", "engine"})`
  - Checks every declared schema at construction (a bad schema fails before the module is ready).
  - `async start()`, `async drain(timeout)` (no new call, the calls received finish), `async close()`.
  - `async respond(name, data, headers, *, uploaded=False) -> InvokeToolResponse`: one call as its reply; never raises.

## What a call goes through
1. Size limits (request 512 KiB; an overflow upload is refused).
2. Discovery's `authorize_tool`: the provider's lease, the declared tool, a READY instance, and a caller token bound to this instance. It returns the verified caller identity.
3. The module's `authorize_tool(name, caller)` hook. Default: the engine's own processes (`api`, `engine`, `dagster`) only. It replaces the default; only `True` allows.
4. A named end user (`context.principal_id`) or workspace (`context.workspace_id`) is honoured only from the callers in `user_callers` (`api` and `engine`). Any other caller that sets either, `dagster` included, gets `PERMISSION_DENIED`.
5. The arguments are validated against the tool's input schema and the configuration against its descriptor (unknown or missing required key): `INVALID_ARGUMENT`, before the handler runs.
6. The handler runs under the caller's deadline (`context.timeout_ms`, at most 300 s, 60 s when unset). A synchronous handler runs on a thread; its deadline stops the wait, not the thread.
7. The result must be JSON (finite numbers), at most 512 KiB, and match the output schema if declared.

Errors are a stable code and a message with no detail of the handler's failure: `UNAUTHENTICATED`, `PERMISSION_DENIED`, `TOOL_NOT_FOUND`, `MODULE_UNAVAILABLE`, `INVALID_ARGUMENT`, `PAYLOAD_TOO_LARGE`, `DEADLINE_EXCEEDED`, `TOOL_ERROR`.
