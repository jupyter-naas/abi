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
| `memberships.py` | `MEMBERSHIPS`: who works where and at which level ("Levels as groups"). In a grouped container the role-based API (`grant`, `revoke`, `check`, `seed`, `roles_of`, `members`, `org_directory`) reads and changes the groups ("<W> workspace", "<W> admins", "<O> people", "<O> admins", the level groups); in one recorded before #1585, `builtin.<role>` attachments as before. `level_of`, `LastOrgAdminError` (409); registers and deletes the containers (`register_org`, `register_workspace`, `drop_scope`); reads as `api`, changes checked as the caller then written as `api` |
| `levels.py` | The level groups ("Viewers", "Members"), "Workspace admins" (every model), "Platform admins" and the generic level policies ("Viewer access", "Member access", "Workspace admin access"): `LEVELS.get` (made on first need and at start), `LEVELS.peek` (reads, never made), `level_document` |
| `names.py` | Every name Nexus builds, through core's `names`: `org_container`, `workspace_container`, `org_below`, `nexus_resource(type, container=, id=)`, and their readers `org_of`, `workspace_of` |
| `legacy_names.py` | The old grammar's `NO_ORG`, `org_scope`, `workspace_scope`: only for the start-up moves that predate container paths |
| `placements.py` | Which workspace (or organization: `Placement.organization`) owns the kernel resources Nexus keeps (`placement_source`, `place`, `place_existing`) |
| `bootstrap.py` | Startup: register the catalog, move the old membership rows into IAM once (`iam_migrations`) |
| `listers.py` | What naas_abi lists for the policy builder, registered with IAM at startup (`register`): organizations and workspaces (labels; IAM keeps only what its registry holds), members, the features in `enabled_features`, and every module's agents, apps, workflows and pipelines (`modules/scopes.gather`, named in the container asked). Each query runs on the API's loop (`OnLoop`) |
| `role_features.py` | Startup, once: what each role brought in each workspace becomes that workspace's policy "Features of <role>" (`migrate_role_features`, `iam_migrations` `role_features_v1`); then warns while a configuration still sets `role_baseline`, `organization_overrides` or `workspace_overrides` |
| `user_features.py` | A user's feature flags from IAM (`user_feature_flags`: `UseFeature` per workspace, in one `filter`), what `/api/workspaces` shows |
| `feature_overrides.py` | Startup, once: the per-workspace feature overrides of earlier versions (`migrate_feature_overrides`, `iam_migrations` `workspace_feature_sets_v1`) |
| `policy_tree.py` | Startup, once: the sets and the workspace toggles become access policies and their sub-policies (`migrate_sets`, `iam_migrations` `policy_tree_v1`); `pending()` until it is recorded |
| `container_names.py` | Startup, once, after `policy_tree_v1`: organizations and workspaces registered as IAM containers, and every name IAM stored in the old grammar rewritten to container paths (`LegacyNames`, `migrate_names`, `iam_migrations` `container_names_v1`); `pending()` until it is recorded |
| `workspace_offer.py` | "<W> access" as an allow-list ("Ceilings as allow-lists"): `Offer`, `offer_document`, `offer_of`, `with_offer`, `in_offer_form`, `offer_from_seed`, `seeded_offer` |
| `model_sets.py` | "Models · member", "Models · all", "Models · embeddings" (platform policies kept in step with `nexus_config.models.member_set` at start, `ensure_configured`); `level_model_policy_ids(iam, level)` for the level groups |
| `capabilities.py` | Capability groups made on demand (`ensure_capability`): an organization's "Workflow runners", the platform's "Models · all" |
| `given_files.py` | The files a workspace's offer gives outside it: `GivenOrgFiles`, `GivenPlatformFiles`, `GivenSystemFiles` by mode (`statements`, `mode_of`) |
| `files_offer.py` | Startup, once: the Platform Files groups of #1590 into `GivenPlatformFiles`, groups and policies deleted (`iam_migrations` `files_offer_v1`); the legacy drive flags (`convert_legacy_drive_flags`, `DriveFlagChange`) |
| `given_graphs.py` | The graphs a workspace's offer gives outside it and what it closes of its own: `GivenGraphs`, `GivenGraphsWrite`, `GivenGraphsAll`, `OfferGraphsDeny` (`statements`, `fields_of` from a `WorkspaceGraphPolicyConfig`, `config_of` back, `summary`) |
| `workspace_models.py` | The chat models a workspace uses (its offer's `OfferModels`, `*` every one, and `OfferDefaultModel`; ADR `20261126_models_in_the_offer`): `WorkspaceModels` (`model_for` switches to the default, `require` refuses), `models_in_workspace`/`models_in_container` (the offer cache), `for_turn`/`set_for_turn`/`models_for_turn` (the turn's), `turn_llm_model` (by provider: switch, the engine's, or refuse), `install_substitute` (the engine's model registry asks it for a remote module's turn) |
| `models_offer.py` | Startup, once: every model (`*`) into each recorded access policy that names none (`iam_migrations` `models_offer_v1`) |
| `graphs_offer.py` | Startup, once: each workspace's graph assignment into its offer, the `workspace.<ws>.graphs.read|write` policies and their per-person attachments deleted (`iam_migrations` `graphs_offer_v1`); `configured_graphs` for a seeded workspace made later |
| `given_maps.py` | The Maps items a workspace's offer gives it without owning them, and the deployment items it closes: `GivenMaps`, `GivenBasemaps`, `OfferMapsDeny`, `OfferBasemapsDeny` (`statements`, `fields_of` from a `MapsAssignment`, `assignment_of` back, `with_item`, `summary`) |
| `maps_offer.py` | Startup, once: what each workspace may use per `maps_grants` into its offer (`iam_migrations` `maps_offer_v1`); `maps_grants` kept for a workspace whose access policy is no allow-list yet |
| `platform_files_routes.py` | `GET`/`PUT /api/workspaces/{id}/platform-files`: `{workspace_id, mode, can_change}`, the offer's `GivenPlatformFiles`; read as the configuration, written as the caller |
| `container_defaults.py` | Each organization's and workspace's access policy and groups ("Access policies and default groups"): "<O> access", "<O> admins", "<O> people"; "<W> access" (W's bound), "<W> workspace", "<W> admins"; made with it (`ContainerDefaults.org_created`, `workspace_created`, in the creating request's transaction through the adapters' `container_defaults()`), forgotten with it (`dropped`); `grouped` / `grouped_record` (whether its people are groups, #1585); a container recorded before #1585 keeps its "<X> members" and admins in step with the roles (`sync_scope`); recorded in the table `container_defaults`; `migrate` gives those that predate them theirs, at every start, once recorded as `container_defaults_v1` |
| `access_model.py` | Startup, once, after `container_defaults_v1`: per-person attachments become groups, with the report of every access change, compared after the start ("The access move"; `migrate_access`, `complete_report`, `iam_migrations` `access_model_v1`; `abi iam migrate-access --dry-run`, `migrate_from_cli`) |
| `shadow_iam.py` | A copy of an IAM in memory (`shadow_of`), or kept as JSON (`snapshot`, `store_of`): the access move tries its plan there first, and reads its report from the copies' decisions |
| `../invites/migration.py` | Startup, once (background, after the moves): each pending Nexus invitation becomes an invited `users` row holding what its pending grants held, attached as `api` for no user (they were authorized at invitation), the grants withdrawn (`iam_migrations` `invitations_to_people_v1`, `abi user migrate-invitations`; `services/invites/AGENTS.md`) |
| `module_moves.py` | Startup, once, after `container_names_v1`: a module scope a remote module serves now (`MOVES`: the X app, `app/naas_abi_marketplace.applications.x/x_proxy` to `app/applications.x/x_proxy`) renamed in policy documents and keys' narrowing (`iam.rewrite_names(MovedScopes)`, `iam_migrations` `module_moves_v1`): a pattern naming the old item names the new one, a wildcard over the old module gets the new item beside it, one already reaching it is left. Nexus's rows of the app id: migration `0072_remote_x_app.sql` |
| `runtime.py` | Where Nexus gets IAM (the engine's); tests install their own with `configure` |
| `testing.py`, `../../conftest.py` | `NexusIam` (a real IAM on the memory store) and the `nexus_iam` / `team` / `nexus_db` fixtures |
| `route_matrix_test.py` | Every route declares its action; write methods never authorize only a read (the reads sent by POST are `view_as/reads_by_post.py`'s `READS_BY_POST`, one list the read-only guard of a view reads too); every `guard` is decided by level for viewer, member, admin, owner, stranger (roles of before), and for a Viewer, a Member, a workspace admin, an org admin, the platform admin and a stranger through groups (#1585) |

## Rules

- **Level is the whole role model.** `list`/`read` actions are a viewer's, `write` a member's, `admin` an admin's;
  an organization's admins delete its workspaces (`DeleteOrganizationWorkspace`), the platform admin organizations
  (`DeletePlatformOrganization`): owner is no longer assigned (#1585). A state change is never below `write`. IAM generates the
  built-in roles from the catalog, so choosing the level is choosing who may.
- **A route declares its action once**, in the decorator: `dependencies=[guard("PutFile", id=("drive", "path"))]`.
  Where the workspace is in the body or the resource is named only after loading it, call `await authz.require(...)`
  and add `declares(...)`. Kernel-bound routes declare the kernel action (`declares("triple_store:Query")`): the kernel
  decides as the same user.
- **Features** (`UseFeature`) come from policies only, never from a role. An action of a flagged section carries
  its `feature=` in the catalog; the API refuses it where the user lacks the feature. A feature outside
  `enabled_features` is usable by nobody.
- **Memberships change through `MEMBERSHIPS`** only ("Levels as groups"): in a grouped container they are groups,
  never a person's attachment, and the last Org Admin of an organization stays (`LastOrgAdminError`, 409). In a
  container recorded before #1585 an admin cannot grant, demote or remove an owner of before, and the last owner stays
  (IAM answers, whichever API is used). An org owner or admin of before also holds their role below the
  organization (`<org container>/*`, kept by `Memberships.mirror_org_wide` and `sync_org_wide_roles` at start): that
  is how they reach every workspace of the org; org members and viewers inherit nothing. Creating a workspace needs
  `CreateWorkspace` on the new workspace's name as placed, `<org container>/nexus:workspace/<new id>` (an org owner's
  or admin's), never a request field; one with no organization is a personal workspace at the platform,
  `abi:nexus:workspace/<new id>`, which no user may create unless `nexus_config.personal_workspaces` is on
  (a self grant, `bootstrap.self_grants`; catalog 16). Organizations are the platform admins' to create.
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
- **Deleting an organization** (`DELETE /api/organizations/{org}`, `DeletePlatformOrganization` on the
  platform-level `abi:nexus:organization_record/<org>`: the platform admin's alone, #1585) is refused with 409 while it has workspaces, naming each ("Organization O still has
  workspaces: Alpha (ws-…). Delete them first"): deleting their data with it is not this route's to decide. Otherwise
  its row goes (members and domains with it), then its IAM container with what it owns (`drop_scope`), then its
  access policy, the platform's (`ContainerDefaults.dropped`). The row is held for writing first
  (`lock_organization`: `SELECT … FOR UPDATE` on PostgreSQL, which a workspace insert's foreign key check waits for;
  a write on SQLite, which takes the database): a workspace made in it meanwhile waits for the transaction, then finds the organization
  gone, never survives with no organization while its container goes with the organization's. A container IAM still
  registers inside it (a workspace with no row, a module's) refuses it too (`Memberships.containers_in`), named.
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
- **Listed as IAM decides, within the offer.** What a workspace lists of a module (`GET /apps`, the agents roster,
  the workflows and workspace settings › Agents, Apps, Workflows) is what the caller may use there, IAM's `filter`
  (`filter_scopes`): no set, no switch. It is also within the workspace's offer ("<W> access", `Authz.offer_of`,
  remembered 30 s, forgotten by `widen_offer` and the offer editor), so an org admin or the platform admin, whom
  IAM lets use more, sees in W what W offers (ADR `20261120_access_levels_and_groups`, decision 11). A workspace
  with no record, or a policy that is no allow-list yet, is not narrowed. A single item (`require_scope`) is IAM's
  alone.
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
| `organizations.py` | `organization` (a container: `CreateOrganization` `creates`, `DeleteOrganization` `deletes` and `owner_only`, deprecated: no route asks for it), `organization_record` (platform: `DeletePlatformOrganization`, no role's), `DeleteOrganizationWorkspace` (admin, on the organization), `member`, `domain`, `billing`; no user's `CreateOrganization` (catalog 16: the platform admins') |
| `workspaces.py` | `workspace` (a container with `platform_companions`: `CreateWorkspace` `creates`, `DeleteWorkspace` `deletes` and `owner_only`: a workspace in no organization), `member`, `server`, `resource_access`; the personal `CreateWorkspace` is a self grant only with `nexus_config.personal_workspaces` |
| `features.py` | `feature/<key>` (`UseFeature`), `policy_only`: no role holds it |
| `chat.py`, `agents.py`, `apps.py`, `workflows.py` | `conversation`; `agent`, `skill`; `app`, `app_project`, `module` (`ListModuleScopes`); `workflow` (its settings: listed, deprecated switch) |
| `files.py`, `datasets.py`, `office.py` | `file` (drive + path; Organization Files' `ListOrgFiles`, `GetOrgFile`, and admin-level `PutOrgFile`, `DeleteOrgFile` on `<org>/nexus:file/organization/<path>`), `my_file`, `user_storage`, `root_storage`, `platform_file` (Platform Files: `ListPlatformFiles`, `GetPlatformFile`, `PutPlatformFile`, `DeletePlatformFile`) and `system_file` (System Files: `ListObjectStoreFiles`, `GetObjectStoreFile`, `PutObjectStoreFile`, `DeleteObjectStoreFile`), both platform-level and `policy_only`; `dataset`; `project` (slides, documents, sheets) |
| `knowledge.py`, `search.py` | `view`, `graph_cache`, `ontology`, `icon`, `layout`, `layer`, `feed_layer`, `basemap`, `maps_catalog`, `maps_access`; `search`, `topic`, `search_scope` |
| `code.py`, `settings.py`, `platform.py`, `realtime.py` | `code`, `code_settings`; `secret`, `provider_model`, `abi_server`; `analytics` (deprecated, see below), `analytics_conversation` (`policy_only`), `system`; `presence`, `speech`. Analytics are read in a scope: `ReadOrganizationAnalytics` on the organization, `ReadWorkspaceAnalytics` on the workspace (both `admin`), a conversation's messages `ReadAnalyticsConversation` in its workspace, which no role holds (`docs/adr/20261119_analytics_scoped_rollups.md`) |
| `users.py` | `user` (platform: the platform's accounts, Platform Settings › Users, `services/accounts`): `ListUsers`, `InviteUser`, `UpdateUser`, `SuspendUser`, `ResumeUser`, `DeleteUser`; no role reaches it, the platform admin holds it |
| `drives.py` | `drive` (platform: the storage backends, Platform Settings › Drives, `services/drives`): `ListDrives`; no role reaches it, the platform admin holds it |

The kernel services have catalogs of their own (core's `iam_catalog.py` of each service); a route that
only forwards to the kernel declares the kernel action. Choices that differ from "viewers read, members
write, admins administer" and are deliberate: the organization's directory, domains and billing are
`admin` (not `list`/`read`), as are Organization Files' writes (`PutOrgFile`, `DeleteOrgFile`: members read it, a policy lets them write a folder), layout edits, ontology cache refreshes, `GetResourceAccess` and topic
edits (`UpdateTopic`, `DeleteTopic`, `PreviewTopic`); Platform Files and System Files are no role's at all
(platform-level, `policy_only`: a policy grants Platform Files, the platform admin holds both); `SyncAgents` is `write`
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
  the `feature`, `platform_file` and `system_file` types are `policy_only`, `DeleteWorkspace` and `DeleteOrganization` are `owner_only` (and owner is no longer assigned: the platform admin's), and the
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
  choosing for each role the most specific key as the older IAM did (`key_for`). An install from before IAM held
  any role (`iam_roles_v1` recorded with `before_iam`) stored none: its Nexus computed them from the configuration
  on each request, so that is what it had in force, and the keys come from it (`configured_features`: the same
  settings and overlay table, within `enabled_features`; read with the configuration the start runs with). Then:
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
- **The workspace's system-file actions stay declared** (catalog 12). `ListSystemFiles`, `GetSystemFile`,
  `PutSystemFile` and `DeleteSystemFile` (admin level, on `<workspace>/nexus:file/system/...`) decided System
  Files in a workspace; System Files is `system_file` at the platform now. No route asks for them, so they
  authorize nothing, and they stay for the same reason (their description says "Deprecated").
- **The platform analytics actions stay declared** (catalog 15). `ReadAnalytics` and `WriteAnalytics` (on the
  platform singleton `analytics`) decided the platform-wide analytics app; it is removed with its routes (#1536),
  and the analytics are read in Organization and Workspace settings. No route asks for them, so they authorize
  nothing, and they stay for the same reason (their description says "Deprecated"). The tracker's
  `POST /api/analytics/events` is any signed-in user's; a like or dislike in the chat is `UpdateConversation` on
  the owner's conversation (`PATCH /api/chat/conversations/{id}/messages/{id}/feedback`).

## Access policies and default groups

Every organization and every workspace has its own access policy and two groups (`container_defaults.py`), the
policy tree of issue #1413's journeys, the groups of #1585 ("Levels as groups"):

| What | Owner | Parent | Made with | Held |
|---|---|---|---|---|
| "<O> access" | the platform | none | allows nothing (`Nothing`, an Allow no name matches) | by "<O> admins", below the organization (`<O>/*`) |
| "<W> access" | the workspace | "<O> access"; none for a workspace in no organization | its offer (`workspace_offer`) | by "<W> workspace" at W: **W's bound** (core "Bounds"), not a grant |
| "<W> workspace" | W, a membership group of W | | its people | "<W> access" at W (the bound) |
| "<W> admins" | W, a membership group of W | | its admins | `builtin.admin` and "Workspace admin access" at `${my workspaces}` (W alone: its owner) |
| "<O> people" | O, a membership group of O | | the organization's people (its admins, and whoever holds a role at O) | "Organization view" at `${my workspaces}` and at O (O's bound): they see O, nothing it holds; `organization` is `no_membership_roles`, so no level's built-in role reaches O (ADR decision 12, `org_people_view_v1`) |
| "<O> admins" | O | | its admins | "<O> access" below O, `builtin.admin` at O and below it |

A container recorded before #1585 has "<X> members" (every user holding a role at X itself) in place of its
membership group, and its "<X> admins" holds the access policy: its groups follow its roles (below) until the access
move (#1587, "The access move") converts it.

- **"<O> access" is what an organization may use**: the platform admin widens it (agents of chosen modules, apps,
  features). Its admins and owners hold it in every workspace of the organization and derive from it. A widening is
  held where it applies (core's "Where a policy is held"): at the platform and below O, where it is attached, never in
  every container. An agent another organization's workspace turned off (the upgrade's `TurnedOffAgents` Deny, held
  by whoever holds its access or a policy below it) never stops granting it to O; one turned off in a workspace of O
  stops whoever holds that Deny.
- **"<W> access" is what a workspace makes available to its people**, within its organization's. Whoever holds more
  widens it (an org admin, or a workspace owner given more from above); its owners and admins narrow it to hide an
  agent, an app or a feature from everyone below it at once. The policies made in the workspace for its people
  ("Alpha analysts", "Alpha minimal") are sub-policies of it, so narrowing it narrows each of them at the next
  decision. Its admins edit it with the builder within "<O> access" (core's `grantable` answers the editor of a
  sub-policy), and every change is checked as any: they give only what they hold. A workspace in no organization has
  no organization's to be within: its access has no parent and allows nothing until the platform admin widens it.
- **The names follow the container's.** Renaming an organization or a workspace renames its access policy (name and
  description) and its two groups (`ContainerDefaults.renamed`, `align_names`, IAM's `update_group`), and every start
  repairs what an older rename left (`align_all`, in `migrate`). Only what the system made is renamed: a name equal to
  the one made from the previous name, or from a label the access policy's description, as made, still carries (each
  `{label}` of its template is read back); a name a person chose, or a description they rewrote, stays.
- **Who sees a hidden item.** Each person uses what their own policies give them, whatever their role. Hiding an item
  in "<W> access" takes it from whoever holds it through "<W> access" or below it ("<W> admins", member policies).
  Whoever holds it from above keeps it: the org's admins and owners (through "<O> access" below the organization), a
  workspace owner an org admin gave "<O> access" at the workspace, the platform admin. That is also who may show it
  again: someone who holds an item may give it back to the workspace; someone who lost it with it may not.
- **Before #1585, the groups followed the roles** held at the container itself (a grouped container's are the
  memberships themselves, `sync_scope` leaves them) (an org-wide mirror below an organization is not
  "at" its workspaces): `MEMBERSHIPS._notify` calls `ContainerDefaults.sync_scope` after every grant, seed, revoke and
  claimed invitation (`invites/runtime.py` names the organization too), which makes the groups' members the role
  holders (a member added by hand is removed). The joins and leaves are written as `api` for no user, after the role
  change they follow was authorized, as the org-wide mirror is (core's "Writes made for no user"). A group every
  member joins carries no grant meant for some: the ceiling is the access policy, never a group.
- **The record.** IAM holds the policies and groups; `container_defaults` (container name → access policy, members
  group, admins group) says which they are, written in the creating request's transaction. A role changed in another
  process's container is followed by reading the table (`session_factory`, set at start; a container with no record
  is not asked again for a minute, `MISS_SECONDS`). The groups follow `MEMBERSHIPS.members(scope)`.
- **Nothing left behind, nothing made twice.** `make_org` / `make_workspace` find before they make: the groups by
  name among those the container owns, an access policy an earlier attempt made and never recorded by owner, name and
  description. What one attempt made is taken back when a later step fails, and what could not be recorded
  (`store.put`) too, so no orphan "<O> access" stays at the platform. A start that stopped between IAM's writes and its
  record finds them again.
- **Made at start too, after the moves.** `migrate` runs after the moves (`_prepare_iam`) and again after the
  configuration seeds (`_container_defaults_after_seeds`), both under the moves' lock (`container_names.moves_lock`,
  so two API processes never make the same container's), and does nothing while `policy_tree_v1` or
  `container_names_v1` is not recorded: the sets' move makes the access policies it adopts. A route creating an
  organization or a workspace while a move is pending makes none either (`moves_pending`); the start after the moves
  gives it its own. An organization or workspace with no record gets its own (a seed's, an import's); one with a
  record is never touched.
- **Unique to its container.** An organization's access policy names the organization's id in its description, so
  one made and never recorded is found again for that organization only: two organizations of the same name never share
  one (a workspace's is found by its owner, the workspace).
- **Names.** The access policy and the groups keep the name the organization or workspace had when they were made:
  renaming it renames neither (IAM groups have no rename; a policy may be renamed by hand).

## Levels as groups (#1585)

ADR `docs/adr/20261120_access_levels_and_groups.md`. **Where** someone works is a membership group, **what** they do
there is a level. Nothing is attached to a person.

| Level | Groups | What they hold |
|---|---|---|
| Viewer | "Viewers" (level, platform) + "<W> workspace" | `builtin.viewer` and "Viewer access" (features apps, datasets; `module:OpenApp`) at `${my workspaces}`; "Models · embeddings" |
| Member | "Members" (level, platform) + "<W> workspace" | `builtin.member` and "Member access" (features apps, chat, files, datasets, graph, maps, ontology, search; `UseAgent`, `OpenApp`) at `${my workspaces}`; "Models · member", "Models · embeddings" |
| Workspace admin | Member + "<W> admins" | `builtin.admin` and "Workspace admin access" (every feature; agents, apps, workflows, pipelines) at `${my workspaces}`, W alone; "Workspace admins" (platform): "Models · all" |
| Org admin | "<O> admins" (+ "<O> people") | "<O> access" below O, `builtin.admin` at O and below it; "Workspace admins" |
| Platform admin | "Platform admins" (platform) | `builtin.platform_admin`; `set_platform_admin` (`users.is_superadmin`) |

- **A level is a pair** (`levels.py`): the built-in role (the catalog's actions by level, regenerated by IAM, with the
  platform companion IAM derives through `${my workspaces}`) and the generic level policy (features and module scopes
  by type, `${scope}/module:agent/*`, never an instance). Written once, the platform's, kept as written at each start.
  The features of "Viewer access" and "Member access" are the deployment's when it sets
  `nexus_config.feature_flags.level_features` (`viewer`, `member`; a level left out keeps the default above), else the
  defaults: the policy (and its description) is rewritten in place at the next start, found by name and the start of
  its description (`levels.level_features`, `_policy`).
- **Bounded by the workspace's offer.** "<W> workspace" holds "<W> access" at W: core makes it W's bound, so a level
  policy (and any customer policy at `${my workspaces}`, "Workflow runners" included) gives at W only what W offers;
  built-in roles are not bounded (they hold no module scope or feature). A Viewer uses W's apps, a Member its agents
  and apps, a workspace admin its workflows and pipelines too, each only the features both their level and W's offer
  name. An org admin uses "<O> access" in every workspace of O (the organization's offer, not W's).
- **The role-based API is mapped** (`Memberships.grant`; S6 #1589 rewrites the people contract): viewer or member at
  W → the level group plus "<W> workspace", not "<W> admins"; admin or owner (no longer assigned) → "Members" plus
  "<W> workspace" plus "<W> admins"; at O: viewer or member → "<O> people" and the level, admin or owner → "<O>
  people" and "<O> admins" (level unchanged). A level is one choice: giving one anywhere changes it everywhere. The
  roles of before held at the scope (and their mirror below O) are detached; nothing else of before is converted
  (#1587). `revoke` leaves the container's groups and keeps the level.
- **Seats** (#1589, the people contract): `Seat(container, kind, group_id)` names one group, `MEMBERSHIP` ("<W>
  workspace", "<O> people"), `ADMINS` ("<W> admins", "<O> admins") or `CAPABILITY` (a group of
  `capability_groups(org)`: the organization's or the platform's, none of the model's own). `check_seats` (as the
  caller, changing nothing), `take_seat`, `leave_seat`, `check_leaving`, `held_seats`, `set_level`, `clear_level`
  and `access_of` (what Platform › Users shows) are what `services/people` uses; in a container recorded before
  #1585 a seat is the role it stands for. Every join and leave made for someone is a `GroupChange` handed to
  `audit_sinks` (the app logs it). `seed_capabilities` joins the configuration's (`core/users_import`).
- **Who may.** Checked as the caller first (`_require_plan`: `iam:AddGroupMember` / `iam:RemoveGroupMember` on each
  group as its container names it; a level group on its platform name or as named in the container, IAM's level rule;
  `iam:DetachPolicy` on each role of before), then written as `api` for no user: the membership group first (the
  person's first tie to an organization is Nexus's to make: core "The first tie"), then the level, then what is left.
  A level change is logged with who asked. The last Org Admin stays: `LastOrgAdminError` (409).
- **Reads** (`roles_of`, `members`, `org_directory`, `effective_roles`, `/access`) count a role attached to the person
  or to one of their groups, at a scope or at `${my workspaces}` (their membership containers within the group's
  owner). `Member.level` and `DirectoryEntry.level` give Workspace · Level (the member lists' `level`). A read never
  makes the level groups (`LEVELS.peek`).
- **Workspace creation** takes `admin_id` (default the creator; in an organization, someone of its directory, else
  400), who joins "<W> admins" and "<W> workspace"; the defaults are made before the grant.
- **Shared graphs** are the Graphs part of W's offer (`given_graphs.py`): IAM gives them to W's people while they
  belong there; nothing is kept in step with the groups. So are the **Maps items** W does not own (`given_maps.py`).

### The upgrade (`container_defaults_v1`)

At the first start of this version, every organization and workspace gets its access policy and groups, nobody
gaining or losing access (`container_defaults_test.py`: every decision of `policy_tree_test`'s world, after the sets'
and the names' moves, is the same before and after, and again changes nothing):

- **Kept.** The "<O> access" and "<W> access" the sets' move made (`policy_tree`, found by their description) are
  kept. A description only names a candidate: an "<O> access" is the platform's, and a "<W> access" is owned by the
  workspace's own organization (the platform for one in none, or the workspace once moved); of two, the older is
  kept. The IAM admin routes refuse a description ending as the move's do (`policy_tree.MADE`). Each "<W> access" moves from its organization to the workspace with what is below it that its organization
  owned ("<W> modules (admins and owners)", the splits of customer policies), through core's `move_policies`; a tree
  that cannot move (an attachment beyond the workspace) stays its organization's and is named in the report.
- **Not attached.** Neither the kept "<O> access" nor "<W> access" is attached to the admins group: it holds the
  features the move kept from roles, so attaching it would widen. The report's notes say so; an administrator
  attaches it to let admins and owners use it and derive from it. The admins and owners keep what the move gave them
  ("<W> modules (admins and owners)", "Features of <role>").
- **Made.** An organization or workspace made after the sets' move (none of these) gets new ones, which allow nothing,
  so attaching them changes nothing.
- **Groups.** Made for every one, their members the role holders.
- **Recorded** in `iam_migrations` once nothing failed; a failure (logged, named in the report's `failed`) is tried
  again at the next start, the rest kept.

## Ceilings as allow-lists, model sets, capability groups (#1586)

- **"<W> access" is an allow-list** (`workspace_offer.py`): sections by `sid` (`OfferAgents`,
  `OfferApps`, `OfferWorkflows`, `OfferPipelines`, `OfferFeatures`) name each agent, app, workflow,
  pipeline (by name, or `<module>/*` for a shared module offered whole) and feature W offers; nothing
  else, no `module:agent/*` and no Deny list. A module added to the platform is offered nowhere until
  added. A new workspace in an organization offers its seed (`catalog_seed` or the configuration's
  `agents`, `apps`, `modules`, its default agent) and every enabled feature, bounded by "<O> access" (its
  parent); one in no organization offers nothing until widened. At each start a configured workspace's
  seed (the configuration's own entries only) is added to its "<W> access" (instances only: features
  are its Features setting's) and to its organization's (`apply_seeded_offers`, never removes; a ceiling
  of an older version, not in offer form, is left to the access migration, S4).
- **Workspace › Features and the offer** (`services/feature_access`) edit "<W> access" as the caller
  (`iam:UpdatePolicy`): Everyone is the feature offered, Nobody not; Only… is refused. Agents, apps,
  workflows and pipelines: `GET/PUT /api/workspaces/{id}/offer`.
- **Model sets** (`model_sets.py`): no level reaches a model through `builtin.platform.*` any more.
  "Models · member" (`nexus_config.models.member_set`, empty by default), "Models · all" (`model/*`),
  "Models · embeddings" (`Embed` on `model/*`, `Resolve` on the embedding models) are platform policies,
  attached by the level groups (S2, `level_model_policy_ids`). **An agent's own model is always
  allowed**: a module agent's in-process turn lends the models of its agents to whoever may use them
  (`provider_runtime.agents_own_models`, core `model_registry/agent_models.py`).
- **Capability groups** (`capabilities.py`), made on demand: "Workflow runners", the organization's,
  holding a policy (a sub-policy of "<O> access") running every workflow and pipeline, attached at
  `${my workspaces}` (the workspaces of the organization its member belongs to, through their "<W>
  workspace" membership groups); "Models · all", the platform's (a group an organization
  owns is attached only at a scope there, which never reaches a platform model). The Access pages make
  them on demand through `GET`/`POST /api/iam/admin/capabilities` (`../iam_admin/AGENTS.md`).
- **`builtin.self`** (catalog 16): no `CreateOrganization`, no personal `CreateWorkspace`;
  `nexus_config.personal_workspaces: true` gives the latter back (`bootstrap.apply_access_settings`).

## The access move (`access_model_v1`, #1587)

`access_model.migrate_access`, at start in `_prepare_iam`, after `container_defaults.migrate` and under the moves'
lock; it waits for `container_defaults_v1`. Built from what IAM holds now with S2's builders (`group_attachments`,
`levels.LEVELS`, the records), never through the people service:

| Held directly (or through a container's groups) | Groups after |
|---|---|
| `builtin.platform_admin` | "Platform admins", and no other attachment of their own |
| owner or admin at O (or below O) | "<O> people", "<O> admins", "Workspace admins" |
| owner or admin at W | "Members", "<W> workspace", "<W> admins", "Workspace admins" |
| member / viewer at W | "Members" / "Viewers", "<W> workspace" |
| member or viewer at O, no workspace of O, or invited to O (`invitations`) | "<O> people", that level |
| member or viewer at O, a workspace of O, never invited to O | nothing at O: the org Member role goes |

- **A level is global**: the highest held anywhere (a viewer here and a member there is a Member), reported.
- **Records** of before #1585 are converted (`convert_record`): their membership group found by name or made, the
  "<W> admins" a membership group of W, `group_attachments` with the access policy (W's bound), the access policy no
  longer held by "<W> admins" at W; the emptied "<X> members" is deleted.
- **Ceilings to offers** (`ceiling_offer`, `convert_ceiling`): what "<W> access" allowed (a wildcard of every module
  expanded over the deployment's items, `engine_universe` and what policies name) minus what it denied, checked with
  `in_offer_form`. A statement of no offer section that only names a module's declared actions is dropped, listed;
  any other shape stops the move. The features each "Features of <role>" gave at W become W's offer features, those
  given at O (or org-wide) and at O's workspaces "<O> access"'s (its Allows bound its workspaces' offers).
- **Detached**: the built-in roles at organizations and workspaces, "Features of <role>" (and the sets' move's copies
  of an org-wide one, "What <id>, attached at <scope>, granted in <place>", one per workspace for each holder: what
  they gave was the holder's, so they add nothing to W's offer), "<W> modules (...)", every attachment of a platform
  admin. Kept and listed: a customer policy attached to one person, Nexus's per-person
  Denies ("Agents turned off in <W>"); core's companions (`builtin.platform.*`) follow the roles. Shared graph grants
  stay per person and are re-synced: read for W's people, write for its admins.
- **Retired** once nothing holds them: "Features of <role>", "<W> modules (...)", "Feature · <X>", the old groups.
  One a group or an invitation still holds stays, listed (`kept_policies`).
- **No admin**: `nexus_config.migration.default_workspace_admin` (an email Nexus knows) joins "<W> admins" and "<W>
  workspace" of each workspace left with none (and "Members"); unset or unknown, they are listed (`no_admin`).
- **The report** (`Report`, logged and kept as the `iam_migrations` row's `report`) is IAM's own decisions: the plan
  is applied to a copy (`shadow_iam`) first, every person's decisions (Nexus's actions, features, module items,
  declared actions, shared graphs, models) compared, each change a `Change` with a reason (`REASONS`, intended ones
  flagged: members lose workflows and pipelines, members gain datasets, model sets, owners lose delete, org Member
  roles go). Also: empty workspaces, workspaces with no admin, org-only people, retired and kept policies, the drive
  flags (`files_offer.convert_legacy_drive_flags`: into each workspace's offer once its access policy is
  recorded; it drops its holding table; a dry run asks it with `apply=False` on the copy).
- **Safety.** A shape it does not know, or a plan the copy refuses (`AccessModelStop`), stops it: nothing written,
  nothing recorded. Before the real IAM changes, the move is kept (`access_model_v1_planned`: its plan's report, its
  inputs and IAM as it was, `shadow_iam.snapshot`); a start interrupted half way is finished by the next, which
  reports the whole move. Every step is idempotent; a forced second run changes nothing.
- **The start does not wait for the comparison.** `migrate_access` tries the plan on the copy, keeps the move, makes
  it and records it with `decisions` "pending" (who joined which group, what was detached, retired and offered). The
  API then serves, and `main._complete_access_report` runs `complete_report` in the background (one API process,
  `container_names.lock_if_free`): every person's decisions compared from the kept copy, before and after, then the
  real IAM's against the copy's (`unverified`; a change made since the move shows there too), `decisions`
  "compared", the copy dropped. A restart before it ends compares again. On about 150 people in 115 workspaces the
  start takes minutes and the comparison most of an hour.
- **Dry run**: `abi iam migrate-access --dry-run [--json]` (the project's IAM, read from its store; the project's
  `nexus_config`) compares at once, prints the report and writes nothing: levels IAM has not made yet are made in
  the copy. Tests: `access_model_test.py` (decision matrices on `policy_tree_test`'s world and on
  `role_features_test`'s taken back to before #1585), `shadow_iam_test.py`.

## Files given by the workspace's offer (ADR `20261125_offer_gives_outside_resources`)

- **Given sections** of "<W> access" (`given_files.py`, read and written by `workspace_offer`): `GivenOrgFiles`
  (off, read, write; the workspace's organization's `nexus:*OrgFile*` on `<O>/nexus:file/organization` and `/*`, and
  `object_storage` on `<O>/object_storage:object/naas_abi/organization-drive/<o>` and `/*`), `GivenPlatformFiles`
  (off, read, write; `nexus:*PlatformFile*` on `abi:nexus:platform_file/*`, `object_storage` on
  `abi:object_storage:object/naas_abi/platform-drive` and `/*`), `GivenSystemFiles` (off, read;
  `ListObjectStoreFiles`, `GetObjectStoreFile` on `abi:nexus:system_file/*`, `object_storage` read on
  `abi:object_storage:object/*` and `abi:*/object_storage:object/*`). Each is its Nexus half and its object storage
  half (`<sid>2`); read lists and reads, write also puts and deletes. Core IAM gives them to W's people while they
  belong to W, each action within their level there (core "Given statements"): a Viewer reads, a Member writes.
- **Who changes them:** a write of "<W> access" as the caller (`feature_access.FeatureAccessService.set_files`,
  `PUT /api/workspaces/{id}/offer/files`, and `platform_files_routes.py`), held-checked by IAM: the platform admin
  gives Platform and System Files, an organization's admins its Organization Files; a workspace admin narrows or
  removes. `read_offer` says per row the mode, the `choices` the caller has (held, per `grantable` at the platform,
  or narrower than now) and `editable`.
- **My Files** is no section: `feature_flags.viewer_my_files` (default true); off, "Viewer access" denies
  `ListMyFiles`, `GetMyFile`, `ListUserStorage`, `GetUserStorage` (`levels.no_my_files_statement`).
- **The move** `files_offer_v1` (`files_offer.py`, `main._offer_moves`): each "Platform Files · <W> (<id>)" group of
  #1590 becomes `GivenPlatformFiles` in its mode, then the groups and the two policies "Platform Files · read|write"
  are deleted (a policy someone else holds is kept and named). **The legacy flags:**
  `files_offer.convert_legacy_drive_flags(iam, db) -> list[DriveFlagChange]` (`workspace_id`, `flag`
  `"platform"|"system"`, `action` `"converted"|"reported"|"none"`, `detail`) reads `workspace_drive_flags_legacy`,
  gives `GivenPlatformFiles` write for each `platform_drive_enabled`, reports `system_drive_enabled`, then drops the
  table; idempotent; `apply=False` is a dry run.

## Graphs given by the workspace's offer (ADR `20261125_offer_gives_outside_resources`)

- **Sections** of "<W> access" (`given_graphs.py`, read and written by `workspace_offer`, fields `graphs_read`,
  `graphs_write`, `graphs_all`, `graphs_no_create`, `graphs_closed`): `GivenGraphs` (parts `GivenGraphs2`...: the
  `triple_store` actions at the list and read levels on each graph W reads or writes), `GivenGraphsWrite` (parts too:
  `Insert`, `Remove` on each graph it writes), `GivenGraphsAll` (read, `read_all`: `<O>/triple_store:graph/*`,
  `<O>/*/triple_store:graph/*`, W's own for a workspace in none, and the schema graph), and W's only Denies,
  `OfferGraphsDeny` (`CreateGraph` on `${scope}/triple_store:graph/*`: creation closed) and `OfferGraphsDeny2`...
  (every graph action on `${scope}/triple_store:graph/<iri>` of each own graph it excludes, and the name of
  `given_graphs.NEW_GRAPH`, which says it excludes them). Never `ClearGraph` nor `DropGraph`; Nexus's own graphs
  never. Capped per person: a Viewer reads, a Member and an admin write.
- **Names.** Settings › Graphs names a graph it adds as IAM placed it (`graph_iam.graph_name`), which the caller must
  hold (core's held check, unscoped); the migration and a configuration name it wherever placed
  (`given_graphs.anywhere_names`). The graphs that stay keep their names (`fields_of(current=)`), so a workspace
  admin removes one without holding the others.
- **Who changes them:** Settings › Graphs (`resource_access.py`, kind `graphs`) through
  `FeatureAccessService.set_graphs`, as the caller and audited. `read_all` turned on also needs `ManageSystem`.
  A Deny of W's bound restricts W's own admins (core: only whom it does not restrict lifts it): reopening creation or
  W's own graphs is an organization admin's or the platform admin's. `read_offer` says `graphs`
  (`given_graphs.summary`), which the offer editor shows.
- **The move** `graphs_offer_v1` (`graphs_offer.py`, `main._offer_moves` after `files_offer`): each workspace's
  effective assignment (`load_resource_policy`: its row, else its configuration's) becomes its sections, then the
  policies are detached from everyone and deleted. A workspace with something to move and no access policy waits
  (its policies kept, not recorded). Reported: `written`, `kept`, `waiting`, `policies_deleted`,
  `attachments_deleted`, `widened` (a policy of theirs passed `MAX_PATTERNS` names, never written: given for the
  first time), `failed`. A configured workspace made later gets its graphs with its access policy
  (`container_defaults.migrate`, `configured_graphs`); its organization's offer never takes them.

## Maps given by the workspace's offer (ADR `20261125_offer_gives_outside_resources`, "Maps")

- **Sections** of "<W> access" (`given_maps.py`, read and written by `workspace_offer`, fields `maps` and
  `maps_closed`): `GivenMaps` (parts `GivenMaps2`...: `ListLayouts`, `GetLayout`) and `GivenBasemaps` (`ListBasemaps`,
  `GetBasemap`) on absolute names: the deployment's feeds or basemaps, `abi:nexus:<kind>/*` (every one, the ones
  added later too) or `abi:nexus:<kind>/<id>`, and an item another workspace V shares with W, `<V>/nexus:<kind>/<id>`;
  and W's Denies `OfferMapsDeny`, `OfferBasemapsDeny` (the same actions on `${scope}/nexus:<kind>/<id>`: a deployment
  item W does not use though every one is given). List and read only: W administers its own copies through its
  roles. A feed's layers follow their feed; built-in feeds and graph layers are never in it. Hiding an item stays
  W's display choice (`maps_settings.hidden_*`), not the offer's.
- **Read by Nexus** as W's `MapsAssignment` (`given_maps.assignment_of`, `maps/permissions` `IamMapsOffers` through
  `AUTHZ.offer_of`): which deployment items W seeds and lists, which shared items it lists. A workspace whose access
  policy is no allow-list yet (`offer_of` None) still goes by `maps_grants`.
- **Who changes them:** Settings › Maps › Access (`/api/maps/permissions`, item by item) writes the offer of each
  workspace whose answer changes, through `FeatureAccessService.set_maps`, as the caller and audited. Its rules
  first (a deployment item and "every workspace" are the platform admin's, a workspace's item is shared from it to
  workspaces the caller administers), then IAM's: only the platform admin gives a deployment item, an item of V is
  given by whoever holds it in V, a workspace admin closes a deployment item and never reopens it. A change a
  workspace with no allow-list would need is refused (409) before anything is written; the writes are one per
  workspace. `read_offer` says `maps` (`given_maps.summary`), which the offer editor shows.
- **New workspaces** are given every deployment feed and basemap (`container_defaults.platform_maps`, in
  `new_workspace_offer` and for a configured workspace made by `migrate`); their organization's offer never takes it.
- **The move** `maps_offer_v1` (`maps_offer.py`, `main._offer_moves` after `graphs_offer`): each workspace gets every
  deployment item, each one a `maps_grants` row narrowed away from it closed, and each item another workspace
  shared with it (by list or with every workspace) by its name there. Its other sections are kept; idempotent.
  A workspace with no access policy waits (not recorded). Reported: `written`, `kept`, `waiting`, `closed`,
  `shared_with_all` (given to each workspace now, not to one made later), `dropped` (shared by a workspace that is
  gone), `failed`. `maps_grants` stays for the workspaces that are no allow-list yet; one written into a ceiling of
  an older version is kept when the access migration converts it (`access_model.ceiling_offer`).

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
  is set aside, never guessed (a Deny under a wrong name refuses nothing once its module loads): the report keeps
  it in `deferred_agents`, and `policy_tree.deny_deferred_agents`, at every start after `container_defaults`,
  denies it in W's access policy (sid `TurnedOffAgentsLoadedLater`, under the roster's scope) once the engine
  loads its class, then takes it off the list. Until then nobody uses it: the engine serves no agent it did not
  load. A workspace with no access policy yet waits for the next start; a deleted one is forgotten.
- **Agents a workspace built** (no module) and had turned off: "Agents turned off in <W>", W-owned, a Deny of
  `nexus:UseAgent` on each, attached at W to whoever held a role there (directly, through a group, org-wide,
  invited). The roster lists a built agent only to who may use it (`agents/.../_visible_to_caller`).
- **Roles.** Who held `builtin.admin` or `builtin.owner` (at W, org-wide, at `abi:O:-`; a group like a person; a
  pending invitation as a pending grant listed on its Nexus invitation, an org owner's or admin's for every
  workspace, as the org-wide mirror will) gets, at each place the role reached, "<W> modules (admins and owners)":
  a sub-policy of that place's access granting every module scope. Not the access policy itself: it bounds
  features too, and no role brought a feature. An install from before IAM held any role (`iam_roles_v1` recorded
  with `before_iam`) had no module scope and no set: everyone holding a role in a workspace used what it had turned
  on. There every role's holders get it, members and viewers in the workspaces they held a role in (not at the
  organization's own level), as "<W> modules (its people)" (`World.module_roles`).
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
  An attachment or a pending grant held in both grammars (the new one written while the move waited) is merged
  into the twin made first, which keeps its id, date and author (`attachments_merged`, `pending_grants_merged`
  in the report): the store's unique keys never stop the move. Each invitation that listed a dropped grant lists
  the one kept (`remap_invitation_grants`, in the commit that records the move, `invitations_remapped`), so
  revoking either invitation keeps the other's grant. The merge map lives only in the start that rewrote the
  names: when that commit fails (logged, not recorded) or the process stops before it, the next start's rewrite
  merges nothing, so a pending invitation listing a grant IAM no longer holds is given the grant IAM holds for
  its person and one of its own roles or policies. An invitation whose `grant_ids` cannot be read is logged and
  left as it is.
- While the move waits (a move before it stopped), the configuration's seeds, which run after the moves at
  every start, attach the roles they declare in the old grammar (`org_seed._apply_declared_roles`, under the
  moves' lock, read again under it); the move rewrites them. Each organization role they apply holds the
  org-wide role it carries (`abi:<org>:*`, an owner's or admin's) and no other, as `Memberships.mirror_org_wide`
  does in the grammar of today, so a configured demotion takes the former one away (`mirror_old_org_wide`, its
  failure logged apart from the roles). Once it is recorded they take no lock. No `iam_migrations` table (a
  fresh install) or a record that cannot be read (logged) means the grammar of today. A declaration naming no
  organization or workspace is logged and skipped.
- Until it is recorded, module scopes and features are refused (`authz.upgrading`); IAM itself narrows, never
  widens (old names match nothing new). Start-up order (`main._prepare_iam`): the catalog, the moves that write
  the old grammar (feature overrides, role features, sets), this move, then `migrate_role_data` and
  `sync_org_wide_roles` in the new grammar (`container_names.before_names`). The moves before it read the
  roles IAM holds, so first an organization owner's or admin's missing org-wide mirror is made in the old
  grammar (`mirror_old_org_wide`). While Nexus still keeps memberships IAM does not hold (the move of the role
  data, `iam_roles_v1`, not recorded: an install from before IAM held any role, `role_data_pending`), those move
  first, in the old grammar (`bootstrap.migrate_role_data_before_names`: the memberships and `owner_id` fallbacks
  as role attachments at `abi:<org>:-` and `abi:<org>:<ws>`, an org owner's or admin's org-wide too, the
  superadmin flags as `builtin.platform_admin`, as `api` for no user, no container registered), recorded as
  `iam_roles_v1` with `before_iam`, so `migrate_role_data` finds it done. The moves then give that install's
  people what its login gave them: the role features its configuration computed (`role_features`) and, for every
  role in a workspace, what the workspace had turned on (`policy_tree`). If that move fails, nothing moves and
  nothing is recorded, an error says so, and every module scope and feature stays refused until a start moves it.
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
  (only `viewer` attachments): no model (a model set's, "Model sets" below), the apps, agents and modules it
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
- **Datasets are platform-wide, not a workspace's.** The engine's dataset service is global and nothing ties a
  namespace to a workspace, so the Nexus `dataset` type is platform-level (`abi:nexus:dataset/<ns>/<name>`, reached through the catalog's `PLATFORM_ACCESS`).
  The workspace a dataset request names carries the `datasets` feature and the caller's membership only (a
  stranger to it, or a View-as session of another workspace, is refused); it never scopes what is read. List,
  query, describe and preview agree on a namespace: `GET /datasets/` keeps what `ListDatasets` allows on
  `dataset/<ns>/<name>` and on `dataset/<ns>` (two batched `filter` calls, whatever the number of datasets);
  `QueryDataset` is checked on `dataset/<ns>` and on every dataset, and its namespace, that the SQL reads
  (`<other_ns>.<name>` included: `services/datasets/access.py`); describe and preview are guarded on
  `dataset/<ns>/<name>` and also require their action on `dataset/<ns>`. A Deny on `dataset/<ns>` therefore hides
  the namespace from all four. The Datasets agent's tools and the Sheets agent's dataset import make the same checks
  in the turn's workspace, and every query runs in the caller's call context, so the kernel decides it too.
- **Kernel resources need placements.** Nexus places what it creates and registers `placement_source`s for
  what exists, applied at every boot and when a workspace is created (`on_workspace_created`). Two
  platform-level exceptions are deployment grants (`iam.set_platform_grants`, stored in the platform policies so any process's regeneration keeps them): the shared repository that
  slides, documents, sheets and code use (viewers read, members write) and the kernel dataset namespaces the
  deployment shares (`shared_dataset_namespaces`, read for every role; none by default, names only, so the
  engine's own namespaces such as the event archive are never reached by a workspace role). Nexus's own `dataset` type is `PLATFORM_ACCESS` of its catalog, not a grant. The shared repository separates workspaces by Nexus's branch naming only; a per-workspace
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
- **Who makes accounts in the provider's directory.** An invitation IAM authorized: the route's
  `InviteOrganizationMember` / `InviteWorkspaceMember` at its scope, then its pending grants accepted on the inviting
  person's behalf. Nexus then makes the account as `api` (`identity:ProvisionUser` is `builtin.api`'s), so an
  organization admin or a workspace owner needs no right at the provider. Only platform admins create organizations
  (catalog 16), and what bounds invitations is the invite routes' rate limits and `invitation_mails_per_day`; the account's email stays unverified
  until a code mailed to the address proves it. The platform-level invite (no grant) keeps to the inviting user's own
  `identity:ProvisionUser`. See `services/invites/AGENTS.md`.
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
- **Ontologies are decided per ontology file.** *Decision:* a `nexus:ontology` is an ontology file, named by
  its path. Reading one (`GetOntology`, `ExportOntology`) is decided in the workspace, on
  `<workspace>/nexus:ontology/<path>`: every ontology route reads through `ontology_catalog_scope`, the
  workspace's enabled files narrowed to those the caller may get (`ontology/ontology_access.readable_paths`), so
  a Deny on one ontology takes it out of every list, the dictionary, the classes, the relationships and the
  overviews, and its path is not found there. Enabling one in a workspace (`AssignOntology`, admin level) is
  decided in the workspace's organization, on `<organization>/nexus:ontology/<path>` (the platform's for a
  workspace in none): Workspace settings › Ontologies offers only what the caller may assign plus what the
  workspace already enables, and its save refuses another, naming it. The policy page › Configuration of
  "<W> access" has an Ontologies section with the same data (`read_offer`'s `ontologies`: the offer's refs and a
  row per file of the deployment, `assignable`, `editable`, `reason`; a ref no file answers to is a row to
  remove), switched one at a time through `PUT /api/workspaces/{id}/offer/ontologies` (`{changes: {id:
  offered}}`, `FeatureAccessService.save_ontologies`, then `set_ontologies` as the caller): 403 for a file the
  caller may not assign, 422 for one of no file of the deployment. naas_abi lists ontologies for the
  builder (`listers.ontologies`): every file of the deployment at an organization or the platform, a
  workspace's enabled ones there. *Consequences:* an organization's admins and owners assign any ontology to
  its workspaces by their role there (an admin-level action in their container), and the platform admin
  everywhere; a workspace's admins assign only what a policy at the organization or the platform grants them
  (one at the workspace names the workspace's level, which the check does not read), where before they could
  enable any file of the deployment. What a workspace already enables stays, and its admins may still remove
  it.

- **Every organization and workspace has an access policy and default groups.** *Decision* (the owner, for issue
  #1413): "<O> access" (the platform's) and "<W> access" (the workspace's, a sub-policy of its organization's) are made
  with each, allowing nothing, and attached to "<X> admins"; "<X> members" and "<X> admins" follow the roles held
  there. Each person uses and gives only what their own policies hold: the admin role brings no use. *Consequences:*
  a new organization uses nothing until the platform admin widens its access, a new workspace until someone holding
  more widens its; hiding an item there takes it from everyone below "<W> access" at once, and whoever lost it with it
  cannot show it again (who holds it from above can). Member policies are sub-policies of "<W> access". The admins of
  a workspace made after the upgrade use what "<W> access" allows; those of an upgraded one keep what the move gave
  them until an administrator attaches it. #414 had left groups made with a workspace out of scope; the owner brought
  them in.
- **Levels as groups, bounded by the workspace's offer** (#1585). *Decision:* where is a membership group, what a level
  (a built-in role and a generic level policy held by a level group at `${my workspaces}`), and "<W> access" held
  by "<W> workspace" is W's bound (core's rule: a membership group's attachment at its own container). Owner is no
  longer assigned. *Consequences:* a person holds group memberships only; a level policy is written once and narrowed
  per workspace by its offer; workspace admins hold theirs at `${my workspaces}` from W's own group, so W alone; an
  org admin uses the organization's offer; members and viewers lose shared-graph writes in grouped workspaces;
  containers recorded before keep attachments until #1587.
- **The access move reports IAM's own decisions** (#1587). *Decision:* the move is applied to a copy of IAM first
  (`shadow_iam`) and its report is the diff of every person's decisions on the copy, classified by reason; the real
  IAM is changed only after the copy accepted the plan and IAM as it was was kept. The decisions are compared after
  the start, from that copy: comparing decides nothing and took most of an hour on a large deployment.
  "Features of <role>" choices become offer features (of the workspace, and of its organization, whose access bounds
  it). *Consequences:* a dry run writes nothing; an unexpected shape stops the move before any write; the start
  after an interrupted move finishes it with the whole report; a Viewer whose role's features went beyond the Viewer
  level's loses them (`viewer_features`, reported); a group holding a role (a customer group) keeps it.
- **Organization Files is decided at the organization.** *Decision* (#1511): `naas_abi/organization-drive/<org>`
  is the organization's: its object storage is placed in the organization's container (`Placement.organization`,
  `files/placement.py`), and the files API decides on `<org>/nexus:file/organization/<path>` with its own actions,
  reached through a workspace of the organization (its `files` feature; the organization read from IAM's container
  of the workspace). Reading is `list`/`read` (the organization's viewers and up), writing `admin` (its admins and
  owners). No workspace flag. *Consequences:* a role held only in one of the organization's workspaces reaches
  nothing of it; who writes which folder (members writing `operations/`) or who does not read one is a policy at
  the organization, not a code change; the kernel's object storage check follows the organization's roles, so a
  policy widening a write past a viewer's role also grants `object_storage:PutObject` there.
- **Every view of the file system is opened by IAM alone.** *Decision* (#1529, epic #1528): the workspace flags
  `platform_drive_enabled` and `system_drive_enabled` are gone (columns dropped, `0073_drop_drive_flags.sql`).
  Platform Files (`naas_abi/platform-drive`) is `platform_file`, platform-level and `policy_only`: no role holds it,
  owners included; a policy at the platform grants it, the platform admin holds it. System Files (the whole object
  storage) is `system_file`, likewise: the platform admin's alone, workspace admins lose it. Both are decided at the
  platform, whatever workspace the request names, with no feature. The kernel's platform companions no longer reach
  `object/naas_abi/platform-drive` (core's `roles.py`), so the object storage refuses it too until granted: a
  Platform Files grant names both halves, the Nexus actions on `abi:nexus:platform_file/*` (or a folder,
  `abi:nexus:platform_file/platform/<folder>/*`) and `object_storage:ListObjects`, `ListObjectsRecursive`,
  `GetObject`, `GetObjectMetadata`, `GetObjectStream` (and `PutObject`, `PutObjectStream`, `DeleteObject` to write)
  on `abi:object_storage:object/naas_abi/platform-drive` and `.../platform-drive/*`. `GET /api/files/views` lists the
  views a caller may open (My, Workspace, Organization, Platform, System Files), IAM's `List*` on each root.
  *Consequences:* on PostgreSQL the flags are kept and converted (#1590: `platform_drive_enabled` becomes the
  workspace's Platform Files, read and write; "Platform Files given with the workspace" above); on SQLite, or for a
  deployment that ran 0073 before #1590, whoever reached Platform Files through a flag loses it until a platform
  admin gives it again; the catalog is version 12; ADR
  `docs/adr/20261119_file_views_by_iam.md`.
- **An organization with workspaces is not deleted.** *Decision:* `DELETE /api/organizations/{org}` refuses (409) one
  that still has workspaces, naming them, rather than deleting them with it. The issue left it open (UJ-P1); this is
  the default until the owner says otherwise. *Consequences:* its admins delete its workspaces first
  (`DeleteOrganizationWorkspace`, #1585); the platform admin may too, and deletes the organization.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam -q --no-cov
```

`container_defaults_test.py`: an organization and a workspace made through the services get their access policies and
groups; the groups follow the roles (and a role changed in another process); the ceiling narrows a member policy at
once, and who lost an item cannot show it again; a workspace admin's builder within the organization's; an agent
another organization's workspace turned off still granted to a new organization, one turned off in its own refused; an
organization with a workspace is refused, then deleted with its access policy; the delete route by role; the upgrade
on `policy_tree_test`'s world, every decision the same.

Drive real routers with the `team` fixture (`ws-1` of `org-1`: `owner`, `admin`, `member`, `viewer`, `stranger`) and
fake services; never mock `authz`.
