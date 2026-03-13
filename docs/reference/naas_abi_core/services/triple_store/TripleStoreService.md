# `TripleStoreService`

## What it is
A service façade over a triple store adapter (`ITripleStorePort`) that:
- Inserts/removes RDF triples (`rdflib.Graph`) into a triple store.
- Runs SPARQL queries (including adapter-defined “views”).
- Manages named graphs (create/clear/drop/list).
- Publishes insert/delete events to a message bus when the service is wired.
- Loads and tracks Turtle schema files with change detection via stored metadata.

On initialization it also inserts an internal ontology (`SCHEMA_TTL`) describing schema metadata (`internal:Schema`, `internal:hash`, `internal:filePath`, etc.).

## Public API

### Class: `TripleStoreService(triple_store_adapter: ITripleStorePort)`
- **Purpose:** Primary entry point for triple store CRUD, querying, subscriptions, and schema loading.

#### Methods
- `insert(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Inserts all triples into the store via the adapter.
  - If `services_wired` is `True`, publishes one bus message per triple on a topic derived from graph/s/p/o hashes.

- `remove(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Removes all triples via the adapter.
  - If `services_wired` is `True`, publishes delete events similarly to `insert`.

- `get() -> Graph`
  - Returns the full graph from the adapter.

- `query(query: str) -> rdflib.query.Result`
  - Executes a SPARQL query via the adapter.

- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Executes a view-specific query via the adapter.

- `create_graph(graph_name: URIRef) -> None`
  - Creates a named graph via the adapter.

- `clear_graph(graph_name: URIRef | None = None) -> None`
  - Clears a named graph (or default graph if `None`) via the adapter.

- `drop_graph(graph_name: URIRef) -> None`
  - Drops a named graph via the adapter.

- `list_graphs() -> list[URIRef]`
  - Lists graphs via the adapter.

- `subscribe(topic: tuple[URIRef | None, URIRef | None, URIRef | None], callback: Callable[[bytes], None], event_type: OntologyEvent | None = None, graph_name: URIRef | str | None = "*") -> None`
  - Subscribes to bus topics for triple insert/delete events.
  - `topic` is an (s, p, o) pattern; `None` acts as wildcard.
  - `event_type`: `INSERT`, `DELETE`, or `None` for all.
  - `graph_name`: `*` for all graphs, `None` for default graph, or a specific graph identifier.

- `get_subject_graph(subject: str) -> Graph`
  - Returns a subgraph for a given subject (converted to `URIRef`) via the adapter.

#### Schema management
- `load_schemas(filepaths: List[str]) -> None`
  - Loads multiple schema files, first building a cache of existing schema metadata to speed checks.

- `load_schema(filepath: str, schema_cache: Graph | None = None) -> None`
  - Loads a Turtle schema file into the triple store if not present.
  - If already present, compares stored content hash vs current file content hash and:
    - If unchanged: optionally cleans up duplicate metadata entries and returns.
    - If changed: computes triple additions/deletions between old and new Turtle graphs, updates the store, and updates stored metadata.
  - Stores schema metadata as `internal:Schema` instances with:
    - `internal:hash`, `internal:filePath`, `internal:fileLastUpdateTime`, `internal:content` (base64).

- `get_schema_graph() -> Graph`
  - Reconstructs and returns a merged RDF graph of all stored schema contents (`internal:content`) by base64-decoding and parsing Turtle.

## Configuration/Dependencies
- **Adapter dependency:** Requires an `ITripleStorePort` implementation passed to the constructor. The adapter provides storage operations (`insert`, `remove`, `get`, `query`, graph management, etc.).
- **Messaging dependency (optional at runtime):**
  - When `services_wired` is `True`, uses `self.services.bus.topic_publish(...)` and `self.services.bus.topic_consume(...)`.
- **Libraries:**
  - `rdflib` for RDF graphs and SPARQL results.
- **Internal schema ontology:**
  - `SCHEMA_TTL` is parsed and inserted into the store on service initialization.

## Usage

### Basic insert/query (requires a real `ITripleStorePort` implementation)
```python
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF

# triple_store_adapter must implement ITripleStorePort
store = TripleStoreService(triple_store_adapter)

g = Graph()
s = URIRef("http://example.org/Alice")
g.add((s, RDF.type, URIRef("http://example.org/Person")))
g.add((s, URIRef("http://example.org/name"), Literal("Alice")))

store.insert(g)

res = store.query("SELECT ?s WHERE { ?s a <http://example.org/Person> }")
for row in res:
    print(row)
```

### Subscribe to inserts of any triple (when services are wired)
```python
from rdflib.namespace import RDF

def on_msg(payload: bytes) -> None:
    print(payload.decode("utf-8").strip())

store.subscribe(
    topic=(None, None, None),          # wildcard s/p/o
    event_type=OntologyEvent.INSERT,   # only inserts
    graph_name="*",                    # all graphs
    callback=on_msg,
)
```

### Load and track Turtle schemas from files
```python
store.load_schemas(["/path/to/schema1.ttl", "/path/to/schema2.ttl"])
schema_graph = store.get_schema_graph()
print(len(schema_graph))
```

## Caveats
- **Per-triple bus publishing:** `insert()`/`remove()` publish one message per triple when `services_wired` is `True`, which can be expensive for large graphs.
- **Schema timestamp stored as `os.path.getmtime`:** `internal:fileLastUpdateTime` is stored as a numeric timestamp string (not an RDF `xsd:dateTime` literal).
- **`load_schema()` error handling:** Exceptions are caught, logged, and a traceback is printed; errors are not re-raised.
