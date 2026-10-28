# Nexus authorization on IAM - AGENTS.md

## Purpose

Every Nexus authorization decision is a question to the engine's IAM service
([`libs/naas-abi-core/.../services/iam/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/iam/AGENTS.md):
policy language, resource names, evaluation, built-in roles). Nexus calls IAM as `api` acting on behalf
of the signed-in user, so both must be allowed (the intersection: `api` holds enumerated statements,
the user bounds every call). There is no role check outside IAM, no scope list and no second source of
memberships. Sign-in and credentials are in [`../oidc/AGENTS.md`](../oidc/AGENTS.md).

## Files

| File | Role |
|---|---|
| `catalog/` | The `nexus` action catalog: one module per router family (`dsl.py` builds types and actions with a **level**), aggregated by `__init__.py` into `NEXUS_CATALOG`, `FEATURE_OF`, `TYPE_OF`, `LEVEL_OF` |
| `authz.py` | `AUTHZ.require / allowed / decide / filter / name`: builds the resource name, checks `UseFeature` first, maps a refusal to `AuthzDenied` (an `HTTPException`: 403, or 404 for another user's personal resource). `ModuleScope` and `require_scope / allowed_scope / decide_scope / filter_scopes / scope_allowed_in_any` decide module scopes |
| `guards.py` | `guard(action, ...)`, a route dependency that decides before the body is read; `declares(action)` for routes that authorize inline. The matrix test reads both |
| `memberships.py` | `MEMBERSHIPS`: roles are `builtin.<role>` attachments at `abi:<org>:-` (org) and `abi:<org>:<ws>` (workspace); reads as `api`, changes as `api` on behalf of the caller |
| `names.py` | Scopes and resource names; `NO_ORG` (`_none`) is the org of a workspace that has none |
| `placements.py` | Which workspace owns the kernel resources Nexus keeps (`placement_source`, `place`, `place_existing`) |
| `bootstrap.py` | Startup: register the catalog, compute the feature policies, move the old membership rows into IAM once (`iam_migrations`) |
| `sets.py` | The organisation and workspace sets from Nexus's side: what a workspace lists (`within_set`, `in_set`, `workspace_set`), effective features of a workspace, a user's feature flags from IAM (`user_feature_flags`), a new workspace's set (`plan_workspace_set` then `record_workspace_set`, narrowed by its catalog seed), the one-time move of the feature overrides (`migrate_feature_overrides`) |
| `runtime.py` | Where Nexus gets IAM (the engine's); tests install their own with `configure` |
| `testing.py`, `../../conftest.py` | `NexusIam` (a real IAM on the memory store) and the `nexus_iam` / `team` / `nexus_db` fixtures |
| `route_matrix_test.py` | Every route declares its action; write methods never authorize only a read; every `guard` is decided by level for viewer, member, admin, owner, stranger |

## Rules

- **Level is the whole role model.** `list`/`read` actions are a viewer's, `write` a member's, `admin` an admin's;
  owners alone delete workspaces and organizations. A state change is never below `write`. IAM generates the
  built-in roles from the catalog, so choosing the level is choosing who may.
- **A route declares its action once**, in the decorator: `dependencies=[guard("PutFile", id=("drive", "path"))]`.
  Where the workspace is in the body or the resource is named only after loading it, call `await authz.require(...)`
  and add `declares(...)`. Kernel-bound routes declare the kernel action (`declares("triple_store:Query")`): the kernel
  decides as the same user.
- **Features** (`UseFeature`) are policies IAM attaches beside each workspace role (`builtin.features.<key>`,
  computed by `bootstrap.feature_plan` from `feature_flags` and the org overlays), within the sets of the
  workspace and its org ("Sets"). An action of a flagged section carries its `feature=` in the catalog; the API
  refuses it where the user lacks the feature.
- **Memberships change through `MEMBERSHIPS`** only: an admin cannot grant, demote or remove an owner, and the last
  owner stays (IAM answers, whichever API is used). An org owner or admin also holds their role organization-wide
  (`abi:<org>:*`, kept by `Memberships.mirror_org_wide` and `sync_org_wide_roles` at start): that is how they reach
  every workspace of the org; org members and viewers inherit nothing. Creating a workspace needs `CreateWorkspace`
  on its organization (an owner's or an admin's), never a request field; one with no organization is a personal
  workspace (`CreateOrganization`, which every user holds; its scope is the reserved org `_none`).
- **Kernel resources need a placement.** A workspace's role reaches a kernel resource only once IAM placed it in the
  workspace. Place what you create (`placements.place`), register what exists (`@placement_source`).
- **Roles are for users Nexus knows.** `MEMBERSHIPS` reads (`roles_of`, `check`, `revoke`) never create an IAM
  principal: an unknown id has no roles. `grant` and `seed` create the IAM user of a user Nexus has (`known_user`, set
  at startup), and refuse a service account or a group (`UnknownUserError`). A module's service account is never given
  a role through Nexus.
- **A credential's limit travels with the call.** A key's `abi_scope` rides in the call's context and bounds every
  decision of `AUTHZ`; never rebuild a context for the same user without it.
- **The IdP admin app is not a role's:** the platform viewer and member policies and a module's bootstrap Deny
  `discovery:OpenApp` on `app/*/idp/admin`. Do not widen `OpenApp` for a role without it.
- **A create that fails after the row exists removes it** (and the IAM scope): see `OrganizationService.create_organization`
  and `WorkspaceService.create_workspace`. A new workspace places its own resources with `on_workspace_created`, never
  `place_existing`. Its set is decided before anything exists (`sets.plan_workspace_set`, within its org's); placing
  or recording it failing removes the workspace and its placements (`placements.forget_workspace`): 409 when the org's
  set narrowed meanwhile, 503 without IAM. An import or the feature-override move records a workspace's features
  within its org's set (`sets.put_features`).
- **`-`, `*` and `_none` are not workspaces.** Never build a workspace scope or resource name from a path value
  without `Authz.org_of`/`name` (they refuse those ids): `abi:<org>:-` is the organization's own scope.
- **A change that widens what a workspace holds is checked beyond the catalog** (`read_all` is a platform
  administrator's, a graph read→write needs the right to drop it); strings that reach SPARQL are escaped.
- **Work as `api` for no user** only after the route authorized its caller, and only around the one call that needs it
  (`as_service_account("api")`). Never around user data.

## Module scopes

What modules expose is decided with core's `module` catalog, not `nexus` (core `services/iam/AGENTS.md`,
"Module scopes"): `ModuleScope(type, module, name)` is `abi:<org>:<ws>:module:<type>/<module>/<name>` in the
workspace the request names, after the user's membership there. One source of truth: the old `nexus:UseAgent` and
`UseApp` checks on a module's agents and apps are these.

| What | Scope (helper) | Where Nexus checks it |
|---|---|---|
| An agent of a module, engine (naas_abi's own, Abi included) or remote | `agent/<module>/<name>`, `module:UseAgent` (`services/agents/scopes.py`) | the roster and pickers (`GET /agents`, filtered), chat (`authorize_agent_use`), `/v1` models and completions, every in-process turn: the runtime runs no other agent and builds its copy without the others, at every depth: no handoff tool, graph node or intent leads to them (`provider_runtime._turn_copy`, `Agent.duplicate(keep=)`) |
| An app | `app/<module>/<name>`, `module:OpenApp` (`services/apps/scopes.py`) | `GET /apps` and the workspace's app configs (filtered), one config, `access-token` (a link names one app and opens that app's files alone, `app_html_root_of`: module paths nest), `remote-grant`, the workspace a remote app opens in (`remote/access.py`) |
| A workflow or pipeline | `workflow/<module>/<name>` or `pipeline/...`, `RunWorkflow`/`RunPipeline`, `Read*Runs` (`services/workflows/scopes.py`) | `/api/workspaces/{ws}/workflows`: listing, start, the caller's own runs; an agent's tools from an engine module's workflows (`agent_usable_module_scopes`, bound per turn by `bind_usable_agents`) |

- **Agents a workspace builds itself** (a model and a prompt, no module class) have no module scope: `nexus:UseAgent`
  and the roles decide (`agent_scope` answers None, and `filter_scopes` keeps what has none).
- **The `apps` and `agents` features** no longer gate using a module's apps and agents: they are the settings
  sections (`InstallApp`, `UpdateApp`, `UninstallApp`, agent edits) and the app projects. `nexus:UseApp` is left for a
  link that is no module's app (a Pages portal's sign-in).
- **Listed within the set, for everyone.** What a workspace lists of a module (`GET /apps`, its app configs, the agents
  roster, the workflows) is in its effective set (`sets.within_set`), the platform admin included: IAM bounds the
  others with the set already, never the platform admin, who still reaches an item outside it by name. Turning on an
  app, a module agent or a workflow outside the set from workspace settings is refused (403).
- **The listing** `GET /api/modules/scopes?workspace_id=|organization_id=` (`nexus:ListModuleScopes`, admin) is every
  module with its agents, apps, workflows, pipelines and declared catalog, with display data and the `resource` and
  `actions` a policy names (`services/modules/scopes.py`). The policy editor suggests ids from it.
- **Discovery's grants** stay the broker-side check (a member holds `InvokeAgent`, `OpenApp`, `TriggerJob`
  platform-wide); the module scope is checked here first, and a turn that names no workspace runs no module agent
  or workflow.

## Visibility

A workspace's admins turn each agent, app, workflow and pipeline of its set on or off for everyone in it
(`services/visibility`, workspace settings › Agents, Apps, Workflows). `authz` asks it after IAM allows the
use of a module scope (its use action; reading one's own runs is not a use): one turned off is refused
(`decide_scope` reason `hidden`, 403 "This <type> is turned off in this workspace"), left out of `filter_scopes`
and skipped by `scope_allowed_in_any`, for every role, the platform admin included. A listing still shows it to
who may turn that one back on: `filter_scopes(include_hidden=<predicate>)` with `authz.allowed_ids` (`UpdateApp`
/ `UpdateAgent` on each resource, in one `filter`). `filter_scopes(within_set=True)` is a listing of the
workspace: its set first. The settings actions are `nexus`'s
(`InstallApp`, `UpdateApp`, `UninstallApp`, `UpdateAgent`; `ListWorkflowSettings` and `UpdateWorkflow`,
`catalog/workflows.py`, admin, feature `settings`); IAM never sees the state itself.

## The `nexus` catalog

Nexus registers the `nexus` action catalog with IAM at startup (`catalog/__init__.py`, `VERSION`: raise it
when the catalog changes; IAM keeps the highest it has seen). Resources are
`abi:<org>:<ws>:nexus:<type>/<id>`, org-level ones `abi:<org>:-:nexus:...`, platform-level
`abi:-:-:nexus:...` (`rtype(..., platform=True)`); a personal type (`my_file`, `user_storage`) covers only
the caller's own id. One module per router family:

| Module | Resource types |
|---|---|
| `organizations.py` | `organization`, `member`, `domain`, `billing`, `role_features` (org level); `CreateWorkspace` is an org action |
| `workspaces.py` | `workspace`, `member`, `server`, `resource_access` |
| `features.py` | `feature/<key>` (`UseFeature`) |
| `chat.py`, `agents.py`, `apps.py`, `workflows.py` | `conversation`; `agent`, `skill`; `app`, `app_project`, `module` (`ListModuleScopes`); `workflow` (on or off in a workspace) |
| `files.py`, `datasets.py`, `office.py` | `file` (drive + path), `my_file`, `user_storage`, `root_storage`; `dataset`; `project` (slides, documents, sheets) |
| `knowledge.py`, `search.py` | `view`, `graph_cache`, `ontology`, `icon`, `layout`, `layer`, `feed_layer`, `basemap`, `maps_catalog`, `maps_access`; `search`, `topic`, `search_scope` |
| `code.py`, `settings.py`, `platform.py`, `realtime.py` | `code`, `code_settings`; `secret`, `provider_model`, `abi_server`; `analytics`, `system`; `presence`, `speech` |
| `tasks.py` | `task` (`task/<id>`, `task/-` the board), `task_iteration`, `task_settings` (singleton); every action behind the `tasks` feature |

The kernel services have catalogs of their own (core's `iam_catalog.py` of each service); a route that
only forwards to the kernel declares the kernel action. Choices that differ from "viewers read, members
write, admins administer" and are deliberate: the organization's directory, domains and billing are
`admin` (not `list`/`read`), as are layout edits, ontology cache refreshes, `GetResourceAccess`, topic
edits (`UpdateTopic`, `DeleteTopic`, `PreviewTopic`) and the system-drive files; `SyncAgents` is `write`
(every client sends it once per session); `GetPresence` and `Transcribe`/`Speak` are `read`. After editing
a catalog, run the route matrix.

### Roles, features and platform types

- **Built-in roles** `builtin.viewer ⊆ member ⊆ admin ⊆ owner` are generated by IAM from the registered
  catalogs by level (core's `roles.py`) and attached at a scope: `builtin.viewer` at `abi:<org>:<ws>` is the
  read-only policy on that workspace's resources. `builtin.platform_admin` (`*` on `*`, no scope, never
  over sealed resources) is `users.is_superadmin`. `builtin.self` is held by every user.
- **IAM administration by level.** Owners and admins of an org or a workspace manage that level's own policies
  and groups (`services/iam_admin`); members and viewers hold nothing of the `iam` catalog, not even the list of
  their scope's attachments (Nexus reads members as `api`). Deleting a workspace or an org
  (`Memberships.drop_scope`, then IAM's `delete_scope`) deletes the policies and groups it owns, with their
  attachments.
- **Features.** The role defaults come from feature policies, `builtin.features.<role>` and
  `builtin.features.<org>.<role>`, which IAM attaches beside each workspace role and detaches with it.
  `bootstrap.feature_plan` computes them from `feature_flags.role_baseline`, `organization_overrides` and the
  org overlay stored in `organization_role_features`, restricted to `enabled_features`; a key is emitted only
  where it differs from the broader one. A feature outside `enabled_features` is reachable by no role, owner
  and admin included (only the platform admin's `*`). Defaults: `owner` and `admin` get every enabled feature;
  `member` and `viewer` get `maps`, `chat`, `files`, `datasets`, `skills`, `slides`, `documents` and
  `sheets`. An overlay change recomputes the policies. The role's own statements leave out the `feature` type.
  What a workspace (and its org) has is its feature set ("Sets"): no feature policy is a workspace's any more.

## Sets

Core IAM keeps each org's and workspace's set (module items and features) and bounds every user's decision
with them (core `services/iam/AGENTS.md`, "Sets"). Nexus:

- **Shows the user what IAM decides.** The `feature_flags` of a workspace in `/api/workspaces` are IAM's
  `UseFeature` for the user, one `filter` per workspace (`sets.user_feature_flags`), within `enabled_features`:
  role defaults, the sets and any policy granting a feature, the platform admin's `*` included, in one `filter`
  for every workspace listed. Without an IAM it falls back to the role's defaults within the set
  (`build_feature_flags(feature_set=)`). **What is only shown fails closed:** when IAM fails to answer (a NATS
  timeout), the flags are all off and a workspace's set reads as empty (`effective_set`), logged at warning
  level, never a 500 and never wider than IAM would say; only an absent IAM (a route tested alone) reads as
  everything. The features a
  workspace offers (`features` of the org's workspace list and of `/configuration`, the agents a workspace
  syncs) are the roles' defaults within its effective set.
- **Edits sets as the user** through `services/iam_admin` (`/api/iam/admin/sets`, audited): the modules ×
  workspaces page. `settings` is added to every feature set it records (`PINNED_FEATURES`): a set never takes
  a workspace's settings away.
- **Records a new workspace's set** (`plan_workspace_set` before the row exists, `record_workspace_set` after, as `engine`, part of the creation the route authorized),
  a part only where something narrows it, so the rest follows its org's set, now and after the org's set
  changes:
  - `features`, when the create form chose them, within the org's;
  - `modules`, when its **catalog seed** names agents or apps. The seed (`catalog_seed`: agents, apps,
    ontologies, maps) still says what the workspace is created with; its `agents` and `apps` also narrow the
    set: those types become the seeded items the org has (through a whole module, `<type>/<m>/*` or
    `<type>/*/*`), every other type and the declared actions stay as the org has them (`<type>/<m>/*`,
    `<service>:*` for a whole module). In an org with no set, the rest is every module's, installed now or
    later (`workflow/*/*`, `pipeline/*/*`, `*:*`, and the type the seed leaves out): no snapshot of the
    modules running at creation. A seed with no `agents` (or `apps`) key narrows nothing of that type.
  A new org records none: everything.
- **Moved the feature overrides once** (`migrate_feature_overrides`, at start after the role data, recorded in
  `iam_migrations` as `workspace_feature_sets_v1`): `workspaces.feature_overrides`, else the deprecated
  `feature_flags.workspace_overrides`. An override turning a feature off leaves it out of the workspace's
  feature set, which is every other known feature (one the deployment enables later included) and always
  `settings` (`feature_set_from_overrides`, the snapshot import's rule too); one turning it on keeps it there
  and, for each role whose defaults lack it, a workspace policy (`Features kept from the workspace's
  overrides`, enabled features only) attached to the people holding that role there, at the workspace or
  org-wide (the org's owners and admins), keeps it for them. Nobody's features change; the column is
  cleared. Every step may run again (the set is put, the policy found by name and document before it is
  made, attaching is idempotent): a workspace that fails is logged and the move is not recorded, so the next
  start finishes it, and a failure never keeps the rest of startup's authorization (`sync_org_wide_roles`)
  from running. Snapshot imports (`core/workspaces_import.py`)
  record a feature set from a snapshot's overrides likewise, where the workspace has none.
- **Platform-level types.** A workspace role never reaches a platform-level resource. IAM keeps two
  managed policies in step with attachments: `builtin.platform.member` (held while the principal has a
  `member`, `admin` or `owner` attachment at a workspace or org-wide scope) and `builtin.platform.viewer`
  (only `viewer` attachments): the platform's models (`model_registry`), the apps, agents and modules it
  may open or invoke (`discovery`), views, templates, its own runs, its own keys and so on. Org-level
  attachments (`abi:<org>:-`) bring neither: an org member who belongs to no workspace cannot chat with
  models or open apps. Because Nexus calls as `api` on behalf of the user, the user must hold these too.
  Which agents, apps and workflows a user may use in a workspace is the module scope, checked by Nexus
  before the kernel call ("Module scopes").

## Decisions

- **Roles are attachments, and only IAM knows them.** `organization_members`, `workspace_members` and the
  `owner_id` fallbacks were read once into IAM at boot (`iam_migrations` marks it, migration `0059`) and
  are never read for a decision again; the configuration seeds grants. An existing install enforces once
  the boot migration ran; a role changed through the API is never undone by an old row.
- **Owner protection.** An admin cannot attach or detach `builtin.owner` (IAM answers, whichever API is
  used), so an admin cannot grant, demote or remove an owner, and the last owner stays. Creating a
  workspace is `CreateWorkspace` on its organization (`admin` level: org owners and admins), never a field
  of the request.
- **Org owners and admins reach every workspace of their organization, through IAM.** Whoever holds
  `builtin.owner` or `builtin.admin` at `abi:<org>:-` also holds the same role at `abi:<org>:*`, which IAM
  reaches into every workspace. `Memberships.mirror_org_wide` keeps the two together in `grant`, `seed` and
  `revoke`; `sync_org_wide_roles` makes the missing ones at start (and, for one person, after the sign-in
  that claims their invitation). IAM refuses an org admin an organization-wide attachment, so the mirror is
  written as `api` for no user, after the change that asked for the org role was authorized at the
  organization's own scope. The sync only adds: an organization-wide role someone attached on purpose is
  never removed by it. Members and viewers of an organization inherit nothing. Reads follow IAM: a
  workspace's effective role is the highest of the role held there and the organization-wide one
  (`WorkspaceService.get_workspace_role`, `effective_roles`); the members list shows organization-wide
  holders as `source: "organization"`, read-only. Demoting or removing an org owner or admin detaches the
  organization-wide attachment too; deleting an organization detaches both. There is no Nexus resolution of
  inherited roles (it would be a second source of roles).
- **No implicit access.** `builtin.api` and `builtin.engine` are enumerated statements, each with a `sid`
  that says what needs it (core's `roles.py`): `api` holds `nexus:*`, the kernel services it calls for its
  users (each user bounds the call), the sign-in identity actions, `iam:ExchangeToken`, and the IAM
  actions of memberships, scopes, placements, keys and shared-graph policies. Each engine module's jobs
  run as their own account `job/<module_id>` holding `builtin.job`. Acting on behalf of a user never opens
  a sealed resource.
- **Kernel resources need placements.** Nexus places what it creates and registers `placement_source`s for
  what exists, applied at every boot and when a workspace is created (`on_workspace_created`). Two
  platform-level exceptions are deployment grants (`iam.set_platform_grants`): the shared repository that
  slides, documents, sheets and code use (viewers read, members write) and the platform's datasets (read for
  every role). The shared repository separates workspaces by Nexus's branch naming only; a per-workspace
  repository is the way to make IAM enforce it.
- **Roles are for users, and only users Nexus knows become IAM users.** An id from a request path never
  creates an IAM principal; a `usr_` id must name a user record, never a service account or a group. A
  workspace admin can give a role to a person, never to a module's service account: a role is a way to reach
  the platform's apps and models, and a module's account is approved by manifest.
- **The IdP's admin app is not a role's.** A workspace viewer and member reach the platform's apps
  (`discovery:OpenApp` on `app/*`); the IdP's admin app edits who a `sub` is, which is who becomes the
  platform admin. `builtin.platform.viewer`, `builtin.platform.member` and every module's bootstrap policy
  carry an unconditional Deny of `discovery:OpenApp` on `app/*/idp/admin`; only the engine, which serves the
  IdP, opens it.
- **Who makes accounts in the provider's directory.** Every user may create an organization
  (`CreateOrganization` is a platform member's; a setting to turn that off does not exist), and its owner may invite, so the gate that holds is `identity:ProvisionUser` on the
  provider, decided as the inviting user. See `services/invites/AGENTS.md`.
- **Smaller guarantees.** `is_superadmin` is asked of IAM where it is shown (`/auth/me`, `/admin/me`,
  the session and sign-in responses), not on every request; only an absent IAM answers "not an admin",
  any other failure surfaces. A workspace's creation places that workspace's resources alone; the shared
  graph policies are found from one scan of their names (remembered for a minute); the routes that take no
  workspace (speech, the OpenAI gateway) ask IAM once for all the caller's workspaces. A new personal
  workspace (public signup) is registered with IAM, owned by its user and placed at once. The feature
  agents' tools and the admin tools decide through IAM like the routes do.
- **Module scopes, zero trust.** Viewers and members hold no module scope, on upgrade too (no migration
  grant): after the upgrade they use no module's agent (Abi included), app, workflow or pipeline until a policy
  grants it in their workspace; admins and owners hold them all. Nexus adds no role check of its own: IAM decides
  `module:*` like any action, as `api` for the user (`builtin.api` holds `module:*` and every module's declared
  catalog).
- **A workflow run's owner is Nexus's record.** Job runs carry no owner, so a start from a workspace is recorded
  (`workflow_run_owners`: run, user, workspace, time) and a user reads only the runs they started there, with
  `Read*Runs`. An idempotency key is the caller's own in the workspace (hashed with both), so another user's same
  key is another run. A run started elsewhere (the System tab, a schedule, an agent) has no owner here.
- **The workspace's feature set replaces its feature overrides.** An override could add a feature to every
  role; a set only bounds, so a feature beyond a role's defaults is given with a policy (the move made one for
  who held it). `PUT /organizations/{org}/workspaces/{ws}/features` is gone; Org settings › Workspaces and
  workspace settings › General link to the modules × workspaces page. The UI's flags are IAM's, so a policy
  granting a feature shows in the UI as it is enforced.
- **Workspace tasks are IAM's.** Decision: `/api/tasks` and the Tasks agent's tools ask the `nexus` actions of
  `catalog/tasks.py` (feature `tasks`) for the user, the routes with `guard`, the tools with the same names
  (`naas_abi/tools/tasks_tools.py`: opening a call is `ListTasks`, then each tool's action). Levels: reading
  (board, iterations, comments, history, feed, settings) is a viewer's, every change a member's, the settings
  (`UpdateTaskSettings`) and removing someone else's comment (`ModerateTaskComments`) an admin's; a comment's
  author removes their own with `DeleteTaskComment`, the domain service checking the authorship.
  Consequences: the defaults give `tasks` to owners and admins; members and viewers get it from the org
  overlay or a policy granting `UseFeature` on `feature/tasks`, and a workspace's set without `tasks` refuses
  everyone but the platform admin. The settings answer `can_edit` and `can_moderate` from IAM for the UI. Tasks
  have no placement (no kernel resource) and keep nothing in IAM: their rows go with the workspace (foreign
  keys `ON DELETE CASCADE`, `services/tasks/workspace_deletion_test.py`). SQLite (`abi dev`) does not enforce
  foreign keys, so there they stay behind, like every workspace table's rows, unreachable once the workspace's
  scope is dropped.
- **Known limits.** Under the default feature baseline members and viewers get 403 on the graph,
  ontology, search and settings sections (what the flags said, now enforced). `read_all` shares the graphs
  that exist when applied (`services/graph/AGENTS.md`). Per-object sharing beyond personal resources is an
  explicit statement naming the object.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam -q --no-cov
```

Drive real routers with the `team` fixture (`ws-1` of `org-1`: `owner`, `admin`, `member`, `viewer`, `stranger`) and
fake services; never mock `authz`.
