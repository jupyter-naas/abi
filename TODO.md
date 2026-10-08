# TODO

Checked against `feat/standalone-nats-sdk` (PR 1299) on 2026-10-05, from `things-that-must-be-true.md`.

## 200 concurrent sessions on one agent

Done on this branch.

- One provider process accepts 200 live runs, shared by every agent it hosts (`MAX_ACTIVE_RUNS`). The next submit is `AGENT_BUSY`. Distinct `thread_id`s run together.
- A conversation claim is released when discovery no longer lists its owner. The old invocation is marked `OWNER_GONE` and is not replayed. A failed discovery lookup keeps the claim.
- `invoke` and `stream_invoke` send a 300 second deadline unless the caller passes `timeout`. `submit(deadline_seconds=0)` still means no deadline, and the idle watchdog remains 300 seconds.

## Remote agent and remote model from another module

Done on this branch.

- A module calls another module's agent with `get_agent`.
- A module publishes a chat model with `ModelDescriptor` and `expose_model`. Another module calls `(await engine.modules[id].get_chat_model(name)).model`. Inference stays in the publishing process. Tool schemas and tool-call replies travel with the chat request; the caller's agent runs the tools. Streaming is refused. The engine model registry is unchanged.

## Reload one remote module without restarting the engine

Done for standalone modules on this branch. This is not a hot reload of the running process.

`SIGTERM` or `SIGINT` marks the instance `DRAINING`, stops new agent submits, job fetches and model chats, and waits for runs and jobs that already started. A finished run releases its conversation claim. The process then unregisters. The engine and the other modules stay up. A hard kill still ends at lease expiry, and the absent-owner path releases whatever claim is left.

## Zero-downtime module update

Done for standalone modules that share a rollout.

Give every process in the deploy the same `ABI_ROLLOUT_ID`. Set `ABI_ROLLOUT_MODULES` to the module ids that must be up together. An empty list means that module alone. Discovery keeps the current generation ready until each listed module has an initialized instance in the new rollout and its dependencies are satisfied. New calls go to `READY` instances, so they stay on the current generation while the new one is `STAGED`. The cutover marks the previous generation `DRAINING`. Those processes finish in-flight work and then leave. A second replica uses the same rollout id and does not drain its twin. A rollout that never becomes complete does not drain the current generation.

Agent subjects stay instance-addressed. In-flight runs stay on the process that accepted them. They are not moved.

## Health probe

Done on this branch.

`ABI_HEALTH_PORT` opens a standard-library HTTP server (`ABI_HEALTH_HOST`, default `0.0.0.0`). `GET /health` is liveness and stays 200 while the process is up, including `DRAINING` and `STAGED`. `GET /ready` is 200 for `READY`, and for `DISABLED` when discovery is off. Every other status is 503. Leave the port unset and nothing listens. `run_module(..., health_port=)` sets the same port in process.

## Streaming as the way past the 8 MiB NATS limit

Most endpoints are still one request and one reply. The broker `max_payload` stays 8 MiB. A unary call that does not fit is spilled through the overflow host (`docs/adr/20261003_nats-rpc-overflow.md`). Both sides still hold the whole value, up to 256 MiB. Above that, or when the overflow host is full, the call fails with `PAYLOAD_TOO_LARGE`.

Streaming exists for specific large reads and writes: object storage, model token streams, triple-store `query_stream` and `export`, dataset `query_stream` and `write_stream`, vector listing, and event and activity-log `query_stream` (`docs/adr/20261003_nats-streamed-results.md`). Document `find` and vector search stay unary. Agent requests over 128 KiB are rejected, including overflow uploads (`agent_host.py`).

- Move the remaining large reads and writes onto streamed APIs.
- Decide whether ordinary small calls stay unary. Overflow already covers the 8 MiB broker limit for those calls, up to 256 MiB, while still buffering the whole value.

## Add and remove remote modules on the network

With `nats.discovery` enabled, a remote module registers on start and unregisters on shutdown. Lookups skip expired leases. The registry holds at most 256 live instances and one 512 KiB snapshot (`docs/adr/20260923_module-discovery-registry.md`).

Modules loaded from engine config are not in that registry. Their jobs are reached by name (`docs/adr/20261001_nats-jobs.md`). A crash waits out the lease. Standalone shutdown now drains in-flight runs before unregister. Unregister still does not clear a claim whose run did not finish.

- Add and remove engine-configured modules the same way, or document that only standalone SDK modules join and leave at runtime.
- On remove, finish or release that module's runs and claims.
- Raise or split the 256-instance registry cap if the network will be larger than that.
