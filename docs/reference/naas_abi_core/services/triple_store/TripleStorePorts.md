# TripleStorePorts

## What it is
Abstract interfaces (ports) and shared types for a triple store subsystem:
- Custom exceptions grouped under `Exceptions`
- `OntologyEvent` enum for change events
- Two ABCs defining required methods for implementations:
  - `ITripleStorePort` (low-level adapter/backend)
  - `ITripleStoreService` (service layer with subscriptions and schema helpers)

## Public API

### Exceptions
Container class defining exception types (no behavior beyond type identity):
- `Exceptions.SubjectNotFoundError`
- `Exceptions.SubscriptionNotFoundError`
- `Exceptions.ViewNotFoundError`
- `Exceptions.GraphNotFoundError`
- `Exceptions.GraphAlreadyExistsError`

### OntologyEvent (Enum)
- `OntologyEvent.INSERT` — insertion event
- `OntologyEvent.DELETE` — deletion event

### ITripleStorePort (ABC)
Backend/adapter contract; all methods are abstract:
- `insert(triples: Graph, graph_name: URIRef | None = None)` — insert triples into (optionally) a named graph.
- `remove(triples: Graph, graph_name: URIRef | None = None)` — remove triples from (optionally) a named graph.
- `get() -> Graph` — return the full graph from the store.
- `handle_view_event(view: tuple[URIRef|None, URIRef|None, URIRef|None], event: OntologyEvent, triple: tuple[URIRef|None, URIRef|None, URIRef|None])` — handle an event for a view pattern.
- `query(query: str) -> rdflib.query.Result` — execute a SPARQL query.
- `query_view(view: str, query: str) -> rdflib.query.Result` — execute a query scoped to a view (string identifier).
- `get_subject_graph(subject: URIRef) -> Graph` — return triples for a specific subject.
- `create_graph(graph_name: URIRef)` — create a named graph.
  - May raise: `Exceptions.GraphAlreadyExistsError`
- `clear_graph(graph_name: URIRef | None = None)` — clear triples from a graph (default or named).
  - May raise: `Exceptions.GraphNotFoundError`
- `drop_graph(graph_name: URIRef)` — drop a named graph.
  - May raise: `Exceptions.GraphNotFoundError`
- `list_graphs() -> list[URIRef]` — list named graphs.

### ITripleStoreService (ABC)
Service-layer contract; all methods are abstract:
- `subscribe(topic: tuple[URIRef|None, URIRef|None, URIRef|None], callback: Callable[[bytes], None], event_type: OntologyEvent | None = None, graph_name: URIRef | str | None = "*") -> None`
  - Register a callback for matching triple events (INSERT/DELETE).
  - Note: despite docstring mentioning a subscription ID, the signature returns `None`.
- `insert(triples: Graph, graph_name: URIRef | None = None)` — insert triples.
- `remove(triples: Graph, graph_name: URIRef | None = None)` — remove triples.
- `get() -> Graph` — get all triples.
- `query(query: str) -> rdflib.query.Result` — execute a SPARQL query.
- `query_view(view: str, query: str) -> rdflib.query.Result` — query within a view.
- `get_subject_graph(subject: str) -> Graph` — get triples for a subject.
- `create_graph(graph_name: URIRef)` — create a named graph.
  - May raise: `Exceptions.GraphAlreadyExistsError`
- `clear_graph(graph_name: URIRef | None = None)` — clear a graph.
  - May raise: `Exceptions.GraphNotFoundError`
- `drop_graph(graph_name: URIRef)` — drop a named graph.
  - May raise: `Exceptions.GraphNotFoundError`
- `list_graphs() -> list[URIRef]` — list named graphs.
- `load_schema(filepath: str)` — load schema triples from a file into the store.
- `get_schema_graph() -> Graph` — retrieve schema/ontology triples.

## Configuration/Dependencies
- Depends on **rdflib**:
  - `rdflib.Graph`, `rdflib.URIRef`, and `rdflib.query.Result`
- Uses Python standard library:
  - `abc.ABC`, `abc.abstractmethod`
  - `enum.Enum`
  - typing: `Callable`, `Dict`, `List`, `Tuple`

## Usage
This module defines interfaces only; you must implement them to use a concrete store.

```python
from rdflib import Graph, URIRef
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStorePort

class InMemoryTripleStore(ITripleStorePort):
    def __init__(self):
        self._g = Graph()

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        for t in triples:
            self._g.add(t)

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        for t in triples:
            self._g.remove(t)

    def get(self) -> Graph:
        return self._g

    # Remaining abstract methods must be implemented for instantiation.
```

## Caveats
- Both `ITripleStorePort` and `ITripleStoreService` are abstract; they cannot be instantiated without implementing **all** abstract methods.
- `ITripleStoreService.subscribe(...)` has a return type of `None`, but its docstring describes returning a subscription ID; implementations should reconcile this mismatch.
