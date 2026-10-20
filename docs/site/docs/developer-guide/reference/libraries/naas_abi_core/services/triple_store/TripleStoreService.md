# TripleStoreService

## What it is
- A service facade over an `ITripleStorePort` adapter that provides:
  - CRUD-like operations on named RDF graphs (insert/remove triples; create/clear/drop graphs; list graphs).
  - SPARQL querying (including optional “view” queries) and streaming query/export APIs.
  - An internal **schema graph** (`http://ontology.naas.ai/graph/schema`) that stores:
    - A small bootstrap vocabulary (`SCHEMA_TTL`) describing schema metadata.
    - Loaded schema TTL content (base64) + metadata (`hash`, `filePath`, `fileLastUpdateTime`).
  - Optional event publishing (e.g., `TriplesInserted`, `GraphCreated`, `TripleStoreError`) and optional bus notifications per triple when `services_wired` is enabled.

## Public API

### Class: `TripleStoreService(ServiceBase, ITripleStoreService)`
- `__init__(triple_store_adapter: ITripleStorePort)`
  - Stores the adapter, sets the internal schema graph IRI, and bootstraps `SCHEMA_TTL` into that graph (if not already present).

#### Properties
- `adapter -> ITripleStorePort`
  - Exposes the underlying adapter instance.

#### Triple/graph operations
- `insert(triples: rdflib.Graph, graph_name: rdflib.term.URIRef, *, timeout_seconds: float | None = None) -> None`
  - Inserts `triples` into `graph_name` via the adapter.
  - Publishes `TriplesInserted` and, on failure, `TripleStoreError`.
  - If wired, publishes one bus message per triple (batched publish) to `triple_store` namespace.

- `remove(triples: rdflib.Graph, graph_name: rdflib.term.URIRef, *, timeout_seconds: float | None = None) -> None`
  - Removes `triples` from `graph_name` via the adapter.
  - Publishes `TriplesRemoved` and, on failure, `TripleStoreError`.
  - If wired, publishes one bus message per triple (batched publish).

- `get() -> rdflib.Graph`
  - Returns the adapter’s graph (adapter-defined).

- `create_graph(graph_name: rdflib.term.URIRef, *, timeout_seconds: float | None = None) -> None`
  - Creates a named graph. Publishes `GraphCreated` / `TripleStoreError`.

- `clear_graph(graph_name: rdflib.term.URIRef, *, timeout_seconds: float | None = None) -> None`
  - Clears a named graph. Publishes `GraphCleared` / `TripleStoreError`.

- `drop_graph(graph_name: rdflib.term.URIRef, *, timeout_seconds: float | None = None) -> None`
  - Drops a named graph. Publishes `GraphDropped` / `TripleStoreError`.

- `list_graphs() -> list[rdflib.term.URIRef]`
  - Lists named graphs via the adapter.

#### Querying
- `query(query: str) -> rdflib.query.Result`
  - Executes SPARQL. Publishes `TripleStoreError` on failure.

- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Executes SPARQL against an adapter “view”. Publishes `TripleStoreError` on failure.

- `query_stream(query: str) -> contextmanager[QueryStream]`
  - Context manager yielding a `QueryStream` from the adapter (`rows` and `triples` iterators).
  - Wraps iterator consumption to publish `TripleStoreError` if backend errors occur while iterating.

- `export(graph_name: rdflib.term.URIRef | None = None) -> contextmanager[Iterator[Triple]]`
  - Context manager yielding a streaming iterator of triples from the adapter.
  - Publishes `TripleStoreError` on stream setup or mid-stream errors.

#### Subscriptions / bus notifications
- `subscribe(topic: tuple[URIRef|None, URIRef|None, URIRef|None], callback: Callable[[bytes], None], event_type: OntologyEvent|None = None, graph_name: URIRef|str = "*") -> None`
  - Subscribes to hashed bus routing keys:
    - `ts.<insert|delete|*>.g.<graph|*>.s.<s|*>.p.<p|*>.o.<o|*>`
  - `None` in `(s,p,o)` becomes wildcard `*`. `graph_name="*"` matches any graph.

- `get_subject_graph(subject: str, graph_name: str = "*") -> rdflib.Graph`
  - Delegates to adapter `get_subject_graph(URIRef(subject), graph_name)`.

#### Schema management (internal schema graph)
- `load_schemas(filepaths: list[str]) -> None`
  - Loads multiple schema files in parallel.
  - For each file, applies new/changed triples to the internal schema graph and updates stored metadata.
  - Publishes `SchemaLoaded` per file (and `TripleStoreError` on error).

- `load_schema(filepath: str, schema_cache: rdflib.Graph | None = None) -> None`
  - Loads/updates a single schema file. `schema_cache` is accepted but ignored.
  - Publishes `SchemaLoaded` (and `TripleStoreError` on error).

- `remove_schema(filepath: str) -> None`
  - Removes schema triples and their metadata entries for the given `filepath`.
  - Publishes `SchemaRemoved` (and `TripleStoreError` on error).

- `get_schema_graph() -> rdflib.Graph`
  - Reconstructs and returns a merged graph of **all** loaded schema TTL contents stored in metadata (`internal:content` base64).

## Configuration/Dependencies
- Requires an adapter implementing `ITripleStorePort`, including methods used here:
  - `insert`, `remove`, `get`, `query`, `query_view`, `query_stream`, `export`,
    `create_graph`, `clear_graph`, `drop_graph`, `list_graphs`, `get_subject_graph`.
- Uses `rdflib` (`Graph`, `URIRef`, SPARQL `Result`, parsing Turtle).
- Optional event publishing:
  - Uses `ServiceBase.services.events.publish(...)` when `services_wired` and `events_available()`.
  - Uses `ServiceBase.services.bus.publish_many(...)` / `subscribe(...)` for per-triple notifications.
- Internal constants:
  - Schema graph IRI: `http://ontology.naas.ai/graph/schema`
  - Schema metadata vocabulary is bootstrapped via `SCHEMA_TTL`.

## Usage

```python
from rdflib import Graph, URIRef
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService

# Provide an adapter implementing ITripleStorePort (not shown).
adapter = ...

svc = TripleStoreService(adapter)

g = Graph()
g.parse(data='@prefix ex: <http://ex/> . ex:a ex:b ex:c .', format="turtle")

graph = URIRef("http://example.org/graph/main")
svc.create_graph(graph)
svc.insert(g, graph_name=graph)

for row in svc.query("SELECT * WHERE { ?s ?p ?o }"):
    print(row)

# Manage schemas in the internal schema graph
svc.load_schema("/path/to/schema.ttl")
schema_graph = svc.get_schema_graph()
print(len(schema_graph))
```

## Caveats
- `insert/remove/create_graph/clear_graph` assert `graph_name` is not `None` (and for create/clear it must be a `URIRef`).
- Adapter timeouts are only passed if the adapter method accepts a `timeout_seconds` parameter.
- Schema loading/removal:
  - Updated schemas are diffed by parsing stored and new content as **Turtle**.
  - `_apply_schema_for_file(...)` and `_do_remove_schema(...)` catch exceptions and log/print tracebacks internally (they do not re-raise), while the wrapper methods still publish `TripleStoreError` when exceptions propagate.
- Bus routing keys are hash-based; use `subscribe()` to build correct wildcard/pattern topics.
