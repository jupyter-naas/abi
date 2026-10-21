# The tool catalog over NATS: list, get and search, read only

## Status

Accepted. Step 2 of the tool registry's NATS work
(`docs/adr/20260923_tool-registry-and-agent-composition.md`, sections 5 and 7).
Tools published by SDK modules and the remote execution of engine tools
(`docs/adr/20261022_remote-module-tools.md`,
`docs/adr/20261023_remote-callers-run-engine-tools.md`) build on the contract defined here.

## Date

2026-10-21

## Context

Each engine process has a registry of its own: the modules it loads publish their
tools to it, and bindings (live Python objects) never leave it. Only the serving
engine owns the shared vector-store index. So a client engine, a standby engine
or an SDK module cannot see what the serving engine's modules published. The
remote model registry (`docs/adr/20260924_remote-model-registry.md`) is the
pattern for a kernel service the engine serves and others call: register locally,
read over NATS, with calls authenticated by the caller's service token.

Two constraints decide the shape. 3.0 has no tool contract (`naas-abi-proto` has no
tool message) and no Protovalidate: kernel services validate requests on the
server. And a caller's rights cannot come from its request: nothing in a request
is trusted, only the verified service identity is.

## Decision

### A read-only contract: `abi.tool_registry.v1`

`naas_abi_proto/tool_registry/v1/tool_registry.proto`, served on
`abi.svc.tool_registry.v1` as the NATS micro service `tool_registry` with three
unary operations:

| Operation | Request | Reply |
|---|---|---|
| `list_tools` | filter, `limit` (1..200, default 100), `after` | entries sorted by id, `next_after` |
| `get_tool` | `ref` (`ns/name` or `ns/name@version`) | one entry |
| `search_tools` | `query`, `limit` (1..50, default 5), `min_score`, filter | matches, best first |

An *entry* is a `ToolDefinition` and its `ToolAvailability`. The definition is the
portable form of a published tool and is meant to be reused as is by the next
steps (module-published tools, remote execution): id (`<namespace>/<name>@<version>`
and its parts), module, description, input schema (and optional output schema) as
UTF-8 JSON, tags, config requirements (`key`, `description`, `secret`, `required`;
a requirement names a credential and never carries one), `requires_workspace` and
required scopes. Availability says whether the tool could be built now, as the
owner sees it: the required keys still empty even with the publishing module's
own values, which are never sent. A filter narrows list and search before the
limit: module (any of), tags (all of), `available_only`.

No call resolves a binding, builds or runs a tool, and no reply holds a binding
value. `ToolRegistryService.search_local` ranks definitions only.

### Who may see what: the verified identity

The primary reads `Nats-Auth-Token` and takes the caller's scopes from that
identity alone. `CallContext` is not read (its principal, workspace and tenant are
carried, not enforced, as for the other services), the proto has no scope field,
and unknown fields are ignored.

- The engine's own processes (`api`, `engine`, `dagster`, the first-party
  identities that hold the project secret) hold every scope the catalog uses.
  They apply their end users' scopes themselves (see below).
- An SDK module holds the scopes configured for its identity,
  `nats.tool_registry.module_scopes` (module id to scopes), and none by default:
  it sees the tools that need no scope. The identity is what its module token
  asserts; a module key cannot assert a first-party identity
  (`docs/adr/20261014_module-identities.md`). Configuring scopes for a
  first-party identity is a configuration error.
- The access policy (`IToolAccessPolicy`, action `DISCOVER`) filters every list,
  get and search with those scopes. A tool the caller may not discover is
  reported as not found, with the message of a tool that does not exist.

These scopes decide discovery, and the same scopes (`module_scopes`) are the ones a
module runs tools with (`invoke_tool`, `docs/adr/20261023_remote-callers-run-engine-tools.md`),
which checks access again with the caller's verified identity and adds its own grants.

### Validation on the server

As for the other kernel services, the primary validates each request against the
limits written in the proto's header and in `tool_registry_nats_codec.py`: query 1
to 2000 characters, limits as above, a finite `min_score`, at most 32 module
filters (256 characters) and 16 tag filters (64), a reference of at most 512
characters, `after` of at most 512. Out of range is `INVALID_ARGUMENT`, never
clamped. Errors carry a stable code (`UNAUTHENTICATED`, `INVALID_ARGUMENT`,
`TOOL_NOT_FOUND`, `SEARCH_UNAVAILABLE`, `INTERNAL`) and a message that holds no
backend detail.

A reply stays under half of the broker's `max_payload`, so it never needs RPC
overflow. A list page, or a result list, ends at the tool that would pass it (the
next page continues from `next_after`); a single definition above it, or one JSON
cannot carry (NaN), is neither listed nor returned (`get_tool` says invalid), and
the primary logs which. A search reply says `truncated` when it left matches out
for either reason, so a short answer is not mistaken for "no more": a client
asks again with a larger limit while that adds matches (it gets back what was
skipped as too large, not what the byte budget cut: the budget does not depend on
the limit, and a client stops when a larger limit brings no more). That is a known
bound: matches past a reply's byte budget are unreachable by search on a client
engine.

### Engines that do not serve read the catalog; publish and resolve stay local

`ToolRegistryService` gains an optional catalog (`IToolCatalogPort`, a read-only
secondary port) that `EngineNATSDependencies.wire_tool_registry` sets with the
index role. A client engine, and a standby one before its handover, read the
serving engine's catalog through `ToolRegistrySecondaryAdapterNATSClient` (as the
engine's own process); the serving engine, and an engine with NATS off, have none
and read only what they hold. At a handover, fencing or restore the role changes
and so does the catalog, exactly as the index does.

Reads then cover what the process holds and what the catalog shows:

- **Local wins.** A tool this process holds shadows the catalog's of the same id,
  and a reference without a version resolves here first. What `resolve` can build
  is what a read reports.
- **Search merges.** A client engine's search ranks its own tools with its own
  index and takes the serving engine's matches from the catalog, merged by score
  (both rank with the serving engine's embedding model, through the model
  registry). Without the catalog, a client engine would only ever see its own
  tools, which is the situation this removes; dropping its own would make a tool
  that only it loaded vanish from search. A client engine that has no tool of its
  own ranks exactly as the serving engine does in process.
- **The caller's rights apply on top.** The serving engine filtered with the
  engine's identity, so the process applies its caller's context (the
  `ToolContext` of the search) to what comes back, and the caller's `where`. The
  limit is met by asking the catalog for more, doubling up to the contract's 50
  results, until it is filled, the catalog has no more (a short, untruncated
  answer) or a larger limit brings nothing new.
- **Availability** of a catalog-only tool is the owner's, less the keys the caller
  provides in `config`.
- **A tool only the catalog has cannot be built here.** `resolve` raises
  `ToolResolutionError` saying so (until remote execution), instead of a not-found
  that would send an agent looking for a typo. Searching still never resolves.

The serving side answers from `get_local`, `list_local` and `search_local`,
which never read a catalog, so a standby that just took over and still has its
catalog set for an instant cannot call itself over the queue group it joined.

When the catalog cannot answer (the serving engine restarting or in a handover,
the service missing, the 60 s timeout), `list_definitions` and `search_tools` of
a process that holds tools of its own go on with those, and log a warning: agent
composition and `search_capabilities` worked from local tools before there was a
catalog. A process with nothing local to answer with, or whose own search could
not rank, raises, since an empty result would hide the failure. `get_definition`,
`availability` and `check_access` on a tool not held raise too, as a
`ToolCatalogError` (a `ToolRegistryError`; `ToolCatalogRequestError` for a request
the catalog refused). The client sends what the catalog accepts (a query is
stripped and cut at 2000 characters, a blank one asks nothing) and skips a
definition it cannot read, with a warning, instead of failing the whole catalog.
Its connection opens on first use.

### Broker permissions

`MODULE_PERMISSIONS` needs no change: a module may call `abi.svc.>` (it may not
subscribe to it), and the Docker, CLI and `abi dev` broker configurations are the
same. A real-broker test runs an SDK module as the broker's `module` user.

### SDK

`naas_abi_sdk.tool_registry.ToolRegistryClient` comes out of the proto package's
client generator (`make generate`), like the other clients, `OPERATIONS["tool_registry"]` lists the operations, and
`naas_abi_sdk.services.tool_registry.ToolRegistryService` is the facade
(`list_tools`, `get_tool`, `search_tools`, with dataclass results). A module
declares `ModuleDependencies(services=("tool_registry",))`. The standalone demo
exercises every operation from the wheel-only worker.

## Consequences

- Whatever makes the serving engine unreachable (no responder, a closed or refused
  connection, a timeout) reaches the registry as a `ToolCatalogError`, so a client or standby
  engine goes on with its own tools. When it has no search backend, the catalog ranks the
  tools it holds too.

- A client engine and an SDK module find the serving engine's tools by meaning,
  with the same ranking as the serving engine's own search, and an agent composed
  in a client engine can enable the tools its own modules loaded as before.
- A client engine's agent may find a tool it cannot enable: its `enable_capability`
  fails with an explicit message until remote execution lands.
- The first search on a serving engine still embeds its tools (once per change).
  A client call waits for it, up to a minute by default (a search may embed).
- The catalog costs a round trip per read on a client engine, and per search two
  (the model registry's `embed` for a local index, and the search): negligible
  next to the model call an agent makes with it.
- An SDK module sees nothing that needs a scope until an operator grants it one.
- A catalog above 20,000 tools is refused by `list_definitions` on a client
  engine (search and get are not affected).
- Out of scope: tools published by SDK modules (they cannot publish yet), remote
  execution, per-module broker users (see `nats_permissions`), and Protovalidate.
