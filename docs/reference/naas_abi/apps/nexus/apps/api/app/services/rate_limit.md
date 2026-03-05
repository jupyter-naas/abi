# `rate_limit` (Rate Limiting Middleware)

## What it is
- Small helper module to rate-limit requests (intended for auth endpoints) by recording access events in a database table and rejecting requests that exceed a configured threshold within a time window.

## Public API
- `async check_rate_limit(identifier: str, endpoint: str) -> None`
  - Counts recent attempts for an `(identifier, endpoint)` pair within the configured window.
  - Raises `fastapi.HTTPException` (429) when the limit is exceeded.
  - Records the current attempt in `rate_limit_events` when allowed.
- `async cleanup_old_rate_limit_events() -> None`
  - Deletes `rate_limit_events` older than 24 hours.
- `get_rate_limit_identifier(request: fastapi.Request, user_id: str | None = None) -> str`
  - Builds a rate-limit identifier:
    - `user:{user_id}` if `user_id` is provided
    - else `ip:{request.client.host}` if available
    - else `"unknown"`

## Configuration/Dependencies
- Depends on:
  - `settings` from `naas_abi.apps.nexus.apps.api.app.core.config`:
    - `rate_limit_enabled` (bool)
    - `rate_limit_window_seconds` (int)
    - `rate_limit_login_attempts` (int)
  - `async_engine` from `naas_abi.apps.nexus.apps.api.app.core.database` (SQLAlchemy async engine)
  - `UTC` from `naas_abi.apps.nexus.apps.api.app.core.datetime_compat`
  - Database table `rate_limit_events` with columns used by queries:
    - `id`, `identifier`, `endpoint`, `created_at`
- Uses raw SQL via `sqlalchemy.text()`.

## Usage
```python
from fastapi import FastAPI, Request
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit,
    get_rate_limit_identifier,
)

app = FastAPI()

@app.post("/login")
async def login(request: Request):
    identifier = get_rate_limit_identifier(request)  # or pass user_id if known
    await check_rate_limit(identifier=identifier, endpoint="/login")
    return {"ok": True}
```

## Caveats
- `check_rate_limit()` always records an event when rate limiting is enabled and the request is not blocked; ensure the `rate_limit_events` table exists and is writable.
- Timestamps are stored/compared as naive datetimes derived from `datetime.now(UTC).replace(tzinfo=None)`. Ensure your DB column type and comparisons align with this behavior.
- The 429 response includes a `Retry-After` header set to `settings.rate_limit_window_seconds` and a message that reports minutes as `rate_limit_window_seconds // 60` (integer division).
