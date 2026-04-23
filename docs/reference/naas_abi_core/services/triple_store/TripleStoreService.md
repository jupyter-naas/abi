# TripleStoreService

## What it is
- A service facade over an `ITripleStorePort` adapter that:
  - Inserts/removes RDF triples into named graphs.
  - Runs SPARQL queries (optionally against a “view”).
  - Manages a dedicated internal “schema graph” that tracks loaded Turtle schema files and their metadata (hash, file path, last update time, base64 content).
  - Optionally publishes triple insert/delete events on a service bus when `services_wired` is enabled.

## Public API

### Class: `TripleStoreService(ServiceBase, ITripleStoreService)`
Constructor:
- `__init__(triple_store_adapter: ITripleStorePort)`
  - Stores the adapter.
  - Initializes an internal schema graph at `http://ontology.naas.ai/graph/schema`.
  - Inserts `SCHEMA_TTL` (internal ontology describing schema metadata) into that schema graph.

Core triple-store operations:
- `insert(triples: rdflib.Graph, graph_name: rdflib.term.URIRef) -> None`
  - Inserts all triples into `graph_name` via the adapter.
  - If `services_wired` is `True`, publishes one bus message per triple on a hashed topic `ts.insert...`.
- `remove(triples: rdflib.Graph, graph_name: rdflib.term.URIRef) -> None`
  - Removes all triples from `graph_name` via the adapter.
  - If `services_wired` is `True`, publishes one bus message per triple on a hashed topic `ts.delete...`.
- `get() -> rdflib.Graph`
  - Returns the adapter’s graph (implementation-defined by adapter).
- `query(query: str) -> rdflib.query.Result`
  - Executes a SPARQL query through the adapter.
- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Executes a SPARQL query against a named “view” through the adapter.

Graph management:
- `create_graph(graph_name: URIRef) -> None`
- `clear_graph(graph_name: URIRef) -> None`
- `drop_graph(graph_name: URIRef) -> None`
- `list_graphs() -> list[URIRef]`

Subscriptions / notifications:
- `subscribe(topic: tuple[URIRef|None, URIRef|None, URIRef|None], callback: Callable[[bytes], None], event_type: OntologyEvent|None = None, graph_name: URIRef|str = "*") -> None`
  - Subscribes to bus topics for triple insert/delete events.
  - `None` in the `(s, p, o)` tuple acts as a wildcard.
  - `event_type` supports `OntologyEvent.INSERT`, `OntologyEvent.DELETE`, or `None` for wildcard.
  - `graph_name="*"` matches any graph; otherwise it is hashed into the topic.
- `get_subject_graph(subject: str, graph_name: str = "*") -> rdflib.Graph`
  - Delegates to adapter to retrieve a subject-focused graph.

Schema management (stored in the internal schema graph):
- `load_schemas(filepaths: List[str]) -> None`
  - Preloads existing schema metadata into a local cache graph, then calls `load_schema()` for each filepath.
- `load_schema(filepath: str, schema_cache: Graph | None = None) -> None`
  - If metadata for `filepath` exists:
    - Compares current file hash vs stored hash.
    - If changed, computes added/removed triples by parsing old vs new Turtle content and applies `insert`/`remove` to the schema graph.
    - Updates the stored metadata (hash, last update time, base64 content).
    - Removes duplicate metadata subjects for the same `filepath`.
  - If metadata does not exist:
    - Parses the Turtle file and inserts its triples into the schema graph.
    - Inserts a new `internal:Schema` metadata node with hash, filepath, mtime, and base64 content.
  - Exceptions are caught; errors are logged and a traceback is printed.
- `remove_schema(filepath: str) -> None`
  - Finds schema metadata entries by `internal:filePath`.
  - Reconstructs schema triples from stored base64 content and removes:
    - The schema triples from the schema graph.
    - The associated metadata triples.
  - Exceptions are caught; errors are logged and a traceback is printed.
- `get_schema_graph() -> rdflib.Graph`
  - Rebuilds and returns a merged `rdflib.Graph` of all loaded schema contents by decoding each stored `internal:content` (base64 Turtle) and parsing it.

## Configuration/Dependencies
- Requires an adapter implementing `ITripleStorePort` with methods used here:
  - `insert`, `remove`, `get`, `query`, `query_view`, `create_graph`, `clear_graph`, `drop_graph`, `list_graphs`, `get_subject_graph`.
- Uses `rdflib` for `Graph`, `URIRef`, parsing Turtle, and SPARQL result types.
- Event publishing/subscription relies on `ServiceBase.services.bus`:
  - Publishes to/consumes from bus namespace `"triple_store"`.
  - Only active when `services_wired` is `True`.
- Internal schema graph IRI: `http://ontology.naas.ai/graph/schema`.

## Usage

```python
from rdflib import Graph, URIRef
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService

# Provide an adapter that implements ITripleStorePort (not shown here).
adapter = ...  # e.g., a filesystem/db-backed triple store adapter

ts = TripleStoreService(adapter)

g = Graph()
g.parse(data='@prefix ex: <http://ex/> . ex:a ex:b ex:c .', format="turtle")

graph_name = URIRef("http://example.org/graph/main")
ts.create_graph(graph_name)
ts.insert(g, graph_name=graph_name)

res = ts.query("SELECT * WHERE { ?s ?p ?o }")
for row in res:
    print(row)

# Load a Turtle schema file into the internal schema graph and track metadata.
ts.load_schema("path/to/schema.ttl")

# Get the merged graph of all loaded schema contents.
schema_graph = ts.get_schema_graph()
print(len(schema_graph))
```

## Caveats
- `insert()`/`remove()` assert `graph_name` is not `None`; `create_graph()`/`clear_graph()` also assert it is a `URIRef`.
- Schema loading assumes Turtle content:
  - Existing schemas are parsed using `format="turtle"` from stored base64 content.
  - New schemas are parsed via `Graph().parse(filepath)` (rdflib will infer format; typically `.ttl` is expected).
- `load_schema()` and `remove_schema()` swallow exceptions (log + print traceback) rather than raising.
- Event topics are hash-based (SHA-256 truncated) per graph/s/p/o, so subscribers must use `subscribe()` to construct matching patterns rather than guessing raw topic strings.
