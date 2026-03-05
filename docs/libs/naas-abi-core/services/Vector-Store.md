# Vector Store Service

`VectorStoreService` provides embeddings collection management and similarity search.

Related pages: [[Configuration]], [[services/Overview]].

## Core API

- `ensure_collection(name, dimension, distance_metric, recreate=False)`
- `add_documents(collection, ids, vectors, metadata=None, payloads=None)`
- `search_similar(collection, query_vector, k=10, filter=None, score_threshold=None)`
- `get_document(collection, document_id)`
- `update_document(...)`
- `delete_documents(collection, ids)`
- `get_collection_size(collection)`
- `list_collections()`

## Adapter options

- `qdrant`: external Qdrant server.
- `qdrant_in_memory`: in-memory implementation for local/dev tests.
- `custom`: pluggable adapter.

## Config example

```yaml
services:
  vector_store:
    vector_store_adapter:
      adapter: "qdrant"
      config:
        host: "localhost"
        port: 6333
        https: false
        timeout: 30
```

## Notes

- Service auto-initializes adapter on first call.
- Input validation checks length consistency for ids/vectors/metadata/payloads.
- `score_threshold` filtering is applied client-side on results.
