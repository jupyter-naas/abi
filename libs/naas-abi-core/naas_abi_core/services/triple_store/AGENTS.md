# Triple Store Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/triple_store/`. Canonical reference for agents.

## Purpose

CRUD + SPARQL facade over RDF named graphs. Publishes domain events on every mutation. Supports view subscriptions (callback on SPO patterns) and schema loading.

## Files

| File | Role |
|---|---|
| `TripleStorePorts.py` | `ITripleStorePort`, `ITripleStoreService`, exceptions |
| `TripleStoreService.py` | Public service: SPARQL + graph ops + event emission + subscribe + schema loading |
| `TripleStoreFactory.py` | Pre-wired service builders |
| `resolve.py` | Resolve local `abi dev` HTTP service URLs for standalone scripts |
| `oxigraph_server.py` | Minimal HTTP SPARQL server wrapping `pyoxigraph.Store` for `abi dev` no-docker runtime |
| `adaptors/secondary/` | Concrete adapters |
| `adaptors/secondary/base/` | Filesystem/ObjectStorage shared helper (`TripleStoreService__SecondaryAdaptor__FileBase`) |
| `tests/triple_store__secondary_adapter__generic_test.py` | **Generic adapter contract tests** — reuse for new adapters |
| `ontologies/` | RDF event classes (`TriplesInserted`, `TriplesRemoved`, `GraphCreated`, `GraphCleared`, `GraphDropped`, `SchemaLoaded`, `SchemaRemoved`) |

## Port (`TripleStorePorts.py`)

```python
class ITripleStorePort:
    def insert(triples: Graph, graph_name: URIRef)
    def remove(triples: Graph, graph_name: URIRef)
    def get() -> Graph
    def handle_view_event(view, event: OntologyEvent, triple)
    def query(query: str) -> rdflib.query.Result
    def query_view(view: str, query: str) -> rdflib.query.Result
    def get_subject_graph(subject: URIRef, graph_name: str | URIRef) -> Graph
    def create_graph(graph_name: URIRef)         # raises GraphAlreadyExistsError
    def clear_graph(graph_name: URIRef)          # raises GraphNotFoundError
    def drop_graph(graph_name: URIRef)           # raises GraphNotFoundError
    def list_graphs() -> list[URIRef]
```

## Service API (`TripleStoreService.py`)

```python
insert(triples, graph_name)                              # → publishes TriplesInserted
remove(triples, graph_name)                              # → publishes TriplesRemoved
get() -> Graph
query(sparql) -> rdflib.query.Result
query_view(view, sparql) -> rdflib.query.Result
get_subject_graph(subject, graph_name="*") -> Graph
create_graph(graph_name)                                 # → publishes GraphCreated
clear_graph(graph_name)                                  # → publishes GraphCleared
drop_graph(graph_name)                                   # → publishes GraphDropped
list_graphs() -> list[URIRef]

subscribe(topic=(s|None, p|None, o|None), callback, event_type=None, graph_name="*")
load_schema(filepath, schema_cache=None)                 # → publishes SchemaLoaded
load_schemas(filepaths)                                  # parallel, max 8 workers
remove_schema(filepath)                                  # → publishes SchemaRemoved
get_schema_graph() -> Graph
```

## Available Adapters (`adaptors/secondary/`)

| Adapter | Backend |
|---|---|
| `AWSNeptune.py` | AWS Neptune (also `AWSNeptuneSSHTunnel`) |
| `ApacheJenaTDB2.py` | Apache Jena Fuseki (TDB2) over HTTP |
| `Oxigraph.py` | Oxigraph HTTP endpoint |
| `TripleStoreService__SecondaryAdaptor__OxigraphEmbedded.py` | Oxigraph embedded in-process |
| `TripleStoreService__SecondaryAdaptor__Filesystem.py` | Local RDF files |
| `TripleStoreService__SecondaryAdaptor__ObjectStorage.py` | S3-compatible object storage |

## Factory (`TripleStoreFactory.py`)

```python
TripleStoreFactory.TripleStoreServiceNaas(naas_api_key, workspace_id, storage_name, base_prefix="ontologies")
TripleStoreFactory.TripleStoreServiceFilesystem(path)
TripleStoreFactory.TripleStoreServiceAWSNeptuneSSHTunnel(...)   # all args optional, reads env if None
TripleStoreFactory.TripleStoreServiceOxigraph(oxigraph_url=None)        # local abi dev oxigraph URL
TripleStoreFactory.TripleStoreServiceApacheJenaTDB2(jena_tdb2_url=None) # JENA_TDB2_URL or http://localhost:3030/ds
TripleStoreFactory.TripleStoreServiceOxigraphEmbedded(store_path, graph_base_iri="http://ontology.naas.ai/graph/default")
```

## `oxigraph_server.py`

Run an embedded Oxigraph store as an HTTP SPARQL endpoint (single-writer file lock):

```bash
python -m naas_abi_core.services.triple_store.oxigraph_server \
    --location <store_path> --bind 127.0.0.1:7878
```

Endpoints: `POST /query`, `POST /update`, `GET /store`, `POST /store?default` (bulk insert), `DELETE /store?default` (bulk delete).

## Tests

```bash
# unit / events
uv run pytest libs/naas-abi-core/naas_abi_core/services/triple_store/TripleStoreService_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/triple_store/TripleStoreService_events_test.py

# adapter unit tests
uv run pytest libs/naas-abi-core/naas_abi_core/services/triple_store/adaptors/secondary/

# integration (require running server)
uv run pytest libs/naas-abi-core/naas_abi_core/services/triple_store/adaptors/secondary/ApacheJenaTDB2_integration_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/triple_store/adaptors/secondary/Oxigraph_integration_test.py

# concurrency
uv run pytest libs/naas-abi-core/naas_abi_core/services/triple_store/adaptors/secondary/TripleStoreService__SecondaryAdaptor__Filesystem_concurrency_test.py

# generic contract tests (run these against any new adapter)
uv run pytest libs/naas-abi-core/naas_abi_core/services/triple_store/tests/triple_store__secondary_adapter__generic_test.py
```

## Adding a new adapter

1. Implement every abstract method of `ITripleStorePort` in `adaptors/secondary/<Name>.py`.
2. If file-based, inherit from `adaptors/secondary/base/TripleStoreService__SecondaryAdaptor__FileBase` and reuse `iri_hash`, `triples_by_subject`.
3. Add a `<Name>_test.py` (unit) and `<Name>_integration_test.py` if applicable.
4. Wire it into the **generic contract tests** at `tests/triple_store__secondary_adapter__generic_test.py` — that is the source of truth for adapter behavior.
5. Add a factory builder to `TripleStoreFactory.py` for any zero-config setup.

## NATS RPC adapters

`adapters/primary/triple_store__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/TripleStoreSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/triple_store/v1/`.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
The maximum message size is 8 MiB (or a lower broker limit); oversized replies
return non-retryable `PAYLOAD_TOO_LARGE`, and micro-service error headers raise
instead of becoming an empty success. Larger results require streaming or a
storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
