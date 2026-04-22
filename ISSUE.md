# Feature Spec: My Drive + Chat File Upload Workflow

## Problem Statement
Nexus currently supports a workspace-level file manager for shared documents. We now need a user-level personal storage space (`My Drive`) and a chat file ingestion flow so users can upload/select files and have the LLM answer using file content.

## Goals
- Add a persistent personal file space (`My Drive`) scoped by `user_id` and shared across all workspaces.
- Allow chat users to upload files or select existing files from `My Drive`.
- Process selected files into markdown, chunk, embed, and store vectors in a chat-scoped vector collection.
- Reuse previously computed embeddings for identical files (`sha256`) and embedding config (`model`, `dimension`) to avoid recomputation.
- Update chat agent retrieval behavior to automatically use chat vectors when available.
- Provide clear UI feedback for ingestion progress and completion.

## Out of Scope (for this iteration)
- Cross-user sharing of `My Drive` files.
- Workspace-level permissions redesign.
- Advanced document versioning and deduplication.
- Citation rendering in chat answers.

## User Stories
1. As a user, I can access `My Drive` in any workspace and see the same personal files.
2. As a user, I can upload files from chat without manually moving them elsewhere.
3. As a user, I can pick an existing file from `My Drive` when chatting.
4. As a user, I can see ingestion progress (upload, conversion, chunking, embedding, ready/failed).
5. As a user, once processing is complete, I can ask questions and get answers grounded in uploaded file content.

## Functional Requirements

### 1) My Drive Storage Model
- Introduce a per-user storage namespace in object storage.
- Namespace key pattern: `my-drive/{user_id}/...`.
- Chat uploads default path: `my-drive/{user_id}/uploads/{filename}`.
- `My Drive` is not partitioned by workspace.
- Access control: only owner (`user_id`) can list/read/write/delete their `My Drive` objects.

### 2) Chat File Ingestion Flow
When a user uploads/selects a file in chat:
1. File is resolved (new upload or existing `My Drive` path).
2. File is converted to markdown (or parsed text normalized to markdown).
3. Service computes `sha256` from source file content.
4. Service checks embedding cache key: (`sha256`, `embedding_model`, `embedding_dimension`).
5. If cache hit:
   - Reuse cached chunks + vectors.
   - Materialize/relink them into current chat collection without recomputing embeddings.
6. If cache miss:
   - Markdown is chunked.
   - Chunks are embedded using current embedding provider.
   - Cache is written using the cache key.
7. Embeddings are upserted to vector store collection named from chat/thread id.
8. Chat receives status updates and final success/failure event.

### 3) Embedding Cache Requirements
- Cache identity key must be: `sha256(file_content) + embedding_model + embedding_dimension`.
- Cache is global (not scoped per workspace or chat) and reusable across user chats.
- Cache must store enough payload to avoid full recompute:
  - normalized markdown (optional but recommended)
  - chunk list (text + order)
  - vector embeddings per chunk
  - metadata about model/version/dimension and chunking strategy
- Cache lookup should happen before chunking/embedding starts.
- Cache writes must be idempotent (safe under duplicate concurrent requests).
- Cache invalidation strategy:
  - no invalidation needed for immutable key (`sha256` + model + dimension)
  - new model version/dimension naturally creates a new cache entry.

### 4) Vector Collection Convention
- Collection identifier: `chat_{thread_id}`.
- Metadata per chunk should include at least:
  - `thread_id`
  - `user_id`
  - `source_path`
  - `filename`
  - `file_sha256`
  - `embedding_model`
  - `embedding_dimension`
  - `cache_hit` (boolean)
  - `chunk_index`
  - `ingested_at`

### 5) Agent Retrieval Behavior
On each agent invocation:
1. Read `thread_id` from invocation context.
2. Check whether corresponding vector collection exists.
3. If collection exists:
   - Run similarity search using user query.
   - Retrieve top-k relevant chunks.
   - Inject chunks as context into prompt.
4. If collection does not exist (or retrieval fails):
   - Continue normal chat flow without retrieval.
5. Retrieval must be best-effort and must not block normal response flow on non-critical errors.

### 6) UI/UX Requirements
- In chat composer, allow:
  - Upload new file.
  - Select file from `My Drive`.
- After action starts, show processing states:
  - `uploading`
  - `hashing`
  - `cache_lookup`
  - `converting` (if cache miss path requires it)
  - `chunking` (if cache miss)
  - `vectorizing` (if cache miss)
  - `reusing_vectors` (if cache hit)
  - `ready` or `failed`
- On `ready`, add system confirmation message in chat.
- On `failed`, show actionable error with retry option.

## Non-Functional Requirements
- Security: enforce strict user isolation on `My Drive` storage paths.
- Performance target: first file usable in chat within acceptable UX window (define SLA during implementation).
- Performance target: cache-hit ingestion should be significantly faster than cache-miss ingestion (define SLA during implementation).
- Reliability: ingestion is idempotent for repeated processing requests on the same file/thread pair.
- Reliability: cache lookup/write must be safe under concurrency.
- Lifecycle: no retention cleanup is required for chat vector collections in this iteration.
- Observability: structured logs + metrics for each ingestion stage and retrieval usage.

## API/Service Changes (High Level)
- File service:
  - Support user-scoped personal root (`My Drive`).
  - Support chat upload destination (`uploads/`).
- Ingestion pipeline service:
  - Orchestrate hash -> cache lookup -> (convert -> chunk -> embed on miss) -> upsert.
  - Emit progress events consumable by chat UI.
  - Provide cache read/write via a dedicated port (to keep domain logic technology-agnostic).
- Cache service (`naas_abi_core.services.cache.CacheService`):
  - Evolve from decorator-oriented helper into a first-class platform service accessible from domains/pipelines.
  - Support centralized object-storage-backed cache namespace for embedding cache payloads.
  - Expose explicit read/write APIs for large JSON/binary payloads and existence checks.
  - Preserve adapter-based design (port + adapters) to keep business logic technology-agnostic.
- Agent service (`Agent.py`):
  - Add retrieval middleware/step keyed by `thread_id`.
  - Graceful fallback when collection is missing.

## Reuse of Existing Document Domain
- Candidate module: `libs/naas-abi-marketplace/naas_abi_marketplace/domains/document/`.
- Existing ingestion code already computes `sha256` in `FilesIngestionPipeline`, which can be reused as the cache identity basis.
- Existing conversion pipelines (`PdfToMarkdownPipeline`, `DocxToMarkdownPipeline`, `PptxToMarkdownPipeline`) can be reused in cache-miss path.
- Recommended approach:
  - Create a new embedding-cache domain contract (port + model) near document pipelines.
  - Implement central object-storage cache adapter and wire it through core cache service.
  - Keep storage/vector backend implementation in adapters.
  - Keep orchestration logic in domain/pipeline layer.

## Data and Event Contracts (Draft)

### Ingestion Request
- `thread_id`
- `user_id`
- `source_type` (`upload` | `my_drive`)
- `source_path`
- `filename`
- `embedding_model`
- `embedding_dimension`

### Embedding Cache Key
- `file_sha256`
- `embedding_model`
- `embedding_dimension`

### Embedding Cache Entry
- `file_sha256`
- `embedding_model`
- `embedding_dimension`
- `chunking_strategy_version`
- `markdown_content` (optional)
- `chunks` (ordered)
- `vectors` (aligned with chunks)
- `created_at`
- `updated_at`

### Ingestion Progress Event
- `thread_id`
- `file_id` or `source_path`
- `status` (`uploading|hashing|cache_lookup|converting|chunking|vectorizing|reusing_vectors|ready|failed`)
- `progress` (optional percentage)
- `message` (human-readable)
- `error_code` (only on failure)
- `cache_hit` (optional boolean)

## Edge Cases
- Unsupported file type -> fail fast with clear error.
- Empty/near-empty extracted content -> mark failed with explanation.
- Large file timeout -> mark failed, allow retry.
- Duplicate uploads in same thread -> define overwrite/upsert semantics (default: upsert by chunk id).
- Same file, different embedding model/dimension -> cache miss by design.
- Cache entry exists but chunking strategy version mismatches current strategy -> treat as miss.
- Thread deleted -> cleanup policy for associated vector collection (to define).

## Acceptance Criteria
1. User can open `My Drive` from multiple workspaces and sees same personal files.
2. User can upload a file from chat and it is saved under `my-drive/{user_id}/uploads/`.
3. User can select a `My Drive` file from chat and trigger ingestion.
4. UI shows end-to-end ingestion progress and final state.
5. Re-ingesting the same file with same model/dimension in another chat reuses cached vectors (no re-embedding).
6. On ready state, asking relevant questions uses document-grounded context.
7. If no chat collection exists, agent still replies via normal flow.
8. Access checks prevent user A from reading user B `My Drive` files.
9. A single chat can ingest multiple files, all available through the same `chat_{thread_id}` collection.

## Implementation Notes
- Prefer asynchronous ingestion with status events rather than blocking request/response.
- Keep domain contracts technology-agnostic (ports), adapters for object storage/vector store/event bus.
- Add tests for:
  - `My Drive` authorization and path resolution.
  - Cache key generation (`sha256`, model, dimension).
  - Cache hit path (no conversion/chunking/embedding calls).
  - Cache miss path (conversion/chunking/embedding + cache write).
  - Concurrent requests on same cache key (single write, safe reuse).
  - Ingestion pipeline status transitions.
  - Agent retrieval enabled/disabled flows.

## Open Questions
1. Should the object-storage-backed cache be delivered in this feature scope, or split into a dedicated foundational initiative with a temporary local adapter first?
2. What payload format should be canonical in object storage for embedding cache entries (single JSON, JSON + binary blobs, or compressed archive)?

## Decisions Log
- Single chat supports multiple files in one collection: **Yes**.
- Chat collection naming: **`chat_{thread_id}`**.
- Retention/cleanup for old chat vector collections: **None for now**.
- Embedding cache physical location: **central object storage namespace shared platform-wide**.
- Citation rendering in UI: **Not in this iteration** (kept out of scope).

## Delivery Plan (Phase Split)

### Phase 1 - Foundational Cache Service (Core)
Objective: make cache a first-class reusable platform service in `naas-abi-core`.

Scope:
- Introduce object-storage-backed cache adapter under `naas_abi_core.services.cache`.
- Define central namespace convention, for example:
  - `cache/embeddings/{sha256}/{embedding_model}/{embedding_dimension}/...`
- Support explicit APIs for read/write/delete/exists for large payloads.
- Add serialization contract for embedding cache entries (versioned schema).
- Add concurrency-safe write semantics for same cache key.
- Keep `CacheService` backward compatible with existing decorator usage.

Suggested architecture:
- Port: extend `ICacheAdapter`/`ICacheService` contracts where needed for explicit service usage.
- Adapter: object storage implementation (secondary adapter).
- Factory/config: enable selecting cache adapter via existing configuration pattern.
- Tests:
  - adapter contract tests
  - TTL/exists/get/set behavior tests
  - large payload and concurrent write scenarios

Phase 1 acceptance criteria:
1. Any domain can access cache service through engine/services wiring.
2. Object-storage adapter can persist and retrieve JSON/binary cache entries.
3. Cache keys are deterministic and stable.
4. Concurrent writes on same key are safe and idempotent.
5. Existing cache decorator-based usages remain functional.

### Phase 2 - Chat Ingestion + Vector Reuse (Feature)
Objective: implement file ingestion in chat using phase-1 cache service.

Scope:
- Add `My Drive` user-scoped storage behavior.
- Implement chat upload/select flow with progress states.
- Compute file `sha256` and lookup embedding cache by
  (`sha256`, `embedding_model`, `embedding_dimension`).
- Cache miss path: convert -> chunk -> embed -> cache write -> upsert to `chat_{thread_id}`.
- Cache hit path: reuse vectors/chunks -> upsert/link to `chat_{thread_id}` without re-embedding.
- Update `Agent.py` to run retrieval best-effort from `chat_{thread_id}` collection.

Phase 2 acceptance criteria:
1. User can ingest files from upload or `My Drive` selection.
2. Re-ingesting same file with same model/dimension in another chat avoids re-embedding.
3. Multiple files are supported in the same `chat_{thread_id}` collection.
4. Chat agent uses retrieved chunks when collection exists.
5. Normal chat flow continues when no collection exists or retrieval fails.

## Suggested Execution Order
1. Implement Phase 1 object-storage cache adapter + service wiring in `naas-abi-core`.
2. Add embedding cache schema/versioning and tests.
3. Integrate Phase 2 ingestion pipeline with cache hit/miss orchestration.
4. Add agent retrieval integration for `chat_{thread_id}`.
5. Add end-to-end tests for cross-chat reuse behavior.

## Phase 1 Technical Blueprint (Concrete)

### A) Core File-Level Plan (`naas-abi-core`)
- Update `libs/naas-abi-core/naas_abi_core/services/cache/CachePort.py`:
  - keep existing generic cache contracts;
  - add optional `set_if_absent(key, value) -> bool` on `ICacheAdapter` for concurrency-safe first-write behavior;
  - add `delete(key)` on `ICacheService` contract (already present on adapter).
- Update `libs/naas-abi-core/naas_abi_core/services/cache/CacheService.py`:
  - expose explicit non-decorator service APIs as first-class usage (`get`, `set_json`, `set_binary`, `exists`, `delete`);
  - add `set_json_if_absent` and `set_binary_if_absent` wrappers when adapter supports `set_if_absent`;
  - keep current decorator behavior fully backward compatible.
- Add `libs/naas-abi-core/naas_abi_core/services/cache/adapters/secondary/CacheObjectStorageAdapter.py`:
  - implement `ICacheAdapter` on top of `IObjectStorageDomain`;
  - store one serialized cache entry per key under object storage namespace;
  - use create-if-absent semantics where backend supports it, else optimistic write with collision check.
- Update `libs/naas-abi-core/naas_abi_core/services/cache/CacheFactory.py`:
  - keep `CacheFS_find_storage`;
  - add object-storage constructor, e.g. `CacheObjectStorage(cache_prefix: str = "cache")`.
- Add tests:
  - `libs/naas-abi-core/naas_abi_core/services/cache/adapters/secondary/CacheObjectStorageAdapter_test.py`
  - extend `libs/naas-abi-core/naas_abi_core/services/cache/CacheService_test.py` for explicit service API use-cases.

### B) Cache Key and Storage Conventions
- Canonical key string for embedding entries:
  - `embeddings:{sha256}:{embedding_model}:{embedding_dimension}`
- Object storage path convention (adapter internal):
  - `<cache_prefix>/entries/{sha256(key_string)}.json`
- Keep original key string inside payload (`CachedData.key`) so adapter hash strategy is transparent to callers.

### C) Payload Shape (for Embedding Cache Entry)
- Define embedding payload schema in marketplace domain (not in core generic cache), then store via `set_json`:
  - `schema_version`
  - `file_sha256`
  - `embedding_model`
  - `embedding_dimension`
  - `chunking_strategy_version`
  - `markdown_content` (optional)
  - `chunks` (ordered)
  - `vectors` (ordered)
  - `created_at`

### D) Service Wiring Plan
- Wire one shared cache service instance in engine/services initialization using object storage adapter.
- Keep local FS cache adapter available for tests and offline local development.
- Configuration target:
  - `cache.adapter = object_storage | fs`
  - `cache.prefix = cache`

### E) Concurrency Strategy
- Preferred: adapter-level atomic `set_if_absent`.
- Fallback (if backend lacks atomic primitive):
  1. `exists(key)` check
  2. write with temporary object name
  3. attempt finalize only if target still absent
  4. on race/loss, discard temporary object and treat as cache hit path.

### F) Minimal Test Matrix (Phase 1)
1. `CacheObjectStorageAdapter` set/get roundtrip for `TEXT`, `JSON`, `BINARY`, `PICKLE`.
2. `exists` and `delete` behavior matches `CacheFSAdapter` contract.
3. `set_if_absent` returns `True` first time, `False` on duplicate key.
4. `CacheService` explicit APIs work without decorator usage.
5. Decorator path remains backward compatible.
6. TTL expiration behavior unchanged.
7. Concurrent writes with same key result in single persisted winner and valid payload.

### G) Phase 2 Integration Hook Points
- In ingestion orchestration, call cache service with canonical key before conversion/chunking/embedding.
- On hit, deserialize payload and proceed directly to vector upsert into `chat_{thread_id}`.
- On miss, compute pipeline, write cache via `set_json_if_absent`, then upsert.

### H) Proposed Work Items (Implementable)
1. Add/adjust core cache contracts and service methods.
2. Implement object-storage cache adapter + tests.
3. Add cache factory wiring and config plumbing.
4. Add marketplace embedding cache schema model + validation.
5. Integrate cache-hit/miss orchestration in chat ingestion pipeline.
