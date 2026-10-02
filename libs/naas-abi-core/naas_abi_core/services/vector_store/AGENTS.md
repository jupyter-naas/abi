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
    def list_vectors(collection_name, limit=100, cursor=None,
                     include_vectors=False) -> VectorPage
    def get_collection_info(collection_name) -> CollectionInfo
    def close()
```

`list_vectors` pages through every document (metadata and payload, vectors only
on request) in a stable, adapter-defined order: SqliteVec by id, Qdrant by point
id (scroll). `VectorPage.next_cursor` is opaque; pass it back as `cursor` to
start the next page (`None`: last page). `CollectionInfo` gives `dimension` and
`distance_metric` (`None` when the backend cannot say, e.g. Qdrant named
vectors) and `size` (point count).

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
list_documents(collection_name, *, limit=100, cursor=None,
               include_vectors=False) -> VectorPage   # 1 <= limit <= 10_000
get_collection_info(collection_name) -> CollectionInfo
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
uv run pytest libs/naas-abi-core/naas_abi_core/services/vector_store/adapters/SqliteVecAdapter_test.py
uv run pytest --import-mode=importlib libs/naas-abi-core/naas_abi_core/services/vector_store/adapters/secondary
```

`GenericVectorStoreAdapterTest` (`IVectorStorePort_test.py`) runs against every
adapter: QdrantInMemory, SqliteVec, the NATS client (through a real primary on
a local `nats-server`, else a Docker container) and remote Qdrant when
`QDRANT_HOST` is set. SqliteVec reports the distance as `score` (lower is
closer), so its `test_search_vectors` is a strict xfail.

## Adding a new adapter

1. Implement every method of `IVectorStorePort` in `adapters/<Name>Adapter.py`.
2. Support all five distance metrics (or raise a clear error for unsupported ones).
3. Honour metadata / payload filtering semantics — `filter` is a backend-agnostic dict; translate it.
4. Add an `<Name>Adapter_test.py`.
5. Register it under a recognisable name in `VectorStoreFactory.create_adapter()` so `VECTOR_STORE_ADAPTER` env can select it.

## NATS RPC adapters

`adapters/primary/vector_store__primary_adapter__NATS.py` exposes the service's
protobuf endpoints, one per port method (`list_vectors` and `get_collection_info`
included). `adapters/secondary/VectorStoreSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/vector_store/v1/`.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
The maximum message size is 8 MiB (or a lower broker limit); oversized replies
return non-retryable `PAYLOAD_TOO_LARGE`, and micro-service error headers raise
instead of becoming an empty success. Larger results require streaming or a
storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.

NATS primaries emit mutation audit events through an injected owner-side event
publisher. Remote VectorStoreService facades must remain unwired for events to
avoid duplicating them. Failures in audit publication do not fail persistence.
