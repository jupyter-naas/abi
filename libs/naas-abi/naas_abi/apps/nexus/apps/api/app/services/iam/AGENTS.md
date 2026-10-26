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
| `authz.py` | `AUTHZ.require / allowed / decide / filter / name`: builds the resource name, checks `UseFeature` first, maps a refusal to `AuthzDenied` (an `HTTPException`: 403, or 404 for another user's personal resource) |
| `guards.py` | `guard(action, ...)`, a route dependency that decides before the body is read; `declares(action)` for routes that authorize inline. The matrix test reads both |
| `memberships.py` | `MEMBERSHIPS`: roles are `builtin.<role>` attachments at `abi:<org>:-` (org) and `abi:<org>:<ws>` (workspace); reads as `api`, changes as `api` on behalf of the caller |
| `names.py` | Scopes and resource names; `NO_ORG` (`_none`) is the org of a workspace that has none |
| `placements.py` | Which workspace owns the kernel resources Nexus keeps (`placement_source`, `place`, `place_existing`) |
| `bootstrap.py` | Startup: register the catalog, compute the feature policies, move the old membership rows into IAM once (`iam_migrations`) |
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
  computed by `bootstrap.feature_plan` from `feature_flags`, org overlays and workspace overrides). An action of a
  flagged section carries its `feature=` in the catalog; the API refuses it where the role lacks the feature.
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
  `place_existing`.
- **`-`, `*` and `_none` are not workspaces.** Never build a workspace scope or resource name from a path value
  without `Authz.org_of`/`name` (they refuse those ids): `abi:<org>:-` is the organization's own scope.
- **A change that widens what a workspace holds is checked beyond the catalog** (`read_all` is a platform
  administrator's, a graph read→write needs the right to drop it); strings that reach SPARQL are escaped.
- **Work as `api` for no user** only after the route authorized its caller, and only around the one call that needs it
  (`as_service_account("api")`). Never around user data.

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
| `chat.py`, `agents.py`, `apps.py` | `conversation`; `agent`, `skill`; `app`, `app_project`, `module` |
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
  catalogs by level (core's `roles.py`) and attached at a scope: `builtin.viewer` at `abi:<org>:<ws>` is the
  read-only policy on that workspace's resources. `builtin.platform_admin` (`*` on `*`, no scope, never
  over sealed resources) is `users.is_superadmin`. `builtin.self` is held by every user.
- **Features.** `UseFeature` is granted only by feature policies, `builtin.features.<role>`,
  `builtin.features.<org>.<role>` and `builtin.features.<org>.<workspace>.<role>`, which IAM attaches beside
  each workspace role and detaches with it. `bootstrap.feature_plan` computes them from
  `feature_flags.role_baseline`, `organization_overrides`, the org overlay stored in
  `organization_role_features` and the workspace overrides (`workspaces.feature_overrides`), restricted to
  `enabled_features`; a key is emitted only where it differs from the broader one. A feature outside
  `enabled_features` is reachable by no role, owner and admin included (only the platform admin's `*`).
  Defaults: `owner` and `admin` get every enabled feature; `member` and `viewer` get `maps`, `chat`,
  `files`, `datasets`, `skills`, `slides`, `documents` and `sheets`. An overlay or a workspace change
  recomputes the policies. The role's own statements leave out the `feature` type.
- **Platform-level types.** A workspace role never reaches a platform-level resource. IAM keeps two
  managed policies in step with attachments: `builtin.platform.member` (held while the principal has a
  `member`, `admin` or `owner` attachment at a workspace or org-wide scope) and `builtin.platform.viewer`
  (only `viewer` attachments): the platform's models (`model_registry`), the apps, agents and modules it
  may open or invoke (`discovery`), views, templates, its own runs, its own keys and so on. Org-level
  attachments (`abi:<org>:-`) bring neither: an org member who belongs to no workspace cannot chat with
  models or open apps. Because Nexus calls as `api` on behalf of the user, the user must hold these too.
  Which agents and apps a workspace may use stays a Nexus decision (`nexus:UseAgent`, `UseApp`,
  `UseFeature`, checked before the kernel call).

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
