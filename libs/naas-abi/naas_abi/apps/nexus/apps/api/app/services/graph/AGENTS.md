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
| `adapters/secondary/workspace_policy.py` | `build_scope` / `load_workspace_scope`: the view of one workspace for one user; `catalog_graphs`; `catalog_inventory` (platform administrators) |
| `adapters/secondary/graph_iam.py` | What Nexus asks IAM beyond the kernel's own checks: `allowed` (filter graphs by an action, as the user), `may_create`, `owned_by`, `owners`, `within` (the graphs a `read_all` may reach) |
| `adapters/secondary/graph_placements.py` | `placement_source`s: graphs that still carry a `graphWorkspaceId` triple in Nexus's application graph are placed in that workspace at startup; the saved assignments are projected into IAM in the same pass; a new workspace holds its assignments (`on_workspace_created`) |
| `adapters/secondary/graph_grants.py` | `GRANTS`: projects a workspace's saved assignments into IAM policies and keeps their holders in step with its members |
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
- **Sharing is a statement for the receiving workspace.** A policy attached at a
  scope may only allow `${scope}:` resources, so a grant onto another workspace's
  graph cannot be a scoped attachment. For each workspace `GRANTS` keeps two
  policies, `workspace.<ws>.graphs.read` and `workspace.<ws>.graphs.write`:
  - `read` Allows the list and read actions on the graphs the workspace reads or
    writes (`SharedGraphsRead`), and Denies what the workspace closes: creating
    graphs when `allow_create` or `include_owned` is off (`NoNewGraphs`), and its
    own graphs it excludes (`OwnGraphsClosed`);
  - `write` Allows `Insert` and `Remove` on the graphs it may write.
  They name graphs wherever placed (`abi:*:*:triple_store:graph/<iri>`, so a graph
  keeps its identity if it moves) and are attached **without scope** to the members
  who hold a role in the workspace: `read` to every role, `write` to member and
  above. `ClearGraph` and `DropGraph` are never shared: lifecycle stays with the
  workspace that owns the graph. Nexus's application graph and the schema graph are
  never shared for writing.
- **The saved assignments stay the editable document.** `workspace_resource_policies`
  (`kind=graphs`, edited on the workspace's resource-access page, routes in
  `services/workspaces/adapters/primary/resource_access.py`) is what administrators
  edit; saving it, and startup, project it into IAM (`graph_grants.sync_workspace`,
  `sync_all`). Saving checks more than the catalog: an administrator may add only
  graphs they may drop (their workspace's own) or that the workspace already holds;
  a platform administrator any; moving a graph from read to write needs the right
  to drop it; turning `read_all` on is for platform administrators (`ManageSystem`).
- **What remains in Nexus** is `GraphAccessScope`. A user who belongs to several
  workspaces holds the rights of all their graphs; each workspace's pages still
  list, query and cache only its own.

## Consequences

- **Holders follow memberships.** `GRANTS` registers on
  `MEMBERSHIPS.on_workspace_roles_changed`, so a role change through `MEMBERSHIPS`
  calls `sync_members(workspace_id)` (a deleted workspace calls `forget`), and the
  invitation claim calls `MEMBERSHIPS.changed(scope)`. Any new code that attaches or
  detaches workspace roles outside `MEMBERSHIPS` must call `GRANTS.sync_members`, or
  a removed member keeps the shared graphs and a new one lacks them.
- `api` needs the `iam:*Policy` actions (create, update, delete, get, list) and
  attach/detach, which the enumerated `builtin.api` statements hold.
- `read_all` shares the graphs that exist when the assignment is applied (a graph
  created later joins at the next sync), and only those of the workspace's own
  organization and the platform's (`graph_iam.within`): never another organization's,
  nor another personal workspace's (the shared `_none` organization).
- Dropping or clearing a graph shared for writing is the owning workspace's alone.
- Strings that reach SPARQL are escaped (`query/sparql_safe.py`): Nexus reads every
  graph as itself when it consults its application graph.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/graph --import-mode=importlib --no-cov -q
```

`graph_authorization_test.py` proves who may read and write which graph on a real
kernel (real IAM and triple store); `access_test.py` the workspace's view;
`graph_routes_authorization_test.py` the routes; `adapters/secondary/graph_grants_test.py`
the projected statements.
