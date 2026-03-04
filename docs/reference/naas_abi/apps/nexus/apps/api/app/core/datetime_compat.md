# `datetime_compat`

## What it is
- A tiny compatibility module that provides a `UTC` timezone object across Python versions.

## Public API
- `UTC`: A `datetime.tzinfo` instance representing UTC.
  - Uses `datetime.UTC` if available (newer Python versions).
  - Falls back to `datetime.timezone(datetime.timedelta(0))` otherwise.

## Configuration/Dependencies
- Depends only on the Python standard library:
  - `datetime.datetime`, `datetime.timedelta`, `datetime.timezone`

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC

now_utc = datetime.now(UTC)
print(now_utc.isoformat())
```

## Caveats
- `UTC` is defined at import time; it is a constant timezone object, not a function.
