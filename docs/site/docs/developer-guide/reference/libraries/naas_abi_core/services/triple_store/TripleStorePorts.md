# TripleStorePorts

## What it is
Abstract interfaces and shared types for a triple-store layer built on **rdflib**, including:
- Domain exceptions (including an HTTP-friendly `RequestError`).
- `OntologyEvent` for INSERT/DELETE notifications.
- `QueryStream` for incremental SPARQL result consumption.
- Helper `graph_export_query()` for exporting a named graph via SPARQL.
- Two ABCs: `ITripleStorePort` (adapter/port) and `ITripleStoreService` (service-level API).

## Public API

### Types
- `Triple = tuple[rdflib.term.Node, rdflib.term.Node, rdflib.term.Node]` — a single RDF triple.
- `QueryStream` (`@dataclass`) — incremental view of a SPARQL result:
  - Fields:
    - `result_type: str` — `"SELECT" | "ASK" | "CONSTRUCT" | "DESCRIBE"` (as produced)
    - `vars: list[str]` — SELECT variable names
    - `ask_answer: bool | None` — ASK answer when applicable
    - `rows: Iterator[dict[str, Node]]` — SELECT rows (single-use iterator)
    - `triples: Iterator[Triple]` — CONSTRUCT/DESCRIBE triples (single-use iterator)
  - `QueryStream.from_result(result: Any) -> QueryStream` — adapts:
    - `bool` (ASK), `rdflib.Graph` (CONSTRUCT/DESCRIBE), or `rdflib.query.Result`.

### Exceptions
`Exceptions` container class with nested exceptions (all subclass `Exception`):
- `Exceptions.SubjectNotFoundError`
- `Exceptions.SubscriptionNotFoundError`
- `Exceptions.ViewNotFoundError`
- `Exceptions.GraphNotFoundError`
- `Exceptions.GraphAlreadyExistsError`
- `Exceptions.RequestError` — carries server diagnostics for HTTP-backed adapters:
  - `__init__(*, operation: str, message: str, status_code: int|None = None, response_body: str|None = None, endpoint: str|None = None, attempts: int|None = None)`
  - `.detail() -> str` — multi-line summary including server response body if present.

### Enums
- `OntologyEvent(Enum)`:
  - `OntologyEvent.INSERT`
  - `OntologyEvent.DELETE`

### Functions
- `graph_export_query(graph_name: URIRef) -> str`
  - Returns a SPARQL `CONSTRUCT` query that reads every triple from `GRAPH <graph_name>`.
  - Raises `ValueError` if `graph_name` is not an absolute IRI (validated by regex).

### Interfaces

#### `ITripleStorePort` (ABC)
Adapter-facing port (backend implementation contract):
- `insert(triples: Graph, graph_name: URIRef)`
- `remove(triples: Graph, graph_name: URIRef)`
- `get() -> Graph`
- `handle_view_event(view, event: OntologyEvent, triple)`  
  - `view`: `tuple[URIRef|None, URIRef|None, URIRef|None]`  
  - `triple`: `tuple[URIRef|None, URIRef|None, URIRef|None]`
- `query(query: str) -> rdflib.query.Result`
- `query_view(view: str, query: str) -> rdflib.query.Result`
- `get_subject_graph(subject: URIRef, graph_name: str | URIRef) -> Graph`
- `create_graph(graph_name: URIRef)`  
  - May raise `Exceptions.GraphAlreadyExistsError` (when backend can detect it).
- `clear_graph(graph_name: URIRef)`  
  - May raise `Exceptions.GraphNotFoundError`.
- `drop_graph(graph_name: URIRef)`  
  - May raise `Exceptions.GraphNotFoundError`.
- `list_graphs() -> list[URIRef]`
- Default streaming helpers (override if backend can stream):
  - `query_stream(query: str) -> contextmanager[QueryStream]` — yields `QueryStream.from_result(self.query(query))`
  - `export(graph_name: URIRef | None = None) -> contextmanager[Iterator[Triple]]`
    - If `graph_name is None`: yields `iter(self.get())`
    - Else: runs `graph_export_query(graph_name)` and yields `result.triples`

#### `ITripleStoreService` (ABC)
Service-facing interface (higher-level contract):
- `subscribe(topic, callback, event_type: OntologyEvent|None = None, graph_name: URIRef|str="*") -> None`  
  - `topic`: SPO pattern `(subject, predicate, object)` with `None` wildcards.
  - `callback`: `Callable[[bytes], None]`.
  - Docstring says it returns a subscription id (`str`), but signature returns `None`.
- `insert(triples: Graph, graph_name: URIRef, *, timeout_seconds: float|None = None)`
- `remove(triples: Graph, graph_name: URIRef, *, timeout_seconds: float|None = None)`
- `get() -> Graph`
- `query(query: str) -> rdflib.query.Result`
- `query_view(view: str, query: str) -> rdflib.query.Result`
- `get_subject_graph(subject: str, graph_name: str | URIRef) -> Graph`  
  - Docstring: may raise `SubjectNotFoundError`.
- `create_graph(graph_name: URIRef, *, timeout_seconds: float|None = None)`
- `clear_graph(graph_name: URIRef, *, timeout_seconds: float|None = None)`
- `drop_graph(graph_name: URIRef, *, timeout_seconds: float|None = None)`
- `list_graphs() -> list[URIRef]`
- Streaming:
  - `query_stream(query: str) -> AbstractContextManager[QueryStream]`
  - `export(graph_name: URIRef | None = None) -> AbstractContextManager[Iterator[Triple]]`
- Schema helpers:
  - `load_schema(filepath: str)`
  - `get_schema_graph() -> Graph`

## Configuration/Dependencies
- Depends on `rdflib`:
  - `rdflib.Graph`, `rdflib.URIRef`, `rdflib.query.Result`, `rdflib.term.Node`
- Uses standard library:
  - `abc`, `dataclasses`, `enum`, `contextlib`, `re`, `collections.abc`

## Usage
These are interfaces; you must provide an implementation. Example typing against the service:

```python
from rdflib import Graph, URIRef
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService

def run(store: ITripleStoreService) -> None:
    graph_name = URIRef("http://example.org/graph")
    g = Graph()  # populate as needed

    store.create_graph(graph_name)
    store.insert(g, graph_name)

    with store.query_stream("SELECT * WHERE { ?s ?p ?o } LIMIT 5") as qs:
        for row in qs.rows:
            print(row)
```

## Caveats
- `ITripleStoreService.subscribe(...)` docstring describes returning a subscription ID (`str`), but the method signature returns `None`.
- `graph_export_query()` validates `graph_name` as an absolute IRI and raises `ValueError` otherwise.
- `QueryStream.rows` and `QueryStream.triples` are single-use iterators intended to be consumed within the `query_stream` context manager block.
