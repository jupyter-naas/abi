# AWSNeptune

## What it is

An AWS Neptune triple store adapter that:
- Discovers a Neptune instance endpoint via `boto3` (`describe_db_instances`)
- Signs SPARQL HTTP requests with AWS SigV4 (`neptune-db` service)
- Supports RDFLib `Graph` insert/remove and SPARQL query/update operations
- Optionally connects to VPC-only Neptune via an SSH tunnel (`AWSNeptuneSSHTunnel`)

## Public API

### Enums
- `QueryType`
  - `INSERT_DATA`, `DELETE_DATA`: used when generating SPARQL from an RDFLib graph.
- `QueryMode`
  - `QUERY`, `UPDATE`: used when submitting SPARQL operations.

### Constants
- `NEPTUNE_DEFAULT_GRAPH_NAME`: `URIRef("http://aws.amazon.com/neptune/vocab/v01/DefaultNamedGraph")`

### Classes

#### `AWSNeptune(ITripleStorePort)`
Constructor:
- `__init__(aws_region_name, aws_access_key_id, aws_secret_access_key, db_instance_identifier, default_graph_name=NEPTUNE_DEFAULT_GRAPH_NAME)`
  - Creates a `boto3.Session`, discovers endpoint/port, builds `neptune_sparql_url`, stores credentials for SigV4.

Methods:
- `submit_query(data, timeout=60) -> requests.Response`
  - POSTs to `/sparql` with SigV4-signed headers. Expects XML results (`Accept: application/sparql-results+xml`).
- `insert(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Converts graph to SPARQL `INSERT DATA` for a named graph (defaults to `default_graph_name`) and submits as `UPDATE`.
- `remove(triples: Graph, graph_name: URIRef | None = None) -> None`
  - Converts graph to SPARQL `DELETE DATA` for a named graph (defaults to `default_graph_name`) and submits as `UPDATE`.
- `get() -> Graph`
  - Retrieves all triples via `select ?s ?p ?o where {?s ?p ?o}` and returns an RDFLib `Graph`.
- `query(query: str, query_mode: QueryMode = QueryMode.QUERY) -> rdflib.query.Result`
  - Runs SPARQL via Neptune endpoint.
  - Parses results as:
    - XML for `SELECT` / `ASK`
    - RDF for `CONSTRUCT` / `DESCRIBE`
  - Uses `SPARQLWrapper` only to detect query type.
- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Currently ignores `view` and delegates to `query(query)`.
- `get_subject_graph(subject: URIRef) -> Graph`
  - `SELECT ?s ?p ?o WHERE { <subject> ?p ?o }` and returns triples for that subject.
- `graph_to_query(graph: Graph, query_type: QueryType, graph_name: URIRef) -> str`
  - Generates SPARQL `INSERT DATA` / `DELETE DATA` with `GRAPH <...> { ... }`.
  - Skips triples containing blank nodes.
  - Emits non-core namespace prefixes from `graph.namespaces()`.
- Graph management:
  - `create_graph(graph_name: URIRef) -> None`
  - `clear_graph(graph_name: URIRef | None = None) -> None` (uses `CLEAR DEFAULT` when `None`)
  - `drop_graph(graph_name: URIRef) -> None`
  - `copy_graph(source_graph_name: URIRef, target_graph_name: URIRef) -> None`
  - `add_graph_to_graph(source_graph_name: URIRef, target_graph_name: URIRef) -> None`
  - `list_graphs() -> list[URIRef]`
- `handle_view_event(view, event, triple) -> None`
  - No-op (`pass`).

#### `AWSNeptuneSSHTunnel(AWSNeptune)`
Constructor:
- `__init__(aws_region_name, aws_access_key_id, aws_secret_access_key, db_instance_identifier, bastion_host, bastion_port, bastion_user, bastion_private_key, default_graph_name=NEPTUNE_DEFAULT_GRAPH_NAME)`
  - Initializes base `AWSNeptune`, then creates an SSH tunnel via `sshtunnel.SSHTunnelForwarder`.
  - Monkey-patches `socket.getaddrinfo` so connections to the Neptune hostname resolve to `127.0.0.1` (to traverse the local tunnel).
  - Updates `neptune_sparql_url` to use the tunnel’s local port while keeping the original hostname.

## Configuration/Dependencies

### Required
- AWS credentials and region:
  - `aws_region_name`, `aws_access_key_id`, `aws_secret_access_key`
- Neptune instance identifier:
  - `db_instance_identifier` (used with `neptune.describe_db_instances`)

Python packages:
- `boto3`, `botocore`
- `requests`
- `rdflib`
- `SPARQLWrapper`

### Optional (only for `AWSNeptuneSSHTunnel`)
- `paramiko`
- `sshtunnel`

Notes:
- `bastion_port` may be provided as `str`; it is converted to `int` if possible.

## Usage

### Direct connection

```python
from rdflib import Graph, URIRef, RDF, Literal
from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import AWSNeptune

neptune = AWSNeptune(
    aws_region_name="us-east-1",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    db_instance_identifier="my-neptune-instance",
)

g = Graph()
alice = URIRef("http://example.org/alice")
g.add((alice, RDF.type, URIRef("http://example.org/Person")))
g.add((alice, URIRef("http://example.org/name"), Literal("Alice")))
neptune.insert(g)

res = neptune.query("SELECT ?p ?o WHERE { <http://example.org/alice> ?p ?o }")
for row in res:
    print(row)
```

### VPC Neptune via SSH tunnel

```python
from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import AWSNeptuneSSHTunnel

neptune = AWSNeptuneSSHTunnel(
    aws_region_name="us-east-1",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    db_instance_identifier="my-neptune-instance",
    bastion_host="bastion.example.com",
    bastion_port=22,
    bastion_user="ubuntu",
    bastion_private_key="-----BEGIN ... -----END ...",
)

print(neptune.list_graphs())
```

## Caveats

- `get()` fetches **all triples** and may be expensive on large datasets.
- `graph_to_query()` skips any triple containing a blank node (`rdflib.BNode`).
- `AWSNeptuneSSHTunnel` monkey-patches global `socket.getaddrinfo`, which can affect other networking in the same process.
- `query_view()` does not enforce view scoping; it runs the query against the whole dataset.
