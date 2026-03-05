# TripleStoreService__SecondaryAdaptor__Filesystem

## What it is
A filesystem-backed triple store adaptor that persists RDF triples as Turtle files, partitioned by subject hash, and maintains an in-memory “live” aggregate `rdflib.Graph` for querying.

- Stores per-subject graphs under `<store_path>/triples/<subject_hash>.ttl`
- Loads all stored triples on initialization into an in-memory graph
- Supports basic insert/remove/get/query and a filesystem-based “view” mechanism using symlinks
- Does **not** support named graphs

## Public API

### Class: `TripleStoreService__SecondaryAdaptor__Filesystem`
Implements `ITripleStorePort` and extends `TripleStoreService__SecondaryAdaptor__FileBase`.

#### `__init__(store_path: str, triples_path: str = "triples")`
- Creates the triples directory (under `store_path`).
- Loads all existing triples into the live in-memory graph.

#### `insert(triples: rdflib.Graph, graph_name: URIRef | None = None) -> None`
- Inserts triples into:
  - Per-subject Turtle file(s)
  - The in-memory live graph
- Binds namespaces from `triples` into stored files (for new subject files) and into the live graph.
- Raises `NotImplementedError` if `graph_name` is provided.

#### `remove(triples: rdflib.Graph, graph_name: URIRef | None = None) -> None`
- Removes triples from per-subject Turtle file(s) (if present) and from the live graph.
- Raises `NotImplementedError` if `graph_name` is provided.

#### `get() -> rdflib.Graph`
- Returns the in-memory live graph.

#### `get_subject_graph(subject: URIRef) -> rdflib.Graph`
- Loads and returns the Turtle file for the given subject hash.
- Raises `Exceptions.SubjectNotFoundError` if the subject file does not exist.

#### `load() -> rdflib.Graph`
- Loads and merges all Turtle files found in `<store_path>/triples` into a single graph.
- Binds namespaces from loaded graphs into the aggregate.
- Logs and re-raises parse errors.

#### `query(query: str) -> rdflib.query.Result`
- Runs a SPARQL query against the in-memory live graph.

#### `query_view(view: str, query: str) -> rdflib.query.Result`
- Runs a SPARQL query against an aggregate graph built from Turtle files in `<store_path>/views/<view>/`.
- Raises `Exceptions.ViewNotFoundError` if the view directory does not exist.

#### `handle_view_event(view, event: OntologyEvent, triple) -> None`
- Handles view updates by creating/removing symlinks inside `<store_path>/views/<dir_name>/`.
- Computes `dir_name` from the object’s `rdfs:label` (looked up in the object’s partition file) and the object’s IRI tail.
- On `OntologyEvent.INSERT`: symlinks the subject’s Turtle file into the view directory.
- On `OntologyEvent.DELETE`: removes the symlink.
- Asserts `s` and `o` are `BNode` or `URIRef`.

#### Named graph methods (not supported)
- `create_graph(graph_name: URIRef) -> None` → raises `NotImplementedError`
- `clear_graph(graph_name: URIRef | None = None) -> None` → raises `NotImplementedError`
- `drop_graph(graph_name: URIRef) -> None` → raises `NotImplementedError`
- `list_graphs() -> list[URIRef]` → returns `[]`

#### Utility
- `hash_triples_path(hash_value: str) -> str`
  - Returns path `<store_path>/triples/<hash_value>.ttl` (adds `.ttl` if needed).

## Configuration/Dependencies
- **Filesystem layout**
  - Triples directory: `<store_path>/triples` (created on init)
  - Views directory: `<store_path>/views/<view_name>/` (created on demand by `handle_view_event`)
- **Dependencies**
  - `rdflib` (`Graph`, SPARQL querying, Turtle parsing/serialization)
  - `threading.Lock` used to serialize operations (`insert`, `remove`, `load`, `query`, `query_view`)
  - Base class `TripleStoreService__SecondaryAdaptor__FileBase` is expected to provide:
    - `iri_hash(...)`
    - `triples_by_subject(...)`
- **Exceptions**
  - Uses `Exceptions.SubjectNotFoundError` and `Exceptions.ViewNotFoundError` from `naas_abi_core.services.triple_store.TripleStorePorts`.

## Usage

```python
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDFS

from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)

store = TripleStoreService__SecondaryAdaptor__Filesystem(store_path="/tmp/naas_store")

EX = Namespace("http://example.org/")

g = Graph()
g.bind("ex", EX)

alice = URIRef(EX["alice"])
g.add((alice, RDFS.label, Literal("Alice")))

store.insert(g)

result = store.query("""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?s ?label WHERE { ?s rdfs:label ?label }
""")
for row in result:
    print(row.s, row.label)

subject_graph = store.get_subject_graph(alice)
print(len(subject_graph))
```

## Caveats
- **Named graphs are not supported**: any `graph_name` usage raises `NotImplementedError` (except `list_graphs()` which returns empty).
- **Persistence model**: triples are partitioned by **subject** into separate Turtle files; removing a triple only affects the subject’s file.
- **Views use symlinks**:
  - Requires OS/filesystem support for `os.symlink`.
  - `handle_view_event` derives the view directory name from `rdfs:label` and the object IRI tail; missing/odd labels may lead to unexpected directory names.
