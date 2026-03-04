# Audit Logging Service (`audit.py`)

## What it is
- An async audit logging helper for tracking sensitive operations (e.g., login/logout/password change).
- Writes audit records to an `audit_logs` table using SQLAlchemy’s async engine.
- Best-effort: logging failures are swallowed to avoid breaking the main request.

## Public API
- `async log_audit_event(action, user_id=None, resource_type=None, resource_id=None, details=None, request=None, success=True) -> None`
  - Core function to write an audit log entry.
  - Extracts `ip_address` and `user_agent` from a FastAPI `Request` when provided.
  - JSON-encodes `details` when provided.

- `async log_login(user_id: str, success: bool, request: Request | None = None, details: dict | None = None) -> None`
  - Logs a login attempt (`action="login"`), with success flag and optional details.

- `async log_logout(user_id: str, request: Request | None = None) -> None`
  - Logs a logout (`action="logout"`).

- `async log_register(user_id: str, request: Request | None = None) -> None`
  - Logs a registration (`action="register"`) and sets `resource_type="user"`, `resource_id=user_id`.

- `async log_password_change(user_id: str, request: Request | None = None, forced: bool = False) -> None`
  - Logs a password change (`action="password_change"`) with details `{"forced": forced}` and `resource_type="user"`.

- `async log_token_refresh(user_id: str, request: Request | None = None) -> None`
  - Logs a token refresh (`action="token_refresh"`).

- `async log_token_revocation(user_id: str, reason: str, request: Request | None = None) -> None`
  - Logs a token revocation (`action="token_revocation"`) with details `{"reason": reason}`.

## Configuration/Dependencies
- Database:
  - Uses `async_engine` from `naas_abi.apps.nexus.apps.api.app.core.database`.
  - Inserts into table `audit_logs` with columns:
    - `id, user_id, action, resource_type, resource_id, details, ip_address, user_agent, success, created_at`
- Time:
  - Uses `UTC` from `naas_abi.apps.nexus.apps.api.app.core.datetime_compat`.
  - Stores `created_at` as a naive `datetime` (`tzinfo` removed).
- Web framework integration:
  - Optionally uses `fastapi.Request` to capture client IP and user-agent header.

## Usage
```python
from fastapi import FastAPI, Request
from naas_abi.apps.nexus.apps.api.app.services.audit import log_login

app = FastAPI()

@app.post("/login")
async def login(request: Request):
    user_id = "user_123"
    success = True  # set based on your auth result
    await log_login(user_id=user_id, success=success, request=request)
    return {"ok": True}
```

## Caveats
- Audit write failures do not raise; they are printed (`print(f"Audit log failed: {e}")`).
- `details` is stored as JSON text (`json.dumps(details)`); non-serializable objects will cause logging to fail (and be printed).
- `created_at` is stored without timezone info (naive datetime).
