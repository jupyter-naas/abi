# TripleStorePorts

## What it is
Abstract port/service interfaces and shared types for a triple store layer built on **rdflib**, including:
- A set of domain exceptions.
- An `OntologyEvent` enum for INSERT/DELETE notifications.
- Two ABCs (`ITripleStorePort`, `ITripleStoreService`) defining the required methods for implementations.

## Public API

### Exceptions
Container class grouping custom exceptions (all subclasses of `Exception`):
- `Exceptions.SubjectNotFoundError` — subject graph lookup failed.
- `Exceptions.SubscriptionNotFoundError` — subscription ID not found (unsubscribe is currently commented out).
- `Exceptions.ViewNotFoundError` — view lookup failed.
- `Exceptions.GraphNotFoundError` — named graph not found (when backend can detect it).
- `Exceptions.GraphAlreadyExistsError` — named graph already exists (when backend can detect it).

### OntologyEvent (Enum)
- `OntologyEvent.INSERT` — insert event type.
- `OntologyEvent.DELETE` — delete event type.

### ITripleStorePort (ABC)
Backend-facing port for a triple store implementation.

Methods:
- `insert(triples: Graph, graph_name: URIRef)` — insert triples into a named graph.
- `remove(triples: Graph, graph_name: URIRef)` — remove triples from a named graph.
- `get() -> Graph` — return the complete RDF graph.
- `handle_view_event(view, event: OntologyEvent, triple)` — handle a view-related event.
  - `view`: `Tuple[URIRef|None, URIRef|None, URIRef|None]`
  - `triple`: `Tuple[URIRef|None, URIRef|None, URIRef|None]`
- `query(query: str) -> rdflib.query.Result` — execute a SPARQL query.
- `query_view(view: str, query: str) -> rdflib.query.Result` — query within a named “view” (implementation-defined).
- `get_subject_graph(subject: URIRef, graph_name: str | URIRef) -> Graph` — return triples for a subject from a graph.
- `create_graph(graph_name: URIRef)` — create a named graph.
  - May raise `Exceptions.GraphAlreadyExistsError`.
- `clear_graph(graph_name: URIRef)` — clear triples from a named graph.
  - May raise `Exceptions.GraphNotFoundError`.
- `drop_graph(graph_name: URIRef)` — drop a named graph.
  - May raise `Exceptions.GraphNotFoundError`.
- `list_graphs() -> list[URIRef]` — list named graph URIs.

### ITripleStoreService (ABC)
Service-facing interface (higher-level than the port). Includes subscription/event concepts and schema helpers.

Methods:
- `subscribe(topic, callback, event_type: OntologyEvent|None = None, graph_name: URIRef|str = "*") -> None`
  - `topic`: `(subject, predicate, object)` pattern; `None` acts as wildcard per element.
  - `callback`: `Callable[[bytes], None]` invoked with serialized event bytes.
  - `event_type`: restrict to INSERT/DELETE, or both when `None`.
  - Note: docstring mentions returning a subscription ID, but the signature returns `None`.
- `insert(triples: Graph, graph_name: URIRef)` — insert triples into a named graph.
- `remove(triples: Graph, graph_name: URIRef)` — remove triples from a named graph.
- `get() -> Graph` — return the complete RDF graph.
- `query(query: str) -> rdflib.query.Result` — execute a SPARQL query.
- `query_view(view: str, query: str) -> rdflib.query.Result` — query within a named “view”.
- `get_subject_graph(subject: str, graph_name: str | URIRef) -> Graph` — return triples for a subject; may raise `SubjectNotFoundError` (as documented).
- `create_graph(graph_name: URIRef)` — create an empty named graph; may raise `Exceptions.GraphAlreadyExistsError`.
- `clear_graph(graph_name: URIRef)` — clear triples from a graph; may raise `Exceptions.GraphNotFoundError`.
- `drop_graph(graph_name: URIRef)` — drop a named graph; may raise `Exceptions.GraphNotFoundError`.
- `list_graphs() -> list[URIRef]` — list named graph URIs.
- `load_schema(filepath: str)` — load an RDF/OWL schema file into the store.
- `get_schema_graph() -> Graph` — return only schema/ontology triples.

## Configuration/Dependencies
- Depends on **rdflib**:
  - `rdflib.Graph`
  - `rdflib.URIRef`
  - `rdflib.query.Result`
- No concrete configuration is defined in this module (interfaces only).

## Usage
These are abstract interfaces; you must implement them. Minimal example showing how to type against the service:

```python
from rdflib import Graph, URIRef
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService

def run(store: ITripleStoreService):
    g = Graph()
    # add triples to g as needed...
    graph_name = URIRef("http://example.org/graph")
    store.create_graph(graph_name)
    store.insert(g, graph_name)
    result = store.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10")
    print(list(result))
```

## Caveats
- `ITripleStoreService.subscribe(...)` has a signature returning `None`, but its docstring describes returning a subscription ID (`str`).
- `unsubscribe` is present only as commented-out code; it is not part of the public API in this file.
- Exceptions for graph existence (`GraphNotFoundError`, `GraphAlreadyExistsError`) are documented as conditional “when backend can detect it”.
