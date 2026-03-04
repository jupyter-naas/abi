# NEXUS ORM Models (`models.py`)

## What it is
- A collection of **SQLAlchemy 2.0 declarative ORM models** representing the NEXUS API database tables.
- Uses a shared `Base` declarative class and a helper `_utcnow()` to populate timestamp columns.

## Public API
### Helper
- `def _utcnow() -> datetime`
  - Returns current time in `UTC` with timezone info removed (`tzinfo=None`), used for `created_at`/`updated_at` defaults.

### ORM Models (tables)
- `OrganizationModel` (`organizations`)
  - Organization record plus branding/login customization fields.
  - Relationships: `owner`, `members`, `domains`, `workspaces`.

- `OrganizationMemberModel` (`organization_members`)
  - User membership in an organization with a role.
  - Unique constraint: `(organization_id, user_id)`.
  - Relationships: `organization`, `user`.

- `OrganizationDomainModel` (`organization_domains`)
  - Custom domain associated with an organization, with verification status/token.
  - Relationship: `organization`.

- `UserModel` (`users`)
  - User identity and profile fields.
  - Relationships: `organizations_owned`, `org_memberships`, `workspaces_owned`, `memberships`, `conversations`, `password_reset_tokens`.

- `PasswordResetTokenModel` (`password_reset_tokens`)
  - Password reset token with expiry and used flag.
  - Relationship: `user`.

- `WorkspaceModel` (`workspaces`)
  - Workspace record (optionally linked to an organization) with workspace-level theming fields.
  - Relationships: `owner`, `organization`, `members`, `conversations`, `graph_nodes`, `graph_edges`, `secrets`, `abi_servers`, `inference_servers`.

- `ABIServerModel` (`abi_servers`)
  - External ABI server configuration per workspace.
  - Unique constraint: `(workspace_id, endpoint)`.
  - Relationship: `workspace`.

- `InferenceServerModel` (`inference_servers`)
  - Generic inference server configuration (e.g., ollama/vLLM/custom) per workspace.
  - Relationship: `workspace`.

- `WorkspaceMemberModel` (`workspace_members`)
  - User membership in a workspace with a role.
  - Unique constraint: `(workspace_id, user_id)`.
  - Relationships: `workspace`, `user`.

- `ConversationModel` (`conversations`)
  - Conversation metadata (title/agent/pinned/archived) for a workspace+user.
  - Relationships: `workspace`, `user`, `messages` (ordered by `MessageModel.created_at`).

- `MessageModel` (`messages`)
  - Message in a conversation with `role` and `content`.
  - Column `metadata_` maps to DB column `"metadata"` (stored as `Text`, intended to hold a JSON string).
  - Relationship: `conversation`.

- `OntologyModel` (`ontologies`)
  - Ontology definitions per workspace with a JSON schema stored in column `"schema"` (attribute `schema_`).

- `GraphNodeModel` (`graph_nodes`)
  - Graph node with `type`, `label`, and JSON `properties` stored as `Text`.
  - Relationships: `workspace`, `edges_as_source`, `edges_as_target`.

- `GraphEdgeModel` (`graph_edges`)
  - Graph edge connecting two nodes with `type` and JSON `properties` stored as `Text`.
  - Relationships: `workspace`, `source_node`, `target_node`.

- `ApiKeyModel` (`api_keys`)
  - API key metadata (hash/prefix, optional workspace scoping).
  - Note: `last_used_at` and `expires_at` are stored as `String` columns.

- `ProviderConfigModel` (`provider_configs`)
  - Provider configuration per workspace; `config` stored as JSON string in `Text`.
  - `enabled` is an `Integer` flag.

- `AgentConfigModel` (`agent_configs`)
  - Agent configuration per workspace (prompt/provider/model metadata).
  - `enabled` is `Boolean`; `is_default` is an `Integer` flag.

- `SecretModel` (`secrets`)
  - Encrypted secret stored per workspace.
  - Unique constraint: `(workspace_id, key)`.
  - Relationship: `workspace`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.core.database.Base` (SQLAlchemy declarative base).
  - `naas_abi.apps.nexus.apps.api.app.core.datetime_compat.UTC` (timezone object used by `_utcnow()`).
  - SQLAlchemy ORM and column types (`Column`, `String`, `Text`, `Boolean`, `DateTime`, `Integer`, `ForeignKey`, `UniqueConstraint`, `relationship`).
- Timestamp behavior:
  - Many models use `created_at = default=_utcnow`.
  - Many models use `updated_at = default=_utcnow, onupdate=_utcnow`.
  - All `DateTime` columns are declared with `timezone=False`.

## Usage
Minimal example creating a few related records (assumes you already have an engine/session configured for `Base`):

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    UserModel, WorkspaceModel, ConversationModel, MessageModel
)

engine = create_engine("sqlite:///:memory:", future=True)
Base.metadata.create_all(engine)

with Session(engine) as session:
    user = UserModel(id="u1", email="a@example.com", name="Alice", hashed_password="hash")
    ws = WorkspaceModel(id="w1", name="Demo", slug="demo", owner_id="u1")
    conv = ConversationModel(id="c1", workspace_id="w1", user_id="u1", title="Hello")
    msg = MessageModel(id="m1", conversation_id="c1", role="user", content="Hi")

    session.add_all([user, ws, conv, msg])
    session.commit()
```

## Caveats
- `_utcnow()` returns a UTC-based time but explicitly strips timezone info (`tzinfo=None`), and `DateTime(timezone=False)` is used throughout.
- Several JSON-like fields are stored as plain `Text` (e.g., `MessageModel.metadata_`, `OntologyModel.schema_`, `Graph*Model.properties`, `ProviderConfigModel.config`); serialization/deserialization is handled elsewhere.
- Some date-like fields are stored as `String` in `ApiKeyModel` (`last_used_at`, `expires_at`), not `DateTime`.
- Cascade behavior is defined on multiple relationships (notably `cascade="all, delete-orphan"`), which affects deletion semantics.
