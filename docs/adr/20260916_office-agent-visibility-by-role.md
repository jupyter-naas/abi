# Nexus office agent visibility follows the caller's feature access

## Status

Proposed (implemented on `nexus-build-app`, awaiting review)

## Date

2026-09-16

## Context

Two mechanisms decided which agents a Nexus workspace offers, and neither
answered "may *this* user see this agent".

1. **The roster seed.** `POST /api/agents/sync` reconciles `agent_configs`
   with the code class registry and aligns `enabled` to the workspace
   roster: the `agents:` list in the workspace seed when present, otherwise
   the engine default alone (`agents__primary_adapter__FastAPI.py`,
   `core/workspace_catalog_seed.py`). `enabled` is a column on a
   workspace-scoped row.
2. **The feature flags.** `build_feature_flags` resolves, per request, what
   a user's role may open in a workspace: deployment `role_baseline`,
   overlaid by the organization override, then workspace overrides
   (`core/feature_flags.py`). A member may hold `apps` and `files` while an
   owner also holds `ontology` and `settings`.

The right-hand chat pane binds a section's office agent through
`pickFeatureOfficeAgent` (`lib/pick-workspace-default-agent.ts`), which
requires the agent to be **listed and `enabled`**, and otherwise falls back
to the workspace default. So a workspace that had not seeded
`naas_abi AppsAgent` bound its default orchestrator on the Apps page — the
symptom that prompted this.

Adding the office agents to the roster fixes that, but makes the roster
workspace-wide: every member then gets Ontology, Settings and Agent Catalog
in the picker, including members whose role cannot open those sections.

`enabled` cannot express the role rule. It is one row per workspace, shared
by every member; a member's sync writing it would narrow what the owner
sees, and the sync endpoint is reachable by any member.

## Decision

1. **The roster stays the workspace-level answer.** `agents:` decides which
   agents the workspace runs, and `sync` keeps writing `enabled` from it
   for everyone. No per-user state is persisted.
2. **The role rule is applied when a listing is rendered, per caller.**
   `GET /api/agents`, `POST /api/agents/sync` and `GET /api/agents/{id}`
   resolve the caller's flags with the same `build_feature_flags` the
   workspace listing uses, and drop the office agents whose features the
   caller does not hold (`core/agent_feature_access.py`). `GET /{id}` is
   gated too, so a hidden agent is not merely invisible but unaddressable.
3. **The rule covers `naas_abi`'s own office agents only.** A class matches
   only when its registry key is `naas_abi.<module>/<Class>` *and* the class
   is in `FEATURE_AGENTS` (`spec_for_class_name`). Another module's
   `ShopAppsAgent`, and naas_abi's own Abi orchestrator, carry no feature
   flag and pass through untouched. This mirrors `isFeatureOfficeAgent` on
   the web side.
4. **An agent serving several features survives on any one of them**
   (Settings holds `settings`, `settings.workspace`,
   `settings.organization`; Agent Catalog holds `agents` and `skills`).
5. **The agent tools apply the same filter.** `AgentCatalogAgent`'s
   `list_workspace_agents` / `get_workspace_agent` read the roster through
   the registry service, not the HTTP route, so they would otherwise name
   agents the listing hides. `caller_feature_flags` takes the caller's open
   session precisely so a tool can reuse it; the HTTP adapter opens one of
   its own. `list_agent_classes` is deliberately *not* filtered: it reports
   the code registry (what a deployment may put in `agents:`), not the
   workspace's data.
6. **The workspace default is never dropped**, whatever its class: the
   picker and the pane fall back to it, so removing it would leave a user
   with no agent at all.

## Consequences

- A member who can open Apps, Files and Ontology gets exactly the Apps,
  Files and Ontology agents plus the workspace default; the owner in the
  same workspace still gets the full roster. One `agent_configs` table,
  two different responses.
- Feature access and agent access can no longer drift: both derive from
  `build_feature_flags`, so a change to `role_baseline` moves the agents
  with the sections.
- The web side needs no change. An agent absent from the response is
  absent from `useAgentsStore`, so `pickFeatureOfficeAgent` finds nothing
  and `bindFeaturePaneAgent` falls back to the default, which is the
  wanted behaviour on a section the user cannot open anyway.
- `DocumentsAgent` is outside this rule. It is bound by its own
  `pickDocumentsOfficeAgent` on the web side and has no `FEATURE_AGENTS`
  row, so the `documents` flag does not gate it. Bringing it under the rule
  means giving it a registry entry, which also changes Abi's handoff line
  and the web parity test; left for a separate change.
- Adding a feature agent to `FEATURE_AGENTS` now also gates it. A new
  office agent must list its `feature_keys`, or it stays hidden from every
  role.
- The listing costs one extra query per call (workspace row plus the
  organization role override) on a route that already hits the database.
- Deployments still have to seed the office agents they want in `agents:`.
  The role rule narrows a roster; it never widens one.
