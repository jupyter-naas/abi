# Agents domain - AGENTS.md

## Purpose

A workspace's agents (`agent_configs`): the modules' agents, engine and remote, reconciled into
rows (`_reconcile_workspace_agents`), and the agents the workspace builds itself (a model and a
prompt). Who may use a module's agent is its module scope (`scopes.py`, `module:UseAgent`); one
the workspace built is `nexus:UseAgent` and the roles.

## Files

| File | Role |
|---|---|
| `port.py`, `service.py` | `AgentService` over the agent rows |
| `adapters/primary/agents__primary_adapter__FastAPI.py` | The class registry, the reconciliation and the routes (`GET /`, `POST /sync`, CRUD) |
| `scopes.py` | `agent_scope`, `class_scope`, `scope_resolver`; the workflows an agent may run as tools |
| `visibility.py` | `AgentsVisibility`: the module agents a workspace turned off, for `services/visibility` |
| `remote/` | Remote modules' agents from discovery |

## Rules

- **The set limits the roster.** The listing (and `GET /{id}`) keeps a module's agent only within the workspace's
  effective set (`iam/sets.within_set`), for everyone, the platform admin included; an agent the workspace built is
  always its own. Turning a module's agent on, or creating a row for one, outside the set is 403.
- **On or off for everyone.** `enabled` (with `enabled_override`, so a later sync keeps the choice) is the workspace's
  switch. One off is listed only to who holds `UpdateAgent` on that agent, and refused to everyone when used: chat
  (`authorize_agent_use` checks the row), `/v1`, and as a sub-agent (the in-process runtime runs only the enabled
  roster, `core/agent_feature_access.bind_usable_agents`).

## Tests

```bash
uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/agents -q --no-cov
```

`adapters/primary/agents__primary_adapter__FastAPI_iam_test.py`: who lists, changes and reads agents, the set, an
agent turned off listed to its admins alone; chat's refusal is in `chat/.../chat__primary_adapter__FastAPI_test.py`.
