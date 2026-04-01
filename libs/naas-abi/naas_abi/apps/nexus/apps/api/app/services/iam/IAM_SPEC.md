# IAM Service Specification (NEXUS API)

## Purpose

Define a centralized authorization service for the API so permission checks are consistent, testable, and reusable across endpoints and application services.

This IAM service is **authorization-only**. Authentication (JWT issue/refresh/revoke, current user resolution) remains in `auth`.

## Goals

- Centralize permission checks behind a single API.
- Support role-based access (workspace/org roles) and token scopes.
- Make checks composable in both endpoints and services.
- Return machine-readable deny reasons for audit and debugging.
- Keep rollout incremental and backward-compatible.

## Non-Goals (v1)

- No external IdP integration.
- No UI permissions management.
- No policy DSL engine (OPA/Cedar) in v1.
- No cross-service distributed authorization protocol.

## Current Context (must be preserved)

- Authn already exists in `auth`:
  - JWT access tokens with `sub`, `jti`, `exp`.
  - Refresh token rotation + access token revocation.
- Access control currently mixes:
  - workspace/org membership checks in endpoints.
  - ad-hoc role checks (`owner/admin/...`) in endpoints.
  - resource ownership checks in some services (e.g., chat conversation ownership).

IAM should absorb this authorization logic, while preserving existing behavior by default.

## Proposed Domain Boundaries

Create a dedicated IAM domain under:

`app/services/iam`

Suggested layout:

- `README.md` (optional overview)
- `spec` (this file)
- `port.py` (authorization contracts/DTOs)
- `service.py` (IAM application/domain service)
- `factory.py` (constructor wiring)
- `adapters/secondary/postgres.py` (role/resource lookup adapter)
- `adapters/secondary/postgres_test.py`
- `service_test.py`

IAM must not import endpoint modules. Endpoints/services depend on IAM, not the reverse.

## Authorization Model

### Subject

Normalized caller context:

- `user_id: str`
- `token_scopes: set[str]` (optional in v1, default empty)
- `is_authenticated: bool`

### Resource

Typed resources:

- `workspace:{workspace_id}`
- `conversation:{conversation_id}`
- `organization:{org_id}`
- later: `secret`, `agent`, `file`, etc.

### Action

Verb-like permissions, examples:

- workspace:
  - `workspace.read`
  - `workspace.update`
  - `workspace.members.read`
  - `workspace.members.invite`
  - `workspace.members.update_role`
  - `workspace.members.remove`
- chat:
  - `chat.conversation.list`
  - `chat.conversation.read`
  - `chat.conversation.create`
  - `chat.conversation.update`
  - `chat.conversation.delete`
  - `chat.message.read`
  - `chat.message.create`
  - `chat.message.update`
- org:
  - `org.read`
  - `org.update`
  - `org.members.manage`

### Decision

`ALLOW` or `DENY`, with metadata:

- `allowed: bool`
- `reason: str` (e.g., `missing_membership`, `insufficient_role`, `missing_scope`, `not_owner`)
- `required_role: str | None`
- `required_scope: str | None`

## Policy Rules (v1 baseline)

### Workspace role matrix

Use current semantics as baseline:

- `owner`: all workspace actions
- `admin`: most management actions except ownership-only actions
- `member`: read and standard usage actions (chat use, graph use)
- `viewer`: read-only actions

### Conversation ownership

- Conversation operations must satisfy both:
  - workspace access for the parent workspace
  - conversation ownership (`conversation.user_id == subject.user_id`) unless explicit shared-thread rule is introduced.

### Scope checks

Support now, enforce gradually:

- If an endpoint/service defines a required scope, caller token must include it.
- If scope not required for that route in v1, skip scope enforcement for compatibility.

## IAM Service Contract (v1)

Define in `port.py`:

- `AuthorizationSubject`
- `AuthorizationRequest`
- `AuthorizationDecision`
- `IAmPolicyPort` (secondary adapter contract for data lookups)

Define in `service.py`:

- `authorize(request: AuthorizationRequest) -> AuthorizationDecision`
- `require(request: AuthorizationRequest) -> None`
  - raises `PermissionError` or typed IAM exception with deny reason.

Convenience helpers (optional, but recommended):

- `require_workspace_action(user_id, workspace_id, action, scopes=None)`
- `require_conversation_action(user_id, conversation_id, action, scopes=None)`
- `require_org_action(user_id, org_id, action, scopes=None)`

## Adapter Responsibilities (Postgres)

`adapters/secondary/postgres.py` should provide:

- lookup workspace role for `(user_id, workspace_id)`
- lookup org role for `(user_id, org_id)`
- lookup conversation owner + workspace for `(conversation_id)`
- optional token scope extraction helper (if persisted server-side in future)

No policy logic in adapter; adapter only returns data.

## Integration Plan

### Phase 1 (safe extraction)

- Add IAM service and adapter.
- Re-route existing `require_workspace_access` and chat ownership checks through IAM, preserving current behavior.
- Keep endpoint signatures unchanged.

### Phase 2 (scope-aware routes)

- Introduce required scopes for selected routes:
  - chat read/write
  - secret management
  - workspace member management
- Parse scopes from JWT (if present), fallback empty set.

### Phase 3 (full adoption)

- Replace all ad-hoc endpoint role checks with IAM `require(...)`.
- Keep legacy helper wrappers for compatibility but delegate internally to IAM.

## Error Mapping

IAM errors should map consistently:

- unauthenticated -> `401`
- authenticated but unauthorized -> `403`
- concealed ownership (resource should appear absent) -> optional `404` policy mode

For chat resources, preserve existing behavior where appropriate (some routes currently use `404` for non-owned conversation IDs).

## Testing Requirements

### Unit tests (`service_test.py`)

- role matrix allow/deny cases
- scope allow/deny cases
- conversation ownership allow/deny cases
- precedence checks (deny if either role or scope fails)

### Adapter tests (`postgres_test.py`)

- role lookup for workspace/org
- conversation owner/workspace lookup
- missing rows behavior

### Integration tests (incremental)

- chat routes enforce owner-only conversation access via IAM
- workspace member management routes enforce owner/admin via IAM

## Observability

Add structured logs for denies:

- `user_id`
- `action`
- `resource_type/resource_id`
- `reason`
- request correlation id (if available)

Do not log tokens or secret values.

## Open Questions (for implementation agent)

- Should non-owner workspace members be allowed to read list of all conversations in a workspace, or only their own?
  - Current expected behavior after recent changes: only own conversations.
- Should we standardize unauthorized resource responses to `403` or keep selective `404` for concealment?
- Scope namespace convention: `chat:read` style or dotted `chat.read` style?
  - Pick one and apply consistently.

## Acceptance Criteria (v1)

- IAM service exists with clear contract and adapter boundary.
- At least chat authorization paths use IAM (no duplicated ad-hoc checks in chat flow).
- Existing passing behavior preserved for current tests.
- New IAM tests cover role/scope/ownership deny and allow paths.
- No direct policy logic in endpoints beyond calling IAM.
