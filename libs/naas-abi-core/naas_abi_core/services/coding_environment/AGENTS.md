# CodingEnvironment Service - AGENTS.md

## Purpose

Provision and manage coding workspaces through interchangeable providers.

## Files

- `CodingEnvironmentPorts.py`: port, value types, and domain errors.
- `CodingEnvironmentService.py`: service orchestration and event publication.
- `CodingEnvironmentFactory.py`: composition helpers.
- `adapters/primary/`: NATS RPC server.
- `adapters/secondary/`: local/provider implementations and NATS RPC client.
- `tests/`: generic adapter contract tests.

## Port

Implement every abstract method of `ICodingEnvironmentAdapter` in `CodingEnvironmentPorts.py`.
Keep provider dependencies in secondary adapters and preserve typed domain errors.

`list_all_environments()` is the platform admin view (the Nexus System app): every
user's workspaces. Coder pages `GET /workspaces` with the admin token; in-memory and
local-directory list every record; compose returns its one shared editor.
`WorkspaceStatus` carries `owner`, `template` and `created_at` when the backend knows
them (`""`/`None` otherwise); keep filling them in new adapters.

## Service API

`CodingEnvironmentService(adapter)` delegates port operations and publishes domain events.
See its public methods for orchestration beyond the adapter contract.

## Adapters

CoderAdapter, CodeServerComposeAdapter, LocalDirectoryAdapter, InMemoryAdapter, plus `CodingEnvironmentSecondaryAdapterNATSClient`.
Unsupported methods must explicitly raise `NotImplementedError`.

## Factory

Use `CodingEnvironmentFactory` for the existing provider composition helpers.
Engine configuration can also construct adapters, including `nats_rpc`.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/coding_environment/ --import-mode=importlib
```

## Adding a new adapter

1. Implement the complete port with constructor-injected configuration.
2. Add colocated tests and run the generic adapter contract tests.
3. Add the relevant factory/configuration wiring.

## NATS RPC adapters

A `NotImplementedError` in the wrapped adapter crosses NATS as the non-retryable
code `UNIMPLEMENTED` and is raised again as `NotImplementedError` by the client.
`adapters/secondary/CodingEnvironmentSecondaryAdapterNATSClient_broker_test.py` runs
`list_all_environments` against a local `nats-server` (no Docker).

`adapters/primary/coding_environment__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/CodingEnvironmentSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/coding_environment/v1/`.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB (docs/adr/20261003_nats-rpc-overflow.md); above
that, at the overflow host's capacity, or with an older peer, the call fails
with non-retryable `PAYLOAD_TOO_LARGE`. Micro-service error headers raise
instead of becoming an empty success. Overflowed values are held whole in
memory; results that should not be require streaming or a storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
