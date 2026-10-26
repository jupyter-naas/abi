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
| `iam_catalog.py` | IAM action catalog |
| `sparql_access.py` | What a SPARQL query reads and an update touches, for authorization |
| `TripleStoreService_authorization_test.py` | Authorization contract: FROM, GRAPH, default graph, streams, exports |

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

Streamed reads: `QueryStream` has
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
TripleStoreFactory.TripleStoreServiceNaas(
    naas_api_key, workspace_id, storage_name, base_prefix="ontologies"
)
TripleStoreFactory.TripleStoreServiceFilesystem(path)
TripleStoreFactory.TripleStoreServiceAWSNeptuneSSHTunnel(
    ...
)  # all args optional, reads env if None
TripleStoreFactory.TripleStoreServiceOxigraph(
    oxigraph_url=None
)  # local abi dev oxigraph URL
TripleStoreFactory.TripleStoreServiceApacheJenaTDB2(
    jena_tdb2_url=None
)  # JENA_TDB2_URL or http://localhost:3030/ds
TripleStoreFactory.TripleStoreServiceOxigraphEmbedded(
    store_path, graph_base_iri="http://ontology.naas.ai/graph/default"
)
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

## Authorization

Every operation is checked in the domain service against IAM, for the caller of
the current `CallContext`, so in process and over NATS answer the same. The
cross-cutting pattern (`ResourceGuard`, errors, the create rule, who owns the
check) is in [services/iam/AGENTS.md](../iam/AGENTS.md), "Enforcing in a data
service". The catalog is `iam_catalog.py`, registered by the serving engine at
boot. A caller who cannot see a resource gets `Exceptions.GraphNotFoundError`
(`GRAPH_NOT_FOUND`); one who can see it but not act gets `PermissionDeniedError`
(`PERMISSION_DENIED`). A service not wired into an engine with IAM (a library
use, a NATS facade whose server checks) does not check. The contract test is
`TripleStoreService_authorization_test.py`: no policy, granted and denied
principals, in process and over NATS.

### Resources and actions

* `graph/<iri>` is a named graph (`opaque` id, placed); the store's default
  graph is `graph/default` (an encoded IRI always holds `%3A`, so the two never
  collide). `view/<name>` is a platform-level view. `schema/<source>` (`path`
  id, platform-level) is a schema of the schema graph by its source.
* `LoadSchema` covers the bookkeeping too: the caller needs no right on the
  schema graph itself. The service checks the source, then reads and writes the
  graph as the engine, and a source removes only triples no other stored schema
  asserts.
* Actions (subject is the operation under `abi.svc.triple_store.v1.`):

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListGraphs` | list | each `graph/<iri>` | `list_graphs` |
| `Get` | read | each graph in the dump; the result holds only readable graphs | `get` |
| `GetSubjectGraph` | read | `graph/<iri>` when a graph is named, else filtered over all graphs | `get_subject_graph` |
| `Query` | read | the query's dataset (below) | `query` |
| `QueryStream` | read | as `Query` | transfer, operation `query` |
| `QueryView` | read | `view/<name>`, plus the `Query` rules on the graphs it reads | `query_view` |
| `Export` | read | `graph/<iri>`, or filtered over all graphs when none is given | transfer, operation `export` |
| `Subscribe` | read | `graph/<iri>`, or every graph for `*` | in process only |
| `Insert` | write | `graph/<iri>` (`default` with no graph) | `insert` |
| `Remove` | write | `graph/<iri>` | `remove` |
| `CreateGraph` | write | `graph/<iri>` (creates) | `create_graph` |
| `ClearGraph` | admin | `graph/<iri>` | `clear_graph` |
| `DropGraph` | admin | `graph/<iri>` | `drop_graph` |
| `HandleViewEvent` | admin | `view/<name>` | `handle_view_event` |
| `LoadSchema` | write | `schema/<source>` (platform-level): a module's ontology is `schema/module/<module id>/<path>` | `load_schema` |

### Names are validated before the check

IAM percent-encodes an id, so any string matches a prefix pattern whatever
follows it; a store that interpolates the raw string would run something else.
So graph names and subjects are absolute IRIs (`checked_iri`) in `insert`,
`remove`, `create_graph`, `clear_graph`, `drop_graph`, `export`, `subscribe` and
`get_subject_graph` (the subject too), before any check and with no
denied/not-found oracle: `Exceptions.InvalidRequest` (`INVALID_ARGUMENT`).
Adapters that build SPARQL from strings write graph names with `iri_n3`, which
validates again. Graphs the SPARQL parser finds in a request are validated too,
all of them before any check: rdflib keeps the backslash of an escaped prefixed
name (`g:\/private`) that the SPARQL grammar and the stores drop, so IAM would
check `http://g\/private` while the store drops `http://g/private`, a graph a
Deny names. Only the literals `default` and `*` are taken as they are.

### SPARQL queries (`query`, `query_stream`, `query_view`; `sparql_access.py`)

For a caller who may not read every graph:

* every graph the query names (`FROM`, `FROM NAMED`, `GRAPH <iri>`, in `EXISTS`
  too) must be readable: one that is not is `GraphNotFoundError` or
  `PermissionDeniedError` by the usual rule;
* the query runs over a `QueryDataset` of the graphs the caller may read:
  `GRAPH ?g` ranges over the readable named graphs and the default graph is the
  readable graphs only, whatever union-default setting the backend has;
* a `SERVICE` anywhere needs every graph;
* an unparsable request is `Exceptions.InvalidRequest` (`INVALID_ARGUMENT`), and
  so is an update sent to `query_view`, for every caller (a view is queried,
  never updated; a view query is always parsed for this).

How an adapter confines the query: it gets the dataset through `query_dataset` /
`query_stream_dataset`. HTTP stores (Oxigraph, ABI's `oxigraph_server`, Fuseki)
receive SPARQL Protocol `default-graph-uri` and `named-graph-uri`, which take
precedence over the query's own clauses; embedded Oxigraph receives
`default_graph` and `named_graphs`. "No graph" is the sentinel IRI
`urn:abi:iam:no-graph`, since the protocol has no other way to say it. A store
whose default graph is the union of its named graphs (Fuseki as deployed)
declares `union_default_graph`: a confined default graph is then the union of the
readable graphs. An adapter that cannot confine a query (the rdflib-backed
filesystem and object-storage stores, which keep no graph names, and Neptune)
refuses a confined caller with `PermissionDeniedError`: on those stores a user
with narrow rights cannot query at all. Callers allowed every graph skip the
parse and the restriction (`IIAMService.allows_every`, a conservative shortcut).
`get`, `export()` and `get_subject_graph(s)` read the confined dataset too.

### SPARQL Update (through `query`)

Checked, not confined: each operation needs its action on each graph it
touches.

| Operation | Action needed |
|---|---|
| `INSERT DATA` | `Insert` |
| `DELETE DATA` | `Remove` |
| `DELETE/INSERT ... WHERE` | `Insert` and/or `Remove` on the targets, `Query` on the graphs `WHERE` reads |
| `LOAD` | `Insert`, and `Query` on every graph: the store dereferences the source itself and it may be one of its own graphs |
| `CLEAR` / `DROP` / `CREATE` | `ClearGraph` / `DropGraph` / `CreateGraph` |
| `ADD` | `Query` on the source, `Insert` on the target |
| `COPY`, `MOVE` | as `ADD`, plus `ClearGraph` on the target (they replace it), and `DropGraph` on the source for `MOVE` |

`DEFAULT`, `NAMED`, `ALL` and graph variables need the action on every graph
(in practice `graph/*`); a `SERVICE` anywhere in `WHERE` needs every graph,
`USING` or not; on a union-default store a read of the default graph is a read
of every graph. A request the parser cannot classify is refused
(`INVALID_ARGUMENT`).

Each request is parsed once (`sparql_access.analyze`), under a lock of its own:
rdflib's grammar (pyparsing) is not thread-safe. Other rdflib parsing in the
process does not take it. A confined query therefore costs the graph list, a
filter and one parse; broad callers pay none of it, except on a view, which is
always parsed to refuse an update.

### Other rules

* `list_graphs`, `get`, `export()` and `get_subject_graph(s)` without a graph
  hold only readable graphs.
* A subscription is a read (`Subscribe`, in process only): its messages are one
  graph's triples, so a graph needs `Subscribe` on it and `*` needs every
  graph. It is checked when made; a policy changed afterwards does not cancel it.
* Over NATS the primary maps to `INVALID_ARGUMENT` only the service's own
  refusals (`Exceptions.InvalidRequest`: an IRI that is not absolute, SPARQL the
  analysis cannot classify). Any other error comes from a backend (rdflib, a
  store), may name paths or connection strings, and is an internal error:
  logged, never sent.

### Graph placement and assignments

Which workspace a graph belongs to is an IAM placement, never a triple in the
graph store:

* `create_graph` applies the create rule (`ResourceGuard.create`): a graph
  created while the call names a target workspace is placed in it
  (`iam.workspace_org`), otherwise on the platform; a name an existing placement
  covers keeps it, and a mismatching target workspace is refused.
  `drop_graph` drops the placement. An `Insert` into a graph nobody placed is
  checked against the platform's name for it.
* A workspace's roles reach exactly the graphs placed in it. That is the whole
  ownership model: the kernel keeps no per-workspace graph list of its own.
* Sharing a graph with another workspace is an Allow statement naming the graph
  wherever it is placed (`abi:*:*:triple_store:graph/<iri>`). A policy attached
  at a scope may only allow `${scope}:` resources, so such a grant is attached
  without scope. `ClearGraph` and `DropGraph` are never shared: lifecycle stays
  with the owning workspace.
* The Nexus graph service owns the editable assignments (what a workspace reads,
  writes and may create) and projects them into these statements; see
  [the Nexus graph service](../../../../naas-abi/naas_abi/apps/nexus/apps/api/app/services/graph/AGENTS.md).

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

Every primary runs its domain call as the verified caller: it authenticates the
request with `nats_rpc.authenticate_request` (built on `engine/nats_identity.py`,
it answers a refusal itself) and hands that `CallContext`
(`engine/call_context.py`) to its dispatcher. The actor is the
token's identity; the user it acts for is named by the token itself: a
delegated token (`abi:delegated:agent`, `act` the acting service, `sub` the user)
made by IAM's token exchange, never a header (the old `Abi-On-Behalf-Of` header is
refused); trace and target workspace come from the request's `context`. Never read identity from request fields
(`principal_id` and `tenant_id` are reserved). Clients of `api` and `engine` send a
delegation for the current call's user, and the call's trace and workspace; the domain service authorizes on that
context (Authorization above).

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB; above
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
- The call runs as the verified caller (`authenticate_request`), and the domain service
  decides: `triple_store:LoadSchema` on `schema/<source>` (Authorization above), before
  anything is parsed. A refusal is `PERMISSION_DENIED`, or `NOT_FOUND` for a caller that
  may load no such source at all.
- Content that is not UTF-8 or not Turtle: `INVALID_ARGUMENT`, nothing written.
- A file above the broker limit travels through RPC overflow like any request (the
  SDK facade `load_schema(source, content)`, run by `run_module` for a module's
  `ontologies/`, see `libs/naas-abi-sdk/AGENTS.md`).

Tests: `adapters/primary/triple_store__primary_adapter__NATS_test.py` (validation, no
broker), `..._NATS_integration_test.py` (an SDK module against a real `nats-server`: load,
restart writes nothing, changed file applies the diff, upload above the broker limit) and
`TripleStoreService_authorization_test.py` (a module loads its own sources, not another
module's, in process and through the primary).

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
disk, and authorized with IAM like every operation: `triple_store:LoadSchema` on
`schema/<source>`, which a module's default manifest asks for on its own sources only
(`schema/module/${module.id}/*`); the engine and the platform admin load any. Content may
not use the
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

