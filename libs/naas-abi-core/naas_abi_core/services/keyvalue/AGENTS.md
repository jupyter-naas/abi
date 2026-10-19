# KeyValue Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/keyvalue/`. Canonical reference for agents.

## Purpose

Bytes-in / bytes-out key-value store with optional TTL and atomic compare-and-set / compare-and-delete primitives. Publishes events for set / delete / error via the event service.

## Files

| File | Role |
|---|---|
| `KeyValuePorts.py` | `IKeyValueAdapter`, `KVNotFoundError`, `KVLockTimeoutError` |
| `KeyValueService.py` | Public service (inherits `ServiceBase`) |
| `adapters/secondary/PythonAdapter.py` | In-memory dict, optional SQLite persistence |
| `adapters/secondary/RedisAdapter.py` | Redis backend (requires `redis` package) |
| `tests/` | Service + generic adapter contract tests |
| `ontologies/` | Event classes |
| `iam_catalog.py` | IAM action catalog |

## Port (`KeyValuePorts.py`)

```python
class IKeyValueAdapter:
    def get(key: str) -> bytes                                       # raises KVNotFoundError
    def set(key: str, value: bytes, ttl: int | None = None) -> None
    def set_if_not_exists(key: str, value: bytes, ttl=None) -> bool
    def delete(key: str) -> None                                     # raises KVNotFoundError
    def delete_if_value_matches(key: str, value: bytes) -> bool
    def exists(key: str) -> bool
    def list_keys(prefix="", *, limit=100, after=None) -> KVKeyPage  # live keys, ascending
    def get_ttl(key: str) -> int | None                              # seconds left; None: no expiry; raises KVNotFoundError
```

`KVKeyPage(keys, next_after)`: pass `next_after` back as `after` (strictly after it).
`limit` is 1..`MAX_KEYS_PER_PAGE` (1000); `paginate_keys` pages a full enumeration for
adapters without an ordered index. PythonAdapter pages in SQL; RedisAdapter SCANs the
prefix (glob-escaped), so it is O(keys under the prefix): for administration.

Exceptions: `KVNotFoundError`, `KVLockTimeoutError` (from `KeyValueService.lock`).

## Service API (`KeyValueService.py`)

```python
get(key) -> bytes                                              # raises KVNotFoundError
set(key, value, ttl=None)                                      # → KeyValueSet on success, KeyValueError on failure
set_if_not_exists(key, value, ttl=None) -> bool                # atomic; event only if written
delete(key)                                                    # → KeyValueDeleted; raises KVNotFoundError
delete_if_value_matches(key, value) -> bool                    # atomic; event only if matched
exists(key) -> bool
list_keys(prefix="", limit=100, after=None) -> KVKeyPage       # validates limit (ValueError)
get_ttl(key) -> int | None                                     # raises KVNotFoundError
lock(key, ttl=30, timeout=10.0, retry_delay=0.05)              # context manager; SET NX + CAD
```

`lock` is a service-level composition of the adapter primitives, not a new adapter method:

```python
with kv.lock("lock:object:finance/billing/graph.ttl", ttl=60, timeout=30):
    ...
```

- Acquire: `set_if_not_exists(key, random_token, ttl=ttl)`
- Release: `delete_if_value_matches(key, token)` so only the holder can unlock
- `ttl` must outlast the critical section (crash recovery)
- Cross-process only if the adapter is shared (Redis, or PythonAdapter with the same SQLite `persistence_path`)
- The Jena TDB2 adapter currently inlines the same SET NX / CAD loop; new callers should use `lock()` instead.

## Available Adapters

| Adapter | Backend |
|---|---|
| `PythonAdapter` | In-memory dict; can persist to SQLite |
| `RedisAdapter` | Redis (`redis_url=` arg) |

## Instantiation

No factory file — wire directly:

```python
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import PythonAdapter
from naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter import RedisAdapter

kv = KeyValueService(PythonAdapter())
kv = KeyValueService(RedisAdapter(redis_url="redis://localhost:6379/0"))
```

## Authorization

Every operation is checked in the domain service against IAM (RFC
[§5, §6.4](../../../../../docs/specs/rfcs/20261013_identity-and-authorization.md)),
for the caller of the current `CallContext`, so in process and over NATS answer
the same. The catalog is `iam_catalog.py`, registered by the serving engine at
boot. A caller who cannot see a resource gets `KVNotFoundError` (`KV_NOT_FOUND`; `exists` is False); one who can see it but not
act gets `PermissionDeniedError` (`PERMISSION_DENIED`). A service not wired into
an engine with IAM (a library use, a NATS facade whose server checks) does not
check. The contract test is `KeyValueService_authorization_test.py`: no policy, granted and denied
principals, in process and over NATS.

* Each key is `key/<key>` (opaque), placed by key prefix.
* `list_keys` pages after filtering: it scans only the key prefixes the
  caller's Allows name (`ResourceGuard.id_prefixes`), then drops what a Deny or
  a placement excludes.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/KeyValueService_events_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/KeyValueService_lock_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/kv__secondary_adapter__generic_test.py
```

## Adding a new adapter

1. Implement every method of `IKeyValueAdapter` in `adapters/secondary/<Name>Adapter.py`.
2. Honour the atomicity contract for `set_if_not_exists` and `delete_if_value_matches` — these are the primitives the rest of the codebase relies on for compare-and-swap.
3. Subclass `tests/kv__secondary_adapter__generic_test.py::GenericKVSecondaryAdapterTest` (fixtures `adapter_class`, `adapter`) in the adapter's test: it covers listing, paging, expiry and TTL. PythonAdapter runs it in memory and on SQLite, RedisAdapter on `fakeredis` (and on a real server with `REDIS_URL`), the NATS client over a live `nats-server`.

## NATS RPC adapters

`adapters/primary/keyvalue__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/KeyValueSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/keyvalue/v1/`.

Every primary runs its domain call as the verified caller: it authenticates the
request with `nats_rpc.authenticate_request` (built on `engine/nats_identity.py`,
it answers a refusal itself) and hands that `CallContext`
(`engine/call_context.py`) to its dispatcher. The actor is the
token's identity; the user it acts for is named by the token itself: a
delegated token (`abi:delegated:agent`, `act` the acting service, `sub` the user)
made by IAM's token exchange, never a header (the old `Abi-On-Behalf-Of` header is
refused); trace and target workspace come from the request's `context`. Never read identity from request fields
(`principal_id` and `tenant_id` are reserved). Clients of `api` and `engine` send a
delegation for the current call's user, and the call's trace and workspace. Nothing authorizes on it yet.

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
