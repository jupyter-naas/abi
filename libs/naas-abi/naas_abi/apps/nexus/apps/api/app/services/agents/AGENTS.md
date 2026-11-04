# Agents domain - AGENTS.md

## Purpose

A workspace's agents (`agent_configs`): the modules' agents, engine and remote, reconciled into
rows (`_reconcile_workspace_agents`), and the agents the workspace builds itself (a model and a
prompt). Who may use a module's agent is its module scope (`scopes.py`, `module:UseAgent`); one
the workspace built is `nexus:UseAgent` and the roles. The rows hold each agent's configuration
(name, prompt, model, the workspace default), never an on/off state.

## Files

| File | Role |
|---|---|
| `port.py`, `service.py` | `AgentService` over the agent rows |
| `adapters/primary/agents__primary_adapter__FastAPI.py` | The class registry, the reconciliation and the routes (`GET /`, `POST /sync`, CRUD) |
| `scopes.py` | `agent_scope`, `class_scope`, `scope_resolver`; the workflows an agent may run as tools |
| `remote/` | Remote modules' agents from discovery |

## Rules

- **IAM alone decides the roster.** The listing (`GET /`, `POST /sync`, `GET /{id}`) is exactly the agents the
  caller may use: a module's agent by its module scope, the platform admin included (no role holds one by itself), an
  office agent also by its feature (`core/agent_feature_access`); an agent the workspace built is always listed (its
  use is `nexus:UseAgent`, checked by chat). A workspace that should not offer an agent denies it in a policy.
- **No on/off switch.** `agent_configs.enabled` and `enabled_override` are read and written by nothing here (the
  upgrade reads them once and drops them): `enabled` is no field of the record nor of `PATCH /{id}`, a sync aligns no
  row to the `agents:` seed (its `default_agent` still marks the default), and the pickers
  (`pick_workspace_chat_agent_id`, `pick_workspace_*_agent_id`) pick among the agents the caller may use. Chat
  (`authorize_agent_use`), `/v1` and the in-process turn (`bind_usable_agents`, `caller_usable_class_names`) ask IAM
  alone.
- **A remote agent is listed while its module is READY** (`_served`, from discovery; all rows when discovery cannot
  be read). Its row is kept while the module is away, never deleted.
- **A remote agent runs in its own workspace.** The run is placed in its agent row's workspace, the one
  `authorize_agent_use` cleared it in (`ResolvedProvider.run_workspace_id`), never the workspace a request names: a
  turn with only a conversation id, or naming another workspace, changes nothing.
  `RemoteAgentDirectory.stream(..., workspace_id=)` submits under it (`SubmitRequest.context.workspace_id`), and the
  module's host runs the handler for the user there: an action the module declares is decided in that workspace
  (`require_action`).

## Tests

```bash
uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/agents -q --no-cov
```

`adapters/primary/agents__primary_adapter__FastAPI_iam_test.py`: who lists, changes and reads agents, the roster
exactly what IAM allows (a Deny removes an agent), no role listing a module agent without a policy, remote agents
listed while served; chat's refusal is in `chat/.../chat__primary_adapter__FastAPI_test.py`.
