# KeyValuePorts

## What it is
Defines the key-value storage *port* (interface) used by the service layer, plus helper types and functions for key listing pagination and common key-value related exceptions.

## Public API

### Constants
- `MAX_KEYS_PER_PAGE: int = 1000`
  - Upper bound for a single `list_keys` page.

### Exceptions
- `class KVNotFoundError(Exception)`
  - Indicates a key was not found (typically raised by adapter implementations).

- `class KVLockTimeoutError(Exception)`
  - Raised when a lock acquisition times out (used by higher-level service code).
  - Attributes:
    - `key: str`
    - `attempts: int`
    - `timeout: float`

### Data structures
- `@dataclass(frozen=True) class KVKeyPage`
  - A page of keys in ascending order.
  - Fields:
    - `keys: tuple[str, ...]`
    - `next_after: str | None` — continuation token (the last key in the page) or `None` if no more keys.

### Functions
- `check_page_limit(limit: int) -> None`
  - Validates `limit` is within `1..MAX_KEYS_PER_PAGE`; raises `ValueError` otherwise.

- `paginate_keys(keys: Iterable[str], prefix: str, limit: int, after: str | None) -> KVKeyPage`
  - Builds a single `KVKeyPage` from an arbitrary iterable of keys (any order, duplicates allowed):
    - filters by `prefix`
    - filters to keys strictly greater than `after` (if provided)
    - deduplicates
    - sorts ascending
    - returns at most `limit` keys and a `next_after` token when more exist

### Interface
- `class IKeyValueAdapter(abc.ABC)`
  - Adapter contract for key-value backends:
  - `get(self, key: str) -> bytes`
  - `set(self, key: str, value: bytes, ttl: int | None = None) -> None`
  - `set_if_not_exists(self, key: str, value: bytes, ttl: int | None = None) -> bool`
  - `delete(self, key: str) -> None`
  - `delete_if_value_matches(self, key: str, value: bytes) -> bool`
  - `exists(self, key: str) -> bool`
  - `list_keys(self, prefix: str = "", *, limit: int = 100, after: str | None = None) -> KVKeyPage`
    - Returns live (unexpired) keys starting with `prefix`, strictly after `after`, ascending, with `limit` constrained to `1..MAX_KEYS_PER_PAGE`.
  - `get_ttl(self, key: str) -> int | None`
    - Whole seconds before expiration (rounded up), or `None` if it never expires; raises `KVNotFoundError` when missing.

## Configuration/Dependencies
- Standard library:
  - `abc` (`ABC`, `abstractmethod`)
  - `collections.abc.Iterable`
  - `dataclasses.dataclass`
- Uses Python 3.10+ type union syntax (`str | None`, `int | None`).

## Usage

### Paginate an in-memory key list
```python
from naas_abi_core.services.keyvalue.KeyValuePorts import paginate_keys

keys = ["app:a", "app:b", "other:x", "app:b"]  # duplicates and mixed prefixes
page1 = paginate_keys(keys, prefix="app:", limit=1, after=None)
print(page1.keys, page1.next_after)  # ('app:a',) 'app:a'

page2 = paginate_keys(keys, prefix="app:", limit=10, after=page1.next_after)
print(page2.keys, page2.next_after)  # ('app:b',) None
```

## Caveats
- `IKeyValueAdapter` is an interface only; backend behavior (TTL handling, when `KVNotFoundError` is raised, key liveness/expiry semantics) is determined by implementations.
- `paginate_keys` deduplicates keys and sorts them; it is intended for adapters that enumerate all keys and then page locally.
