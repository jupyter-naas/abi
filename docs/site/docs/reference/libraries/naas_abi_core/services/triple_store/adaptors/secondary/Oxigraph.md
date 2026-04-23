# Oxigraph

## What it is
An `ITripleStorePort` adapter that connects to an Oxigraph RDF triple store over HTTP, supporting SPARQL query/update operations and RDFLib `Graph` integration.

## Public API
### Class: `Oxigraph(ITripleStorePort)`
- `__init__(oxigraph_url: str = "http://localhost:7878", timeout: int = 60)`
  - Initializes endpoints (`/query`, `/update`, `/store`) and validates connectivity via a test query.
- `insert(triples: rdflib.Graph, graph_name: rdflib.URIRef)`
  - Inserts RDF triples into a named graph via SPARQL `INSERT DATA`.
  - Skips triples containing blank nodes.
  - If HTTP 413 occurs, falls back to posting N-Triples to the `/store?default` endpoint.
  - If `len(triples) > 100000` and `graph_name is not None`, raises `NotImplementedError`.
- `remove(triples: rdflib.Graph, graph_name: rdflib.URIRef)`
  - Removes RDF triples via SPARQL `DELETE DATA`.
  - Skips triples containing blank nodes.
  - If HTTP 413 occurs, currently calls the large **insert** fallback (likely unintended).
  - If `len(triples) > 100000` and `graph_name is not None`, raises `NotImplementedError`.
- `get() -> rdflib.Graph`
  - Retrieves all triples from the store endpoint and parses them as Turtle into an RDFLib `Graph`.
- `query(query: str) -> rdflib.query.Result | rdflib.Graph`
  - Executes SPARQL:
    - Update commands (e.g., `INSERT`, `DELETE`, `CREATE`, `DROP`, etc.) are sent to `/update`.
    - Other queries are sent to `/query`.
  - Returns:
    - For SELECT/ASK JSON results: an iterator of RDFLib `ResultRow`.
    - For CONSTRUCT/DESCRIBE results in N-Triples/Turtle: an RDFLib `Graph`.
    - For updates: an empty `rdflib.query.Result("SELECT")`.
- `query_view(view: str, query: str)`
  - Ignores `view` and delegates to `query()`.
- `get_subject_graph(subject: rdflib.URIRef, graph_name: str | rdflib.URIRef) -> rdflib.Graph`
  - Runs a `CONSTRUCT` query for all `(subject, ?p, ?o)` inside the specified named graph.
- `create_graph(graph_name: rdflib.URIRef) -> None`
  - Executes `CREATE GRAPH <graph_name>`.
- `clear_graph(graph_name: rdflib.URIRef) -> None`
  - Executes `CLEAR GRAPH <graph_name>`.
- `drop_graph(graph_name: rdflib.URIRef) -> None`
  - Executes `DROP GRAPH <graph_name>`.
- `list_graphs() -> list[rdflib.URIRef]`
  - Returns URIs of graphs that contain at least one triple.
- `handle_view_event(view, event: OntologyEvent, triple)`
  - No-op (`pass`).

## Configuration/Dependencies
- Requires:
  - `requests`
  - `rdflib`
  - `naas_abi_core.services.triple_store.TripleStorePorts` (`ITripleStorePort`, `OntologyEvent`)
- Oxigraph endpoints (derived from `oxigraph_url`):
  - Query: `{oxigraph_url}/query`
  - Update: `{oxigraph_url}/update`
  - Store: `{oxigraph_url}/store`
- Optional environment usage in module’s `__main__`:
  - `OXIGRAPH_URL` (default: `http://localhost:7878`)
  - Uses `python-dotenv` only in the script block, not required for importing the adapter.

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

rows = ox.query(f"SELECT ?s ?p ?o WHERE {{ GRAPH <{gname}> {{ ?s ?p ?o }} }}")
for row in rows:
    print(row.s, row.p, row.o)

alice_graph = ox.get_subject_graph(alice, gname)
print(len(alice_graph))

ox.remove(g, gname)
ox.drop_graph(gname)
```

## Caveats
- Blank nodes are not inserted/removed (triples containing `BNode` terms are skipped).
- Large-graph behavior:
  - For `len(triples) > 100000`, named-graph insert/remove is explicitly unsupported (`NotImplementedError`).
  - HTTP 413 fallback writes to the **default** graph via `/store?default`, not the provided named graph.
- `remove()` 413 fallback calls the large **insert** routine (`__insert_large_graph`) instead of the large remove routine. This is likely a bug and may not remove anything in that case.
- `get()` fetches *all* triples; can be expensive for large datasets.
- `handle_view_event()` is unimplemented.
