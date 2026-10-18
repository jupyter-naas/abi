# `event_filter`

## What it is
EventBridge-style filtering utilities for checking whether a decoded JSON event (a `dict`) matches a filter expression. Filters map dotted field paths (e.g. `detail.status`) to matchers and are AND-combined across keys.

## Public API
- `OPERATORS: set[str]`
  - Supported operator names for operator-dict matchers:
    - `eq`, `ne`, `in`, `gt`, `gte`, `lt`, `lte`, `prefix`, `suffix`, `contains`, `exists`

- `validate(filter: Any) -> dict[str, Any]`
  - Validates a filter structure:
    - Must be a `dict` mapping dotted paths to matchers.
    - Path keys must match `^[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*$`.
    - If a matcher is an operator dict, all operator keys must be known.
  - Returns the original `filter` if valid; raises `TypeError`/`ValueError` otherwise.

- `matches(data: Any, filter: dict[str, Any] | None) -> bool`
  - Returns whether `data` (decoded JSON) passes the filter.
  - Behavior:
    - If `filter` is falsy (`None`/`{}`), returns `True`.
    - If `data` is not a `dict`, returns `False`.
    - For each filter key:
      - Walks the dotted path in `data`; missing/non-dict traversal yields `None`.
      - Applies matcher logic (see below); all keys must match.

### Matcher forms (as used by `matches`)
For a given path, `expected` may be:
- Scalar (including strings/numbers/bools): matches when `actual is not None` and `str(actual) == str(expected)`
- `None`: matches only when `actual is None`
- List: matches when `actual in expected`
- Operator dict: all operators in the dict must match (AND)
  - `{"exists": bool}`: `(actual is not None) == bool`
  - `{"eq": v}` / `{"ne": v}`: string equality/inequality via `str(...)`
  - `{"in": iterable_or_none}`: `actual in (value or [])`
  - Numeric: `gt/gte/lt/lte` compare `float(actual)` to `float(value)` (non-numeric -> `False`)
  - String ops (require `actual` is `str`):
    - `prefix`: `actual.startswith(str(value))`
    - `suffix`: `actual.endswith(str(value))`
    - `contains`: `str(value) in actual`

## Configuration/Dependencies
- Standard library only:
  - `re` for validating dotted paths
  - `typing.Any` for type annotations

## Usage
```python
from naas_abi_sdk import event_filter

event = {"detail": {"status": "OK", "count": 3}, "source": "app-core"}

flt = {
    "detail.status": {"eq": "OK"},
    "detail.count": {"gte": 2},
    "source": {"prefix": "app-"},
}

event_filter.validate(flt)
print(event_filter.matches(event, flt))  # True
```

## Caveats
- All filter keys are ANDed together; there is no OR composition.
- Scalar `eq/ne` comparisons are string-based (`str(actual)` vs `str(value)`), not type-strict.
- Path traversal over non-dicts or missing keys yields `None`; most operators then fail except `exists` and comparisons against `None`.
- `in` operator expects a container-like `value`; if `value` is `None`/falsy it becomes an empty list (`[]`).
