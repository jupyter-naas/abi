# rate_limit

## What it is
- Async rate-limiting helpers for FastAPI endpoints.
- Uses a database table (`rate_limit_events`) to:
  - Count recent attempts per `(identifier, endpoint)`.
  - Record each attempt.
  - Periodically delete old events.

## Public API
- `async check_rate_limit(identifier: str, endpoint: str) -> None`
  - Enforces rate limit for the given identifier and endpoint.
  - When enabled, counts attempts within the configured window and:
    - Raises `fastapi.HTTPException` with `429 Too Many Requests` if limit exceeded.
    - Otherwise inserts a new event into `rate_limit_events`.

- `async cleanup_old_rate_limit_events() -> None`
  - Deletes rate limit events older than 24 hours.

- `get_rate_limit_identifier(request: fastapi.Request, user_id: str | None = None) -> str`
  - Returns a stable identifier:
    - `user:{user_id}` if provided,
    - else `ip:{client_host}` if available,
    - else `"unknown"`.

## Configuration/Dependencies
- Settings (`naas_abi...core.config.settings`):
  - `rate_limit_enabled` (bool): disables/enables enforcement.
  - `rate_limit_window_seconds` (int): time window for counting attempts.
  - `rate_limit_login_attempts` (int): maximum allowed attempts within the window.
- Database:
  - `async_engine` (`naas_abi...core.database.async_engine`) used for async SQL execution.
  - Requires a table named `rate_limit_events` with at least:
    - `id`, `identifier`, `endpoint`, `created_at`.
- Time:
  - Uses `UTC` from `naas_abi...core.datetime_compat`.
  - Writes and compares naive datetimes (`tzinfo` removed) against `created_at`.

## Usage
```python
from fastapi import FastAPI, Request
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit,
    get_rate_limit_identifier,
)

app = FastAPI()

@app.post("/auth/login")
async def login(request: Request):
    identifier = get_rate_limit_identifier(request)  # IP-based if no user_id
    await check_rate_limit(identifier=identifier, endpoint="/auth/login")
    return {"ok": True}
```

## Caveats
- Must be called explicitly in your endpoint logic; it is not an auto-installed middleware here.
- Relies on a `rate_limit_events` table existing and being compatible with the SQL used.
- Datetimes are stored/compared as naive timestamps; ensure the DB column semantics match this expectation.
- If `request.client` is missing, the identifier becomes `"unknown"` (shared across such requests).
