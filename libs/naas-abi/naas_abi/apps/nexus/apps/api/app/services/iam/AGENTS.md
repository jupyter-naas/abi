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
| `authz.py` | `AUTHZ.require / allowed / decide / filter / name`: builds the resource name in its container (`where`, `container_of`: a workspace's container as IAM registered it, cached), checks `UseFeature` first, maps a refusal to `AuthzDenied` (an `HTTPException`: 403, or 404 for another user's personal resource). `ModuleScope` and `require_scope / allowed_scope / decide_scope / filter_scopes / scope_allowed_in_any` decide module scopes; `upgrading()` refuses every module scope and feature until the sets are policies |
| `guards.py` | `guard(action, ...)`, a route dependency that decides before the body is read; `declares(action)` for routes that authorize inline. The matrix test reads both |
| `memberships.py` | `MEMBERSHIPS`: roles are `builtin.<role>` attachments at the organization's container and the workspace's; registers and deletes the containers (`register_org`, `register_workspace`, `drop_scope`); reads as `api`, changes as `api` on behalf of the caller |
| `names.py` | Every name Nexus builds, through core's `names`: `org_container`, `workspace_container`, `org_below`, `nexus_resource(type, container=, id=)`, and their readers `org_of`, `workspace_of` |
| `legacy_names.py` | The old grammar's `NO_ORG`, `org_scope`, `workspace_scope`: only for the start-up moves that predate container paths |
| `placements.py` | Which workspace owns the kernel resources Nexus keeps (`placement_source`, `place`, `place_existing`) |
| `bootstrap.py` | Startup: register the catalog, move the old membership rows into IAM once (`iam_migrations`) |
| `listers.py` | What naas_abi lists for the policy builder, registered with IAM at startup (`register`): organizations and workspaces (labels; IAM keeps only what its registry holds), members, the features in `enabled_features`, and every module's agents, apps, workflows and pipelines (`modules/scopes.gather`, named in the container asked). Each query runs on the API's loop (`OnLoop`) |
| `role_features.py` | Startup, once: what each role brought in each workspace becomes that workspace's policy "Features of <role>" (`migrate_role_features`, `iam_migrations` `role_features_v1`); then warns while a configuration still sets `role_baseline`, `organization_overrides` or `workspace_overrides` |
| `user_features.py` | A user's feature flags from IAM (`user_feature_flags`: `UseFeature` per workspace, in one `filter`), what `/api/workspaces` shows |
| `feature_overrides.py` | Startup, once: the per-workspace feature overrides of earlier versions (`migrate_feature_overrides`, `iam_migrations` `workspace_feature_sets_v1`) |
| `policy_tree.py` | Startup, once: the sets and the workspace toggles become access policies and their sub-policies (`migrate_sets`, `iam_migrations` `policy_tree_v1`); `pending()` until it is recorded |
| `container_names.py` | Startup, once, after `policy_tree_v1`: organizations and workspaces registered as IAM containers, and every name IAM stored in the old grammar rewritten to container paths (`LegacyNames`, `migrate_names`, `iam_migrations` `container_names_v1`); `pending()` until it is recorded |
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
- **Features** (`UseFeature`) come from policies only, never from a role. An action of a flagged section carries
  its `feature=` in the catalog; the API refuses it where the user lacks the feature. A feature outside
  `enabled_features` is usable by nobody.
- **Memberships change through `MEMBERSHIPS`** only: an admin cannot grant, demote or remove an owner, and the last
  owner stays (IAM answers, whichever API is used). An org owner or admin also holds their role below the
  organization (`<org container>/*`, kept by `Memberships.mirror_org_wide` and `sync_org_wide_roles` at start): that
  is how they reach every workspace of the org; org members and viewers inherit nothing. Creating a workspace needs
  `CreateWorkspace` on the new workspace's name as placed, `<org container>/nexus:workspace/<new id>` (an org owner's
  or admin's), never a request field; one with no organization is a personal workspace at the platform,
  `abi:nexus:workspace/<new id>`, which every user may create (`builtin.self`).
- **Names are built by `names.py` alone.** No f-string makes a name, a scope or a `${scope}` pattern elsewhere: an
  organization is `org_container(org)`, a workspace `workspace_container(org, ws)` (or `AUTHZ.container_of(ws)`
  when only its id is known), a resource `nexus_resource(type, container=, id=)`, a module scope
  `ModuleScope.resource(container)`. A policy Nexus writes at a scope uses `${scope}` and `${scope}/...` patterns.
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
- **A create that fails after the row exists removes it** (and its IAM container): see `OrganizationService.create_organization`
  and `WorkspaceService.create_workspace`. A new workspace places its own resources with `on_workspace_created`, never
  `place_existing`; placing failing removes the workspace and its placements (`placements.forget_workspace`). Its
  catalog seed (agents, apps, ontologies, maps) only installs: a new workspace grants nothing, a snapshot import
  neither.
- **`-` and `*` are not workspaces.** Never build a workspace's container or a resource name from a path value
  without `Authz.container_of`/`name` (they refuse those ids, and a workspace IAM does not know).
- **The call is made in the workspace's container.** Where Nexus names the workspace of a call (the request
  middleware from `/workspaces/{id}` or `?workspace_id=`, a chat turn, a graph or a repository it creates), it sets
  `CallContext.container` to the workspace's container as IAM registered it (`AUTHZ.container_of`), never to a
  value of the request: IAM places what the call creates there and names module scopes there.
- **A change that widens what a workspace holds is checked beyond the catalog** (`read_all` is a platform
  administrator's, a graph read→write needs the right to drop it); strings that reach SPARQL are escaped.
- **Work as `api` for no user** only after the route authorized its caller, and only around the one call that needs it
  (`as_service_account("api")`). Never around user data.

## Module scopes

What modules expose is decided with core's `module` catalog, not `nexus` (core `services/iam/AGENTS.md`,
"Module scopes"): `ModuleScope(type, module, name)` is `<workspace container>/module:<type>/<module>/<name>` in
the workspace the request names (`ModuleScope.resource(container)`), after the user's membership there. A grant
of one at a workspace is `${scope}/module:<type>/<module>/<name>`. One source of truth: the old `nexus:UseAgent` and
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
- **Listed as IAM decides.** What a workspace lists of a module (`GET /apps`, the agents roster, the workflows and
  workspace settings › Agents, Apps, Workflows) is what the caller may use there, IAM's `filter` alone
  (`filter_scopes`): no set, no switch. A workspace that should not offer a module denies it in a policy (its
  access policy's Denies, "The upgrade").
- **The listing** `GET /api/modules/scopes?workspace_id=|organization_id=` (`nexus:ListModuleScopes`, admin, or
  whoever may create or update policies there) is every module with its agents, apps, workflows, pipelines and
  declared catalog, with display data and the `resource` and `actions` a policy names (`services/modules/scopes.py`),
  **narrowed to what the caller may grant there** (`scopes.granted`, from IAM's `grantable` as the caller): an item
  none of whose actions the caller may grant on it, a declared action they may not grant, and a module left with
  nothing are left out. An admin who holds no module scope gets an empty list. The policy editor suggests ids
  from it. What exists is read as Nexus's own account (`api`), whoever asks (`scopes.gather`): someone holding
  policies but no role (so no discovery listing) still sees what they may grant, and the listers' cache of it is
  everyone's; each caller is narrowed afterwards.
- **Discovery's grants** stay the broker-side check (a member holds `InvokeAgent`, `OpenApp`, `TriggerJob`
  platform-wide); the module scope is checked here first, and a turn that names no workspace runs no module agent
  or workflow.

## The `nexus` catalog

Nexus registers the `nexus` action catalog with IAM at startup (`catalog/__init__.py`, `VERSION`: raise it
when the catalog changes; IAM keeps the highest it has seen). Its publisher is naas_abi (`publisher:
naas_abi`, core `services/iam/AGENTS.md`, "Publishers and listing"), as are the agents, apps, workflows and
pipelines of the engine module `naas_abi` in the `module` catalog. `organization` and `workspace` are its
containers (`rtype(..., container=True)`): an organization is `abi:nexus:organization/<org>`, a workspace
`abi:nexus:organization/<org>/nexus:workspace/<ws>` (`abi:nexus:workspace/<ws>` for one in no organization),
and actions on them are decided on those names. What a workspace holds is `<workspace>/nexus:<type>/<id>`,
what an organization holds `<organization>/nexus:<type>/<id>`, platform-level resources `abi:nexus:<type>/<id>`
(`rtype(..., platform=True)`); a personal type (`my_file`, `user_storage`) covers only the caller's own id. One
module per router family:

| Module | Resource types |
|---|---|
| `organizations.py` | `organization` (a container: `CreateOrganization` `creates`, `DeleteOrganization` `deletes` and `owner_only`), `member`, `domain`, `billing`; every user's `CreateOrganization` is a `PLATFORM_ACCESS` row (`organization/*`) |
| `workspaces.py` | `workspace` (a container with `platform_companions`: `CreateWorkspace` `creates`, `DeleteWorkspace` `deletes` and `owner_only`), `member`, `server`, `resource_access`; every user's personal `CreateWorkspace` is a `PLATFORM_ACCESS` row (`workspace/*`) |
| `features.py` | `feature/<key>` (`UseFeature`), `policy_only`: no role holds it |
| `chat.py`, `agents.py`, `apps.py`, `workflows.py` | `conversation`; `agent`, `skill`; `app`, `app_project`, `module` (`ListModuleScopes`); `workflow` (its settings: listed, deprecated switch) |
| `files.py`, `datasets.py`, `office.py` | `file` (drive + path), `my_file`, `user_storage`, `root_storage`; `dataset`; `project` (slides, documents, sheets) |
| `knowledge.py`, `search.py` | `view`, `graph_cache`, `ontology`, `icon`, `layout`, `layer`, `feed_layer`, `basemap`, `maps_catalog`, `maps_access`; `search`, `topic`, `search_scope` |
| `code.py`, `settings.py`, `platform.py`, `realtime.py` | `code`, `code_settings`; `secret`, `provider_model`, `abi_server`; `analytics`, `system`; `presence`, `speech` |

The kernel services have catalogs of their own (core's `iam_catalog.py` of each service); a route that
only forwards to the kernel declares the kernel action. Choices that differ from "viewers read, members
write, admins administer" and are deliberate: the organization's directory, domains and billing are
`admin` (not `list`/`read`), as are layout edits, ontology cache refreshes, `GetResourceAccess`, topic
edits (`UpdateTopic`, `DeleteTopic`, `PreviewTopic`) and the system-drive files; `SyncAgents` is `write`
(every client sends it once per session); `GetPresence` and `Transcribe`/`Speak` are `read`. After editing
a catalog, run the route matrix.

### Roles, features and platform types

- **Built-in roles** `builtin.viewer ⊆ member ⊆ admin ⊆ owner` are generated by IAM from the registered
  catalogs by level (core's `roles.py`) and attached at a container: `builtin.viewer` at a workspace's container
  is the read-only policy on that workspace and what it holds. `builtin.platform_admin` (`*` on `*`, no scope, never
  over sealed resources) is `users.is_superadmin`. `builtin.self` is held by every user.
- **IAM administration by level.** Owners and admins of an org or a workspace manage that level's own policies
  and groups (`services/iam_admin`); members and viewers hold nothing of the `iam` catalog, not even the list of
  their scope's attachments (Nexus reads members as `api`). Deleting a workspace or an org
  (`Memberships.drop_scope`, IAM's `delete_container`) deletes the policies and groups it owns, every
  attachment and placement at it, and everything below it (an org's workspaces).
- **What the roles leave out is the catalog's to say** (core's `services/iam/AGENTS.md`, "Action catalogs"):
  the `feature` type is `policy_only`, `DeleteWorkspace` and `DeleteOrganization` are `owner_only`, and the
  platform rows the roles' platform companions reach of Nexus (creating an organization, provider models, a
  user's own files and storage) are the catalog's `PLATFORM_ACCESS` (`catalog/organizations.py`,
  `settings.py`, `files.py`). Core's `roles.py` names no Nexus action or type.
- **Features: zero trust.** No role brings a feature, owners and admins included: a member of a workspace uses
  none until a policy grants it, attached directly, through a group, or carried by an invitation
  (`services/invites`). Each workspace has, after the move below, a policy "Features of <role>" for each role
  that had features there, to attach to newcomers. A feature outside `enabled_features` exists nowhere: it is
  offered nowhere and refused to everyone, the platform admin included, before IAM is asked
  (`authz.feature_exists`).
- **The move of the role features** (`role_features.migrate_role_features`, at start after the overrides' move
  and the org-wide roles, recorded in `iam_migrations` as `role_features_v1`). It reads what IAM has in force,
  never the configuration: the stored `builtin.features.<key>` an older version made (from `role_baseline`,
  `organization_overrides` and `organization_role_features`, within `enabled_features`) and the roles held now,
  choosing for each role the most specific key as the older IAM did (`key_for`). Then:
  - a role held at a workspace becomes the workspace's "Features of <role>", attached there; a role held
    org-wide (`abi:<org>:*`) becomes the organization's "Features of <role>", attached org-wide, so it still
    reaches the organization's workspaces made later; a group holding the role gets it like a person;
  - each workspace has its "Features of <role>" for every role that had features there, held or not, for
    invitations to carry;
  - each pending invitation to a role (IAM's pending grant) gets the matching pending grant beside it (an
    organization owner's or admin's: the organization's, org-wide, where the role is mirrored), listed on the
    Nexus invitation (`grant_ids`, `policy_ids`), so revoking it withdraws both.

  The old policies stay in force until the move is recorded, then are retired with their attachments
  (`iam.retire_policies`; a start that recorded the move but failed to retire finishes it; once none is
  left, `role_features_retired_v1` is recorded and later starts look no more), and the overlay
  table is dropped (the move runs after the SQL migrations, so no numbered migration could; `0040` creates
  nothing any more). Every step may run again. An item that cannot move (a stale attachment, say) is named
  in the log ("could not move builtin.member of usr_… at abi:…") and the rest goes on, but the move is not
  recorded until a start moves everything; a failure leaves the move unrecorded and nothing retired, so
  nobody loses or gains a feature at any step, whatever the configuration says by then (tested on a database at
  the previous state, `role_features_test.py`; and across versions, an IAM store written by the previous
  version's own code). Until the move, a role detached takes its own old companion with it (an admin made
  viewer loses the admin's features), as before; a role attached brings none. Afterwards `role_baseline`, `organization_overrides` and `workspace_overrides` do
  nothing, and a configuration that still sets them gets a warning at each start. The repository's own root
  configurations and `abi new project`'s drop them: an existing deployment may too, since the move does not
  read them (the overrides' move still does, once, before it).
- **The role features' actions stay declared.** `GetRoleFeatures` and `UpdateRoleFeatures` (and the
  `role_features` type) have no route and authorize nothing: IAM refuses a catalog version dropping an action a
  policy still names, which would stop Nexus's start, so they are kept, deprecated. `GET /access` reports
  neither.

## The upgrade: sets and toggles become policies

Before, three things decided whether a user used a module's item or a feature in a workspace: the policies (and
`builtin.admin` / `builtin.owner`, which held every module scope at their scope), core IAM's sets of the org and
the workspace (the Modules & features pages), and what the workspace turned off (`services/visibility`, workspace
settings › Agents, Apps, Workflows, and a workspace-built agent's own switch). `policy_tree.migrate_sets` (at
start, after the overrides' move and the role features' move, `role_features_v1`: an old feature policy kept as a
sub-policy's parent is detached, so its retirement is not waited for; recorded in `iam_migrations` as
`policy_tree_v1`) keeps every decision, then they are gone:

- **The tree.** Each org O gets "<O> access", platform-owned: its set's module items and features (everything
  with no set). Each workspace W gets "<W> access", O-owned, a sub-policy of it: W's own set's items and features,
  the apps it had turned on one by one (an app was off until turned on or seeded), and a Deny of the agents,
  workflows and pipelines it had turned off (use only: a workflow's runs stay readable). A set of nothing is an
  Allow no name matches (`Nothing`), never a Deny. A turned-off engine agent whose class the engine did not load
  stops the move (its scope would be guessed): load the module or delete the row.
- **Agents a workspace built** (no module) and had turned off: "Agents turned off in <W>", W-owned, a Deny of
  `nexus:UseAgent` on each, attached at W to whoever held a role there (directly, through a group, org-wide,
  invited). The roster lists a built agent only to who may use it (`agents/.../_visible_to_caller`).
- **Roles.** Who held `builtin.admin` or `builtin.owner` (at W, org-wide, at `abi:O:-`; a group like a person; a
  pending invitation as a pending grant listed on its Nexus invitation, an org owner's or admin's for every
  workspace, as the org-wide mirror will) gets, at each place the role reached, "<W> modules (admins and owners)":
  a sub-policy of that place's access granting every module scope. Not the access policy itself: it bounds
  features too, and no role brought a feature.
- **Customer policies.** One that grants module scopes or features moves under the access policy of its owner (a
  workspace's under "<W> access", an org's under "<O> access", the "Features of <role>" included), split from what
  else it grants (files, graphs, Denies stay in it, its modules and features move to a sub-policy beside it). An
  attachment the owner's access would not bound as the sets did (an org's policy attached in a workspace or
  org-wide, a platform policy attached anywhere) becomes, at each place it reached, one of a sub-policy of that
  place's access holding the same statements (`statements_at`: glob patterns cut to the place, exactly). A
  platform policy's unscoped reach of the platform's own names (`abi:-:-:`) stays unbounded, as it was. A split
  spells out the actions a wildcard reached beyond module scopes and features, `MAX_PATTERNS` per statement.
- **Service accounts.** Never bounded by a set, but Nexus refused them what a workspace had turned off, like
  everyone: at each place a grant reached, they get a copy cut to it, in a workspace a sub-policy of its "<W>
  toggles (service accounts)" (every module scope and feature but what it had turned off), else with no parent.
- **Named, not silent** (the report's `notes`, logged): a grant attached org-wide or with no scope that moved to
  the workspaces of today (naming the policy and the principal: a workspace made later gets nothing from it), and
  a wildcard of every service spelled out (the bus and services registered later are no longer in it).
- **Exact or stopped.** A sub-policy made before with module grants, a managed policy granting them to users, an
  action acting on module scopes and other types: the move stops, names it in the log, records nothing. Until it
  is recorded, `authz.upgrading()` refuses every module scope and feature (and the flags show none): never wider
  than before. Every step may run again (policies found by owner, name and description; a policy's document is
  rewritten last).
- **Then** IAM's legacy sets (`drop_legacy_scope_sets`) and `workflow_visibility` go. `app_configs.enabled` and
  `agent_configs.enabled` stay in their tables, unread (no ORM column).
- **What changes** (`policy_tree.NOTES`, in the report): the platform admin reaches what a workspace had turned off;
  an org's admins and owners reach a workspace made later only through a policy attached there (or org-wide after
  the upgrade); a module installed later is in no access policy until someone adds it; someone given a role later in
  a workspace uses the agents it had built and turned off. Calls that skip Nexus (a module's `require_action`,
  discovery's `OpenApp`) are not gated while the move is pending.

Tested on a database at the previous state (`policy_tree_test.py`: every user and a service account, workspace,
module item, declared action, built agent and feature compared before and after, on the memory, SQLite and
PostgreSQL stores; once; interrupted; stopped; pending invitations; `*` and `nexus:*` policies split; the notes;
narrowing "<O> access" narrows below at once; an admin with no policy uses nothing).

## The upgrade: names become container paths

Names were `abi:<org>:<ws>:<service>:<type>/<id>`; core IAM now names paths of containers and knows no
organization (core `services/iam/AGENTS.md`, "Resource names", "Migrating an existing install"). The org and
workspace fields were Nexus's, so the move is: `container_names.migrate_names` (at start, once, after
`policy_tree_v1`, recorded as `container_names_v1`) reads Nexus's organizations and workspaces, and has IAM
register them as containers and rewrite every stored name in one transaction (`iam.rewrite_names(LegacyNames)`):

- **Scopes and owners.** `abi:O:W` is the workspace's container, `abi:O:-` the organization's, `abi:O:*` below
  the organization's, `abi:-:-` the platform `abi:`; an owner `abi:_none:-` (what the sets' move made for the
  workspaces in no organization) the platform, which nobody's role reached either. A scope or an owner naming
  what Nexus does not know any more is left as it was: in core's `UNRESOLVED`, it decides nothing.
- **Patterns** become the patterns that name, in the new grammar, exactly what they named: `abi:*:*:R` is
  `names.anywhere(R)`, `abi:O:*:R` `<O>/R` and `<O>/*/R`, a field with another wildcard each organization or
  workspace it matched; the singletons `nexus:organization/-` and `nexus:workspace/-` the containers themselves,
  for the actions on those types (a statement split by type of action where needed); `CreateWorkspace`, decided
  on the organization before, on `<O>/nexus:workspace/*`, `CreateOrganization` on `abi:nexus:organization/*`;
  a pattern of the platform's or an organization's own level cut to the types that are no container there (a
  `*` crosses into containers now), only those its statement's actions are on. What is spelled out for the
  organizations, workspaces or services of today is named in the report's notes.
- Placements, keys' narrowing, manifests, invitations and bindings likewise. What is already a path is kept,
  so the move may run again; a statement whose rewrite names nothing is kept as written (it named nothing).
- Until it is recorded, module scopes and features are refused (`authz.upgrading`); IAM itself narrows, never
  widens (old names match nothing new). Start-up order (`main._prepare_iam`): the catalog, the moves that write
  the old grammar (feature overrides, role features, sets), this move, then `migrate_role_data` and
  `sync_org_wide_roles` in the new grammar (`container_names.before_names`). The moves before it read the
  roles IAM holds, so first an organization owner's or admin's missing org-wide mirror is made in the old
  grammar (`mirror_old_org_wide`); and while Nexus still keeps memberships IAM does not hold (the move of the
  role data, `iam_roles_v1`, not recorded: an install from before #360), nothing moves and nothing is recorded,
  an error says so, and every module scope and feature stays refused (`role_data_pending`): such an install
  upgrades through a version that moved its role data first, never by recording moves that moved nothing.
- **Several API processes.** The moves run in one process at a time (`container_names.moves_lock`): on
  PostgreSQL a session advisory lock, on a connection of its own, that the other processes wait for at start,
  then find each move recorded and skip it. SQLite has no lock between processes: an install on SQLite starts
  one API process for the start that upgrades. A process that still refuses module scopes and features after
  its start (its move failed, or another process was making it) re-reads `iam_migrations` every minute
  (`main._watch_upgrade`, `container_names.refresh_pending`) and stops refusing once the moves are recorded,
  without a restart.

Tested on a store the code before container paths made (`container_names_test.py`,
`tests/artifacts/names_v1`: 1872 decisions of platform, org, org-wide, workspace and orgless roles, an org's
group, a platform policy attached org-wide, a sub-policy, a Deny, absolute patterns of every shape, a service
account, invitations, a binding, placements, a narrowed key): every one is the same after, but one rule change
(an admin of an organization's own level may attach below it, what it grants there still checked); once and
again changes nothing. `policy_tree_test.py`, `role_features_test.py` and `feature_overrides_test.py` run the
chain from an old-grammar world (`testing.LegacyNexusIam`) through their move and this one.

## Platform-level types and the flags shown

- **Platform-level types.** A workspace role never reaches a platform-level resource. IAM keeps two
  managed policies in step with attachments: `builtin.platform.member` (held while the principal has a
  `member`, `admin` or `owner` attachment at a workspace or below an organization) and `builtin.platform.viewer`
  (only `viewer` attachments): the platform's models (`model_registry`), the apps, agents and modules it
  may open or invoke (`discovery`), views, templates, its own runs, its own keys and so on (the `workspace` type's
  `platform_companions`). Attachments at an organization's own container bring neither: an org member who belongs to no workspace cannot chat with
  models or open apps. Because Nexus calls as `api` on behalf of the user, the user must hold these too.
  Which agents, apps and workflows a user may use in a workspace is the module scope, checked by Nexus
  before the kernel call ("Module scopes").
- **The flags shown** (`feature_flags` of `/api/workspaces`) are IAM's `UseFeature` for the user
  (`user_features.user_feature_flags`), one `filter` for every workspace listed, within `enabled_features`;
  without an IAM every feature is shown off, and when IAM fails to answer too (logged). The features a workspace
  offers (`features` of `/configuration` and of the org's workspace list) are the deployment's enabled ones.

## Decisions

- **naas_abi lists its own, IAM filters.** Decision: naas_abi registers listers with the engine's IAM at
  start (`listers.py`) for `organization`, `workspace`, `member`, `feature` and the `module` catalog's four types;
  each returns candidates from Nexus's database (or the modules' listing) and IAM keeps what the caller may list
  (core `services/iam/AGENTS.md`, "Publishers and listing"). Organizations and workspaces are IAM's containers:
  its registry decides which exist, naas_abi only labels them. Features come from `enabled_features` alone, so a
  disabled feature is listed nowhere, as it is usable nowhere (`authz.feature_exists`). Consequences: IAM is
  synchronous and the database async, so each query runs on the API's loop from IAM's thread (`OnLoop`); asked
  from that loop it fails, and the type comes back as wildcards rather than blocking. The modules' items are
  gathered at most every 30 seconds. Nexus's other types (conversations, files, …) are offered as wildcards: no
  lister yet.
- **Roles are attachments, and only IAM knows them.** `organization_members`, `workspace_members` and the
  `owner_id` fallbacks were read once into IAM at boot (`iam_migrations` marks it, migration `0059`) and
  are never read for a decision again; the configuration seeds grants. An existing install enforces once
  the boot migration ran; a role changed through the API is never undone by an old row.
- **Owner protection.** An admin cannot attach or detach `builtin.owner` (IAM answers, whichever API is
  used), so an admin cannot grant, demote or remove an owner, and the last owner stays. Creating a
  workspace is `CreateWorkspace` on its name in its organization (`admin` level: org owners and admins),
  never a field of the request.
- **Org owners and admins reach every workspace of their organization, through IAM.** Whoever holds
  `builtin.owner` or `builtin.admin` at the organization's container also holds the same role below it
  (`<org container>/*`), which IAM reaches into every workspace. `Memberships.mirror_org_wide` keeps the two together in `grant`, `seed` and
  `revoke`; `sync_org_wide_roles` makes the missing ones at start (and, for one person, after the sign-in
  that claims their invitation). An org admin holds nothing below the organization to grant there, so the
  mirror is written as `api` for no user, after the change that asked for the org role was authorized at the
  organization's container. The sync only adds: a role below the organization someone attached on purpose is
  never removed by it. Members and viewers of an organization inherit nothing. Reads follow IAM: a
  workspace's effective role is the highest of the role held there and the one below its organization
  (`WorkspaceService.get_workspace_role`, `effective_roles`); the members list shows organization-wide
  holders as `source: "organization"`, read-only. Demoting or removing an org owner or admin detaches the
  attachment below the organization too; deleting an organization drops both with its container. There is no Nexus resolution of
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
- **Module scopes, zero trust.** No role holds a module scope, admins and owners included: a user uses no module's
  agent (Abi included), app, workflow, pipeline or declared action until a policy grants it in their workspace
  (the upgrade gave each what the roles and sets let them use). Nexus adds no role check of its own: IAM decides
  `module:*` like any action, as `api` for the user (`builtin.api` holds `module:*` and every module's declared
  catalog).
- **A workflow run's owner is Nexus's record.** Job runs carry no owner, so a start from a workspace is recorded
  (`workflow_run_owners`: run, user, workspace, time) and a user reads only the runs they started there, with
  `Read*Runs`. An idempotency key is the caller's own in the workspace (hashed with both), so another user's same
  key is another run. A run started elsewhere (the System tab, a schedule, an agent) has no owner here.
- **No role brings a feature.** *Decision:* features are granted by policies only, like agents; the role
  features (`role_baseline`, `organization_overrides`, the organisation role features table, its routes
  `/api/organizations/{org}/roles/features` and page; the actions stay declared, deprecated) and the
  new-workspace form's feature choice (`WorkspaceCreate.features`, `GET /organizations/{org}/workspace-features`)
  are gone. *Consequences:* a new member has no feature until a policy grants one (an invitation can carry
  "Features of member"); a workspace's creator holds none in it either, unless a policy above it grants them;
  `enabled_features` alone decides which features exist. The tasks routes declare `ListTasks`, `UpdateTasks`
  and `ManageTasks` (feature `tasks`) instead of checking roles.
- **Policies are the one place access is decided.** *Decision:* the sets (core IAM's, and the Modules & features
  pages, `/api/iam/admin/sets`), the workspace on/off toggles (`services/visibility`) and the catalog seed's
  narrowing go; what a user lists and uses is IAM's decision alone. *Consequences:* an org's access is its
  "<O> access" policy, a workspace's its sub-policy; narrowing one narrows everything below at the next decision.
  A workspace that should not offer something denies it there. The feature overrides' route
  (`PUT /organizations/{org}/workspaces/{ws}/features`) stays gone; the UI's flags are IAM's.
- **Known limits.** A member with no feature policy gets 403 on every flagged section (what the flags say,
  enforced). `read_all` shares the graphs
  that exist when applied (`services/graph/AGENTS.md`). Per-object sharing beyond personal resources is an
  explicit statement naming the object.

- **Organizations and workspaces are IAM containers.** *Decision:* Nexus declares `organization` and
  `workspace` as container types of its catalog (ids opaque, the Nexus ids) and registers each one with IAM
  as it creates it, with its own account (`api`): an organization at the platform, a workspace in its
  organization's container, or at the platform when it belongs to none (no reserved org: `_none` is gone from
  every name). The organization resource is the organization's container, the workspace resource the
  workspace's; `CreateOrganization` and `CreateWorkspace` are checked on the new one's name as placed (the
  route picks its id first, `new_org_id`, `new_workspace_id`), and deleting either deletes its container
  (`iam.delete_container`). An organization's owners and admins are mirrored below it. *Consequences:* every
  scope Nexus attaches at, owns a policy or a group with, invites or binds at is a container name (`abi:`,
  `<org container>`, `<workspace container>`, `<org container>/*`); a workspace's container is read from IAM
  (`Authz.container_of`, cached, forgotten on a change made here), never from a request; a role at a workspace
  brings the platform companions, one at an organization's own level does not (`platform_companions`);
  deleting an organization removes what its workspaces owned in IAM with it. The start-up moves that predate
  container paths (`feature_overrides`, `role_features`, `policy_tree`) still read and write the old grammar
  (`legacy_names`) until the move of the names (`container_names`) rewrites it; `migrate_role_data` and
  `sync_org_wide_roles` run after that move, in the new grammar.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam -q --no-cov
```

Drive real routers with the `team` fixture (`ws-1` of `org-1`: `owner`, `admin`, `member`, `viewer`, `stranger`) and
fake services; never mock `authz`.
