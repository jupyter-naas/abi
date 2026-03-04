# Oxigraph

## What it is
An `ITripleStorePort` adapter that connects to an Oxigraph RDF triple store over HTTP, supporting:
- SPARQL query (`/query`) and update (`/update`)
- Bulk store operations via `/store`
- RDFLib `Graph` integration for insert/remove/get and CONSTRUCT results

## Public API
### Class: `Oxigraph(ITripleStorePort)`
- `__init__(oxigraph_url: str = "http://localhost:7878", timeout: int = 60)`
  - Initializes endpoints and tests connectivity by issuing a simple query.
- `insert(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Inserts RDFLib triples.
  - Uses SPARQL `INSERT DATA` for up to 100,000 triples; uses `/store?default` with N-Triples for larger graphs (default graph only).
  - Skips triples containing blank nodes.
- `remove(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Removes RDFLib triples.
  - Uses SPARQL `DELETE DATA` for up to 100,000 triples; uses HTTP `DELETE` on `/store?default` for larger graphs (default graph only).
  - Skips triples containing blank nodes.
- `get() -> Graph`
  - Fetches **all** triples from the store endpoint and parses as Turtle into an RDFLib `Graph`.
- `query(query: str) -> rdflib.query.Result`
  - Executes SPARQL:
    - If query starts with an update keyword (`INSERT`, `DELETE`, `CREATE`, `DROP`, `CLEAR`, `LOAD`, `COPY`, `MOVE`, `ADD`): POST to `/update`, returns an empty RDFLib `Result("SELECT")`.
    - Otherwise: POST to `/query` and parses:
      - SPARQL JSON results into an iterator of RDFLib `ResultRow` (SELECT/ASK-style responses).
      - `application/n-triples` or `text/turtle` into an RDFLib `Graph` (CONSTRUCT/DESCRIBE).
- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Currently ignores `view` and delegates to `query()`.
- `get_subject_graph(subject: URIRef) -> Graph`
  - Runs a CONSTRUCT query for `<subject> ?p ?o` and returns an RDFLib `Graph` (empty graph if response is not a graph).
- `create_graph(graph_name: URIRef) -> None`
  - Runs `CREATE GRAPH <graph_name>`.
- `clear_graph(graph_name: URIRef | None = None) -> None`
  - If `None`: `CLEAR DEFAULT`; else `CLEAR GRAPH <graph_name>`.
- `drop_graph(graph_name: URIRef) -> None`
  - Runs `DROP GRAPH <graph_name>`.
- `list_graphs() -> list[URIRef]`
  - Returns distinct named graphs that contain at least one triple.

### Interface hook (present but not implemented)
- `handle_view_event(view, event: OntologyEvent, triple) -> None`
  - No-op (`pass`).

## Configuration/Dependencies
- Requires a running Oxigraph instance with endpoints:
  - `GET/POST {oxigraph_url}/query`
  - `POST {oxigraph_url}/update`
  - `GET/POST/DELETE {oxigraph_url}/store`
- Python dependencies:
  - `requests`
  - `rdflib`
  - `naas_abi_core.services.triple_store.TripleStorePorts` (`ITripleStorePort`, `OntologyEvent`)
- Optional (only used in `__main__` example):
  - `python-dotenv`

## Usage
```python
from rdflib import Graph, URIRef, RDF, Literal
from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import Oxigraph

ox = Oxigraph("http://localhost:7878")

g = Graph()
alice = URIRef("http://example.org/alice")
g.add((alice, RDF.type, URIRef("http://example.org/Person")))
g.add((alice, URIRef("http://example.org/name"), Literal("Alice")))

ox.insert(g)

rows = ox.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5")
for row in rows:
    print(row.s, row.p, row.o)

alice_graph = ox.get_subject_graph(alice)
print("alice triples:", len(alice_graph))

ox.remove(g)
```

## Caveats
- Blank nodes (`rdflib.BNode`) are filtered out during insert/remove (triples containing any blank node are skipped).
- Large-graph operations (`len(triples) > 100000`) use the `/store?default` endpoint and **do not support named graphs** (`graph_name` raises `NotImplementedError`).
- `get()` retrieves the entire dataset and can be expensive on large stores.
- `remove()` fallback on HTTP `413` calls the *insert* large-graph helper (likely unintended); behavior is as implemented.
