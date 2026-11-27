# Knowledge graphs - AGENTS.md

## Purpose

Nexus's graph domain: the explorer, the query compiler, views and the workspace's
graph pages. **Nexus does not decide who may read or write a graph.** The kernel's
triple store authorizes every call for the signed-in user, by the workspace IAM
placed each graph in and the statements that share it
([`libs/naas-abi-core/.../services/triple_store/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/triple_store/AGENTS.md),
[`libs/naas-abi-core/.../services/iam/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/iam/AGENTS.md)).
What stays in Nexus is the workspace's *view* of the graphs and the editable
document that says what a workspace shares.

## Files

| File | Role |
|---|---|
| `access.py` | `GraphAccessScope`: the graphs *this workspace* offers a caller, already narrowed to what the kernel lets them read (`readable`) and write (`writable`); `workspace_graph_operation` guards every service entry point and maps the kernel's refusals to `GraphAccessError` |
| `adapters/secondary/workspace_policy.py` | `build_scope` / `load_workspace_scope`: the view of one workspace for one user (`graph_config`: what its offer says, else its saved assignments); `catalog_graphs`; `catalog_inventory` (platform administrators) |
| `adapters/secondary/graph_iam.py` | What Nexus asks IAM beyond the kernel's own checks: `allowed` (filter graphs by an action, as the user), `may_create`, `owned_by`, `owners`, `within` (the graphs a `read_all` may reach) |
| `adapters/secondary/graph_placements.py` | `placement_source`: graphs that still carry a `graphWorkspaceId` triple in Nexus's application graph are placed in that workspace at startup |
| `adapters/secondary/scoped_store.py` | Narrows every graph data query to the workspace's SPARQL dataset (its view), on top of the kernel's own checks |
| `service.py`, `explorer.py`, `query/` | The use cases; routes in `adapters/primary/` declare the kernel action they perform (`declares("triple_store:...")`) |

## Decision: a workspace's graphs are IAM placements, and what it shares is an Allow statement

Two authorities (Nexus rewriting queries, the kernel authorizing calls) would
disagree, and the data is reachable without Nexus. So Nexus keeps no graph access
rule of its own.

- **Owned graphs are placements.** The kernel's create rule places a graph created
  through a route in the workspace the call names. At startup `graph_placements`
  places the graphs that still carry a legacy `graphWorkspaceId` triple (the first
  workspace when several are recorded, with a warning). The workspace's roles then
  reach exactly its graphs: viewers list and read, members insert, remove and
  create, admins clear and drop (the levels of the `triple_store` catalog). New
  graphs write no ownership triple.
- **Sharing is the receiving workspace's offer.** What a workspace is given of other
  graphs is the Graphs part of its "<W> access" (`iam/given_graphs.py`, ADR
  `20261125_offer_gives_outside_resources`): Allows on absolute names (`GivenGraphs`,
  `GivenGraphsWrite`, `GivenGraphsAll` for `read_all`), which IAM gives the workspace's
  people while they belong to it, each within their level (a Viewer reads, a Member
  writes), and Denies within `${scope}` for what it closes (`OfferGraphsDeny`: creating
  graphs, its own graphs it excludes). `ClearGraph` and `DropGraph` are never given:
  lifecycle stays with the workspace that owns the graph. Nexus's application graph and
  the schema graph are never given for writing.
- **Settings › Graphs writes the offer.** The editor (`kind=graphs`, routes in
  `services/workspaces/adapters/primary/resource_access.py`) reads the offer and writes
  it as the caller (`FeatureAccessService.set_graphs`), so IAM's held check applies: an
  administrator gives only a graph they hold (to read, or to write). The catalog still
  offers only graphs they may drop or that the workspace holds; turning `read_all` on is
  for platform administrators (`ManageSystem`). A workspace whose access policy is no
  allow-list yet is refused (409); its view goes by `workspace_resource_policies`.
  `graphs_offer_v1` moved the saved assignments and deleted the per-person
  `workspace.<ws>.graphs.read|write` policies of before.
- **What remains in Nexus** is `GraphAccessScope`. A user who belongs to several
  workspaces holds the rights of all their graphs; each workspace's pages still
  list, query and cache only its own.

## Consequences

- **Nothing follows memberships.** A person given a graph through W holds it while they
  belong to W's groups; leaving ends it at the next decision. An organization's admin,
  in none of W's groups, is not given W's graphs (nor held by its Denies).
- `read_all` names patterns, so a graph created later in the organization is read too;
  only those placed in the workspace's own organization (its own for a workspace in
  none), plus the schema graph: never another organization's, nor another personal
  workspace's, nor a platform graph (named in `read` to be given).
- Nexus's own graphs (`graph/nexus`, `graph/nexus-identity`, any `graph/nexus-<name>`:
  `graph_policy_config.is_nexus_system_graph`) are in no workspace's catalog, view or
  assignment, even named.
- Dropping or clearing a graph shared for writing is the owning workspace's alone.
- Strings that reach SPARQL are escaped (`query/sparql_safe.py`): Nexus reads every
  graph as itself when it consults its application graph.
- **Uploads are data.** `/analyze` and `/import` read at most `GRAPH_UPLOAD_MAX_BYTES`
  (413 past it) and parse with `naas_abi_core.utils.rdf_upload`: a child process
  with no network and a time limit, off the event loop. JSON-LD may only use
  embedded contexts. Errors are fixed messages; details stay in the log.
- **Caches follow the graphs a scope reads.** A cache key digests the generations
  of the graphs its scope reads (`_scope_cache_key`); a write advances its graph's
  generation (`_invalidate_graph_cache`), so only scopes reading that graph miss.
  The cache directory is pruned by age and count (`_prune_cache_dir`).

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/graph --import-mode=importlib --no-cov -q
```

`graph_authorization_test.py` proves who may read and write which graph on a real
kernel (real IAM and triple store); `access_test.py` the workspace's view;
`graph_routes_authorization_test.py` the routes; `graph_offer_test.py` what a
workspace's offer gives (grouped workspaces, levels, Settings › Graphs).
