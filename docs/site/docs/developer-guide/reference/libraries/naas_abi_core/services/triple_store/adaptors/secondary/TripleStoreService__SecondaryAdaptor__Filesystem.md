# TripleStoreService__SecondaryAdaptor__Filesystem

## What it is
A filesystem-backed RDF triple store adaptor that implements `ITripleStorePort` using `rdflib.Graph`. It persists triples as Turtle files partitioned by subject hash under a store directory, maintains an in-memory “live” aggregate graph, and supports basic SPARQL querying and a simple “view” mechanism via symlinks.

## Public API

### Class: `TripleStoreService__SecondaryAdaptor__Filesystem(ITripleStorePort, TripleStoreService__SecondaryAdaptor__FileBase)`
Filesystem-based triple store adaptor.

#### `__init__(store_path: str, triples_path: str = "triples")`
- Creates `<store_path>/<triples_path>` if missing.
- Loads existing triples into an in-memory live graph via `load()`.

#### `insert(triples: rdflib.Graph, graph_name: URIRef | None = None) -> None`
- Inserts triples into per-subject Turtle files and updates the in-memory live graph.
- **Named graphs are not supported**: raises `NotImplementedError` if `graph_name` is provided.

#### `remove(triples: rdflib.Graph, graph_name: URIRef | None = None) -> None`
- Removes triples from per-subject Turtle files and updates the in-memory live graph.
- **Named graphs are not supported**: raises `NotImplementedError` if `graph_name` is provided.

#### `get() -> rdflib.Graph`
- Returns the in-memory live graph.

#### `get_subject_graph(subject: URIRef, graph_name: str | URIRef) -> rdflib.Graph`
- Loads and returns the stored graph file for a given subject (based on subject hash).
- Raises `Exceptions.SubjectNotFoundError` if the subject file does not exist.
- `graph_name` is accepted but not used.

#### `load() -> rdflib.Graph`
- Loads all Turtle files from `<store_path>/triples` and returns an aggregated graph.
- Logs and re-raises parsing/loading errors.

#### `query(query: str) -> rdflib.query.Result`
- Runs a SPARQL query against the in-memory live graph.

#### `query_view(view: str, query: str) -> rdflib.query.Result`
- Runs a SPARQL query against an aggregated graph built from Turtle files found under `<store_path>/views/<view>/`.
- Raises `Exceptions.ViewNotFoundError` if the view directory does not exist.

#### `handle_view_event(view, event: OntologyEvent, triple) -> None`
- Maintains “views” as directories under `<store_path>/views/`.
- For `OntologyEvent.INSERT`, creates a symlink in a view directory pointing to a subject’s triple file.
- For `OntologyEvent.DELETE`, removes the symlink if present.
- View directory name is derived from the object’s `rdfs:label` and ID (last path/fragment segment).

#### Named graph management (not supported)
- `create_graph(graph_name: URIRef) -> None` → `NotImplementedError`
- `clear_graph(graph_name: URIRef | None = None) -> None` → `NotImplementedError`
- `drop_graph(graph_name: URIRef) -> None` → `NotImplementedError`
- `list_graphs() -> list[URIRef]` → always returns `[]`

#### Helper
- `hash_triples_path(hash_value: str) -> str`
  - Returns `<store_path>/triples/<hash_value>.ttl` (adds `.ttl` if missing).

## Configuration/Dependencies
- **Filesystem layout**
  - Triples directory: `<store_path>/triples/` (note: hardcoded `"triples"` in several places).
  - Views directory: `<store_path>/views/`.
- **Dependencies**
  - `rdflib` for RDF graphs and SPARQL query.
  - `TripleStoreService__SecondaryAdaptor__FileBase` for helper methods (e.g., `iri_hash(...)`, `triples_by_subject(...)`).
  - `naas_abi_core.services.triple_store.TripleStorePorts` for:
    - `Exceptions` (`SubjectNotFoundError`, `ViewNotFoundError`)
    - `OntologyEvent`
- **Concurrency**
  - Uses an internal `threading.Lock` to protect insert/remove/load/query operations.

## Usage

```python
from rdflib import Graph, Namespace, URIRef, Literal
from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)

EX = Namespace("http://example.org/")

store = TripleStoreService__SecondaryAdaptor__Filesystem(store_path="/tmp/naas_store")

g = Graph()
g.bind("ex", EX)
g.add((URIRef(EX["s1"]), URIRef(EX["p"]), Literal("v")))

store.insert(g)

res = store.query("SELECT ?s ?o WHERE { ?s <http://example.org/p> ?o }")
for row in res:
    print(row)

subject_graph = store.get_subject_graph(URIRef(EX["s1"]), graph_name="ignored")
print(len(subject_graph))
```

## Caveats
- **Named graphs are not supported**; `graph_name` must be `None` for `insert`/`remove`, and graph lifecycle methods raise `NotImplementedError`.
- `triples_path` passed to `__init__` is not consistently used (some paths are hardcoded to `"triples"`), so non-default values may not behave as expected.
- View handling uses filesystem symlinks (`os.symlink`), which may require elevated privileges or special settings on some platforms (notably Windows).
- `handle_view_event` builds view directory names using the object’s `rdfs:label`; if no label exists, the directory name will include `None` (stringified).
