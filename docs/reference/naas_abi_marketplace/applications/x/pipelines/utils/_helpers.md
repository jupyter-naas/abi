# `_helpers` (X pipeline utilities)

## What it is
Small, dependency-free helper functions shared by the X graph-builder modules. Designed to avoid import cycles by not importing sibling builder modules.

## Public API
- `uri_for(namespace: str, class_name: str, stable_id: str) -> str`
  - Builds a deterministic IRI under `namespace` for `class_name`, keyed by `stable_id`.
  - Sanitizes `stable_id` by replacing non `[A-Za-z0-9_-]` characters with `_`.

- `parse_dt(value: Any) -> datetime | None`
  - Parses an X v2 ISO-8601-like timestamp into a `datetime`.
  - Returns:
    - the input as-is if it is already a `datetime`
    - `None` for falsy inputs or unparseable values

- `first(value: Any) -> str | None`
  - Returns:
    - the first element (as `str`) if `value` is a non-empty list
    - the string itself if `value` is a `str`
    - `None` otherwise

## Configuration/Dependencies
- Standard library only:
  - `re`
  - `datetime.datetime`
  - `typing.Any`

## Usage
```python
from naas_abi_marketplace.applications.x.pipelines.utils._helpers import (
    uri_for, parse_dt, first
)

iri = uri_for("https://example.org/", "Tweet", "id:123/abc")
# "https://example.org/Tweet/id_123_abc"

dt = parse_dt("2024-01-02T03:04:05")
# datetime(2024, 1, 2, 3, 4, 5)

v1 = first(["a", "b"])  # "a"
v2 = first("hello")     # "hello"
v3 = first([])          # None
```

## Caveats
- `parse_dt()` uses `datetime.fromisoformat(...)`; inputs like `"2024-01-02T03:04:05Z"` may not parse on some Python versions and will return `None`.
- `uri_for()` does not URL-encode; it only replaces disallowed characters with `_`.
