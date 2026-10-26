# Triple Store Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/triple_store/`. Canonical reference for agents.

## Purpose

CRUD + SPARQL facade over RDF named graphs. Publishes domain events on every mutation. Supports view subscriptions (callback on SPO patterns) and schema loading, from a file of the engine or from content sent by a remote module.

## Files

| File | Role |
|---|---|
| `TripleStorePorts.py` | `ITripleStorePort`, `ITripleStoreService`, exceptions |
| `TripleStoreService.py` | Public service: SPARQL + graph ops + event emission + subscribe + schema loading (files and content) |
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
    # Streamed reads (non-abstract: the defaults read query()/get())
    def query_stream(query: str) -> ContextManager[QueryStream]
    def export(graph_name: URIRef | None = None) -> ContextManager[Iterator[Triple]]
```

Streamed reads (docs/adr/20261003_nats-streamed-results.md): `QueryStream` has
`result_type`, `vars`, `ask_answer`, and lazy `rows` (dicts, unbound variables
absent) or `triples`. Read them once, inside the `with`. Adapters that can
stream override the defaults: Oxigraph and ApacheJenaTDB2 (TSV and N-Triples
parsed line by line in `adaptors/secondary/base/sparql_stream.py`; a backend
aborting mid-response raises `RequestError` from the iterator), OxigraphEmbedded
(pyoxigraph's lazy results: open and read on ONE thread, another thread touching
them aborts the process), and the NATS client.

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
query_stream(sparql) -> ContextManager[QueryStream]     # → TripleStoreError on failure
export(graph_name=None) -> ContextManager[Iterator[Triple]]

subscribe(topic=(s|None, p|None, o|None), callback, event_type=None, graph_name="*")
load_schema(filepath, schema_cache=None)                 # → publishes SchemaLoaded
load_schema_content(source, content, file_last_update_time=None) -> bool
                                                         # same, from Turtle text; → SchemaLoaded
load_schemas(filepaths)                                  # parallel, max 8 workers
remove_schema(filepath)                                  # → publishes SchemaRemoved
get_schema_graph() -> Graph
```

## Schema loading

`internal:Schema` metadata (`filePath`, `hash`, `fileLastUpdateTime`, base64 `content`)
lives in the schema graph `http://ontology.naas.ai/graph/schema`, next to the triples.
`load_schema(filepath)` and `load_schema_content(source, content)` share one
implementation, `_apply_schema_content(source, content, update time, entries, format,
base, validate=None)`: no entry → insert the triples and the metadata; same hash → write nothing (a hash
comparison, no parse); different hash → apply the diff (triples added and removed) and
swap the metadata. New content is parsed once there, and `validate` (for
`load_schema_content`, the refusal of the service's own `internal:` vocabulary) checks
that parse: unchanged content is neither parsed nor checked. `source` is the `filePath` key: a file path for engine modules,
`module/<module_id>/<path>` for a remote module's ontology.

- `load_schema` logs and swallows a failure (as it always did) and returns nothing;
  `load_schema_content` raises: `Exceptions.InvalidSchemaError` for content that is not
  Turtle (checked before any write, so nothing is written) or that uses the service's own
  `http://triple-store.internal` vocabulary (a file could otherwise forge another source's
  `internal:Schema` entry), and returns whether the graph was written. Both publish
  `SchemaLoaded` or `TripleStoreError`.
- Relative IRIs resolve against the file's URI for a file, and against
  `http://ontology.naas.ai/<source>` for content, never against the working directory.
- Content loads run one at a time (a lock), so two replicas of a module starting together
  cannot both add the same source.
- Loading is additive. Nothing unloads a source whose file was removed: its triples stay,
  as for in-engine modules (`remove_schema(filepath)` removes one by hand).

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

`/query` and `GET /store` stream their response (chunked) from one dedicated
thread per request; a syntax error is still a 400, an error after the first
bytes truncates the body. `adaptors/secondary/Oxigraph_http_test.py` runs the
generic contract against it in-process.

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
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB (docs/adr/20261003_nats-rpc-overflow.md); above
that, at the overflow host's capacity, or with an older peer, the call fails
with non-retryable `PAYLOAD_TOO_LARGE`. Micro-service error headers raise
instead of becoming an empty success. Overflowed values are held whole in
memory; results that should not be require streaming or a storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

### `load_schema` (a remote module's ontology)

`abi.svc.triple_store.v1.load_schema` (`LoadSchemaRequest { context, source, content_ttl }` →
`LoadSchemaResponse { error, changed }`) calls `load_schema_content`; it is the one endpoint
that needs the domain service (`NOT_SUPPORTED` over a bare port). The primary adapter checks:

- `source` is `module/<module_id>/<relative path ending in .ttl>` (`parse_schema_source`):
  at most 512 characters; module id as discovery names a module (letters, digits, `_`,
  `.`, `:`, `-`); path segments of letters, digits, `_`, `.`, `-`, none empty, `.` or `..`.
  Else `INVALID_ARGUMENT`. This also keeps quotes and newlines out of the stored key.
- The caller identity (the token's `sub`, `_caller_identity`) is `<module_id>`, or a
  first-party identity (`api`, `engine`, `dagster`), which may load any `module/` source.
  Else `PERMISSION_DENIED`, before anything is parsed. Module keys cannot assert a
  first-party identity (Decision (2026-10-25) below), so a module never loads
  under another id. Other operations still have no identity scoping.
- Content that is not UTF-8 or not Turtle: `INVALID_ARGUMENT`, nothing written.
- A file above the broker limit travels through RPC overflow like any request (the
  SDK facade `load_schema(source, content)`, run by `run_module` for a module's
  `ontologies/`, see `libs/naas-abi-sdk/AGENTS.md`).

Tests: `adapters/primary/triple_store__primary_adapter__NATS_test.py` (authorization and
validation, no broker) and `..._NATS_integration_test.py` (an SDK module against a real
`nats-server`: load, restart writes nothing, changed file applies the diff, another
module's id refused, upload above the broker limit).

Streamed reads go through `transfer/v1` sessions on
`abi.svc.triple_store.v1.transfer` (operations `query` and `export`, frames in
`adapters/triple_store_stream_codec.py`): the primary produces each stream on
its own thread (`nats_transfer.thread_frames`), the client fetches frames as the
caller iterates, and falls back to the unary call against an older engine.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.

## Decision (2026-10-25): remote modules load their ontologies

**Decision.** A remote module's `ontologies/**/*.ttl` reaches the shared schema graph through
`load_schema(source, content_ttl)`, content-based since the engine cannot read the module's
disk, and scoped to the caller's identity: a module loads only under `module/<its id>/`
(`PERMISSION_DENIED` otherwise), the first-party identities (`api`, `engine`, `dagster`) any
`module/` source. Module keys cannot assert a first-party identity. Content may not use the
`http://triple-store.internal` vocabulary, which would let a module forge another source's
`internal:Schema`. The SDK sends the files once its instance is `READY` or `DEGRADED`,
retrying in the background.

**Consequences.**
- Loading is additive: a file a module later removes or renames stays in the schema graph,
  as in-engine; `load_schema` has no unload.
- The schema graph is shared, so a source removes a triple (its changed content no longer
  asserts it, or the source is removed) only when no other stored schema asserts it
  (`_asserted_elsewhere`): a module cannot delete a core class by repeating it and dropping
  it again. When another stored schema cannot be read, nothing is removed.
- Other triple-store operations have no identity scoping: a module with the `triple_store`
  dependency reads and writes the engine's triples, as before.

