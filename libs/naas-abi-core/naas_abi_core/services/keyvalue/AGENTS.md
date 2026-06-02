# KeyValue Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/keyvalue/`. Canonical reference for agents.

## Purpose

Bytes-in / bytes-out key-value store with optional TTL and atomic compare-and-set / compare-and-delete primitives. Publishes events for set / delete / error via the event service.

## Files

| File | Role |
|---|---|
| `KeyValuePorts.py` | `IKeyValueAdapter`, `KVNotFoundError` |
| `KeyValueService.py` | Public service (inherits `ServiceBase`) |
| `adapters/secondary/PythonAdapter.py` | In-memory dict, optional SQLite persistence |
| `adapters/secondary/RedisAdapter.py` | Redis backend (requires `redis` package) |
| `tests/` | Service + generic adapter contract tests |
| `ontologies/` | Event classes |

## Port (`KeyValuePorts.py`)

```python
class IKeyValueAdapter:
    def get(key: str) -> bytes                                       # raises KVNotFoundError
    def set(key: str, value: bytes, ttl: int | None = None) -> None
    def set_if_not_exists(key: str, value: bytes, ttl=None) -> bool
    def delete(key: str) -> None                                     # raises KVNotFoundError
    def delete_if_value_matches(key: str, value: bytes) -> bool
    def exists(key: str) -> bool
```

Exception: `KVNotFoundError`.

## Service API (`KeyValueService.py`)

```python
get(key) -> bytes                                              # raises KVNotFoundError
set(key, value, ttl=None)                                      # → KeyValueSet on success, KeyValueError on failure
set_if_not_exists(key, value, ttl=None) -> bool                # atomic; event only if written
delete(key)                                                    # → KeyValueDeleted; raises KVNotFoundError
delete_if_value_matches(key, value) -> bool                    # atomic; event only if matched
exists(key) -> bool
```

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

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/KeyValueService_events_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/keyvalue/tests/kv__secondary_adapter__generic_test.py
```

## Adding a new adapter

1. Implement every method of `IKeyValueAdapter` in `adapters/secondary/<Name>Adapter.py`.
2. Honour the atomicity contract for `set_if_not_exists` and `delete_if_value_matches` — these are the primitives the rest of the codebase relies on for compare-and-swap.
3. Run the generic contract tests against the new adapter (see `tests/kv__secondary_adapter__generic_test.py`).
