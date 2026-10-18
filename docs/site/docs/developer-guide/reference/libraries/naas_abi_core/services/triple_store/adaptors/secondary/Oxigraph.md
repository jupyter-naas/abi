# Oxigraph

## What it is
An `ITripleStorePort` adapter for an [Oxigraph](https://oxigraph.org/) RDF triple store over HTTP. It supports SPARQL query/update, basic named-graph operations, and integrates with RDFLib (`Graph`, `URIRef`, etc.). It also provides a streaming query/export API via `sparql_stream`.

## Public API

### Class: `Oxigraph(ITripleStorePort)`
- `__init__(oxigraph_url: str = "http://localhost:7878", timeout: int = 60)`
  - Builds endpoints (`/query`, `/update`, `/store`) and performs a connectivity test.
  - URL resolution:
    - If `oxigraph_url` is the default, it may be resolved via `resolve_local_http_url(..., env_var="OXIGRAPH_URL")`.
    - Otherwise, it can be overridden by `OXIGRAPH_URL` env var.

- `insert(triples: rdflib.Graph, graph_name: rdflib.URIRef)`
  - Sends a SPARQL `INSERT DATA { GRAPH <graph_name> { ... } }` to the update endpoint.
  - Skips any triple containing a blank node (`BNode`).
  - If response is HTTP `413`, falls back to posting N-Triples to `POST {store_endpoint}?default`.
  - If `len(triples) > 100000` and `graph_name is not None`, raises `NotImplementedError`.
  - No-op if `triples` is empty.

- `remove(triples: rdflib.Graph, graph_name: rdflib.URIRef)`
  - Sends a SPARQL `DELETE DATA { GRAPH <graph_name> { ... } }` to the update endpoint.
  - Skips any triple containing a blank node (`BNode`).
  - If response is HTTP `413`, calls the same fallback used for large inserts (`__insert_large_graph`).
  - If `len(triples) > 100000` and `graph_name is not None`, raises `NotImplementedError`.
  - No-op if `triples` is empty.

- `get() -> rdflib.Graph`
  - `GET` from the store endpoint with `Accept: text/turtle` and parses into an RDFLib `Graph`.

- `query(query: str) -> rdflib.query.Result | rdflib.Graph`
  - Routes updates (based on starting keyword) to `/update` and queries to `/query`.
  - For updates: returns an empty `rdflib.query.Result("SELECT")`.
  - For query responses:
    - If JSON SPARQL results: returns an RDFLib `Result` (`SELECT` or `ASK`) populated from bindings.
    - If `application/n-triples` or `text/turtle`: returns an RDFLib `Graph`.
    - Otherwise: raises `ValueError` for unexpected content type.

- `query_stream(query: str) -> contextmanager[QueryStream]`
  - For non-update queries: posts to `/query` with streaming `Accept` header from `sparql_stream.ACCEPT` and yields a parsed streaming reader (`sparql_stream.read_query_response(...)`).
  - For updates: delegates to `super().query_stream(query)`.

- `export(graph_name: rdflib.URIRef | None = None) -> contextmanager[Iterator[Triple]]`
  - Streams triples using `query_stream()`:
    - If `graph_name` provided: uses `graph_export_query(graph_name)`.
    - Else: uses `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }` (default graph, similar to `get()`).
  - Yields `result.triples` iterator.

- `query_view(view: str, query: str) -> rdflib.query.Result | rdflib.Graph`
  - Ignores `view` and delegates to `query(query)`.

- `get_subject_graph(subject: rdflib.URIRef, graph_name: str | rdflib.URIRef) -> rdflib.Graph`
  - Runs a `CONSTRUCT` over the given named graph for `<subject> ?p ?o`.
  - Returns an empty `Graph()` if the underlying `query()` does not return a `Graph`.

- `create_graph(graph_name: rdflib.URIRef) -> None`
  - Executes `CREATE GRAPH <graph_name>`.
  - If Oxigraph returns an error containing `"already exists"`, raises `Exceptions.GraphAlreadyExistsError`.

- `clear_graph(graph_name: rdflib.URIRef) -> None`
  - Executes `CLEAR GRAPH <graph_name>`.

- `drop_graph(graph_name: rdflib.URIRef) -> None`
  - Executes `DROP GRAPH <graph_name>`.

- `list_graphs() -> list[rdflib.URIRef]`
  - Executes `SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }` and returns `URIRef` values.

- `handle_view_event(view, event: OntologyEvent, triple) -> None`
  - Declared but intentionally unimplemented (empty method body).

### Module-level helper
- `_is_update(query: str) -> bool`
  - Returns `True` if the query string starts with one of: `INSERT`, `DELETE`, `CREATE`, `DROP`, `CLEAR`, `LOAD`, `COPY`, `MOVE`, `ADD`.

## Configuration/Dependencies
- Python dependencies:
  - `requests`
  - `rdflib`
  - `naas_abi_core.services.triple_store.TripleStorePorts` (interfaces/types/exceptions)
  - `naas_abi_core.services.triple_store.adaptors.secondary.base.sparql_stream`
  - `naas_abi_core.services.triple_store.resolve.resolve_local_http_url`
- Environment:
  - `OXIGRAPH_URL` can override the configured/default Oxigraph URL.
- Endpoints (derived from `oxigraph_url.rstrip("/")`):
  - Query: `{base}/query`
  - Update: `{base}/update`
  - Store: `{base}/store`

## Usage
```python
from rdflib import Graph, URIRef, RDF, Literal
from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import Oxigraph

ox = Oxigraph(oxigraph_url="http://localhost:7878")

gname = URIRef("http://example.org/graphs/demo")
ox.create_graph(gname)

g = Graph()
alice = URIRef("http://example.org/alice")
g.add((alice, RDF.type, URIRef("http://example.org/Person")))
g.add((alice, URIRef("http://example.org/name"), Literal("Alice")))

ox.insert(g, gname)

res = ox.query(f"SELECT ?s ?p ?o WHERE {{ GRAPH <{gname}> {{ ?s ?p ?o }} }}")
for row in res:
    print(row.s, row.p, row.o)

ox.drop_graph(gname)
```

## Caveats
- Blank nodes are ignored on insert/remove (triples containing `BNode` terms are skipped).
- Large graphs:
  - If `len(triples) > 100000` and a named graph is requested, insert/remove raises `NotImplementedError`.
  - HTTP 413 fallback writes to/removes from the **default graph** via `.../store?default`, not the provided named graph.
- `remove()` on HTTP 413 calls the insert fallback (`__insert_large_graph`) rather than the remove fallback.
- `get()` retrieves *all* triples and can be expensive on large datasets.
- `handle_view_event()` is a no-op.
