# Chat Persistence Spec (NEXUS API)

## Status

- Draft
- Date: 2026-03-26
- Scope: `apps/nexus/apps/api` chat persistence for conversations/messages with PostgreSQL and LangChain-backed agents

## Goals

- Persist chat conversations and messages reliably for every workspace.
- Enforce strict workspace isolation for all chat read/write operations.
- Align SQL transcript persistence with LangChain/ABI thread memory continuity.
- Support robust streaming persistence with partial recovery on provider failures.

## Non-goals

- Redesigning UI/UX chat presentation.
- Replacing provider adapters.
- Implementing long-term retention policies (covered separately).

## Current Baseline

Implemented today:

- PostgreSQL tables `conversations` and `messages` with ORM models in `app/models.py`.
- Chat endpoints in `app/api/endpoints/chat.py`:
  - `GET /api/chat/conversations`
  - `POST /api/chat/conversations`
  - `GET /api/chat/conversations/{conversation_id}`
  - `PATCH /api/chat/conversations/{conversation_id}`
  - `DELETE /api/chat/conversations/{conversation_id}`
  - `POST /api/chat/complete`
  - `POST /api/chat/stream`
  - `GET /api/chat/conversations/{conversation_id}/export`
- Streaming endpoint pre-creates user + assistant rows and updates assistant content incrementally.
- ABI in-process streaming uses `thread_id` and can set `agent.state.thread_id`.

Known issues/gaps:

- `conversation_id` reuse path in `_get_or_create_conversation` does not enforce workspace access before returning existing conversation.
- `POST /api/chat/stream` returns early when no provider is available, before persisting user message.
- Message payload persistence is incomplete (images/tool traces/provider details are not stored structurally).
- `/complete` provider support is not parity with `/stream` (ABI/openai-compatible differences).
- Frontend state is mostly local-persisted and not fully hydrated from backend conversation history.

## Domain Model

## Context Identity and Lookup Model

Chat persistence is keyed by a strict context chain:

- `tenant_id`
- `organization_id`
- `workspace_id`
- `user_id`
- `thread_id`

Rules:

- `tenant_id`, `organization_id`, and `workspace_id` define what can be loaded.
- `user_id` defines ownership/permissions within the scoped workspace.
- `thread_id` identifies the chat thread within that scoped context and is used to list/replay chats.

Practical mapping in NEXUS:

- `organization_id` is currently available on `workspaces.organization_id`.
- `tenant_id` can be represented as organization scope for now, or added explicitly later.
- `thread_id` should be a first-class persisted key on conversations (or conversation `id` becomes canonical `thread_id`).

### Conversation

Conversation is the durable thread boundary.

Required fields:

- `id` (string, stable conversation key)
- `thread_id` (stable thread identifier for provider memory and chat lookup)
- `tenant_id` (explicit tenant scope, optional if derived from organization)
- `organization_id` (optional denormalized field; can be derived from workspace)
- `workspace_id` (tenant boundary)
- `user_id` (creator)
- `title`
- `agent` (currently selected agent marker)
- `pinned`
- `archived`
- `created_at`, `updated_at`

Optional extension:

- `thread_key` (deprecated alias of `thread_id`; keep only during migration if needed).

### Message

Message is append-only event-like content inside a conversation.

Base fields (existing):

- `id`
- `conversation_id`
- `role` (`user|assistant|system`)
- `content`
- `agent`
- `metadata`
- `created_at`

Required extensions for production persistence:

- `status` (`pending|streaming|completed|error|aborted`)
- `images` (JSON payload of image references/base64 metadata)
- `tool_events` (JSON payload of tool invocations/results)
- `provider_type`
- `provider_model`
- `error_message` (nullable)

Storage recommendation:

- Prefer PostgreSQL `JSONB` for `metadata`, `images`, and `tool_events`.

## Tenant Isolation Rules

Hard requirements:

- Context load order must be enforced: tenant -> organization -> workspace -> user -> thread.
- `thread_id` is only valid inside its workspace/organization/tenant scope.
- Every operation touching a conversation must verify membership against the conversation's `workspace_id`.
- Client-provided `workspace_id` is advisory and cannot bypass conversation-owned workspace checks.
- Any workspace mismatch in request payload vs conversation row returns `403` (or `400` with explicit mismatch detail).

Security invariants:

- A user cannot read, write, patch, stream, export, or delete another workspace's conversation.
- `conversation_id` must never become a cross-tenant write primitive.

## API Behavior Spec

Context-driven lookup behavior:

- List chats uses context filters (`tenant_id`, `organization_id`, `workspace_id`, optional `user_id`) and returns thread headers.
- Thread replay uses `thread_id` + scoped context; never by `thread_id` alone.
- If client sends `thread_id` with mismatched workspace/org/tenant, request is rejected.

### `POST /api/chat/complete`

- If `conversation_id` is absent:
  - Validate `workspace_id` access.
  - Create conversation.
- If `conversation_id` is present:
  - Load conversation.
  - Validate access against conversation workspace.
  - Reject if not found or unauthorized.
- Persist user message before provider call.
- Persist assistant message after provider response.
- On provider failure, persist assistant error payload with `status=error`.

### `POST /api/chat/stream`

- Must perform the same conversation access validation as `/complete`.
- Must persist user message before any early error response.
- Must create assistant placeholder row with `status=streaming`.
- During stream:
  - Update assistant content incrementally (throttled DB writes).
- On completion:
  - Set assistant `status=completed`.
  - Update conversation `updated_at`.
- On failure/abort:
  - Save partial assistant content.
  - Set assistant `status=error|aborted`.
  - Return SSE error event.

### `GET /api/chat/conversations`

- Filter by `workspace_id` and enforce access.
- Optionally filter by `organization_id`, `tenant_id`, `user_id` when exposed.
- Return paginated conversation headers, ordered by `updated_at DESC`.
- Exclude archived by default (optional flag to include archived).

### `GET /api/chat/conversations/{conversation_id}`

- Enforce workspace access from loaded conversation.
- `include_messages=true` returns ordered message timeline with structured metadata.

### `GET /api/chat/threads/{thread_id}` (recommended)

- Resolve thread by (`thread_id`, `workspace_id`) at minimum.
- Enforce workspace access, and organization/tenant scope when provided.
- Return thread header + messages.

### `PATCH /api/chat/conversations/{conversation_id}`

- Allowed fields: `title`, `pinned`, `archived`.
- Enforce workspace access.

### `DELETE /api/chat/conversations/{conversation_id}`

- Enforce workspace access.
- Delete conversation and cascade messages.

## LangChain / ABI Memory Alignment

Requirement:

- SQL persistence and LangChain thread memory must represent the same logical conversation.

Default strategy:

- Use `thread_id` as memory key for all messages in a conversation.
- In phase 1, `thread_id = conversation_id` to avoid a breaking change.

Alternative strategy:

- Use `conversation_id:agent_id` if strict per-agent memory partitioning is required.

Decision for this phase:

- Adopt `thread_id` as canonical memory key, with `thread_id = conversation_id` initially.

## Migrations

Create a migration to evolve `messages`:

- Add `status` column with default `completed` (or `pending` for new placeholders).
- Add `images` (`JSONB` preferred).
- Add `tool_events` (`JSONB` preferred).
- Add `provider_type`, `provider_model`, `error_message`.
- Convert `metadata` from `TEXT` JSON-string to `JSONB` (or keep text temporarily with dual-read).

Create a migration to evolve `conversations`:

- Add `thread_id` (unique within workspace, or globally unique if preferred).
- Optionally add denormalized `organization_id` and `tenant_id` for faster scoped queries.
- Backfill existing rows with `thread_id = id`.

Index recommendations:

- `messages(conversation_id, created_at)`
- `messages(status)`
- `conversations(workspace_id, updated_at DESC)`
- `conversations(workspace_id, thread_id)`
- Optional scoped index: `conversations(tenant_id, organization_id, workspace_id, user_id, updated_at DESC)`

## Error Handling

- Never drop user input silently.
- If provider is unavailable, persist a deterministic assistant error message and return actionable diagnostics.
- For stream interruption, preserve partial assistant content and final status.

## Observability

Log structured events with correlation keys:

- `workspace_id`
- `conversation_id`
- `message_id`
- `provider_type`
- `agent`
- `status`

Add counters (or logs) for:

- stream started/completed/failed
- provider resolution failures
- authorization denials

## Test Plan (TDD)

Add/extend tests in `apps/api/tests/test_chat.py` and security tests:

1. `complete` rejects write to foreign-workspace conversation (`403`).
2. `stream` rejects write to foreign-workspace conversation (`403`).
3. `stream` persists user message even when provider unavailable.
4. `stream` persists partial assistant content and error status on provider exception.
5. `complete` and `stream` persist provider metadata fields.
6. `get conversation` returns ordered message timeline with metadata/images.
7. Scoped lookup rejects `thread_id` access outside tenant/org/workspace context.
8. Listing chats by context + `thread_id` returns only authorized threads.

## Rollout Plan

Phase 1 (security + correctness):

- Fix conversation access checks in all write paths.
- Ensure `stream` persists user prompt before early exit.

Phase 2 (schema + richer persistence):

- Apply message schema migration.
- Persist structured metadata/images/provider fields.

Phase 3 (parity + frontend hydration):

- Align provider handling between `/complete` and `/stream`.
- Hydrate frontend conversation history from backend APIs.

## Acceptance Criteria

- No cross-workspace chat access is possible via `conversation_id` reuse.
- Every submitted user message is persisted, including stream failure cases.
- Assistant messages have explicit terminal status (`completed|error|aborted`).
- Conversation replay reproduces the persisted timeline deterministically.
- LangChain/ABI thread continuity follows conversation boundaries.
- Chat loading follows scoped context (`tenant_id`, `organization_id`, `workspace_id`) and uses `thread_id` for thread selection.
