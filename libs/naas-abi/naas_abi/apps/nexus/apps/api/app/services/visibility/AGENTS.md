# Workspace visibility - AGENTS.md

## Purpose

What a workspace turned off. Its admins turn each agent, app, workflow and pipeline of its set
on or off for everyone in it (workspace settings › Agents, Apps, Workflows). One turned off is
refused when used, by every role, the platform admin included, and listed only to who may turn
it back on. Which resources a workspace has is its set (`../iam/AGENTS.md`, "Sets"); who may use
each is IAM's module scopes.

## Files

| File | Role |
|---|---|
| `port.py` | `VisibilityReaderPort`: one kind's `hidden(workspace_id, scopes)` |
| `service.py` | `WorkspaceVisibility`: asks each kind's reader (`type` -> reader); a kind with no reader hides nothing; a reader that fails hides every scope it was asked about (logged) |
| `runtime.py` | `configure` / `current`: where `authz` finds it; none (a route tested alone) hides nothing |
| `factory.py` | `default_visibility`, `install` (the API's start, `main._prepare_iam`) |
| `testing.py` | `visibility_installed(readers)` for tests |

The readers live with the state they read, each kind keeping today's flag:

| Kind | Reader | State | Never switched |
|---|---|---|---|
| `app` | `apps/visibility.py` `AppsVisibility` | `app_configs.enabled`, else the catalog seed (`resolve_app_enabled`) | off |
| `agent` | `agents/visibility.py` `AgentsVisibility` | `agent_configs.enabled` of the rows of that module scope | not hidden here (no row: the in-process runtime runs only its enabled roster) |
| `workflow`, `pipeline` | `workflows/visibility.py` `WorkflowsVisibility` | `workflow_visibility` (migration `0064`) | on |

## Where it is checked

`authz` asks it after IAM allows the **use** of a module scope (its use action, `ModuleScope.is_use`;
`../iam/authz.py`): `decide_scope` / `require_scope` refuse one turned off (reason `hidden`, 403
"This <type> is turned off in this workspace"), `filter_scopes` leaves it out,
`scope_allowed_in_any` skips the workspace (asked only where IAM allows, until one answers).
Every use goes through them: chat, `/v1`, app links and remote grants, a workflow start, the
agents and workflows an in-process turn may reach. Reading one's own runs of a workflow is not a
use: turning it off keeps the runs already started readable.

Who still lists one turned off is asked **on that resource**, as its toggle is guarded:
`filter_scopes(include_hidden=<predicate>)`, fed by `authz.allowed_ids("UpdateApp" | "UpdateAgent",
ids=...)` (the feature once, one IAM `filter` for the listing). A per-app or per-agent grant to switch
it lists it while it is off. Settings › Workflows lists the whole set to who holds
`ListWorkflowSettings`, never filtered by the caller's own right to run each one. An agent the workspace built has no module scope: chat checks its row's
`enabled` (`chat/.../chat__primary_adapter__dependencies.authorize_agent_use`).

## Decisions

- **Visibility is not a permission.** Decision: hiding is the workspace's state, kept in Nexus
  next to each kind's rows, and applies to everyone in the workspace; IAM keeps who may use what.
  Consequences: a hidden resource cannot be granted back to one person; IAM's simulator does not
  show it; a link already minted to an app works until it expires (eight hours at most).
- **Fail closed.** A reader that cannot answer hides what it was asked about: a resource is never
  used on a failed read.

## Tests

```bash
uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/visibility -q --no-cov
```

The refusals by kind are in the routes' suites: `apps/.../apps__primary_adapter__FastAPI_iam_test.py`,
`agents/.../agents__primary_adapter__FastAPI_iam_test.py`, `chat/.../chat__primary_adapter__FastAPI_test.py`,
`workflows/.../workflows__workspace_routes_test.py`.
