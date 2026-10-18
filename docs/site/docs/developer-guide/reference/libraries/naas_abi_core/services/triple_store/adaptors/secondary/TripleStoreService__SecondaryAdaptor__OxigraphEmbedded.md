# TripleStoreService__SecondaryAdaptor__OxigraphEmbedded

## What it is
A secondary triple-store adaptor implementing `ITripleStorePort` using an embedded [Oxigraph](https://oxigraph.org/) store via `pyoxigraph`. Data is persisted to a filesystem directory and queried with SPARQL, returning results as `rdflib` objects or streamed iterators.

## Public API

### Class: `TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(ITripleStorePort)`
Oxigraph-backed triple store adaptor (embedded).

- `__init__(store_path: str, graph_base_iri: str = "http://ontology.naas.ai/graph/default") -> None`
  - Creates/opens an Oxigraph store at `store_path` (directory is created if needed).
  - Uses `graph_base_iri` as the default graph IRI when no `graph_name` is provided.
  - Reuses the same underlying store per `store_path` across instances (process-wide cache).

- `insert(triples: rdflib.Graph, graph_name: rdflib.term.URIRef | None = None) -> None`
  - Loads triples into the named graph (or default graph when `graph_name is None`).
  - No-op if `triples` is empty.

- `remove(triples: rdflib.Graph, graph_name: rdflib.term.URIRef | None = None) -> None`
  - Deletes matching triples from the specified graph via `DELETE DATA`.
  - Filters out triples containing any blank nodes (`BNode`) before deletion.
  - No-op if input is empty or everything is filtered out.

- `get() -> rdflib.Graph`
  - Returns all triples from the default graph and all named graphs using a `CONSTRUCT` query.

- `get_subject_graph(subject: rdflib.term.URIRef, graph_name: str | rdflib.term.URIRef) -> rdflib.Graph`
  - Returns a `CONSTRUCT` graph of all triples `<subject> ?p ?o`.
  - If `graph_name == "*"`, searches default + all named graphs; otherwise queries only that graph IRI.
  - Raises `Exceptions.SubjectNotFoundError` if no triples are found.

- `query(query: str) -> Any`
  - Executes SPARQL against Oxigraph and returns:
    - `rdflib.Graph` for triple results (`CONSTRUCT`/triple results).
    - `rdflib.query.Result` for `SELECT` and `ASK` (parsed from JSON).
  - Raises `ValueError` for unsupported result types or missing serialized bytes.

- `query_stream(query: str) -> Iterator[QueryStream]` *(context manager)*
  - Yields a `QueryStream` wrapping Oxigraph’s lazy results:
    - `"ASK"`: `ask_answer=bool(...)`
    - `"SELECT"`: `vars=[...]` and `rows` generator of dicts (`rdflib` terms)
    - `"CONSTRUCT"`: `triples` generator of `(s, p, o)` as `rdflib` terms
  - Note: results are thread-affine; consume the stream on the same thread that executed the query.

- `export(graph_name: rdflib.term.URIRef | None = None) -> Iterator[Iterator[Triple]]` *(context manager)*
  - Yields an iterator of triples for:
    - one named graph when `graph_name` is provided
    - otherwise all graphs (similar to `get()`, but as an iterator).
  - Output terms are converted to `rdflib` nodes.

- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Delegates to `query(query)`; `view` is not used.

- `handle_view_event(view, event, triple) -> None`
  - No-op.

- `create_graph(graph_name: rdflib.term.URIRef) -> None`
  - Creates a named graph.
  - Raises `Exceptions.GraphAlreadyExistsError` if it already exists.

- `clear_graph(graph_name: rdflib.term.URIRef) -> None`
  - Clears all triples in a named graph.
  - Raises `Exceptions.GraphNotFoundError` if it does not exist.

- `drop_graph(graph_name: rdflib.term.URIRef) -> None`
  - Removes a named graph.
  - Raises `Exceptions.GraphNotFoundError` if it does not exist.

- `list_graphs() -> list[rdflib.term.URIRef]`
  - Returns the list of existing named graphs.

### Function: `_term(node: Any) -> rdflib.term.Node`
Internal helper converting `pyoxigraph` terms to `rdflib` nodes:
- `NamedNode` → `URIRef`
- `BlankNode` → `BNode`
- language-tagged literals → `Literal(..., lang=...)`
- `xsd:string` → plain `Literal(value)`
- other datatypes → `Literal(value, datatype=URIRef(datatype))`

## Configuration/Dependencies
- Python packages:
  - `pyoxigraph` (required). If missing, `__init__` raises `ImportError` with install hint.
  - `rdflib`
- Filesystem:
  - `store_path` directory is created (`mkdir(..., exist_ok=True)`).
- Concurrency:
  - Per-instance `threading.RLock` guards operations.
  - Global `_stores_lock` and `_stores` cache reuse one store per `store_path`.

## Usage
```python
from rdflib import Graph, URIRef, Literal

from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded import (
    TripleStoreService__SecondaryAdaptor__OxigraphEmbedded,
)

ts = TripleStoreService__SecondaryAdaptor__OxigraphEmbedded("./oxigraph_store")

gname = URIRef("http://example.org/graph")
ts.create_graph(gname)

g = Graph()
s = URIRef("http://example.org/s")
p = URIRef("http://example.org/p")
g.add((s, p, Literal("v")))
ts.insert(g, graph_name=gname)

out = ts.get_subject_graph(s, gname)
print(len(out))

with ts.query_stream(f"SELECT ?o WHERE {{ GRAPH <{gname}> {{ <{s}> <{p}> ?o }} }}") as stream:
    for row in stream.rows:
        print(row["o"])
```

## Caveats
- `remove()` will not delete triples containing blank nodes (`BNode`); those triples are filtered out before issuing `DELETE DATA`.
- `query_stream()` yields lazy results that must be consumed on the same thread that performed the query (per the inline warning).
- Multiple adaptor instances created with the same `store_path` share a single underlying store object within the process.
