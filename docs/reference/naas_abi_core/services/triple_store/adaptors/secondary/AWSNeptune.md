# AWSNeptune

## What it is

An AWS Neptune triple-store adapter implementing `ITripleStorePort` to:

- Discover a Neptune SPARQL endpoint via AWS API
- Sign HTTP requests with AWS SigV4 IAM authentication
- Execute SPARQL queries/updates and manage named graphs
- Optionally connect to VPC-only Neptune via an SSH tunnel (`AWSNeptuneSSHTunnel`)

## Public API

### Constants / Enums

- `NEPTUNE_DEFAULT_GRAPH_NAME: URIRef`  
  Default named graph URI used when a graph name is not provided.

- `QueryType (Enum)`
  - `INSERT_DATA` / `DELETE_DATA`: used by `graph_to_query()`.

- `QueryMode (Enum)`
  - `QUERY` / `UPDATE`: used by `query()` and `submit_query()` payload keys.

### Class: `AWSNeptune(ITripleStorePort)`

#### Constructor

- `AWSNeptune(aws_region_name, aws_access_key_id, aws_secret_access_key, db_instance_identifier, default_graph_name=NEPTUNE_DEFAULT_GRAPH_NAME)`
  - Discovers endpoint/port using `boto3` Neptune client `describe_db_instances`.
  - Builds `neptune_sparql_url` as `https://{endpoint}:{port}/sparql`.

#### Methods

- `submit_query(data, timeout=60) -> requests.Response`
  - Sends a signed `POST` to the SPARQL endpoint.
  - Uses `Accept: application/sparql-results+xml` and form encoding.

- `insert(triples: Graph, graph_name: URIRef)`
  - Converts graph to `INSERT DATA { GRAPH <...> { ... } }` and submits as update.
  - If `graph_name is None`, uses `default_graph_name`.
  - Note: signature requires `graph_name`; passing `None` is handled.

- `remove(triples: Graph, graph_name: URIRef)`
  - Converts graph to `DELETE DATA { GRAPH <...> { ... } }` and submits as update.

- `get() -> Graph`
  - Retrieves all triples via `select ?s ?p ?o where {?s ?p ?o}` and returns an RDFLib `Graph`.

- `query(query: str, query_mode: QueryMode = QueryMode.QUERY) -> rdflib.query.Result`
  - Submits query/update.
  - Determines query type using `SPARQLWrapper(...).queryType`:
    - `SELECT`, `ASK` → parses XML results (`XMLResultParser`)
    - `CONSTRUCT`, `DESCRIBE` → parses RDF results (`RDFResultParser`)
    - otherwise raises `ValueError`.

- `query_view(view: str, query: str) -> rdflib.query.Result`
  - Currently ignores `view` and calls `query(query)`.

- `get_subject_graph(subject: URIRef, graph_name: str | URIRef) -> Graph`
  - Runs a `GRAPH <graph_name> { <subject> ?p ?o }` SELECT and returns an RDFLib `Graph`.

- `graph_to_query(graph: Graph, query_type: QueryType, graph_name: URIRef) -> str`
  - Builds an `INSERT DATA` / `DELETE DATA` SPARQL statement:
    - Adds non-core namespace prefixes from the input graph.
    - Skips any triple containing blank nodes (`rdflib.BNode`).
    - Serializes terms using `.n3()`.

#### Named graph management

- `create_graph(graph_name: URIRef) -> None`  
  Submits `CREATE GRAPH <graph_name>`.

- `clear_graph(graph_name: URIRef) -> None`  
  Submits `CLEAR GRAPH <graph_name>`.

- `drop_graph(graph_name: URIRef) -> None`  
  Submits `DROP GRAPH <graph_name>`.

- `copy_graph(source_graph_name: URIRef, target_graph_name: URIRef) -> None`  
  Submits `COPY GRAPH <source> TO <target>`.

- `add_graph_to_graph(source_graph_name: URIRef, target_graph_name: URIRef) -> None`  
  Submits `ADD GRAPH <source> TO <target>`.

- `list_graphs() -> list[URIRef]`  
  Queries `SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }` and returns URIRefs.

#### Interface hook

- `handle_view_event(view, event: OntologyEvent, triple) -> None`
  - No-op (`pass`).

### Class: `AWSNeptuneSSHTunnel(AWSNeptune)`

Extends `AWSNeptune` to access VPC-only Neptune via bastion host.

- `AWSNeptuneSSHTunnel(..., bastion_host, bastion_port, bastion_user, bastion_private_key, default_graph_name=...)`
  - Initializes base `AWSNeptune`, then:
    - Creates an SSH tunnel (`sshtunnel.SSHTunnelForwarder`)
    - Monkey-patches `socket.getaddrinfo` to resolve the Neptune hostname to `127.0.0.1` (global process change)
    - Updates `neptune_sparql_url` to use the tunnel local port while keeping the Neptune hostname in the URL.

## Configuration/Dependencies

### Required Python dependencies

- `boto3`, `botocore` (AWS API + SigV4 signing)
- `requests` (HTTP to Neptune)
- `rdflib` (graph and result parsing)
- `SPARQLWrapper` (used to detect query type)

### Optional (only for `AWSNeptuneSSHTunnel`)

- `paramiko`
- `sshtunnel`

If `paramiko` is missing, `AWSNeptuneSSHTunnel` raises an `ImportError` with installation guidance.

### AWS / Neptune requirements

- IAM credentials with access to:
  - `neptune:DescribeDBInstances` (endpoint discovery)
  - `neptune-db:*` as needed for SPARQL operations (via SigV4 signed requests)
- Network access to the Neptune endpoint:
  - direct for `AWSNeptune`
  - via bastion host SSH access for `AWSNeptuneSSHTunnel`

## Usage

### Direct connection

```python
from rdflib import Graph, URIRef, RDF
from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import AWSNeptune

neptune = AWSNeptune(
    aws_region_name="us-east-1",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    db_instance_identifier="my-neptune-instance",
)

g = Graph()
g.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/T")))

neptune.insert(g, graph_name=None)  # uses default graph
res = neptune.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o }")
for row in res:
    print(row)
```

### SSH tunnel (VPC deployment)

```python
from rdflib import Graph, URIRef, RDF
from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import AWSNeptuneSSHTunnel

with open("bastion_key.pem", "r") as f:
    key = f.read()

neptune = AWSNeptuneSSHTunnel(
    aws_region_name="us-east-1",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    db_instance_identifier="my-neptune-instance",
    bastion_host="bastion.example.com",
    bastion_port=22,
    bastion_user="ec2-user",
    bastion_private_key=key,
)

g = Graph()
g.add((URIRef("http://example.org/s"), RDF.type, URIRef("http://example.org/T")))
neptune.insert(g, graph_name=None)
```

## Caveats

- `insert()` / `remove()` signatures require `graph_name`, but `insert()` explicitly handles `graph_name is None`; callers may pass `None`.
- `get()` retrieves *all* triples and can be expensive for large datasets.
- `graph_to_query()` skips any triple containing a blank node (`rdflib.BNode`).
- `AWSNeptuneSSHTunnel`:
  - Monkey-patches `socket.getaddrinfo` globally (process-wide), which may affect other networking code.
  - Uses `paramiko.AutoAddPolicy()` (trust-on-first-use host key behavior).
  - Temporarily writes the private key to a temp file during tunnel setup.
