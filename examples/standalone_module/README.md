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
It exercises 101 RPC endpoints across 12 services, plus publish, publish_many, subscribe,
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
