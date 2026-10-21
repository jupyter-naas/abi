# ApacheJenaTDB2

## What it is
- An HTTP adapter implementing `ITripleStorePort` for an Apache Jena Fuseki dataset backed by TDB2.
- Derives Fuseki endpoints from a base dataset URL:
  - `/<dataset>/query` for SPARQL queries
  - `/<dataset>/update` for SPARQL updates
  - `/<dataset>/data` reserved (not used directly here)
- Verifies connectivity on initialization via an `ASK { ?s ?p ?o }` probe with retries.
- Supports:
  - atomic per-request writes (`INSERT DATA` / `DELETE DATA`)
  - retry on transient server failures (HTTP `500`, `503`)
  - optional distributed write serialization via a `KeyValueService`
  - result streaming via `query_stream()` / `export()`

## Public API

### Functions

#### `_recover_truncated_sparql_results_json(text: str) -> dict[str, Any] | None`
- Best-effort recovery of usable SPARQL JSON when Fuseki returns HTTP 200 but truncates the JSON mid-stream (e.g., appends a Java exception).

#### `_parse_sparql_results_json(text: str) -> dict[str, Any]`
- Parses SPARQL JSON, using `_recover_truncated_sparql_results_json()` if parsing fails.

### Class: `ApacheJenaTDB2(ITripleStorePort)`
HTTP triple-store adapter for Fuseki/TDB2.

#### `__init__(jena_tdb2_url="http://localhost:3030/ds", timeout=60, max_retries=3, retry_delay=0.5, key_value_service=None)`
- Configures endpoints, HTTP session, timeout and retry behavior.
- Creates:
  - process-local write lock (`threading.Lock`)
  - optional distributed lock key derived from dataset URL hash
- Calls `_test_connection()` (connectivity probe with retry/backoff).
- **Raises** `Exceptions.RequestError` on persistent connectivity failure.

#### `insert(triples: rdflib.Graph, graph_name: rdflib.URIRef | None = None) -> None`
- Sends one SPARQL update request:
  - `INSERT DATA { ... }` into default graph
  - or `INSERT DATA { GRAPH <graph_name> { ... } }`
- No-op if `triples` is empty.
- Skips any triple containing a blank node (`rdflib.BNode`).

#### `remove(triples: rdflib.Graph, graph_name: rdflib.URIRef | None = None) -> None`
- Sends one SPARQL update request:
  - `DELETE DATA { ... }` from default graph
  - or `DELETE DATA { GRAPH <graph_name> { ... } }`
- No-op if `triples` is empty.
- Skips any triple containing a blank node.

#### `query(query: str) -> Any`
- Routes to:
  - `/update` if the query is detected as an update (based on leading keyword after stripping `PREFIX`/`BASE`)
  - `/query` otherwise
- Return types:
  - For SPARQL Update: returns `rdflib.query.Result("SELECT")` as a placeholder
  - For `ASK`: returns `rdflib.query.Result("ASK")` with `.askAnswer`
  - For `SELECT`: returns `rdflib.query.Result("SELECT")` with `.vars` and `.bindings`
  - For RDF responses (N-Triples or Turtle): returns an `rdflib.Graph`
- Retries malformed SPARQL JSON parsing up to `max_retries`.
- **Raises**:
  - `Exceptions.RequestError` for HTTP errors / transport errors
  - `ValueError` for unexpected response content types

#### `query_stream(query: str) -> contextmanager[QueryStream]`
- Streams query results as they are produced by Fuseki (TSV rows or N-Triples), parsed line-by-line.
- Uses `naas_abi_core.services.triple_store.adaptors.secondary.base.sparql_stream`.
- If query is an update, falls back to the base class `query_stream`.
- The stream may raise `Exceptions.RequestError` after yielding partial results if the server aborts mid-response.

#### `export(graph_name: rdflib.URIRef | None = None) -> contextmanager[Generator[Triple, None, None]]`
- Exposes a streaming triple generator using `query_stream()`:
  - default: `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }`
  - named graph: uses `graph_export_query(graph_name)`

#### `get() -> rdflib.Graph`
- Returns all triples via `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }`.
- Returns an empty `Graph` if the query does not return a graph.

#### `query_view(view: str, query: str) -> Any`
- Pass-through to `query(query)`; `view` is unused.

#### `get_subject_graph(subject: rdflib.URIRef, graph_name: str | rdflib.URIRef) -> rdflib.Graph`
- `CONSTRUCT`s all `(subject, ?p, ?o)` triples from a named graph.

#### `create_graph(graph_name: rdflib.URIRef) -> None`
- Executes: `CREATE GRAPH <graph_name>`.

#### `clear_graph(graph_name: rdflib.URIRef | None = None) -> None`
- If `graph_name is None`: executes `CLEAR DEFAULT`.
- Else: executes `CLEAR GRAPH <graph_name>`.

#### `drop_graph(graph_name: rdflib.URIRef) -> None`
- Executes: `DROP GRAPH <graph_name>`.

#### `list_graphs() -> list[rdflib.URIRef]`
- Executes: `SELECT DISTINCT ?g WHERE { GRAPH ?g { } FILTER(isIRI(?g)) }`
- Returns only `URIRef` graph names.
- Uses `FILTER(isIRI(?g))` to avoid Jena issues with null/blank graph nodes and truncated JSON responses.

#### `handle_view_event(...) -> None`
- Present but unimplemented (`pass`).

## Configuration/Dependencies
- **Python dependencies**
  - `requests` (HTTP client via `requests.Session`)
  - `rdflib` (graphs, terms, and `rdflib.query.Result`)
- **Internal ABI dependencies**
  - `naas_abi_core.services.triple_store.TripleStorePorts` (ports/types/exceptions)
  - `naas_abi_core.services.triple_store.adaptors.secondary.base.sparql_stream` (streaming)
- **External service**
  - Apache Jena Fuseki dataset endpoint, e.g. `http://localhost:3030/ds`
- **Optional distributed locking**
  - Provide `key_value_service` implementing:
    - `set_if_not_exists(key, value, ttl=...) -> bool`
    - `delete_if_value_matches(key, value) -> bool | None`
  - Lock key is derived from the dataset URL; TTL is `timeout + 10` seconds.

## Usage

```python
from rdflib import Graph, Namespace, URIRef
from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import ApacheJenaTDB2

adapter = ApacheJenaTDB2(jena_tdb2_url="http://localhost:3030/ds")

EX = Namespace("http://example.org/")
g = Graph()
g.add((EX.s, EX.p, EX.o))

# Write to default graph
adapter.insert(g)

# Read via SELECT
res = adapter.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5")
for row in res:
    print(row)

# Named graph ops
gn = URIRef("http://example.org/graph")
adapter.create_graph(gn)
adapter.insert(g, graph_name=gn)
print(adapter.list_graphs())
adapter.clear_graph(gn)
adapter.drop_graph(gn)

# Stream export (triples generator)
with adapter.export() as triples:
    for i, (s, p, o) in zip(range(3), triples):
        print(s, p, o)
```

## Caveats
- **Blank nodes are skipped** in `insert()` and `remove()` (any triple containing `rdflib.BNode` is omitted).
- **No batching/chunking**: each `insert()`/`remove()` call generates one SPARQL Update request; very large graphs may exceed HTTP/proxy limits or time out.
- **Retry policy**
  - Retries only on HTTP `500` and `503` (exponential backoff + jitter).
  - Transport errors (timeouts/connection failures) are surfaced as `Exceptions.RequestError` (no retry in `_post_query`/`_post_update` for transport exceptions).
- **Update detection is heuristic**: routing to `/update` is based on leading SPARQL keywords after stripping `PREFIX`/`BASE`.
- **Streaming results can be partial**: `query_stream()` may yield some rows/triples then raise if Fuseki aborts mid-response.
