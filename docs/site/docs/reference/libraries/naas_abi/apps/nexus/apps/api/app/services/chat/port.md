# ChatPersistencePort

## What it is
- Defines the async persistence interface (“port”) for a chat service.
- Provides dataclass record types for conversations, messages, agents, inference servers, and secrets.
- Intended to be implemented by an infrastructure adapter (e.g., database layer).

## Public API

### Records (dataclasses)
- `ChatConversationRecord`
  - Fields: `id`, `workspace_id`, `user_id`, `title`, `agent`, `created_at`, `updated_at`, `pinned=False`, `archived=False`
- `ChatMessageRecord`
  - Fields: `id`, `conversation_id`, `role`, `content`, `agent: str|None`, `metadata_: str|None`, `created_at`
- `ChatAgentRecord`
  - Fields: `id`, `workspace_id`, `name`, `class_name: str|None`, `model_id: str|None`, `provider: str|None`
- `ChatInferenceServerRecord`
  - Fields: `id`, `workspace_id`, `name`, `type`, `endpoint`, `api_key: str|None`
- `ChatSecretRecord`
  - Fields: `encrypted_value`

### Port (abstract base class)
`class ChatPersistencePort(ABC)` — async interface to be implemented.

#### Conversation operations
- `list_conversations_by_workspace(workspace_id, user_id, limit, offset) -> list[ChatConversationRecord]`
  - List conversations for a workspace/user with pagination.
- `create_conversation(conversation_id, workspace_id, user_id, title, agent, now) -> ChatConversationRecord`
  - Create a new conversation.
- `get_conversation_by_id(conversation_id) -> ChatConversationRecord | None`
  - Fetch conversation by id.
- `get_conversation_by_id_for_user(conversation_id, user_id) -> ChatConversationRecord | None`
  - Fetch conversation by id, scoped to a user.
- `update_conversation_agent(conversation_id, agent, now) -> None`
  - Update the agent associated with a conversation.
- `update_conversation_fields(conversation_id, now, title=None, pinned=None, archived=None) -> None`
  - Update selected conversation fields.
- `touch_conversation(conversation_id, now) -> None`
  - Update “last updated” timestamp (implementation-defined).
- `delete_conversation(conversation_id) -> bool`
  - Delete conversation; returns success flag.

#### Message operations
- `list_messages_by_conversation(conversation_id) -> list[ChatMessageRecord]`
  - List messages for a conversation.
- `create_message(message_id, conversation_id, role, content, created_at, agent=None) -> None`
  - Create a message.
- `delete_messages_by_conversation(conversation_id) -> None`
  - Delete all messages for a conversation.
- `update_message_content(message_id, content) -> bool`
  - Update message content; returns success flag.

#### Agent / server / secret operations
- `get_agent_by_id(agent_id) -> ChatAgentRecord | None`
  - Fetch agent by id.
- `list_agent_names_by_ids(agent_ids: set[str]) -> dict[str, str]`
  - Resolve agent id → agent name.
- `get_enabled_workspace_abi_server(workspace_id) -> ChatInferenceServerRecord | None`
  - Fetch the enabled inference server for a workspace.
- `get_workspace_secret(workspace_id, key) -> ChatSecretRecord | None`
  - Fetch a workspace secret by key.

## Configuration/Dependencies
- Standard library only:
  - `abc.ABC`, `abc.abstractmethod`
  - `dataclasses.dataclass`
  - `datetime.datetime`
- All port methods are `async` and must be awaited by callers.

## Usage

```python
import asyncio
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.chat.port import (
    ChatPersistencePort,
    ChatConversationRecord,
)

class InMemoryChatPersistence(ChatPersistencePort):
    def __init__(self):
        self._conversations = {}

    async def list_conversations_by_workspace(self, workspace_id, user_id, limit, offset):
        items = [
            c for c in self._conversations.values()
            if c.workspace_id == workspace_id and c.user_id == user_id
        ]
        return items[offset: offset + limit]

    async def create_conversation(self, conversation_id, workspace_id, user_id, title, agent, now):
        rec = ChatConversationRecord(
            id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            agent=agent,
            created_at=now,
            updated_at=now,
        )
        self._conversations[conversation_id] = rec
        return rec

    async def get_conversation_by_id(self, conversation_id):
        return self._conversations.get(conversation_id)

    async def get_conversation_by_id_for_user(self, conversation_id, user_id):
        c = self._conversations.get(conversation_id)
        return c if c and c.user_id == user_id else None

    async def update_conversation_agent(self, conversation_id, agent, now): ...
    async def update_conversation_fields(self, conversation_id, now, title=None, pinned=None, archived=None): ...
    async def touch_conversation(self, conversation_id, now): ...
    async def delete_conversation(self, conversation_id): ...
    async def list_messages_by_conversation(self, conversation_id): ...
    async def create_message(self, message_id, conversation_id, role, content, created_at, agent=None): ...
    async def delete_messages_by_conversation(self, conversation_id): ...
    async def update_message_content(self, message_id, content): ...
    async def get_agent_by_id(self, agent_id): ...
    async def list_agent_names_by_ids(self, agent_ids): ...
    async def get_enabled_workspace_abi_server(self, workspace_id): ...
    async def get_workspace_secret(self, workspace_id, key): ...

async def main():
    store = InMemoryChatPersistence()
    now = datetime.utcnow()
    conv = await store.create_conversation("c1", "w1", "u1", "Hello", "agent-1", now)
    found = await store.get_conversation_by_id("c1")
    print(conv.id, found.title)

asyncio.run(main())
```

## Caveats
- This file specifies interfaces and record shapes only; behavior (e.g., ordering, filtering semantics, encryption) is defined by implementations.
- All methods are asynchronous; synchronous implementations should be wrapped appropriately.
