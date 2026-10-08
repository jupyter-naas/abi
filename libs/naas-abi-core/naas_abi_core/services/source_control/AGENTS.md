# SourceControl Service - AGENTS.md

## Purpose

Manage repositories, files, branches, proposals, reviews, and checks through interchangeable providers.

## Files

- `SourceControlPorts.py`: port, value types, and domain errors.
- `SourceControlService.py`: service orchestration and event publication.
- `SourceControlFactory.py`: composition helpers.
- `adapters/primary/`: NATS RPC server.
- `adapters/secondary/`: local/provider implementations and NATS RPC client.
- `tests/`: generic adapter contract tests.

## Port

Implement every abstract method of `ISourceControlAdapter` in `SourceControlPorts.py`.
Keep provider dependencies in secondary adapters and preserve typed domain errors.

## Service API

`SourceControlService(adapter)` delegates port operations and publishes domain events.
See its public methods for orchestration beyond the adapter contract.

## Adapters

ForgejoAdapter, LocalGitAdapter, InMemoryAdapter, plus `SourceControlSecondaryAdapterNATSClient`.
Unsupported methods must explicitly raise `NotImplementedError`.

## Factory

Use `SourceControlFactory` for the existing provider composition helpers.
Engine configuration can also construct adapters, including `nats_rpc`.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/source_control/ --import-mode=importlib
```

## Adding a new adapter

1. Implement the complete port with constructor-injected configuration.
2. Add colocated tests and run the generic adapter contract tests.
3. Add the relevant factory/configuration wiring.

## NATS RPC adapters

`adapters/primary/source_control__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/SourceControlSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/source_control/v1/`.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
The maximum message size is 8 MiB (or a lower broker limit); oversized replies
return non-retryable `PAYLOAD_TOO_LARGE`, and micro-service error headers raise
instead of becoming an empty success. Larger results require streaming or a
storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
