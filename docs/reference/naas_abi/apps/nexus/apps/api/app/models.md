# NEXUS ORM Models (`models.py`)

## What it is
- SQLAlchemy declarative ORM models for NEXUS API database tables.
- Defines table schemas (columns, constraints) and ORM relationships.
- Provides a small timestamp helper for consistent UTC defaults.

## Public API

### Helper
- `def _utcnow() -> datetime`
  - Returns the current UTC time as a **naive** `datetime` (timezone removed) for `created_at`/`updated_at` defaults.

### ORM models (tables)
- `OrganizationModel` (`organizations`)
  - Organization identity, branding/login configuration, timestamps, and relations to owner/members/domains/workspaces.
- `OrganizationMemberModel` (`organization_members`)
  - Join table between organizations and users; unique `(organization_id, user_id)`.
- `OrganizationDomainModel` (`organization_domains`)
  - Domain bound to an organization; `domain` is globally unique; verification fields.
- `UserModel` (`users`)
  - User identity/auth fields; relations to owned orgs/workspaces, memberships, conversations, and token tables.
- `PasswordResetTokenModel` (`password_reset_tokens`)
  - Password reset token record linked to a user (`token` unique).
- `MagicLinkTokenModel` (`magic_link_tokens`)
  - Magic-link token record linked to a user (`token` unique); OTP tracking fields.
- `WorkspaceModel` (`workspaces`)
  - Workspace identity, theming, drive feature flags, and relations to members/conversations/graph/secrets/servers.
- `CodingEnvironmentModel` (`coding_environments`)
  - Records binding between a Coder workspace and repo/label plus optional sidecar connection fields.
- `ABIServerModel` (`abi_servers`)
  - External ABI server configuration per workspace; unique `(workspace_id, endpoint)`.
- `InferenceServerModel` (`inference_servers`)
  - Generic inference server configuration per workspace (type, endpoint, optional paths).
- `WorkspaceMemberModel` (`workspace_members`)
  - Join table between workspaces and users; unique `(workspace_id, user_id)`.
- `ConversationModel` (`conversations`)
  - Conversation within a workspace; includes flags (pinned/archived) and ordered `messages` relationship.
- `MessageModel` (`messages`)
  - Message within a conversation; `metadata_` attribute is stored in DB column named `"metadata"`.
- `ChatIngestionJobModel` (`chat_ingestion_jobs`)
  - Tracks ingestion jobs for conversations (source, embedding config, status/progress, timings).
- `OntologyModel` (`ontologies`)
  - Ontology per workspace; `schema_` stored in DB column `"schema"` as text.
- `OntologyIconModel` (`ontology_icons`)
  - Composite primary key `(workspace_id, target_key)`; stores icon assignment and audit fields.
- `GraphNodeModel` (`graph_nodes`)
  - Graph nodes per workspace; JSON-like `properties` stored as text; relationships to edges as source/target.
- `GraphViewModel` (`graph_views`)
  - Stores a saved graph view definition/state per workspace with optional creator linkage.
- `GraphEdgeModel` (`graph_edges`)
  - Graph edges per workspace connecting nodes; JSON-like `properties` stored as text.
- `ApiKeyModel` (`api_keys`)
  - API key record (hash/prefix), scoped optionally to a workspace; includes string fields `last_used_at`, `expires_at`.
- `ProviderConfigModel` (`provider_configs`)
  - Provider/model config per workspace; `config` stored as text (intended JSON).
- `AgentConfigModel` (`agent_configs`)
  - Agent configuration per workspace; notes a partial unique index on `(workspace_id, class_name)` created via migration.
- `SkillModel` (`skills`)
  - User-created reusable prompt skills; includes scope (`user|workspace|organization`) and ordering field `last_used_at`.
- `OrganizationRoleFeaturesModel` (`organization_role_features`)
  - Per-organization role baseline overlay stored as JSON text; primary key `organization_id`.
- `AppConfigModel` (`app_configs`)
  - Per-workspace marketplace app enablement; unique `(workspace_id, app_id)`.
- `SecretModel` (`secrets`)
  - Encrypted secret storage per workspace; unique `(workspace_id, key)`; relationship to workspace.
- `ModelCatalogRecordModel` (`model_catalog`)
  - Persistent display metadata for marketplace AI models, including “source_*” columns and `overridden_fields` JSON text.
- `WorkspaceResourcePolicyModel` (`workspace_resource_policies`)
  - Composite primary key `(workspace_id, resource_kind)`; policy stored as text; revision/audit fields.
- `SearchTopicModel` (`search_topics`)
  - Composite primary key `(workspace_id, topic_id)`; topic definition stored as text (intended JSON).
- `SearchSettingsModel` (`search_settings`)
  - Primary key `workspace_id`; settings stored as text (intended JSON).

## Configuration/Dependencies
- Depends on:
  - `naas_abi.apps.nexus.apps.api.app.core.database.Base` (SQLAlchemy declarative base).
  - `naas_abi.apps.nexus.apps.api.app.core.datetime_compat.UTC` (timezone used by `_utcnow`).
  - SQLAlchemy: `Column`, `ForeignKey`, `UniqueConstraint`, `relationship`, and core column types (`String`, `Text`, `Integer`, `Boolean`, `DateTime`).

## Usage
Minimal in-memory SQLite example (create tables, insert a user/org/workspace/conversation/message):

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    UserModel, OrganizationModel, WorkspaceModel, ConversationModel, MessageModel
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
- `_utcnow()` returns a **naive** `datetime` (UTC converted then `tzinfo` removed); `DateTime(timezone=False)` is used throughout.
- Several fields intended to contain JSON are stored as `Text` with no schema enforcement (e.g., `MessageModel.metadata_`, `OntologyModel.schema_`, `GraphNodeModel.properties`, `ProviderConfigModel.config`, `OrganizationRoleFeaturesModel.role_baseline`).
- `MessageModel.metadata_` maps to a database column named `"metadata"`; use the attribute name `metadata_` in Python to avoid reserved-name conflicts.
- `AgentConfigModel` relies on a **partial unique index** declared in a migration (not expressible portably in the model definition).
