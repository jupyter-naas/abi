# `ChatFileIngestionService`

## What it is
A service that:
- Uploads a user file into object storage (under `my-drive/<user_id>/uploads/`) and/or reads an existing stored file.
- Converts supported file types to Markdown.
- Chunks the Markdown and generates embeddings for each chunk.
- Caches chunks/vectors by file hash + embedding settings.
- Upserts chunk vectors and metadata into a vector store collection tied to a chat conversation.
- Optionally reports progress via a callback.

## Public API

### Types
- **`ProgressCallback`**: `Callable[[str, int], None]`
  - Callback signature receiving `(stage_name, overall_progress_pct)`.

### Exceptions
- **`ChatFileIngestionError`**
  - Raised for invalid input, unsupported files, missing dependencies, empty extraction, and ingestion inconsistencies.

### Data classes
- **`ChatFileIngestionResult`**
  - Fields:
    - `conversation_id`, `source_path`, `collection_name`
    - `file_sha256`
    - `cache_hit`
    - `chunks_count`
    - `statuses` (list of stage names encountered)
    - `embedding_model`, `embedding_dimension`

### Class: `ChatFileIngestionService`
Constructor:
- `__init__(object_storage: ObjectStorageService, vector_store: VectorStoreService, cache_service: CacheService)`

Methods:
- `my_drive_uploads_path(user_id: str) -> str` (static)
  - Returns POSIX path: `my-drive/<user_id>/uploads`.

- `upload_and_ingest(user_id, conversation_id, filename, content, embedding_model="hash-v1", embedding_dimension=256, on_progress=None) -> ChatFileIngestionResult`
  - Stores the provided bytes in object storage under the uploads path, then ingests it.

- `ingest_from_path(user_id, conversation_id, source_path, embedding_model="hash-v1", embedding_dimension=256, on_progress=None) -> ChatFileIngestionResult`
  - Validates `source_path` belongs to `my-drive/<user_id>/...`, downloads bytes from object storage, converts → chunks → embeds (or reuses cached vectors), and upserts into the vector store.

## Configuration/Dependencies

### Required services
- `ObjectStorageService`
  - Used via `put_object(prefix, key, content)` and `get_object(prefix, key)`.
  - Catches `naas_abi_core.services.object_storage.ObjectStoragePort.Exceptions.ObjectNotFound`.

- `VectorStoreService`
  - Used via:
    - `ensure_collection(collection_name, dimension, distance_metric="cosine")`
    - `add_documents(collection_name, ids, vectors, metadata, payloads)`

- `CacheService`
  - Used via:
    - `exists(key)`, `get(key)`
    - `set_json_if_absent(key, payload)`

### Other internal dependencies
From `naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings`:
- `build_chat_collection_name(conversation_id)`
- `build_embedding_cache_key(file_sha256, embedding_model, embedding_dimension)`
- `chunk_markdown(markdown)`
- `embed_texts(chunks, embedding_model, embedding_dimension, on_progress=...)`

### Supported file types
- Direct UTF-8 decode: `.md`, `.txt`, `.py`, `.json`, `.yaml`, `.yml`, `.csv`
- Converted:
  - `.docx` (ZIP + XML parsing)
  - `.pptx` (ZIP + XML parsing)
  - `.xlsx` (requires `openpyxl`)
  - `.pdf` (requires `pymupdf4llm`; uses `fitz` for page counting when available)

### Progress stages and ranges (when `on_progress` is provided)
- `"converting"`: starts at ~30% and for PDFs may advance up to ~70%
- `"chunking"`: ~72%
- `"vectorizing"`: ~75%→~90% (mapped from embedding progress)
- `"reusing_vectors"`: ~90% (cache hit path)
- `"upserting"`: ~92%→~99% (batched upserts)
- `"ready"`: included in `statuses` at completion (no explicit 100% emit here)

## Usage

```python
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_ingestion import (
    ChatFileIngestionService,
)

def on_progress(stage: str, pct: int) -> None:
    print(f"{pct:3d}% {stage}")

# object_storage, vector_store, cache_service must be concrete instances
svc = ChatFileIngestionService(
    object_storage=object_storage,
    vector_store=vector_store,
    cache_service=cache_service,
)

result = svc.upload_and_ingest(
    user_id="user-123",
    conversation_id="conv-456",
    filename="notes.md",
    content=b"# Title\n\nSome content.\n",
    embedding_model="hash-v1",
    embedding_dimension=256,
    on_progress=on_progress,
)

print(result.collection_name, result.chunks_count, result.cache_hit)
```

## Caveats
- **Path ownership is enforced**: `ingest_from_path()` only accepts paths under `my-drive/<user_id>/...` after POSIX normalization; otherwise it raises `ChatFileIngestionError`.
- **PDF and XLSX require optional dependencies**:
  - PDF: `pymupdf4llm` (and its dependency `fitz` is used opportunistically for page batching).
  - XLSX: `openpyxl`.
- **Empty extraction fails**: if conversion yields blank/whitespace-only Markdown, ingestion raises `ChatFileIngestionError`.
- **Vector store upserts are batched**: fixed batch size of 100 points to avoid payload-size limits.
- **IDs are deterministic per chunk index**: derived from `conversation_id`, `file_sha256`, `embedding_model`, `embedding_dimension`, and `chunk_index`.
