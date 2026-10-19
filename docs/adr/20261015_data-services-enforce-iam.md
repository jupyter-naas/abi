# The data services enforce IAM in their domain services

Status: Accepted

Date: 2026-10-15

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §4.4, §5 and §6.4.
Builds on: [`20261013_authorization-policy-model.md`](20261013_authorization-policy-model.md), [`20261013_iam-kernel-service.md`](20261013_iam-kernel-service.md), [`20261015_iam-transitional-bootstrap.md`](20261015_iam-transitional-bootstrap.md).

## Context

**Subtask 4 of #44 makes eight data services enforce IAM:** object storage, document, key-value, secret,
cache, vector store, triple store and dataset. The RFC fixes their catalogs and request-to-resource rules.
Building them raised questions the RFC leaves to the implementation:

- **Where the check sits, and what does not check.** Domain services are also used outside an engine (tests,
  scripts, configuration rendering), and the engine gives its modules NATS facades that are themselves domain
  services over NATS clients.
- **What runs the boot.** Boot ran with no caller (`ANONYMOUS`), and anonymous calls are denied.
- **Services that keep their own data in another service.** The cache stores entries in the key-value or
  object storage service, the activity log and the engine's agent memory in the document service.
- **How a SPARQL query is confined** to the graphs its caller may read, across Oxigraph (HTTP and embedded),
  Fuseki, Neptune and the rdflib-backed adapters.
- **How a dataset query is checked:** the SQL names the tables.

## Decision

1. **One helper, `ResourceGuard` (`services/iam/enforcement.py`), in each domain service.**
   - It places names, checks before the backend is touched, filters lists, pushes the caller's prefixes down to
     key scans, applies the create rule of §4.4 and records or drops placements.
   - It reads IAM from the service's wiring (`ServiceBase.wired_iam`). A service with no IAM does not check:
     outside an engine there is no caller to check, and a NATS facade's server checks the call it receives.
   - NATS primaries keep mapping errors only: `PERMISSION_DENIED`, `NOT_FOUND` or the service's own not-found.
     Clients raise the same exceptions, so in process and over NATS answer alike.
2. **Boot runs as `engine`.** `Engine.load` runs under `as_service_account("engine")`, and the serving engine
   registers every kernel catalog then, the data services' with the runtime services' (`kernel_catalogs.py`).
3. **A service's own storage is used as the engine** (`own_storage`): for no user and no target workspace. The
   caller was authorized on the service's own resource (a cache key, an agent), not on the backing store.
   - It covers a call, a generator's steps and a context manager's entry and exit (a lock, an object stream).
     What the caller then does with a plain result, such as reading a stream's bytes, is the caller's own.
   - **Trust assumption: `internal_call` is core's.** Inside it the user's bounds, scope and audience are
     cleared and the principal is `engine`, which reads the sealed `iam/` secrets and holds
     `dataset:QueryUnchecked`. So it wraps only the single call of a service's own storage, never code a caller
     steers, and nothing outside `naas_abi_core` imports it or `own_storage`, which is the same escalation one
     call at a time (`enforcement_boundary_test.py` checks both). A module that has maintenance to run gets a
     narrow entry instead: `catalog_maintenance(dataset)` (`services/dataset/CatalogMaintenance.py`, typed to a
     dataset) runs each call on the dataset it wraps as the engine, and nothing around it. In-process modules
     are trusted code; the boundary keeps the escalation to one named, reviewable entry. The X module wraps its dataset once and calls it only with its own fixed statements.
     Code that passes a caller's SQL to the wrapped dataset hands that caller the engine's access.
4. **SPARQL is confined by the store, with the dataset.**
   - The triple store parses a query (rdflib) for the graphs it names, which must be readable, and hands the
     adapter a `QueryDataset` of the readable graphs.
   - HTTP stores receive SPARQL Protocol `default-graph-uri` and `named-graph-uri`, which take precedence over
     the query's own clauses; embedded Oxigraph receives `default_graph` and `named_graphs`. ABI's
     `oxigraph_server` honours the parameters as Oxigraph's server does.
   - "No graph" is a sentinel IRI (`urn:abi:iam:no-graph`), since the protocol has no other way to say it.
   - A store whose default graph is the union of its named graphs (Fuseki as deployed) declares
     `union_default_graph`; a confined default graph is then the union of the readable graphs.
   - An adapter that cannot confine a query (the rdflib-backed filesystem and object-storage stores, which keep
     no graph names, and Neptune) refuses a confined caller. Callers allowed every graph skip the parse, through
     `IIAMService.allows_every`, a conservative shortcut.
   - SPARQL Update is checked, not confined: each operation needs its action on each graph it touches. A
     `SERVICE` anywhere in `WHERE` needs every graph, `USING` or not, and so does `LOAD`, whose source the
     store dereferences itself and may be one of its own graphs. On a union-default store a read of the
     default graph is a read of every graph.
   - A view is queried, never updated: `query_view` refuses an update for every caller, broad ones included.
5. **Dataset queries are checked from DuckDB's parser** (`json_serialize_sql`), for every caller: a single
   `SELECT`, base tables resolved against the query's namespace, a few argument-only table functions. A CTE hides a dataset only
   where it is in scope (a recursive CTE's anchor does not see the CTE); a dataset name must be a dataset
   identifier (a quoted path would be a file scan); every name must be a dataset of the catalog, looked up
   by itself, without case as DuckDB does, so a DuckDB view or the lake's metadata is not found. A caller
   allowed every dataset skips only the per-dataset checks: a file-reading function reads no dataset, so
   being allowed every dataset says nothing about it.
   - SQL the check cannot vouch for (`DESCRIBE`, `ALTER`, `CALL ducklake_*`, `duckdb_tables()`) needs a new
     admin action, `QueryUnchecked` on `catalog/-`. The engine holds it through its broad grant; both
     transitional grants deny it, so neither a Nexus user (through `api`) nor a remote module (#60's default manifest carries the same Deny) reads files on
     the engine host. A module's catalog maintenance of its own tables runs as the engine (the X module's).
   - "Call the adapter" was not enough: an engine-hosted module reaches datasets through a NATS facade, whose
     adapter is itself a client of the checked service.
6. **Seals match wherever a placement puts the resource** (`abi:*:*:…`): placing the built-in IdP's namespace in
   a workspace must not unseal it.
7. **Object names are plain paths.** IAM checks `prefix/key` as written, and a backend opens what the path
   resolves to, so `ws1/../ws2/x` would match `ws1/*` and open `ws2/x`, and a key of `/etc/passwd` would replace
   the base path of the filesystem adapter. `ObjectStorageService` therefore refuses, before any check and for
   every caller, a prefix or key with a `.` or `..` segment or an empty segment (one trailing `/` on a prefix
   aside), and a leading `/`: `InvalidObjectPath`, `INVALID_ARGUMENT` over NATS.
   The service also strips only a leading `storage/` from a prefix (it was every occurrence), and does so
   before the check in every operation, metadata included: the name IAM checks is the path the adapter opens.
8. **What IAM checks is what a backend runs.** IAM percent-encodes an id, so any string matches a prefix
   pattern whatever follows the prefix; a store or adapter that interpolates the raw string would run
   something else. So a caller-supplied name is validated before the check, with no denied or not-found
   oracle, and a failure is `InvalidRequest` / `InvalidSecretKey` (`INVALID_ARGUMENT`):
   - **Graph names and subjects** (triple store) must be absolute IRIs (`checked_iri`), for `insert`,
     `remove`, `create_graph`, `clear_graph`, `drop_graph`, `export`, `subscribe` and `get_subject_graph`
     (the subject too). Adapters that build SPARQL from strings (Oxigraph HTTP, Jena, Neptune, embedded
     Oxigraph) write them with `iri_n3`, which validates again. Graphs the SPARQL parser finds in a
     request are validated too, all of them before any check: rdflib keeps the backslash of an escaped
     prefixed name (`g:\/private`) that the SPARQL grammar and the stores drop, so IAM would check
     `http://g\/private` while the store drops `http://g/private`, a graph a Deny names. Only the literals
     `default` and `*` are taken as they are, and an escaped name is `InvalidRequest`.
   - **`COPY` and `MOVE` replace their target**, so they need `ClearGraph` on it as well as `Insert`; `ADD`
     only inserts.
   - **Secret keys** match `[A-Za-z0-9_./:-]+` (`checked_key`) in `Secret.set` and `remove` and in the dotenv
     adapter; `get` of any other key returns the default, since no such key exists. A newline was `%0A` for
     the check and a second line in `.env`.
9. **Backend errors are not sent.** The NATS primaries of the dataset and triple store map to `INVALID_ARGUMENT`
   only the service's own refusals (`DatasetRequestRefused`, `Exceptions.InvalidRequest`: the SQL and SPARQL
   checks, an IRI that is not absolute) and, for datasets, a spec's validation errors. Any other `ValueError`
   comes from a backend (DuckDB, pyarrow, rdflib), may name paths or connection strings, and is an internal
   error: logged, never sent.
10. **A subscription is a read** (`triple_store:Subscribe`, in process only): its messages are one graph's
   triples, so a graph needs `Subscribe` on it and `*` needs every graph. It is checked when made; a policy
   changed afterwards does not cancel it.
11. **Queries over a collection are not filtered per item.** `DocumentService.find`, `iterate` and `count`
    and `VectorStoreService.search` check the collection once (RFC §5.5). A Deny on
    `document/ns/c/secret-*` or on one vector id therefore still lets a query return those items while `get`
    refuses them: per-id Deny does not apply to queries. Deny the collection to hide it from them.
12. **A wired service that finds no usable IAM does not fail silently.** One whose engine offers none runs
    unenforced and logs it once per service class; an IAM that is not an `IIAMService` raises
    (`ServiceBase.wired_iam`).
13. **The document namespace is a name like any other.** The request's namespace is authorized, so a module's
   own namespace is what its policy names; the `api`/`engine` admin identities and the unlocked-proxy gate on
   `document_admin` are removed.

## Consequences

- **Every check is in the domain**, so the NATS endpoints, Nexus and in-process modules are checked the same
  way, and the data services' contract (`services/iam/tests/data_service_contract.py`) proves it per service.
- **Nothing that runs today breaks:** `engine` and `api` hold their transitional broad policies and Nexus
  users theirs (ADR `20261015_iam-transitional-bootstrap.md`, updated). A remote module is a service account
  `module/<project>/<module_id>` (#60): it reaches its own document namespace (`${module.id}`, the namespace
  its SDK binds) and the shared `default` dataset namespace through its approved manifest, and never
  unchecked dataset SQL.
- **Work with no caller needs an identity.** Boot runs as `engine`; after boot, Nexus housekeeping runs as
  `api`, `abi chat` and `abi run script` as `engine`, and bus consumers, worker-pool jobs and warmup threads
  as whoever started them. Anything else that starts a thread without copying its context is denied.
- **Confined SPARQL depends on the store.** On the filesystem, object-storage and Neptune stores a user with
  narrow rights cannot query at all until those adapters learn to confine.
- **Unchecked dataset SQL is an action, held by `dataset:*` on the catalog.** A policy allowing `dataset:*`
  on `*` allows reading files on the engine host; only platform-level grants should say so.
- **A confined query costs more:** the graph list, a filter, and one parse per request, under a lock of the
  check's own, since pyparsing's state is not thread-safe. Broad callers pay none of it, except on a view,
  which is always parsed to refuse an update.
- **The create rule binds Nexus.** During a request, Nexus sets the target workspace from the path; a create
  inside a platform container from such a request is refused. Subtask 11 decides which requests target a
  workspace.
- **Audit events go through `EventService.emit`** (subtask 5): stamped with the caller, appended as the
  engine. A caller authorized for the operation needs no right on the event log.
- **Two guards coexist:** `ResourceGuard` (data services, `enforcement.py`) and subtask 5's `ServiceGuard`
  (runtime services, `guard.py`), with two contract tests (`data_service_contract.py` and
  `authorization_contract.py`). They share the names, placements and wire codes; merging them is a refactor
  left for later.
