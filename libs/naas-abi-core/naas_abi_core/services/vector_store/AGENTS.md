# Vector Store Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/vector_store/`. Canonical reference for agents.

## Purpose

Vector database facade with pluggable backends. Provides collection management, bulk vector storage, configurable similarity search (cosine / euclidean / l2 / dot / l1), and metadata-/payload-filtered retrieval.

Emits `DocumentsAdded`, `DocumentsDeleted`, `DocumentUpdated`, `CollectionEnsured`, `CollectionDeleted`, `VectorStoreError`.

## Files

```
vector_store/
├── IVectorStorePort.py
├── VectorStoreService.py
├── VectorStoreFactory.py
├── adapters/
│   ├── QdrantAdapter.py
│   ├── QdrantInMemoryAdapter.py
│   └── SqliteVecAdapter.py
└── ontologies/
```

## Port (`IVectorStorePort.py`)

```python
class IVectorStorePort:
    def initialize() -> None
    def create_collection(collection_name, dimension, distance_metric="cosine", **kwargs)
    def delete_collection(collection_name)
    def list_collections() -> List[str]
    def store_vectors(collection_name, documents: List[VectorDocument])
    def search(collection_name, query_vector, k=10, filter=None,
               include_vectors=False, include_metadata=True) -> List[SearchResult]
    def get_vector(collection_name, vector_id, include_vector=True) -> VectorDocument | None
    def update_vector(collection_name, vector_id,
                      vector=None, metadata=None, payload=None)
    def delete_vectors(collection_name, vector_ids)
    def count_vectors(collection_name) -> int
    def close()
```

## Service API (`VectorStoreService.py`)

```python
initialize()                                           # lazy adapter init

ensure_collection(collection_name, dimension,
                  distance_metric="cosine",
                  recreate=False, **kwargs)            # create or skip if exists

add_documents(collection_name, ids, vectors,
              metadata=None, payloads=None)

search_similar(collection_name, query_vector, k=10,
               filter=None, score_threshold=None,
               include_vectors=False, include_metadata=True) -> List[SearchResult]

get_document(collection_name, document_id, include_vector=True)
update_document(collection_name, document_id,
                vector=None, metadata=None, payload=None)
delete_documents(collection_name, document_ids)

get_collection_size(collection_name) -> int
list_collections() -> List[str]
delete_collection(collection_name)

close()
```

Distance metrics supported: `cosine`, `euclidean`, `l2`, `dot`, `l1`.

## Available Adapters (`adapters/`)

| Adapter | Backend / Notes |
|---|---|
| `QdrantAdapter` | Qdrant remote server (`host`, `port`, `api_key`, `https`, `timeout`) |
| `QdrantInMemoryAdapter` | Qdrant embedded (memory or filesystem-backed) |
| `SqliteVecAdapter` | SQLite + `sqlite-vec` extension (concurrent-safe dev runtime) |

## Factory (`VectorStoreFactory.py`)

```python
VectorStoreFactory.create_adapter() -> IVectorStorePort   # env-driven (VECTOR_STORE_ADAPTER)
VectorStoreFactory.get_service() -> VectorStoreService    # singleton
VectorStoreFactory.reset()                                # clear singleton
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/vector_store/VectorStoreService_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/vector_store/VectorStoreService_events_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/vector_store/IVectorStorePort_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/vector_store/adapters/QdrantAdapter_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/vector_store/adapters/QdrantInMemoryAdapter_test.py
```

## Adding a new adapter

1. Implement every method of `IVectorStorePort` in `adapters/<Name>Adapter.py`.
2. Support all five distance metrics (or raise a clear error for unsupported ones).
3. Honour metadata / payload filtering semantics — `filter` is a backend-agnostic dict; translate it.
4. Add an `<Name>Adapter_test.py`.
5. Register it under a recognisable name in `VectorStoreFactory.create_adapter()` so `VECTOR_STORE_ADAPTER` env can select it.
