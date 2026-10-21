# ChatSecondaryAdapterPostgres

## What it is
- A PostgreSQL-backed (SQLAlchemy async) implementation of `ChatPersistencePort` for chat-related persistence.
- Reads/writes conversations, messages, agent configs, inference servers, and workspace secrets using ORM models and returns lightweight `*Record` DTOs.

## Public API
### Class: `ChatSecondaryAdapterPostgres(ChatPersistencePort)`
- `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
  - Bind an async DB session directly (`db`) or lazily via `db_getter`.

#### Conversation operations
- `list_conversations_by_workspace(workspace_id: str, user_id: str, limit: int, offset: int) -> list[ChatConversationRecord]`
  - List conversations for a user within a workspace, ordered by `updated_at` descending.
- `create_conversation(conversation_id: str, workspace_id: str, user_id: str, title: str, agent: str, now) -> ChatConversationRecord`
  - Insert a conversation and flush; returns a `ChatConversationRecord`.
- `get_conversation_by_id(conversation_id: str) -> ChatConversationRecord | None`
  - Fetch a conversation by id.
- `get_conversation_by_id_for_user(conversation_id: str, user_id: str) -> ChatConversationRecord | None`
  - Fetch a conversation by id constrained to `user_id`.
- `update_conversation_agent(conversation_id: str, agent: str, now) -> None`
  - Update conversation `agent` and `updated_at` if it exists.
- `update_conversation_fields(conversation_id: str, now, title: str | None = None, pinned: bool | None = None, archived: bool | None = None) -> None`
  - Update any provided fields and `updated_at` if the conversation exists.
- `touch_conversation(conversation_id: str, now) -> None`
  - Update only `updated_at` if the conversation exists.
- `delete_conversation(conversation_id: str) -> bool`
  - Delete a conversation by id; returns `False` if not found.

#### Message operations
- `list_messages_by_conversation(conversation_id: str) -> list[ChatMessageRecord]`
  - List messages ordered by `created_at` ascending.
- `create_message(message_id: str, conversation_id: str, role: str, content: str, created_at, agent: str | None = None) -> None`
  - Insert a message and flush.
- `delete_messages_by_conversation(conversation_id: str) -> None`
  - Bulk-delete messages for a conversation (executes a `DELETE ... WHERE`).
- `update_message_content(message_id: str, content: str) -> bool`
  - Update message content; returns `False` if not found.

#### Agent / inference server / secrets
- `get_agent_by_id(agent_id: str) -> ChatAgentRecord | None`
  - Fetch an agent config by id.
- `list_agent_names_by_ids(agent_ids: set[str]) -> dict[str, str]`
  - Map agent id → agent name for the provided ids (returns `{}` if input is empty).
- `get_enabled_workspace_abi_server(workspace_id: str) -> ChatInferenceServerRecord | None`
  - Fetch the enabled inference server of type `"abi"` for a workspace.
- `get_workspace_secret(workspace_id: str, key: str) -> ChatSecretRecord | None`
  - Fetch a workspace secret by key (returns only `encrypted_value`).

## Configuration/Dependencies
- Requires an SQLAlchemy `AsyncSession` (directly or via `db_getter`).
- Uses ORM models:
  - `ConversationModel`, `MessageModel`, `AgentConfigModel`, `InferenceServerModel`, `SecretModel`
- Uses port/DTO types:
  - `ChatPersistencePort`, `ChatConversationRecord`, `ChatMessageRecord`, `ChatAgentRecord`, `ChatInferenceServerRecord`, `ChatSecretRecord`

## Usage
```python
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.postgres import (
    ChatSecondaryAdapterPostgres,
)

async def main(session: AsyncSession):
    repo = ChatSecondaryAdapterPostgres(db=session)

    now = datetime.now(timezone.utc)
    convo = await repo.create_conversation(
        conversation_id="c1",
        workspace_id="w1",
        user_id="u1",
        title="Hello",
        agent="agent-1",
        now=now,
    )

    await repo.create_message(
        message_id="m1",
        conversation_id=convo.id,
        role="user",
        content="Hi",
        created_at=now,
    )

    messages = await repo.list_messages_by_conversation(convo.id)
    print([m.content for m in messages])

# asyncio.run(main(session))  # Provide a real AsyncSession
```

## Caveats
- The adapter does not commit transactions; it only `flush()`es. The caller is responsible for committing/rolling back.
- If neither `db` nor `db_getter` is bound, accessing `db` raises `RuntimeError`.
- `delete_messages_by_conversation()` executes a bulk delete but does not flush/commit itself.
