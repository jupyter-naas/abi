# chat__schema

## What it is
- A small schema module defining:
  - Typed chat roles
  - Domain exceptions for chat operations
  - Immutable (`frozen=True`) dataclasses used as inputs/outputs for a “complete chat” operation

## Public API

### Types
- `ChatRole = Literal["user", "assistant", "system"]`
  - Allowed roles for chat messages.

### Exceptions
- `ChatDomainError(Exception)`
  - Base exception for chat domain errors.
- `ChatNotFound(ChatDomainError)`
  - Indicates a chat/conversation was not found.
- `ChatForbidden(ChatDomainError)`
  - Indicates access is forbidden.
- `InvalidChatInput(ChatDomainError)`
  - Indicates invalid input data.
- `ProviderUnavailable(ChatDomainError)`
  - Indicates the configured provider is unavailable.

### Dataclasses (immutable)
- `ChatInputMessage`
  - Represents a message in the conversation history.
  - Fields:
    - `role: ChatRole`
    - `content: str`
    - `images: list[str] | None = None`
    - `agent: str | None = None`
- `ChatProviderConfigInput`
  - Provider configuration passed to chat completion.
  - Fields:
    - `id: str`
    - `name: str`
    - `type: str`
    - `enabled: bool`
    - `model: str`
    - `endpoint: str | None = None`
    - `api_key: str | None = None`
    - `account_id: str | None = None`
- `CompleteChatInput`
  - Input payload for a chat completion request.
  - Fields:
    - `message: str`
    - `agent: str`
    - `workspace_id: str | None = None`
    - `conversation_id: str | None = None`
    - `messages: list[ChatInputMessage] = []`
    - `images: list[str] | None = None`
    - `provider: ChatProviderConfigInput | None = None`
    - `system_prompt: str | None = None`
    - `context: dict | None = None`
    - `search_enabled: bool = False`
- `CompleteChatResult`
  - Output payload returned from a chat completion operation.
  - Fields:
    - `conversation_id: str`
    - `assistant_message_id: str`
    - `assistant_content: str`
    - `assistant_agent: str`
    - `provider_used: str | None`
    - `created_at: datetime`
    - `context_sources: list[str] = []`

## Configuration/Dependencies
- Standard library only:
  - `dataclasses`, `datetime`, `typing.Literal`
- No runtime configuration in this module.

## Usage
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import (
    ChatInputMessage,
    ChatProviderConfigInput,
    CompleteChatInput,
    CompleteChatResult,
)

provider = ChatProviderConfigInput(
    id="prov_1",
    name="MyProvider",
    type="openai",
    enabled=True,
    model="gpt-4.1-mini",
    endpoint=None,
    api_key=None,
    account_id=None,
)

inp = CompleteChatInput(
    message="Hello!",
    agent="default-agent",
    workspace_id="ws_123",
    messages=[ChatInputMessage(role="user", content="Hi")],
    provider=provider,
    search_enabled=False,
)

# Example of what a completion result object could look like:
res = CompleteChatResult(
    conversation_id="conv_1",
    assistant_message_id="msg_2",
    assistant_content="Hello! How can I help?",
    assistant_agent="default-agent",
    provider_used=provider.name,
    created_at=datetime.utcnow(),
)
```

## Caveats
- All dataclasses are `frozen=True` (immutable); you must create new instances to “modify” values.
- `ChatRole` is restricted to `"user"`, `"assistant"`, or `"system"`.
