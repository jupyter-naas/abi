# Activity Log Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/activity_log/`. Canonical reference for agents.

## Purpose

Thin domain wrapper that records `ActivityEvent`s per actor and supports filtered replay. **Recording failures are swallowed and logged** — activity logging must never break the call site that produced the event.

## Files

```
activity_log/
├── ActivityLogFactory.py
├── ActivityLogPort.py             # IActivityLogAdapter, IActivityLogDomain, DTOs
├── ActivityLogService.py          # public service
├── adapters/secondary/
│   └── ActivityLogSqliteAdapter.py
└── tests/
    └── activity_log__secondary_adapter__generic_test.py   # generic contract tests
```

## Port (`ActivityLogPort.py`)

```python
class IActivityLogAdapter:
    def record(event: ActivityEvent) -> None
    def query(actor_id: str, query: ActivityLogQuery | None = None) -> list[ActivityEvent]
    def list_actors() -> list[str]
    def shutdown() -> None

class IActivityLogDomain:    # same surface
    ...
```

## Service API (`ActivityLogService.py`)

```python
record(event)                            # swallows exceptions, logs warning
query(actor_id, query=None) -> list[ActivityEvent]
list_actors() -> list[str]
shutdown()                               # close adapter resources
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `ActivityLogSqliteAdapter` | One SQLite DB file **per actor**, WAL mode, per-actor locking, LRU connection cache |

## Factory (`ActivityLogFactory.py`)

```python
ActivityLogFactory.ActivityLogServiceSqlite(
    data_dir: str,
    synchronous: str = "NORMAL",
    journal_mode: str = "WAL",
    max_open_connections: int = 200,
    busy_timeout_ms: int = 5000,
) -> ActivityLogService
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/ActivityLogPort_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/ActivityLogService_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/adapters/secondary/ActivityLogSqliteAdapter_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/activity_log/tests/activity_log__secondary_adapter__generic_test.py
```

## Adding a new adapter

1. Implement `IActivityLogAdapter` in `adapters/secondary/<Name>Adapter.py`.
2. Keep `record` **fail-open** — never raise out of the adapter into the service.
3. Run the generic contract tests against it (`tests/activity_log__secondary_adapter__generic_test.py`).
4. Add a `ActivityLogFactory.<Name>(...)` builder if there's a sensible default config.

## NATS RPC adapters

`adapters/primary/activity_log__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/ActivityLogSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/activity_log/v1/`.

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
