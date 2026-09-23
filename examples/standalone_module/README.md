# Standalone engine-service module

Run from this directory:

```sh
make demo
```

Prerequisites: the repository's UV development environment (`make deps` at the repo
root), plus `nats-server` on PATH with JetStream support. No Docker or external
API credentials are required. The runner builds the proto and SDK wheels, installs
them into a fresh worker virtualenv, and starts a broker and engine, then isolated SDK worker processes:

1. A loopback-only NATS/JetStream broker on a temporary port.
2. A real ABI Engine with all remotely supported services loaded.
3. `user_module.py`, exercising the Python service facades without protobuf imports.
4. `worker.py`, exercising every low-level protobuf endpoint.

The worker runs with Python isolation enabled and asserts ABI core is not installed.
It exercises 117 RPC endpoints across 14 services, plus publish, publish_many, subscribe,
enqueue, and dequeue against the engine. Object storage includes create, read,
list, overwrite/update, metadata, recursive listing, delete, and listing after
removal. Other mutable services have equivalent state checks; append-only logs
verify reads/cursors instead of inventing unsupported deletion operations.

Results print per service and are written to `report.json` with process IDs,
installed distributions, missing operations, and unsupported endpoints. Any failed
assertion, missing endpoint exercise, or missing persisted email exits nonzero.
A successful run has no missing operations and only four worker packages:
`naas-abi-sdk`, `naas-abi-proto`, `nats-py`, and `protobuf`.

Engine data and credentials live in a temporary directory and are removed on exit;
processes are stopped even on failure. The module receives only an issued token,
not the signing key. Only test data is used. Coding environments and source control
use the engine's in-memory adapters; email uses its filesystem adapter. The runner
independently checks that email persisted. No external email is sent.

Limitations are explicit: object streaming, model objects and ontology execution
have no remote contract. Discovery and agent invocation are exercised separately
from the service-endpoint coverage worker. The triple-store
`handle_view_event` endpoint is exercised and its expected `NOT_SUPPORTED` reply
is recorded separately; it is an internal adapter callback, not an engine operation.
Remote `shutdown`/`close` endpoints are exercised only because this engine is
throwaway. Do not run this full exercise against a shared production engine.

The server-only `engine_host` module requests services through the normal engine
loader. It is not installed in the worker. This demo does not depend on or implement
the proposed workload service.

## Module lifecycle and internal domain traffic

`worker.py` now exports `ABIModule(BaseModule)` with nested `Configuration`, declared
`ModuleDependencies`, and load/initialize/unload hooks. `run_module` owns its
transport and lifecycle, and business code uses `self.engine.services` in `user_module.py`; the protocol
coverage worker uses `self.engine.rpc`.
`report.json` includes the module name and the completed lifecycle sequence.

The engine configures hot cache through `keyvalue` and cold cache through
`object_storage`. A broker observer verifies the nested KV, object-storage, and
event-log subjects and records them under `cross_domain_subjects`. This includes
same-process engine calls through the network. The shared asyncio worker pool is
limited to one thread during the exercise to catch shared-pool starvation;
primaries dispatch to independent worker pools. The SDK also exercises tier 0.

See the SDK README for the migration pattern and its limits. This preserves ABI
module structure, not automatic portability of framework-specific components.

Document service CRUD, version checks, collection operations, queries and count
are included in the SDK-only worker (117 RPC operations total). The worker still
installs only four packages; LangGraph is an optional SDK extra.

For the separate LangGraph persistence regression, with the development runtime,
SDK source installed and native `nats-server` available:

```sh
uv run --no-sync pytest examples/standalone_module/checkpoint_integration_test.py -q
```

It pauses a real graph at an interrupt, starts another Python interpreter to
resume from the document service, and checks history and module/agent isolation.
This proves shared persistence across processes, not remote agent invocation.

`user_module.py` demonstrates explicit component injection and task-scoped
`current_module()` access. Its result is recorded under `ergonomic_module`.

## Discovery failure and recovery

The host enables discovery with a two-second lease for the demo. The wheel-only
`discovery_demo.py` starts a consumer before its provider, verifies dependency
startup gating and agent descriptors, kills the provider, waits for lease expiry,
then starts a replacement. The consumer observes recovery with a different
instance identity. `report.json` records the distinct process IDs under discovery.
The consumer also invokes the remote agent, re-submits the same invocation ID
without another execution, consumes SSE events, cancels a run, and reads completed
status through the replacement provider. The base worker still has four packages.

`agent_integration_test.py` additionally hosts real core Agent and IntentAgent
instances with deterministic local model/embedding doubles. It verifies the
compatibility adapter, SSE format, invalid-token rejection and an async LangGraph
parent invoking the remote agent as a tool. No external LLM credentials are used.

### Remote model example

`model_module.py` extends SDK BaseModule and declares only `model_registry`. It
resolves a chat model and embeddings from the engine, invokes/streams through
LangChain proxies, and records its distinct process ID. `make demo-sdk` runs it
in a second core-free environment with the optional `[models]` dependencies.
The engine hosts deterministic models, so no LLM API keys or external model
servers are required. The raw worker also exercises all seven model RPCs,
bringing service coverage to 117 endpoints across 14 services, plus the bus.

`model_integration_test.py` additionally verifies actual core Agent/IntentAgent
use, tool execution, streaming tool arguments, structured output, the core
registry bridge, invalid tokens, caller-bound stream handles, expiry, cleanup,
deadlines and sanitized provider errors over a real local NATS broker.
