# datetime_compat

## What it is
A tiny compatibility module that provides a `UTC` timezone constant across Python versions (using `datetime.UTC` when available, otherwise a `timezone` with zero offset).

## Public API
- `UTC`
  - A `datetime.tzinfo` instance representing Coordinated Universal Time (UTC).
  - Resolved as:
    - `datetime.UTC` if present (newer Python versions), else
    - `timezone(timedelta(0))`

## Configuration/Dependencies
- Depends only on the standard library: `datetime` (`datetime`, `timedelta`, `timezone`).

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC

now_utc = datetime.now(UTC)
print(now_utc.tzinfo)  # UTC
```

## Caveats
- `UTC` may be either `datetime.UTC` or `datetime.timezone(timedelta(0))` depending on Python version, but both behave as a UTC tzinfo.
