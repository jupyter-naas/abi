# `TripleStoreService`

## What it is
- Async client-side facade for a remote RDF triple store service.
- Supports SPARQL queries (regular RPC and streamed), graph management, and triple insert/remove.
- Uses `rdflib` objects for RDF data interchange; streamed operations decode N-Triples frames.

## Public API

### Classes

- `QueryStream`
  - Container for streamed SPARQL query results.
  - Fields:
    - `result_type: str` — `"ASK"`, `"SELECT"`, `"CONSTRUCT"`, or `"DESCRIBE"`.
    - `vars: list[str]` — variable names for `SELECT`.
    - `ask_answer: bool | None` — answer for `ASK`.
    - `rows: AsyncIterator[dict]` — streamed `SELECT` rows; each row maps variable name to an rdflib term.
    - `triples: AsyncIterator[tuple]` — streamed triples for `CONSTRUCT`/`DESCRIBE`.
  - `rows` and `triples` are **single-use** iterators, valid only within the `query_stream` context.

- `TripleStoreService(client)`
  - Main service wrapper; `client` must expose RPC methods matching operation names used below.

### Methods (`TripleStoreService`)

- `async insert(triples, graph_name) -> None`
  - Inserts triples into `graph_name`.
  - `triples` must be an `rdflib.Graph`-like object supporting `serialize(format="nt", encoding="utf-8")`.

- `async remove(triples, graph_name) -> None`
  - Removes triples from `graph_name`.

- `async get() -> rdflib.Graph`
  - Exports the whole store (via streaming) and returns it as an `rdflib.Graph`.

- `async get_subject_graph(subject: str, graph_name: str = "*") -> rdflib.Graph`
  - Retrieves a graph (N-Triples) for a subject within a graph (or `"*"`), returns an `rdflib.Graph`.

- `async query(query: str) -> rdflib.query.Result`
  - Executes a SPARQL query and returns an `rdflib.query.Result`.

- `async query_view(view: str, query: str) -> rdflib.query.Result`
  - Executes a SPARQL query against a named view and returns an `rdflib.query.Result`.

- `async with query_stream(query: str) -> QueryStream`
  - Runs a SPARQL query and streams results:
    - `ASK`: `QueryStream.ask_answer`
    - `SELECT`: `QueryStream.vars` and `QueryStream.rows`
    - `CONSTRUCT`/`DESCRIBE`: `QueryStream.triples`

- `async with export(graph_name=None) -> AsyncIterator[tuple]`
  - Streams triples for the whole store or a specific graph.

- `async create_graph(graph_name) -> None`
  - Creates a named graph.

- `async clear_graph(graph_name) -> None`
  - Clears a named graph.

- `async drop_graph(graph_name) -> None`
  - Drops a named graph.

- `async list_graphs() -> list`
  - Lists graph names; returns a list of `rdflib.URIRef`.

- `subscribe(*args, **kwargs)`
  - Always raises `NotImplementedError` (subscriptions not exposed).

## Configuration/Dependencies
- Requires a `client` that implements the RPC operations used:
  - `insert`, `remove`, `get_subject_graph`, `query`, `query_view`, `create_graph`, `clear_graph`, `drop_graph`, `list_graphs`
- Streaming relies on:
  - `naas_abi_sdk.services._streams.open_stream`
  - `TRANSFER_PREFIX = "abi.svc.triple_store.v1.transfer"`
- RDF support requires `rdflib`.
  - If missing, methods that need RDF will raise:
    - `ImportError("Install naas-abi-sdk[rdf] for RDF service values")`
- RPC errors:
  - Low-level `naas_abi_sdk.transport.RPCError` is converted to a domain error via `naas_abi_sdk.services.errors.domain_error`.
  - Streaming raises `RPCError("UNAVAILABLE", "No triple store engine hosts streams")` if no stream host is available.

## Usage

```python
import asyncio
from rdflib import Graph, URIRef, Literal, Namespace

# client must be provided by your transport layer (not shown here)
from naas_abi_sdk.services.triple_store import TripleStoreService

async def main(client):
    svc = TripleStoreService(client)

    EX = Namespace("http://example.org/")
    g = Graph()
    g.add((EX.s, EX.p, Literal("o")))

    await svc.create_graph(URIRef("http://example.org/graph"))
    await svc.insert(g, graph_name="http://example.org/graph")

    result = await svc.query("ASK { ?s ?p ?o }")
    print(bool(result.askAnswer))

    async with svc.query_stream("SELECT ?s ?p ?o WHERE { ?s ?p ?o }") as stream:
        async for row in stream.rows:
            print(row)  # dict: variable name -> rdflib term

# asyncio.run(main(client))
```

## Caveats
- `QueryStream.rows` and `QueryStream.triples` are **single-use** async iterators and only valid within the `query_stream` context manager.
- Streaming requires an available stream host; otherwise `_frames()` raises an `RPCError` with code `"UNAVAILABLE"`.
- RDF functionality requires `rdflib`; install the extra `naas-abi-sdk[rdf]` as indicated by the import error message.
