# IAMPolicyPort

## What it is
Defines IAM (Identity and Access Management) domain types and an abstract policy port for retrieving roles and access records used by authorization logic.

## Public API

### Type aliases
- `Role`: `Literal["owner", "admin", "member", "viewer"]`
- `ResourceType`: `Literal["workspace", "conversation", "organization"]`

### Data models
- `AuthorizationSubject`
  - Purpose: Represents the subject being authorized (typically a user).
  - Fields:
    - `user_id: str`
    - `token_scopes: set[str]` (default empty)
    - `is_authenticated: bool` (default `True`)

- `TokenData`
  - Purpose: Captures authentication token data.
  - Fields:
    - `user_id: str`
    - `scopes: set[str]` (default empty)
    - `is_authenticated: bool` (default `True`)

- `RequestContext`
  - Purpose: Request-scoped context derived from a token/session; supports impersonation.
  - Fields:
    - `token_data: TokenData`
    - `session_id: str | None` (default `None`)
    - `is_admin_access: bool` (default `False`)
    - `impersonated_user_id: str | None` (default `None`)
  - Properties:
    - `actor_user_id -> str`: `impersonated_user_id` if set, else `token_data.user_id`
    - `scopes -> set[str]`: returns `token_data.scopes`
    - `is_authenticated -> bool`: returns `token_data.is_authenticated`

- `AuthorizationRequest`
  - Purpose: Input payload for an authorization decision.
  - Fields:
    - `subject: AuthorizationSubject`
    - `action: str`
    - `resource_type: ResourceType`
    - `resource_id: str`
    - `required_scope: str | None` (default `None`)

- `AuthorizationDecision`
  - Purpose: Output of an authorization decision.
  - Fields:
    - `allowed: bool`
    - `reason: str`
    - `required_role: str | None` (default `None`)
    - `required_scope: str | None` (default `None`)

- `ConversationAccessRecord`
  - Purpose: Minimal access metadata for a conversation.
  - Fields:
    - `conversation_id: str`
    - `workspace_id: str`
    - `owner_user_id: str`

### Abstract port
- `class IAMPolicyPort(ABC)`
  - Purpose: Interface for fetching roles and conversation access records from a policy source (e.g., database/service).
  - Methods (all `async`, must be implemented):
    - `get_workspace_role(user_id: str, workspace_id: str) -> Role | None`
    - `get_organization_role(user_id: str, org_id: str) -> Role | None`
    - `get_conversation_access_record(conversation_id: str) -> ConversationAccessRecord | None`

## Configuration/Dependencies
- Standard library only: `abc`, `dataclasses`, `typing`.
- Async interface: implementations of `IAMPolicyPort` must provide `async def` methods.

## Usage

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.iam.port import (
    IAMPolicyPort, ConversationAccessRecord, Role
)

class InMemoryIAMPolicy(IAMPolicyPort):
    async def get_workspace_role(self, user_id: str, workspace_id: str) -> Role | None:
        return "admin" if user_id == "u1" and workspace_id == "w1" else None

    async def get_organization_role(self, user_id: str, org_id: str) -> Role | None:
        return None

    async def get_conversation_access_record(
        self, conversation_id: str
    ) -> ConversationAccessRecord | None:
        if conversation_id == "c1":
            return ConversationAccessRecord(
                conversation_id="c1", workspace_id="w1", owner_user_id="u1"
            )
        return None

async def main():
    policy = InMemoryIAMPolicy()
    print(await policy.get_workspace_role("u1", "w1"))  # "admin"
    print(await policy.get_conversation_access_record("c1"))

asyncio.run(main())
```

## Caveats
- This module does **not** implement authorization logic; it only defines data structures and an interface to retrieve roles/access records.
- All dataclasses are `frozen=True` (immutable).
