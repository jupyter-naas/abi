# Standalone engine-service module

Run from this directory:

```sh
make demo
```

Prerequisites: the repository's UV development environment (`make deps` at the repo
root), plus `nats-server` on PATH with JetStream support. No Docker or external
API credentials are required. The runner builds the proto and SDK wheels, installs
them into a fresh worker virtualenv, and starts three separate processes:

1. A loopback-only NATS/JetStream broker on a temporary port.
2. A real ABI Engine with all remotely supported services loaded.
3. `worker.py`, importing only the standalone packages and standard library.

The worker runs with Python isolation enabled and asserts ABI core is not installed.
It exercises 109 RPC endpoints across 13 services, plus publish, publish_many, subscribe,
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

Limitations are explicit: object streaming, model objects, agent/ontology execution,
and registration/heartbeats have no v1 remote contract. The triple-store
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
transport and lifecycle, and business code uses `self.engine.services`.
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
are included in the SDK-only worker (109 RPC operations total). The worker still
installs only four packages; LangGraph is an optional SDK extra.

For the separate LangGraph persistence regression, with the development runtime,
SDK source installed and native `nats-server` available:

```sh
uv run --no-sync pytest examples/standalone_module/checkpoint_integration_test.py -q
```

It pauses a real graph at an interrupt, starts another Python interpreter to
resume from the document service, and checks history and module/agent isolation.
This proves shared persistence across processes, not remote agent invocation.
