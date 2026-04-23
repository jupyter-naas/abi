# ChatService

## What it is
`ChatService` orchestrates chat conversations and messages for the Nexus API:
- Enforces IAM scopes and workspace access.
- Persists conversations/messages through a `ChatPersistencePort`.
- Resolves an AI provider (agent-configured, ABI server/in-process, or Ollama fallback).
- Builds provider-facing message lists, including multi-agent attribution guardrails.
- Optionally injects vector-store document context from chat file embeddings.
- Can run web search via tool execution when requested/implicit.

## Public API

### Data structures
- `ResolvedProvider`
  - Normalized provider configuration used for inference (`id`, `name`, `type`, `endpoint`, `api_key`, `model`, etc.).

### Class: `ChatService`
Constructor:
- `ChatService(adapter: ChatPersistencePort, iam_service: IAMService | None = None)`
  - `adapter`: persistence implementation.
  - `iam_service`: optional IAM integration used by `ensure_scope` / `ensure_workspace_access`.

Conversation operations:
- `list_conversations(context, workspace_id, limit, offset) -> list[ChatConversationRecord]`
  - Lists user conversations in a workspace.
- `create_conversation(context, workspace_id, title, agent, now, conversation_id=None) -> ChatConversationRecord`
  - Creates a conversation (generates `conv-...` id if not provided).
- `get_conversation(context, conversation_id) -> ChatConversationRecord | None`
  - Fetches a conversation for the current user (requires `chat.conversation.read`).
- `get_conversation_for_user(context, conversation_id) -> ChatConversationRecord | None`
  - Same behavior as `get_conversation`.
- `get_or_create_conversation(context, conversation_id, workspace_id, request_message, agent, now) -> str`
  - Ensures a usable conversation id (creates new or recreates when id belongs to another user, subject to workspace access).
- `update_conversation(context, conversation_id, now, title=None, pinned=None, archived=None) -> None`
  - Updates mutable conversation fields.
- `touch_conversation(context, conversation_id, now) -> None`
  - Updates conversation “last activity” timestamp.
- `delete_conversation_with_messages(context, conversation_id) -> bool`
  - Deletes all messages then deletes the conversation.

Message operations:
- `list_messages(context, conversation_id) -> list[ChatMessageRecord]`
  - Lists messages for a conversation.
- `create_message(context, conversation_id, role, content, created_at, agent=None, message_id=None) -> str`
  - Creates a message (generates `msg-...` id if not provided).
- `create_streaming_message_pair(context, conversation_id, user_content, assistant_agent, created_at) -> (str, str)`
  - Creates a user message plus an empty assistant placeholder message.
- `update_message_content(context, conversation_id, message_id, content) -> bool`
  - Updates a message content string.
- `finalize_streaming_response(context, conversation_id, assistant_message_id, content, now) -> None`
  - Writes final assistant content and touches the conversation.

Chat completion:
- `complete_chat_request(context, request: CompleteChatInput, now) -> CompleteChatResult`
  - Persists the user message, resolves a provider, calls provider chat completion, persists assistant message, returns result.
  - Adds multi-agent notice when prior assistant messages exist.
  - May inject retrieved document context from a vector index (if available).
  - If no provider is available, returns a helpful “No AI provider available” message.

Provider and agent utilities:
- `resolve_provider(context, provider, has_images, agent_id=None, workspace_id=None) -> ResolvedProvider | None`
  - Resolution order:
    - Explicit enabled provider passed in `request.provider`.
    - Agent-based provider configuration (including ABI server/in-process ABI, or API-key providers via workspace secrets).
    - Ollama auto fallback if local Ollama is online and has models.
- `build_provider_messages_with_agents(context, request, current_agent_id, conversation_id=None) -> list[ProviderMessage]`
  - Builds provider messages from persisted conversation messages (preferred) or `request.messages`.
  - Adds system messages to prevent attributing other agents’ assistant messages to the current agent.
- `run_search_if_needed(message: str, search_enabled: bool) -> str | None`
  - Uses `execute_tool("search_web", ...)` (Wikipedia and DuckDuckGo) when enabled or implicitly requested.
  - Returns a formatted string containing results, or `None` if search should not run.

## Configuration/Dependencies
- Persistence:
  - Requires an implementation of `ChatPersistencePort` providing conversation/message CRUD, agent/provider/secret accessors.
- IAM:
  - Uses `ensure_scope` and `ensure_workspace_access`.
  - `iam_service` is passed through to these checks.
- Provider runtime:
  - Uses `complete_chat` (imported as `complete_with_provider`), `ProviderConfig`, `check_ollama_status`, and `execute_tool`.
- Secrets:
  - Decrypts workspace secrets via `decrypt_secret_value` for API-key-based providers.
- Vector context injection (best-effort):
  - Uses `naas_abi.ABIModule.get_instance().engine.services.vector_store` if available.
  - Uses chat file embedding helpers: `build_chat_collection_name`, `embed_text`, and defaults (`DEFAULT_EMBEDDING_MODEL`, `DEFAULT_EMBEDDING_DIMENSION`).

## Usage

### Minimal async example (provider, persistence, and IAM are environment-specific)
```python
import asyncio
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import CompleteChatInput
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext

async def main(adapter):
    svc = ChatService(adapter=adapter, iam_service=None)

    ctx = RequestContext(actor_user_id="user-123")  # fields may vary in your implementation
    req = CompleteChatInput(
        workspace_id="ws-123",
        conversation_id=None,
        agent="aia",
        message="Hello",
        messages=[],
        images=None,
        provider=None,
        system_prompt=None,
    )

    result = await svc.complete_chat_request(ctx, req, now=datetime.utcnow())
    print(result.assistant_content)

# asyncio.run(main(adapter=...))
```

## Caveats
- Many methods enforce IAM scopes and workspace/conversation access; failures raise `PermissionError` or deny access via IAM helpers.
- Vector context injection is best-effort and silently disabled if:
  - `ABIModule` is unavailable, vector store errors occur, collection does not exist, or embeddings/search fail.
  - Retrieved chunks are filtered to `metadata["user_id"] == context.actor_user_id`.
- `complete_chat_request` can return an error-formatted assistant response string if provider inference raises an exception.
- If no provider can be resolved, responses are a static “No AI provider available” message (with Ollama setup hints).
