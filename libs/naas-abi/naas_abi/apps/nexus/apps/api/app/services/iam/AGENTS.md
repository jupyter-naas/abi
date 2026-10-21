# Nexus authorization on IAM - AGENTS.md

## Purpose

Every Nexus authorization decision is a question to the engine's IAM service
([`libs/naas-abi-core/.../services/iam/AGENTS.md`](../../../../../../../../naas-abi-core/naas_abi_core/services/iam/AGENTS.md),
RFC `docs/specs/rfcs/20261013_identity-and-authorization.md` §6.5, §7, §13; ADR
`docs/adr/20261019_nexus-authorization-on-iam.md`). Nexus calls IAM as `api` acting on behalf of the signed-in
user, so both must be allowed. There is no role check outside IAM, no scope list and no second source of
memberships.

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
  workspace (`CreateOrganization`, which every user holds).
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

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam -q --no-cov
```

Drive real routers with the `team` fixture (`ws-1` of `org-1`: `owner`, `admin`, `member`, `viewer`, `stranger`) and
fake services; never mock `authz`.
