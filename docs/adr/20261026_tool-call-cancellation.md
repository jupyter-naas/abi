# Tool calls are cancelled on both sides

## Status

Accepted. Extends `docs/adr/20261022_remote-module-tools.md` and
`docs/adr/20261023_remote-callers-run-engine-tools.md`, which left a call that its caller
gave up running to its end.

## Date

2026-10-26

## Context

A tool call crosses a process boundary in two places: the engine calls a tool an SDK
module serves (`abi.tool.v1`, `docs/adr/20261022_remote-module-tools.md`), and a module
calls a tool the engine holds (`abi.tool_registry.v1.invoke_tool`,
`docs/adr/20261023_remote-callers-run-engine-tools.md`). In both, the caller could stop
waiting (its own task was cancelled, its wait ran out) but the callee went on: the
module's handler or the engine's tool ran to its end, with its side effects, its slot
and its cost, and only the *wait* ended at the deadline. A synchronous handler or tool
runs on a thread, and Python cannot interrupt a thread.

The question: can a call really be cancelled, so that the tool stops on the side that runs
it as well as on the side that waits?

## Decision

**A call can be named, and a named call can be cancelled, by the identity that started it.**

- `InvokeToolRequest` (both contracts) has `call_id` (field 7; `abi.tool.v1` reserves 6,
  which `abi.tool_registry.v1` uses for `secret_refs`): 1..128 characters of letters, digits,
  `_` and `-`, unique among the identity's running calls. The SDK clients generate one for
  every call (`ModuleToolClient.invoke`, `ToolRegistryService.invoke`). Empty: the call
  cannot be cancelled and runs to its deadline, as before.
- Each contract has a `CancelToolRequest` / `CancelToolResponse(cancelled)`: for a module
  tool on `abi.mod.<project>.<instance>.tool.<name>.cancel` (same instance as the call,
  same token binding), for an engine tool the operation `abi.svc.tool_registry.v1.cancel_tool`.
  No new broker permission is needed: modules already publish to `abi.svc.>` and to
  `abi.mod.>`.
- **Only the identity that started a call can cancel it.** The module takes the identity
  from discovery's check of the token (`authorize_tool`, the same call that authenticates a
  run; the module's own hook, which decides who may *run* a tool, is not asked), the
  engine from the verified token. The call is keyed by `(identity, call_id)`: an
  unknown id, another identity's id and a finished call all answer `cancelled = false`
  with no error, so a cancel tells nothing about other callers' calls. A guessed id is
  useless without the identity, and ids are random (the clients use UUIDs).
- **A cancel that arrives before its call is registered is kept** (30 seconds, 1024
  entries, per identity and id): the call is still being authorized when a fast caller
  gives up. When the call registers, it is cancelled at once and its handler never runs.
- **How the callee stops** is the same on both sides (`naas_abi_sdk.cancellation`):
  - An **async handler or coroutine tool** runs as a task. A cancel, its deadline, or the
    caller of the host going away cancels the task: it stops at its next `await`, its `finally`
    blocks run, and the caller is answered `CANCELLED` (or `DEADLINE_EXCEEDED`) once it has
    unwound, for at most 5 seconds.
  - A **synchronous handler or tool** cannot be interrupted. It gets a `ToolCancellation`
    (`call.cancellation` in a module handler, `current_cancellation()` anywhere in the call,
    thread included): `cancelled`, `wait(seconds)` in place of `time.sleep`, and
    `raise_if_cancelled()`. A handler that polls it stops; one that does not runs to its end.
    Either way the caller is answered at once, and the call keeps its slot (the engine's
    `max_concurrent`) until the thread returns.
  - The deadline now does the same as a cancel: it used to stop the wait only.
- **The caller tells the callee when it gives up**, best effort and shielded from its own
  cancellation: a cancelled task, or a wait that ran out, sends the cancel (3 seconds) before
  the exception goes on. A reply from the callee (including an error) never triggers one.
  A cancel that cannot be delivered (the callee is gone, an older module without the subject)
  is logged at debug level and does not change what the caller sees.
- **It composes.** An agent in the engine calls a module's tool; the module's async
  handler calls an engine tool: cancelling the first cancels the handler, whose pending
  `registry.invoke` cancels the engine's tool in turn.

On the engine, `EngineToolInvoker` runs each call as a task of its own (the registry
lookup, validation, secret resolution and the tool run on worker threads or, for a coroutine
tool, on the loop), tracks its threads, and releases the slot when the task and every thread
have ended. Activity records a cancelled call with outcome `cancelled`.

## Consequences

- A coroutine tool, or a module's async handler, is really stopped by a cancel or a
  deadline, on the side that runs it. Tools that call out (HTTP, a database) should be
  coroutines for this reason.
- A synchronous tool is stopped only if it cooperates. The alternative, running synchronous
  tools in a killable subprocess, was rejected: the tool, its configuration and the
  credentials it holds live in the engine process, and a subprocess would need them sent or
  re-resolved, and a startup cost per call.
- Dying callers are not detected: if the caller's process or connection is lost, nobody sends
  the cancel, and the callee runs to its deadline (at most 300 seconds). A heartbeat or a
  broker-side disconnect hook is the next step.
- A cancel is best effort: it may arrive after the tool has finished, or a tool may have
  done part of its side effects. Cancelling is not rollback.
- The identity binds the cancel, not the connection: any process holding the same identity
  (every engine process shares `engine`, `api`, ... ) can cancel another's call if it knows
  the id. Ids are not published; a module's identity is its own.
- The wire change is additive (new fields and messages, a new subject): an old engine or
  module ignores `call_id` and never answers the cancel subject.
- The engine's `invoke_tool` answers `CANCELLED` for a cancelled call; nobody reads it
  except in the activity log and a caller that cancelled from another connection.
- Cancelling a call from another SDK module's identity (a stranger) is covered by tests on a
  real broker, with the real call id, in both directions.
