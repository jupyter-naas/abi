# Nexus API Hexagonal Migration Tasks

This checklist tracks the migration from endpoint-heavy chat logic to a hexagonal architecture aligned with `starter_hexagonal_domain_template/`.

## Goals

- Move business logic out of `api/endpoints/chat.py` into domain services.
- Keep FastAPI routes as thin primary adapters.
- Keep infra details in secondary adapters only.
- Standardize IAM and chat patterns to match starter conventions.
- Migrate safely with tests first and backward-compatible behavior.

## Current Baseline

- Chat already has service/factory/port/secondary postgres adapter.
- IAM already has service/factory/port/secondary postgres adapter.
- `api/endpoints/chat.py` still contains orchestration and domain logic.
- `chat/service.py` still depends on endpoint/provider concrete functions.

## Phase 0 - Guardrails and Safety

- [ ] Freeze current behavior with regression tests for chat endpoints (`/complete`, `/stream`, conversation CRUD, export).
- [ ] Add fixtures for representative scenarios: no provider, provider error, multi-agent history, ownership denied, workspace denied.
- [ ] Document non-negotiable behavior to preserve (status codes, response fields, SSE event format).

## Phase 1 - Define Domain Contracts (Chat)

- [ ] Create `app/services/chat/chat__schema.py`.
- [ ] Define chat domain DTOs (request/response models used by domain, not transport models).
- [ ] Define chat domain exceptions (`ChatNotFound`, `ChatForbidden`, `ProviderUnavailable`, `InvalidChatInput`, etc.).
- [ ] Define separated ports:
  - [ ] `IChatPersistencePort`
  - [ ] `IChatProviderPort` (complete + stream)
  - [ ] `IChatSearchPort`
  - [ ] `IChatSecretsPort` (if secret decryption/config retrieval needed)
  - [ ] `IChatClockPort` (optional, for deterministic tests)
- [ ] Ensure all secondary adapters implement all abstract methods (raise `NotImplementedError` when unsupported).

## Phase 2 - Make Chat Domain Pure

- [ ] Create `app/services/chat/chat.py` (or refactor existing `service.py`) as domain/application logic using only ports.
- [ ] Remove imports from endpoint modules inside chat domain (especially `_decrypt` from `api/endpoints/secrets.py`).
- [ ] Remove direct provider/tool calls from chat domain (`check_ollama_status`, `execute_tool`, direct stream function calls).
- [ ] Introduce domain use cases:
  - [ ] `complete_chat`
  - [ ] `stream_chat`
  - [ ] `list_conversations`
  - [ ] `create_conversation`
  - [ ] `update_conversation`
  - [ ] `delete_conversation`
  - [ ] `export_conversation`
- [ ] Keep IAM authorization checks in domain/service layer (not endpoints).

## Phase 3 - Primary Adapter Extraction (FastAPI)

- [ ] Create `app/services/chat/adapters/primary/chat__primary_adapter__FastAPI.py`.
- [ ] Move HTTP request parsing/validation and response mapping from `api/endpoints/chat.py` into this primary adapter.
- [ ] Move domain exception to HTTP mapping into an exception handler module (starter style).
- [ ] Keep route paths and payloads backward-compatible.
- [ ] Keep SSE transport concerns in primary adapter; keep stream orchestration decisions in domain service.

## Phase 4 - Secondary Adapter Split (Infra Concerns)

- [ ] Keep postgres adapter focused only on DB reads/writes.
- [ ] Add provider adapter(s) encapsulating completion/streaming backends.
- [ ] Add search adapter encapsulating tool execution.
- [ ] Add secrets adapter encapsulating key lookup/decryption.
- [ ] Wire adapters via `ChatFactory` only.

## Phase 5 - IAM Alignment with Starter Pattern

- [ ] Introduce `app/services/iam/iam__schema.py` and align naming/contracts to starter style (`IIAMDomain`, `IIAMSecondaryAdapter`, etc.).
- [ ] Keep existing behavior and decision reasons unchanged.
- [ ] Ensure endpoint helpers delegate to IAM once (remove duplicate role check in `require_workspace_access`).
- [ ] Add/align IAM domain exceptions and centralized mapping where needed.

## Phase 6 - Handler Wiring

- [ ] Create `app/services/chat/handlers/chat__http_handler.py` to wire domain + adapters + router.
- [ ] Create/align `app/services/iam/handlers/...` only if needed for direct IAM routes.
- [ ] Update app router registration to include new chat handler router.
- [ ] Keep old endpoint module as thin compatibility layer during transition.

## Phase 7 - Testing Strategy (TDD)

### Domain tests

- [ ] Add unit tests for each chat use case with fake ports.
- [ ] Add permission tests proving IAM decisions are enforced in domain.
- [ ] Add stream workflow tests (message pair creation, incremental update, finalization, error partial save).

### Generic secondary adapter suites

- [ ] Create reusable generic test suite(s) for chat persistence adapters (starter pattern).
- [ ] Make postgres chat adapter tests implement the generic suite.
- [ ] Add generic suite(s) for provider/search adapters where practical.

### Primary adapter tests

- [ ] Add tests that router can register and exposes expected paths.
- [ ] Add transport mapping tests (domain errors -> correct HTTP status/body).
- [ ] Add SSE shape tests (`conversation_id`, `content`, `error`, `[DONE]`).

### Regression tests

- [ ] Verify old public API behavior remains compatible.
- [ ] Verify ownership concealment behavior (`404` vs `403`) stays as expected.

## Phase 8 - Incremental Migration Plan

- [ ] Step 1: Migrate `/complete` first.
- [ ] Step 2: Migrate `/stream` second.
- [ ] Step 3: Migrate conversation CRUD and export.
- [ ] Step 4: Remove duplicated helpers from old endpoint module.
- [ ] Step 5: Delete dead code and simplify imports.

## Phase 9 - Operational Validation

- [ ] Run focused tests:
  - [ ] `uv run pytest libs/naas-abi/.../services/chat -v`
  - [ ] `uv run pytest libs/naas-abi/.../services/iam -v`
- [ ] Run broader checks (`make check` or equivalent targeted lint/type checks).
- [ ] Smoke test key API flows locally.

## Definition of Done

- [ ] `api/endpoints/chat.py` is thin (transport-only or compatibility wrapper).
- [ ] Chat business logic lives in chat domain/service modules only.
- [ ] Domain does not import endpoint modules or concrete provider utilities.
- [ ] IAM and chat follow consistent hexagonal conventions.
- [ ] Generic adapter tests exist and pass.
- [ ] Existing API behavior remains backward-compatible unless intentionally changed.

## Suggested Execution Order (Small PRs)

1. Tests baseline + domain contracts.
2. `/complete` migration.
3. `/stream` migration.
4. Adapter split (provider/search/secrets).
5. IAM naming/alignment cleanup.
6. Final cleanup and dead code removal.
