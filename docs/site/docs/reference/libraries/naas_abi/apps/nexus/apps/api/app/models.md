# NEXUS ORM Models (`models.py`)

## What it is
- A set of **SQLAlchemy 2.0 declarative ORM models** representing NEXUS database tables.
- Provides table schemas, constraints, and relationships to replace raw SQL usage.
- Includes a small helper (`_utcnow`) for consistent timestamp defaults.

## Public API
### Helper
- `def _utcnow() -> datetime`
  - Returns current UTC time as a **naive** `datetime` (`tzinfo=None`), used as default for `created_at`/`updated_at`.

### ORM Models (tables)
- `OrganizationModel` (`organizations`)
  - Organization identity, ownership, branding/login configuration, and relationships to members/domains/workspaces.
- `OrganizationMemberModel` (`organization_members`)
  - Membership join table between organizations and users; unique per (`organization_id`, `user_id`).
- `OrganizationDomainModel` (`organization_domains`)
  - Domain attached to an organization, with verification fields; domain is globally unique.
- `UserModel` (`users`)
  - User identity and auth fields; relationships to owned orgs/workspaces, memberships, conversations, and tokens.
- `PasswordResetTokenModel` (`password_reset_tokens`)
  - Password reset token lifecycle (token, expiry, used flag) linked to a user.
- `MagicLinkTokenModel` (`magic_link_tokens`)
  - Magic-link token lifecycle (token, expiry, used flag) linked to a user.
- `WorkspaceModel` (`workspaces`)
  - Workspace identity, ownership, optional organization linkage, theming fields, and related resources.
- `ABIServerModel` (`abi_servers`)
  - External ABI server configuration per workspace; unique per (`workspace_id`, `endpoint`).
- `InferenceServerModel` (`inference_servers`)
  - Generic inference server configuration per workspace (type, endpoint, optional paths).
- `WorkspaceMemberModel` (`workspace_members`)
  - Membership join table between workspaces and users; unique per (`workspace_id`, `user_id`).
- `ConversationModel` (`conversations`)
  - Chat conversation within a workspace; ordered relationship to messages.
- `MessageModel` (`messages`)
  - Chat message content and role; `metadata_` stored in DB column named `metadata`.
- `ChatIngestionJobModel` (`chat_ingestion_jobs`)
  - Tracks ingestion jobs for conversations (source path/type, embedding config, status/progress, timings).
- `OntologyModel` (`ontologies`)
  - Stores ontology schema (JSON stored as text) per workspace.
- `GraphNodeModel` (`graph_nodes`)
  - Graph nodes per workspace with typed label and JSON properties; relationships to edges.
- `GraphEdgeModel` (`graph_edges`)
  - Graph edges per workspace linking source/target nodes; JSON properties.
- `ApiKeyModel` (`api_keys`)
  - API key records (hash/prefix, optional workspace scope).
- `ProviderConfigModel` (`provider_configs`)
  - Provider/model configuration per workspace; `config` stored as JSON text.
- `AgentConfigModel` (`agent_configs`)
  - Agent configuration per workspace (class path, prompts, provider linkage, enable/default flags).
- `SecretModel` (`secrets`)
  - Encrypted secret storage per workspace; unique per (`workspace_id`, `key`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.core.database.Base` (SQLAlchemy declarative base).
  - `naas_abi.apps.nexus.apps.api.app.core.datetime_compat.UTC` (timezone used by `_utcnow`).
  - SQLAlchemy: `Column`, types (`String`, `Text`, `Integer`, `Boolean`, `DateTime`), `ForeignKey`, `UniqueConstraint`, and ORM `relationship`.
- Timestamps:
  - Many models use `DateTime(timezone=False)` with defaults/onupdate set to `_utcnow`.

## Usage
Minimal example creating a user, an organization, a workspace, a conversation, and a message:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    UserModel, OrganizationModel, WorkspaceModel,
    ConversationModel, MessageModel,
)

engine = create_engine("sqlite:///:memory:", future=True)
Base.metadata.create_all(engine)

with Session(engine) as session:
    user = UserModel(id="u1", email="user@example.com", name="User", hashed_password="hash")
    org = OrganizationModel(id="o1", name="Acme", slug="acme", owner_id="u1")
    ws = WorkspaceModel(id="w1", name="Main", slug="main", owner_id="u1", organization_id="o1")
    conv = ConversationModel(id="c1", workspace_id="w1", user_id="u1", title="New Conversation")
    msg = MessageModel(id="m1", conversation_id="c1", role="user", content="Hello")

    session.add_all([user, org, ws, conv, msg])
    session.commit()
```

## Caveats
- `_utcnow()` returns a **naive** datetime (UTC converted then `tzinfo` removed); DB columns are declared with `timezone=False`.
- Several fields intended to hold JSON are stored as `Text` without validation (e.g., `MessageModel.metadata_`, `OntologyModel.schema_`, `ProviderConfigModel.config`, `GraphNodeModel.properties`, `GraphEdgeModel.properties`).
- `MessageModel.metadata_` maps to a database column named `"metadata"`; attribute name is `metadata_` to avoid conflicts.
