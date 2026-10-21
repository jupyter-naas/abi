# ChatService

## What it is
Chat orchestration for the Nexus API, responsible for:
- Enforcing IAM scopes and workspace/conversation access.
- Persisting conversations and messages via a `ChatPersistencePort`.
- Resolving an inference provider (explicit provider, agent-configured provider, ABI server/in-process ABI agent, or Ollama fallback).
- Building provider-facing message lists with multi-agent attribution guardrails.
- Injecting best-effort vector-store document context from chat file embeddings.
- Supporting message regeneration (“refresh”) without deleting prior content (uses metadata to hide superseded/replay messages from context).

## Public API

### Data structures
- `ResolvedProvider` (dataclass)
  - Normalized provider configuration used for inference: `id`, `name`, `type`, `enabled`, `endpoint`, `api_key`, `account_id`, `model`, optional `llm_model`.

### Functions
- `render_user_context_block(user, workspace_id=None, conversation_id=None) -> str`
  - Renders a first-turn user profile block (name/email/company/role/bio) plus optional technical fields.

### Class: `ChatService`
Constructor:
- `ChatService(adapter, iam_service=None, auth_adapter=None, skills_service=None)`
  - `adapter`: persistence implementation (`ChatPersistencePort`).
  - `iam_service`: optional IAM integration used by scope/workspace checks.
  - `auth_adapter`: optional `AuthPersistencePort` for injecting user profile context on first turn.
  - `skills_service`: optional `SkillService` for injecting visible skills catalog into prompts.

Prompt/context builders:
- `build_system_prompt(agent, explicit_system_prompt, prior_messages, user_id, workspace_id=None, conversation_id=None, context=None, client_context=None) -> str`
  - Builds a provider system prompt including agent prompt, skills catalog, client-context blocks (Slides/Documents/Sheets/Code), feature context, and multi-agent notice or first-turn user profile.
- `build_abi_injection_preamble(prior_messages, user_id, workspace_id=None, conversation_id=None, context=None, client_context=None) -> str | None`
  - Builds a user-message preamble for in-process ABI agents (since they do not use the external `system_prompt`).
- `build_remote_agent_preamble(prior_messages, user_id, workspace_id=None, conversation_id=None) -> str | None`
  - Builds a minimal preamble for remote agents (first-turn user profile only).
- `build_user_context_addendum(prior_messages, user_id, workspace_id=None, conversation_id=None) -> str`
  - Returns a user-profile addendum only on the first assistant turn (requires `auth_adapter`).

Conversation operations:
- `list_conversations(context, workspace_id, limit, offset) -> list[ChatConversationRecord]`
- `create_conversation(context, workspace_id, title, agent, now, conversation_id=None) -> ChatConversationRecord`
- `get_conversation(context, conversation_id) -> ChatConversationRecord | None`
- `get_conversation_for_user(context, conversation_id) -> ChatConversationRecord | None`
- `get_or_create_conversation(context, conversation_id, workspace_id, request_message, agent, now) -> str`
  - Creates a new conversation if needed; if the requested `conversation_id` exists but belongs to another user, a new conversation is created in the given workspace (requires workspace access).
- `update_conversation(context, conversation_id, now, title=None, pinned=None, archived=None) -> None`
- `touch_conversation(context, conversation_id, now) -> None`
- `delete_conversation_with_messages(context, conversation_id) -> bool`

Message operations:
- `list_messages(context, conversation_id) -> list[ChatMessageRecord]`
- `get_message(context, conversation_id, message_id) -> ChatMessageRecord | None`
- `create_message(context, conversation_id, role, content, created_at, agent=None, message_id=None, metadata=None) -> str`
- `create_streaming_message_pair(context, conversation_id, user_content, assistant_agent, created_at, regenerate_of=None) -> (str, str)`
  - Creates a user message and an empty assistant placeholder; adds regeneration metadata when applicable.
- `update_message_content(context, conversation_id, message_id, content) -> bool`
- `update_message_metadata(context, conversation_id, message_id, metadata) -> bool`
  - Merges into existing JSON metadata (does not replace).
- `mark_message_superseded(context, conversation_id, message_id, superseded_by) -> bool`
  - Marks an assistant message as superseded via metadata.
- `finalize_streaming_response(context, conversation_id, assistant_message_id, content, now) -> None`

Chat completion:
- `complete_chat_request(context, request: CompleteChatInput, now) -> CompleteChatResult`
  - Persists the user message, resolves a provider, builds provider messages/system prompt/preambles, calls provider runtime, persists assistant response, applies regeneration bookkeeping, and touches the conversation.
  - If no provider resolves, returns a static “No AI provider available” message with Ollama setup hints.

Provider/agent utilities:
- `resolve_provider(context, provider, has_images, agent_id=None, workspace_id=None) -> ResolvedProvider | None`
  - Resolution order:
    - Enabled explicit `request.provider` (except `type="remote"` is ignored from client payload).
    - Agent row provider configuration:
      - `remote`: routes via remote agent proxy using `agent.class_name`.
      - `abi`: uses workspace ABI server if configured, else in-process ABI.
      - API-key providers (`xai`, `openai`, `anthropic`, `mistral`, `google`, `openrouter`) via workspace secrets.
    - Ollama fallback if online and has models (chooses vision-capable model when images are present).
- `build_provider_messages_with_agents(context, request, current_agent_id, conversation_id=None) -> list[ProviderMessage]`
  - Builds message list from DB messages when possible (filters out regeneration leftovers), otherwise uses `request.messages`.
  - Adds system guardrails before assistant messages produced by other agents.
  - When regenerating, prepends a regeneration directive to the last user message.

## Configuration/Dependencies
- Persistence / ports:
  - `ChatPersistencePort` for conversation/message CRUD and agent/provider/secret access.
  - `AuthPersistencePort` (optional) for user profile lookups.
- IAM:
  - Uses `ensure_scope` and `ensure_workspace_access` (optionally via `IAMService`).
- Provider runtime:
  - `complete_with_provider(...)`, `ProviderConfig`, `check_ollama_status()`, and Ollama endpoint resolution.
- Secrets:
  - Decrypts workspace secrets via `decrypt_secret_value(...)`.
- Skills:
  - Injects skills catalog via `SkillService.list_visible_skills(...)` (optional).
- Vector context injection (best-effort):
  - Uses `naas_abi.ABIModule.get_instance().engine.services.vector_store` when available.
  - Embeddings via `embed_text(...)` and chat collection naming via `build_chat_collection_name(...)`.

## Usage

```python
import asyncio
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import CompleteChatInput
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext

async def main(adapter):
    svc = ChatService(adapter=adapter)  # optionally pass iam_service/auth_adapter/skills_service

    ctx = RequestContext(actor_user_id="user-123")
    req = CompleteChatInput(
        workspace_id="ws-123",
        conversation_id=None,
        agent="aia",
        message="Hello!",
        messages=[],
        images=None,
        provider=None,
        system_prompt=None,
        regenerate_of=None,
        context=None,
    )

    result = await svc.complete_chat_request(ctx, req, now=datetime.utcnow())
    print(result.assistant_content)

# asyncio.run(main(adapter=...))
```

## Caveats
- Access control:
  - Many methods enforce IAM scope and workspace/conversation access; failures can raise `PermissionError`.
- Regeneration bookkeeping:
  - “Refresh” does not delete prior messages; it writes replay/superseded markers in message metadata and filters those messages out of future model context.
- Vector context injection is best-effort:
  - If the vector store is unavailable, the collection is missing, embedding/search fails, or results don’t match `user_id`, no context is injected.
- Provider fallback:
  - If no provider resolves, `complete_chat_request` returns a static Ollama setup hint response instead of calling any external model.
