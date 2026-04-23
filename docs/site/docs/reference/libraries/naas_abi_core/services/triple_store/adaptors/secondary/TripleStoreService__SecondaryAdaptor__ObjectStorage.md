# TripleStoreService__SecondaryAdaptor__ObjectStorage

## What it is
- A secondary triple-store adaptor that persists RDF triples (`rdflib.Graph`) in an `ObjectStorageService`.
- Stores triples *per subject* as Turtle files (`.ttl`) under a configurable prefix, while also maintaining an in-memory “live” graph loaded from object storage at initialization.
- Implements `ITripleStorePort` and extends `TripleStoreService__SecondaryAdaptor__FileBase` utilities (e.g., subject hashing/grouping).

## Public API
### Class: `TripleStoreService__SecondaryAdaptor__ObjectStorage`
Constructor:
- `__init__(object_storage_service: ObjectStorageService, triples_prefix: str = "triples")`
  - Initializes worker pools/locks and loads all stored triples into an in-memory graph.

Methods:
- `insert(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Inserts triples into per-subject Turtle objects and merges them into the live in-memory graph.
  - `graph_name` must be `None` (named graphs not supported).

- `remove(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Removes triples from the live in-memory graph.
  - Attempts to update per-subject stored graphs (see Caveats).
  - `graph_name` must be `None`.

- `get_subject_graph(subject: URIRef, graph_name: str | URIRef) -> Graph`
  - Loads and returns the stored per-subject graph from object storage.
  - Raises `Exceptions.SubjectNotFoundError` if the subject file does not exist.
  - `graph_name` is accepted but not used for storage partitioning.

- `get() -> Graph`
  - Returns the current in-memory live graph.

- `query(query: str) -> rdflib.query.Result`
  - Executes a SPARQL query against the in-memory live graph (thread-safe).

- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Executes a SPARQL query against the in-memory live graph; `view` is ignored.

- `load() -> Graph`
  - Loads all `.ttl` objects under the configured prefix into a single graph (used during initialization).

Named-graph operations (all raise `NotImplementedError`):
- `create_graph(graph_name: URIRef) -> None`
- `clear_graph(graph_name: URIRef | None = None) -> None`
- `drop_graph(graph_name: URIRef) -> None`
- `list_graphs() -> list[URIRef]`

Other:
- `handle_view_event(...) -> None`
  - No-op (`pass`).

## Configuration/Dependencies
- Depends on:
  - `ObjectStorageService` with:
    - `get_object(prefix, key) -> bytes`
    - `put_object(prefix, key, content: bytes) -> None`
    - `list_objects(prefix, queue) -> None` (streams object keys into a queue)
  - `rdflib` (`Graph`, `URIRef`)
  - `WorkerPool` / `Job` for parallel insert/load operations
- Storage layout:
  - Object key: `"{triples_prefix}/{<subject_hash>}.ttl"` (exact path formatting depends on `ObjectStorageService`)
  - Subject hashing/grouping is delegated to `TripleStoreService__SecondaryAdaptor__FileBase` (e.g., `iri_hash`, `triples_by_subject`).

## Usage
```python
from rdflib import Graph, URIRef, Namespace
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage import (
    TripleStoreService__SecondaryAdaptor__ObjectStorage,
)

# Provide a concrete ObjectStorageService instance for your environment
object_storage: ObjectStorageService = ...

ts = TripleStoreService__SecondaryAdaptor__ObjectStorage(
    object_storage_service=object_storage,
    triples_prefix="triples",
)

EX = Namespace("http://example.org/")
g = Graph()
g.add((EX.alice, EX.knows, EX.bob))

ts.insert(g)

results = ts.query("SELECT * WHERE { ?s ?p ?o }")
for row in results:
    print(row)

alice_graph = ts.get_subject_graph(URIRef(EX.alice), graph_name="ignored")
print(len(alice_graph))
```

## Caveats
- Named graphs are not supported; all methods requiring `graph_name` raise `NotImplementedError` if non-`None` (or unconditionally for graph management).
- `remove(...)` updates the stored per-subject graph by **adding** the provided triples before storing, while subtracting from the live graph. This may not remove persisted triples as intended.
- `insert(...)` uses a worker pool and waits for job completion by comparing `result_queue.qsize()` to `result_queue.maxsize`; this relies on the worker pool’s queue semantics.
- `query_view(...)` ignores the `view` argument and queries the same in-memory graph as `query(...)`.
