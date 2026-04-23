# TripleStoreService__SecondaryAdaptor__OxigraphEmbedded

## What it is
A secondary adaptor implementing `ITripleStorePort` backed by an embedded [Oxigraph](https://oxigraph.org/) store via `pyoxigraph`. It persists data to a directory on disk and exposes basic graph/quad operations plus SPARQL querying, returning results as `rdflib` objects.

## Public API

### Class: `TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(ITripleStorePort)`
Oxigraph-embedded triple store service.

- `__init__(store_path: str, graph_base_iri: str = "http://ontology.naas.ai/graph/default")`
  - Creates/opens an embedded Oxigraph store at `store_path`.
  - Uses `graph_base_iri` as the default graph IRI when no `graph_name` is provided.
  - Reuses a single underlying store per `store_path` across instances (process-wide).

- `insert(triples: rdflib.Graph, graph_name: rdflib.term.URIRef | None = None) -> None`
  - Loads RDF triples into the target named graph (default if `graph_name` is `None`).
  - No-op if `triples` is empty.

- `remove(triples: rdflib.Graph, graph_name: rdflib.term.URIRef | None = None) -> None`
  - Deletes matching triples from the target graph using `DELETE DATA`.
  - Filters out any triple containing a blank node (`BNode`) before deleting.
  - No-op if input is empty or all triples are filtered out.

- `get() -> rdflib.Graph`
  - Returns all triples from both the default graph and any named graphs via a `CONSTRUCT` query.

- `get_subject_graph(subject: rdflib.term.URIRef, graph_name: str | rdflib.term.URIRef) -> rdflib.Graph`
  - Returns a `CONSTRUCT`ed graph of all `(<subject> ?p ?o)` triples.
  - If `graph_name == "*"`, searches default + all named graphs.
  - Otherwise queries only the specified named graph IRI.
  - Raises `Exceptions.SubjectNotFoundError` if no triples are found.

- `query(query: str) -> Any`
  - Executes SPARQL query against Oxigraph.
  - Returns:
    - `rdflib.Graph` for triple/construct results.
    - `rdflib.query.Result` for solution (`SELECT`) and boolean (`ASK`) results (parsed from JSON).
  - Raises `ValueError` for unsupported result types or missing serialized bytes.

- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Pass-through to `query(query)`; `view` is ignored.

- `handle_view_event(view, event, triple) -> None`
  - No-op; always returns `None`.

- `create_graph(graph_name: rdflib.term.URIRef) -> None`
  - Creates a named graph.
  - Raises `Exceptions.GraphAlreadyExistsError` if it already exists.

- `clear_graph(graph_name: rdflib.term.URIRef) -> None`
  - Clears all triples in an existing named graph.
  - Raises `Exceptions.GraphNotFoundError` if not found.

- `drop_graph(graph_name: rdflib.term.URIRef) -> None`
  - Removes a named graph.
  - Raises `Exceptions.GraphNotFoundError` if not found.

- `list_graphs() -> list[rdflib.term.URIRef]`
  - Lists existing named graphs as `URIRef` values.

## Configuration/Dependencies
- Python packages:
  - `pyoxigraph` (required; raises `ImportError` with install hint if missing)
  - `rdflib`
- Filesystem:
  - `store_path` directory is created if it does not exist.
- Threading:
  - Per-instance `RLock` for operations.
  - Global lock and cache (`_stores`) to reuse a single Oxigraph store per `store_path`.

## Usage
```python
from rdflib import Graph, URIRef, Literal

from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded,
)

ts = TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(
    store_path="./oxigraph_store",
    graph_base_iri="http://ontology.naas.ai/graph/default",
)

gname = URIRef("http://example.org/graph/one")

# Create a graph and insert triples
ts.create_graph(gname)

triples = Graph()
s = URIRef("http://example.org/s")
p = URIRef("http://example.org/p")
triples.add((s, p, Literal("v")))
ts.insert(triples, graph_name=gname)

# Query
res_graph = ts.query(f"CONSTRUCT {{ <{s}> ?p ?o }} WHERE {{ GRAPH <{gname}> {{ <{s}> ?p ?o }} }}")
print(len(res_graph))

# List graphs
print(ts.list_graphs())
```

## Caveats
- `remove()` will not delete triples containing blank nodes (`BNode`) because it filters them out before issuing `DELETE DATA`.
- Instances sharing the same `store_path` share the same underlying store object (process-wide cache), which can affect expectations in tests or multi-instance setups.
