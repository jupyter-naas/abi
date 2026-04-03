# ApacheJenaTDB2

## What it is
- An HTTP adapter implementing `ITripleStorePort` for an Apache Jena Fuseki dataset backed by TDB2.
- Derives standard Fuseki endpoints from a base dataset URL:
  - `.../query` for SPARQL read queries
  - `.../update` for SPARQL updates (writes)
  - `.../data` reserved (not used directly in this implementation)
- Verifies connectivity on initialization with a lightweight `ASK` query.

## Public API
### Class: `ApacheJenaTDB2(ITripleStorePort)`
#### `__init__(jena_tdb2_url: str = "http://localhost:3030/ds", timeout: int = 60)`
- Configures endpoints from the dataset URL and tests connectivity.
- Parameters:
  - `jena_tdb2_url`: Base dataset URL (trailing `/` is stripped).
  - `timeout`: Requests timeout in seconds for all HTTP calls.

#### `insert(triples: rdflib.Graph, graph_name: rdflib.URIRef | None = None) -> None`
- Inserts all non-blank-node triples via a single `INSERT DATA` update request.
- If `graph_name` is provided, targets that named graph using `GRAPH <...> { ... }`.
- No-op if `triples` is empty.

#### `remove(triples: rdflib.Graph, graph_name: rdflib.URIRef | None = None) -> None`
- Deletes all non-blank-node triples via a single `DELETE DATA` update request.
- If `graph_name` is provided, targets that named graph.
- No-op if `triples` is empty.

#### `get() -> rdflib.Graph`
- Returns the entire dataset as an RDFLib `Graph` using:
  - `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }`

#### `query(query: str) -> Any`
- Executes SPARQL over HTTP:
  - Update queries (detected by leading keyword after `PREFIX`/`BASE`) go to `/update`.
  - Read queries go to `/query`.
- Return types depend on response content:
  - SPARQL JSON results (`application/sparql-results+json`): returns an iterator of `rdflib.query.ResultRow` for `SELECT`, or a `rdflib.query.Result("ASK")` for `ASK`.
  - RDF payloads (`application/n-triples` or `text/turtle`): returns an `rdflib.Graph`.
  - Update requests: returns `rdflib.query.Result("SELECT")` (placeholder result object).

#### `query_view(view: str, query: str) -> Any`
- Pass-through to `query(query)`. `view` is ignored.

#### `get_subject_graph(subject: rdflib.URIRef) -> rdflib.Graph`
- Constructs and returns triples for a single subject:
  - `CONSTRUCT { <subject> ?p ?o } WHERE { <subject> ?p ?o }`

#### `create_graph(graph_name: rdflib.URIRef) -> None`
- Executes `CREATE GRAPH <graph_name>`.

#### `clear_graph(graph_name: rdflib.URIRef | None = None) -> None`
- If `graph_name is None`: executes `CLEAR DEFAULT`.
- Otherwise: executes `CLEAR GRAPH <graph_name>`.

#### `drop_graph(graph_name: rdflib.URIRef) -> None`
- Executes `DROP GRAPH <graph_name>`.

#### `list_graphs() -> list[rdflib.URIRef]`
- Returns distinct named graphs containing at least one triple:
  - `SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }`

#### `handle_view_event(view, event, triple) -> None`
- Defined but not implemented (`pass`).

## Configuration/Dependencies
- External services:
  - A running Apache Jena Fuseki server with a dataset accessible at `jena_tdb2_url`.
- Python dependencies:
  - `requests`
  - `rdflib`
- Network:
  - Uses HTTP POST/GET to Fuseki endpoints with `timeout` applied.

## Usage
```python
from rdflib import Graph, URIRef, Namespace
from libs.naas_abi_core.naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import ApacheJenaTDB2

EX = Namespace("http://example.org/")

store = ApacheJenaTDB2("http://localhost:3030/ds", timeout=30)

g = Graph()
g.add((EX.alice, EX.knows, EX.bob))

# Insert into default graph
store.insert(g)

# Query (SELECT)
rows = store.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o }")
for row in rows:
    print(row.s, row.p, row.o)

# Named graph operations
ng = URIRef("http://example.org/graph1")
store.create_graph(ng)
store.insert(g, graph_name=ng)
print(store.list_graphs())
store.clear_graph(ng)
store.drop_graph(ng)
```

## Caveats
- Blank nodes are skipped during `insert()` and `remove()` (triples containing `rdflib.BNode` are not sent).
- Each `insert()`/`remove()` call is sent as a single SPARQL Update request; there is no batching/chunking.
- `query()` routing to update/read is based on simple leading-keyword detection; ensure update queries begin with an update keyword (after any `PREFIX`/`BASE` declarations).
- Response handling depends on `Content-Type`; unexpected content types raise `ValueError`.
