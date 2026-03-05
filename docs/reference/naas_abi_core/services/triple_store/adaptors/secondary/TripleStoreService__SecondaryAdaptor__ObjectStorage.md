# TripleStoreService__SecondaryAdaptor__ObjectStorage

## What it is
- A secondary triple-store adaptor that persists RDF triples in an `ObjectStorageService` as Turtle (`.ttl`) files.
- Triples are partitioned by **subject**: each subject’s triples are stored under `<triples_prefix>/<subject_hash>.ttl`.
- Maintains an in-memory “live” `rdflib.Graph` loaded from object storage at initialization.

## Public API
### Class: `TripleStoreService__SecondaryAdaptor__ObjectStorage`
Implements `ITripleStorePort` and extends `TripleStoreService__SecondaryAdaptor__FileBase`.

#### `__init__(object_storage_service: ObjectStorageService, triples_prefix: str = "triples")`
- Creates the adaptor, sets storage prefix, initializes worker pool/lock, and loads all persisted triples into memory.

#### `insert(triples: Graph, graph_name: URIRef | None = None)`
- Inserts triples into:
  - Per-subject Turtle files in object storage (parallelized).
  - The in-memory live graph.
- `graph_name` is **not supported** (raises `NotImplementedError` if provided).

#### `remove(triples: Graph, graph_name: URIRef | None = None)`
- Updates the in-memory live graph by removing given triples.
- Attempts to update per-subject Turtle files in object storage.
- `graph_name` is **not supported** (raises `NotImplementedError` if provided).

> Note: The object-storage update path in `remove()` uses `graph.add(...)` for the provided triples; verify behavior against your expectations before relying on persisted removals.

#### `get_subject_graph(subject: str | URIRef) -> Graph`
- Loads and returns the `rdflib.Graph` for a single subject from object storage.
- Raises `Exceptions.SubjectNotFoundError` if the subject’s `.ttl` object does not exist.

#### `load() -> Graph`
- Loads all `.ttl` objects under `triples_prefix` from object storage into a single `rdflib.Graph`.
- Uses a background thread to list objects and a worker pool to parse graphs concurrently.

#### `get() -> Graph`
- Returns the in-memory live graph.

#### `query(query: str) -> rdflib.query.Result`
- Executes a SPARQL query against the live graph (thread-safe via internal lock).

#### `query_view(view: str, query: str) -> rdflib.query.Result`
- Executes a SPARQL query against the live graph; `view` is currently unused.

#### `handle_view_event(...)`
- No-op (`pass`).

#### Named graph operations (all raise `NotImplementedError`)
- `create_graph(graph_name: URIRef)`
- `clear_graph(graph_name: URIRef | None = None)`
- `drop_graph(graph_name: URIRef)`
- `list_graphs() -> list[URIRef]`

## Configuration/Dependencies
- Requires an instance of:
  - `naas_abi_core.services.object_storage.ObjectStorageService.ObjectStorageService`
- Uses:
  - `rdflib.Graph` for RDF storage/querying and Turtle serialization/parsing.
  - `WorkerPool` (from `naas_abi_core.utils.Workers`) for concurrent load/insert operations.
- Storage layout:
  - `prefix = triples_prefix` (default: `"triples"`)
  - `key = f"{subject_hash}.ttl"` where `subject_hash` is derived via `iri_hash(...)` from the base class.

## Usage
```python
from rdflib import Graph, URIRef, Namespace, Literal
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage import (
    TripleStoreService__SecondaryAdaptor__ObjectStorage,
)

# Assume you have a configured ObjectStorageService instance
object_storage_service = ...  # ObjectStorageService

ts = TripleStoreService__SecondaryAdaptor__ObjectStorage(
    object_storage_service=object_storage_service,
    triples_prefix="triples",
)

EX = Namespace("http://example.org/")
g = Graph()
g.bind("ex", EX)

s = URIRef("http://example.org/s1")
g.add((s, EX.p, Literal("v1")))

ts.insert(g)

result = ts.query("SELECT ?o WHERE { <http://example.org/s1> <http://example.org/p> ?o }")
for row in result:
    print(row)

subject_graph = ts.get_subject_graph(s)
print(len(subject_graph))
```

## Caveats
- **Named graphs are not supported**: passing `graph_name` to `insert/remove` or calling graph management methods raises `NotImplementedError`.
- Initialization calls `load()` and may be expensive for large object stores (lists and parses all stored Turtle files).
- `remove()` updates the in-memory graph, but its persistence behavior should be reviewed (it adds triples to the loaded per-subject graph before storing).
