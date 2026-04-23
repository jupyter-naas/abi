# audit (Audit Logging Service)

## What it is
- An async audit logging helper that records sensitive security/compliance events into an `audit_logs` database table.
- Extracts optional client IP and user-agent from a FastAPI `Request`.
- Best-effort: failures during logging are caught and printed, without raising.

## Public API
- `async log_audit_event(action, user_id=None, resource_type=None, resource_id=None, details=None, request=None, success=True) -> None`
  - Core logger. Inserts one row into `audit_logs`.
  - JSON-encodes `details` when provided.
- `async log_login(user_id: str, success: bool, request: Request | None = None, details: dict | None = None) -> None`
  - Convenience wrapper for `action="login"`.
- `async log_logout(user_id: str, request: Request | None = None) -> None`
  - Convenience wrapper for `action="logout"`.
- `async log_register(user_id: str, request: Request | None = None) -> None`
  - Convenience wrapper for `action="register"`; sets `resource_type="user"` and `resource_id=user_id`.
- `async log_password_change(user_id: str, request: Request | None = None, forced: bool = False) -> None`
  - Convenience wrapper for `action="password_change"`; sets `details={"forced": forced}` and user resource fields.
- `async log_token_refresh(user_id: str, request: Request | None = None) -> None`
  - Convenience wrapper for `action="token_refresh"`.
- `async log_token_revocation(user_id: str, reason: str, request: Request | None = None) -> None`
  - Convenience wrapper for `action="token_revocation"`; sets `details={"reason": reason}`.

## Configuration/Dependencies
- Database:
  - Uses `naas_abi.apps.nexus.apps.api.app.core.database.async_engine` (SQLAlchemy async engine).
  - Inserts via raw SQL (`sqlalchemy.text`) into table `audit_logs` with columns:
    - `id, user_id, action, resource_type, resource_id, details, ip_address, user_agent, success, created_at`
- Time handling:
  - Uses `naas_abi.apps.nexus.apps.api.app.core.datetime_compat.UTC`.
  - Stores `created_at` as a timezone-naive `datetime` (timezone info removed).

## Usage
```python
from fastapi import FastAPI, Request
from naas_abi.apps.nexus.apps.api.app.services.audit import log_login

app = FastAPI()

@app.post("/login")
async def login(request: Request):
    # ... authenticate user ...
    await log_login(user_id="user-123", success=True, request=request)
    return {"ok": True}
```

## Caveats
- Logging errors are swallowed (printed only): audit failures will not fail the surrounding request.
- `created_at` is stored as a naive datetime (timezone stripped) even though it is computed using `UTC`.
