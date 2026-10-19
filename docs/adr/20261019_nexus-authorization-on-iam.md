# Nexus authorizes through IAM

Status: Accepted

Date: 2026-10-19

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §6.5, §7 and §13.
Builds on: [`20261015_iam-transitional-bootstrap.md`](20261015_iam-transitional-bootstrap.md), [`20261015_data-services-enforce-iam.md`](20261015_data-services-enforce-iam.md), [`20261015_runtime-services-enforce-iam.md`](20261015_runtime-services-enforce-iam.md).
Related: [`20261019_graph-assignments-on-iam.md`](20261019_graph-assignments-on-iam.md).

## Context

Step 11. Before it:

- Nexus decided for itself: about 40 inline `role in ("owner", "admin")` checks in three routers,
  `require_workspace_access` (membership only) on about 170 routes, and a scope matcher whose callers built
  contexts with `scopes={"*"}`.
- Viewers were read-only in three places (sheets, graph, ontology). Documents, slides, chat, files, datasets,
  apps and code treated a viewer like a member.
- Feature flags only hid the UI.
- An org admin could grant or demote an owner, and a workspace admin could demote or remove the workspace owner
  (bug c). `POST /api/workspaces` took any `organization_id` (bug d).
- The kernel let every Nexus user through (`builtin.transitional.nexus_user`), `api` and `engine` held `*` on `*`.

## Decision

1. **One catalog, one question.** Nexus registers the `nexus` action catalog
   (`services/iam/catalog/`, one module per router family) with IAM at startup. A route declares its action once
   (`guard(...)` before the body is read, or `authz.require(...)` plus `declares(...)` where the workspace is in the
   body or the resource is named after loading it) and IAM decides as `api` on behalf of the signed-in user. The
   built-in roles are generated from the catalog by **level**: `list`/`read` for viewers, `write` for members, `admin`
   for admins, owners alone delete a workspace or an organization. A state change is never below `write`.
2. **Deviations from the RFC table**, each keeping what the code did before:
   the org directory, domains and billing are `admin` (#1346); layout edits, ontology cache refreshes, `GetResourceAccess`,
   topic edits and system-drive files are `admin`; `SyncAgents` is `write` (every client sends it once per session).
3. **Memberships are role attachments.** `builtin.<role>` at `abi:<org>:-` (organization) and `abi:<org>:<workspace>`;
   `users.is_superadmin` is `builtin.platform_admin`. `organization_members`, `workspace_members` and the `owner_id`
   fallbacks are read once into IAM at boot (`iam_migrations` marks it) and never read for a decision again; the
   configuration seeds grants. Changes run as `api` on behalf of the caller, so IAM enforces the owner rules whichever
   API is used (bug c): an admin cannot grant, demote or remove an owner, and the last owner stays.
4. **Bug (d).** Creating a workspace needs `CreateWorkspace` on its organization. A workspace with none (the signup and
   first-workspace flow) is the caller's own and needs `CreateOrganization`, which every user holds; its scope is the
   reserved org `_none`.
5. **Features at the API.** `UseFeature` comes from `builtin.features.<key>` policies IAM attaches beside each
   workspace role (`<role>`, `<org>.<role>`, `<org>.<workspace>.<role>`), computed from `feature_flags`, the stored org
   overlay and the workspace overrides, and recomputed when an overlay or a workspace changes. An action of a flagged
   section carries its feature in the catalog.
6. **No implicit access.**
   - `builtin.transitional.nexus_user` is removed, and IAM retires it (with its attachments) at boot.
   - `builtin.api` and `builtin.engine` are enumerated statements, one per service with a `sid` saying what needs it;
     `api` holds `nexus:*`, the kernel services it calls for its users (each user bounds the call), sign-in identity
     actions and the IAM actions of memberships, scopes, placements and shared-graph policies.
   - Each engine module's jobs run as their own account `job/<module_id>` holding `builtin.job`.
   - Acting on behalf of a user never opens a sealed resource.
7. **Kernel resources need placements.** A workspace role reaches a kernel resource only once IAM placed it in the
   workspace. Nexus places what it creates and registers `placement_source`s for what exists, applied at every boot and
   when a workspace is created. Two platform-level exceptions are deployment grants (`iam.set_platform_grants`):
   the shared repository slides, documents, sheets and code use (viewers read, members write) and the platform's
   datasets (read for every role).
8. **Proof.** `route_matrix_test` reads the declaration of every route off the real application, checks that a write
   method never authorizes only a read, and decides every `guard` for viewer, member, admin, owner and stranger with a
   real IAM. Per-router tests drive the real routers with real roles. The Postgres access suite (`apps/api/tests`)
   runs again.

9. **Credentials and delegation (step 8).** Nexus reads the credential kinds a route takes (`accepted_kinds(path)`):
   a session, a personal API key, or, at the gateway alone, a coding agent's key. The call is `api` acting for the
   user the credential names, and the credential's own limit (`abi_scope` of a key) travels in the call's context, so it
   bounds every Nexus decision as it bounds every kernel one: a key narrowed to reading files reads like its user and
   writes nothing. `Abi-On-Behalf-Of` is gone; `api` and `engine` hold `iam:ExchangeToken` on the `abi:session` and
   `abi:delegated:*` audiences (and a key presented without one), `iam:RevokeTokens` and the key actions, and
   `builtin.self` lets a user manage their own keys. Acting for a user never opens a sealed resource.
10. **Roles are for users, and only users Nexus knows become IAM users.** An id from a request path never creates
    an IAM principal: reading roles, checking or revoking for an unknown id finds nothing and writes nothing, and a
    `usr_` id must name a user record, never a service account or a group. Only `grant` (and the boot seed) of a user that
    exists in Nexus creates the principal. So a workspace admin can give a role to a person, never to a module's service
    account: a role is a way to reach the platform's apps and models, and a module's account is approved by manifest.
11. **The built-in identity provider's admin app is not a role's.** A workspace viewer and member reach the platform's
    apps (`discovery:OpenApp` on `app/*`); the IdP's admin app edits who a `sub` is, which is who becomes the platform
    admin. `builtin.platform.viewer`, `builtin.platform.member` and every module's bootstrap policy carry an
    unconditional Deny of `discovery:OpenApp` on `app/*/idp/admin`; only the engine, which serves the IdP, opens it.
12. **Smaller guarantees.**
    - A failed create takes back what it did: an organization or workspace row whose IAM scope or owner cannot be set is
      removed again (and its scope forgotten), so nothing is left that nobody can administer.
    - `is_superadmin` is asked of IAM where it is shown (`/auth/me`, `/admin/me`, the session and sign-in responses),
      not on every request; only an IAM that is absent answers "not an admin", any other failure surfaces.
    - A workspace's creation places that workspace's resources alone (`on_workspace_created` hooks), never the boot pass over
      all of them; the shared-graph policies are found from one scan of their names, remembered for a minute (a missing
      name too), and the routes that take no workspace (speech, the OpenAI gateway) ask IAM once for all the
      caller's workspaces instead of once per workspace.
    - `-`, `*` and `_none` name no workspace: an organization's own scope is `(org, -)`, so a path naming `-` would
      otherwise be the whole organization's workspace (a viewer could list its members). `Authz.org_of` and `name`
      refuse them, and IAM's `workspace_org` returns no org for them.
    - A new personal workspace (public signup) is registered with IAM, owned by its user and placed at once, not at
      the next boot (the boot migration runs once). The feature agents' tools and the admin tools decide through IAM
      like the routes do, and make every membership change for the asking user.
    - A SPARQL string built from a label (a role label) is escaped as a literal: the lookup runs as Nexus, which
      reads every graph.
    - **Who makes accounts in the provider's directory.** Every user may create an organization (`CreateOrganization`
      is a platform member's, and `nexus.organizations.self_service: false` is still not done), and its owner may
      invite. So the gate that holds is not the organization: `identity:ProvisionUser` on the provider decides, as the
      inviting user (`api` on their behalf, so IAM asks both). Platform members and organization admins do not hold it by
      default; an operator grants it (or an operator is a platform admin). The one exception is an address on a domain
      the organization verified (`organization_domains`, its own, routed to that provider): provisioned as Nexus's own
      call. Otherwise the invitation is made as for a provider that manages its people (pending grants that wait for
      the sign-in; the response says `provisioning_skipped`).
    - **Invitations are authorized at the scope of the roles they carry.** An invitation with an organization role is
      resent and withdrawn by the organization's administrators only; one that names only a workspace, by that
      workspace's administrators or the organization's. A workspace invite never rewrites an organization
      invitation that names the workspace (409), unless the caller administers the organization, who keeps its
      organization role. A workspace invite never carries `owner` (the UI offers none): owners come from the
      organization invite, which only an owner may make.
    - A profile edit never changes the email: invitations and sign-in links find an account by email, and an address
      nobody proved would let a user take an invitation meant for another. An identity provider states its users'
      emails; the built-in login's are changed by an administrator.

## Consequences

- A viewer reads and never writes on every router; chat, office, files, datasets, apps and code now follow the rule.
- Under the default feature baseline members and viewers get 403 on the graph, ontology, search and settings sections:
  that is what the flags said, now enforced.
- Existing installs enforce once the boot migration ran. A role changed through the new API is never undone by an old
  row.
- The shared repository separates workspaces by Nexus's branch naming only, as before; a per-workspace repository is
  the way to make IAM enforce it.
- `read_all` shares the graphs that exist when applied (see the graph ADR).
- What remained after this change, and was done by the login removal: the legacy `urn:abi:nexus` issuer (step 13), the `api_keys` mock
  and login code (step 13).
