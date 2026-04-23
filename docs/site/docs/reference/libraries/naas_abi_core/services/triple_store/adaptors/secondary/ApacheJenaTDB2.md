# ApacheJenaTDB2

## What it is
- An HTTP adapter implementing `ITripleStorePort` for an Apache Jena Fuseki dataset backed by TDB2.
- Derives Fuseki endpoints from a base dataset URL:
  - `/<dataset>/query` for SPARQL queries
  - `/<dataset>/update` for SPARQL updates
  - `/<dataset>/data` reserved (not used directly in this adapter)
- Verifies connectivity on initialization via an `ASK` query.

## Public API

### Class: `ApacheJenaTDB2(ITripleStorePort)`
HTTP triple-store adapter for Fuseki/TDB2.

#### `__init__(jena_tdb2_url="http://localhost:3030/ds", timeout=60, max_retries=3, retry_delay=0.5, key_value_service=None)`
- Configures endpoints, retry behavior, and optional distributed write locking.
- Sends a test `ASK { ?s ?p ?o }` query to confirm connectivity.

#### `insert(triples: rdflib.Graph, graph_name: rdflib.URIRef | None = None) -> None`
- Inserts triples using a single `INSERT DATA { ... }` update request.
- If `graph_name` is provided, inserts into `GRAPH <graph_name> { ... }`.
- Skips blank-node-containing triples.
- No-op if `triples` is empty.

#### `remove(triples: rdflib.Graph, graph_name: rdflib.URIRef | None = None) -> None`
- Removes triples using a single `DELETE DATA { ... }` update request.
- If `graph_name` is provided, deletes from `GRAPH <graph_name> { ... }`.
- Skips blank-node-containing triples.
- No-op if `triples` is empty.

#### `query(query: str) -> Any`
- Routes query to:
  - `/update` if it looks like a SPARQL Update (`INSERT`, `DELETE`, `CREATE`, `DROP`, `CLEAR`, `LOAD`, `COPY`, `MOVE`, `ADD`, `WITH`)
  - `/query` otherwise
- Returns:
  - `rdflib.query.Result` for `ASK` and for update calls (updates return `Result("SELECT")` placeholder)
  - `Iterator[rdflib.query.ResultRow]` for `SELECT` JSON results
  - `rdflib.Graph` for RDF results (N-Triples or Turtle), parsed into an RDFLib graph
- Raises `ValueError` for unexpected response content types.

#### `get() -> rdflib.Graph`
- Returns all triples in the dataset via:
  - `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }`
- Returns an empty `Graph` if the query doesn’t produce a graph.

#### `query_view(view: str, query: str) -> Any`
- Pass-through to `query(query)`. `view` is unused.

#### `get_subject_graph(subject: rdflib.URIRef, graph_name: str | rdflib.URIRef) -> rdflib.Graph`
- Returns triples for a subject from a named graph using `CONSTRUCT` over `GRAPH <graph_name>`.

#### `create_graph(graph_name: rdflib.URIRef) -> None`
- Executes `CREATE GRAPH <graph_name>`.

#### `clear_graph(graph_name: rdflib.URIRef | None = None) -> None`
- If `graph_name` is `None`: executes `CLEAR DEFAULT`.
- Else: executes `CLEAR GRAPH <graph_name>`.

#### `drop_graph(graph_name: rdflib.URIRef) -> None`
- Executes `DROP GRAPH <graph_name>`.

#### `list_graphs() -> list[rdflib.URIRef]`
- Executes `SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }`.
- Returns only bindings where `?g` is a `URIRef`.

#### `handle_view_event(view, event, triple) -> None`
- Present but unimplemented (`pass`).

## Configuration/Dependencies
- **Runtime dependencies**
  - `requests` (HTTP client; uses `requests.Session`)
  - `rdflib` (graphs and query result structures)
- **External service**
  - Apache Jena Fuseki dataset endpoint (e.g. `http://localhost:3030/ds`)
- **Optional distributed locking**
  - `key_value_service`: a `KeyValueService` implementation providing:
    - `set_if_not_exists(key, value, ttl=...) -> bool`
    - `delete_if_value_matches(key, value) -> bool/None`
  - If not provided, write serialization is only within-process (`threading.Lock`).

## Usage

```python
from rdflib import Graph, URIRef, Namespace

from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import ApacheJenaTDB2

adapter = ApacheJenaTDB2(jena_tdb2_url="http://localhost:3030/ds")

EX = Namespace("http://example.org/")

g = Graph()
g.add((EX.s, EX.p, EX.o))

# Insert into default graph
adapter.insert(g)

# Query (SELECT)
rows = adapter.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10")
for row in rows:
    print(row)

# Read whole dataset (CONSTRUCT)
all_triples = adapter.get()
print(len(all_triples))

# Named graph operations
graph_name = URIRef("http://example.org/graph")
adapter.create_graph(graph_name)
adapter.insert(g, graph_name=graph_name)
print(adapter.list_graphs())
adapter.clear_graph(graph_name)
adapter.drop_graph(graph_name)
```

## Caveats
- **Blank nodes are dropped** from `insert()` and `remove()` payloads (any triple containing a `BNode` is skipped).
- **No batching/chunking**: each `insert()`/`remove()` call becomes one SPARQL Update request; very large graphs may hit HTTP/proxy/server limits.
- **Retry behavior**:
  - Retries only on HTTP `500` and `503`, with exponential backoff and jitter.
  - Other failures (4xx, connection errors, etc.) raise immediately.
- **Update detection is heuristic**: update vs query routing is based on leading keywords after stripping `PREFIX`/`BASE`.
