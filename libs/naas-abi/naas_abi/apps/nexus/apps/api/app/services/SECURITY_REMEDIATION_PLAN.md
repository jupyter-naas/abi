# Security Remediation Plan (NEXUS API Services)

Date: 2026-03-31
Scope: `libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/`

## Goal

Track and execute one remediation task per identified security issue from the services audit.

## Tasks

### 1) Unauthenticated WebSocket HTTP admin endpoints
- **Risk:** Critical
- **Issue:** `/websocket/broadcast` and `/websocket/presence/*` are exposed without authentication/authorization.
- **Task:** Require `get_current_user_required` and enforce workspace/user-level authorization before broadcast/presence access.
- **Primary files:**
  - `services/websocket/adapters/primary/websocket__primary_adapter__FastAPI.py`
- **Acceptance criteria:**
  - Unauthenticated requests return `401`.
  - Authenticated users cannot access other users/workspaces' presence (`403/404`).
  - Authorized requests still function.

### 2) Missing workspace authorization in WebSocket runtime
- **Risk:** Critical
- **Issue:** `join_workspace` and room broadcasts trust client-supplied `workspace_id` without membership checks.
- **Task:** Enforce workspace membership/role checks in runtime before joining rooms and before relaying workspace events.
- **Primary files:**
  - `services/websocket/runtime.py`
  - `services/auth/adapters/primary/auth__primary_adapter__dependencies.py` (or shared checker)
- **Acceptance criteria:**
  - Unauthorized workspace join is rejected.
  - Cross-workspace event injection is blocked.
  - WS tests cover authorized and unauthorized paths.

### 3) Password reset token leakage in logs
- **Risk:** High
- **Issue:** Reset URL containing token is logged.
- **Task:** Remove reset URL/token logging and replace with safe audit-style event metadata.
- **Primary files:**
  - `services/auth/adapters/primary/auth__primary_adapter__FastAPI.py`
- **Acceptance criteria:**
  - No logs contain reset token values.
  - Observability preserved with non-sensitive identifiers only.

### 4) Password reset tokens stored in plaintext
- **Risk:** High
- **Issue:** Reset token is stored and queried in plaintext DB fields.
- **Task:** Hash reset tokens before storage and lookup by hash; keep one-time-use and expiry semantics.
- **Primary files:**
  - `services/auth/service.py`
  - `services/auth/adapters/secondary/postgres.py`
  - DB model/migration files for password reset token storage
- **Acceptance criteria:**
  - Database does not store raw reset tokens.
  - Reset flow still works end-to-end.
  - Existing tokens migration/compat behavior is defined.

### 5) SSRF exposure via custom provider endpoint
- **Risk:** High
- **Issue:** User-provided provider endpoint is used for outbound requests without endpoint validation.
- **Task:** Add strict endpoint validation (scheme/domain/IP policy), deny local/private/link-local/metadata targets, and enforce allowlist policy for custom endpoints.
- **Primary files:**
  - `services/chat/service.py`
  - `services/provider_runtime.py`
  - `services/chat/adapters/primary/chat__primary_adapter__schemas.py`
- **Acceptance criteria:**
  - Invalid or disallowed endpoints are rejected at validation time.
  - Attempts to target local/private networks are blocked.
  - Existing approved providers continue to work.

### 6) Secret leakage through logs
- **Risk:** High
- **Issue:** Sensitive values can be logged (query token in URL, provider object with secrets, etc.).
- **Task:** Add centralized redaction helpers and apply them to provider/auth/chat logging paths.
- **Primary files:**
  - `services/provider_runtime.py`
  - `services/chat/adapters/primary/chat__primary_adapter__streaming.py`
  - Any related auth/provider log points
- **Acceptance criteria:**
  - API keys/tokens are masked in all log messages.
  - Error logs retain troubleshooting value without disclosing secrets.

### 7) Files service lacks workspace scoping
- **Risk:** Medium
- **Issue:** File operations are not namespaced by workspace/user in storage keys.
- **Task:** Introduce workspace-scoped object storage prefixes and enforce authorization checks per operation.
- **Primary files:**
  - `services/files/service.py`
  - `services/files/adapters/primary/files__primary_adapter__FastAPI.py`
  - dependency wiring for workspace context
- **Acceptance criteria:**
  - Files are isolated per workspace.
  - Access to another workspace's files is denied.
  - Existing data migration or backward compatibility plan is documented.

## Execution Notes

- Prefer fixing in this order: **1, 2, 3, 4, 5, 6, 7**.
- Add/extend tests for each fix before merge.
- Include security regression tests for authz and token handling.
