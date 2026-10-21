# Org owners and admins reach every workspace of their organization, through IAM

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

`20261014_nexus-platform-managed-users.md` decided that an organization's owners and admins hold, on every
workspace of the organization, the role they hold in the organization (`owner` and `admin`; `member` inherits
nothing). It resolved that in Nexus: a query (`core/workspace_access.py`) took the highest of the workspace row,
the workspace's `owner_id` and the role inherited from the organization.

`20261019_nexus-authorization-on-iam.md` moved every decision into IAM: roles are `builtin.<role>` attachments at
`abi:<org>:-` (the organization's own scope) and `abi:<org>:<workspace>`, there is no role check outside IAM and no
second source of memberships. An org role at `abi:<org>:-` reaches the organization's own resources only: it never
reached a workspace. Resolving inheritance in Nexus again would have put a second source of roles back.

## Decision

1. **The inheritance is an IAM attachment.** Whoever holds `builtin.owner` or `builtin.admin` at `abi:<org>:-` also
   holds the same role organization-wide, at `abi:<org>:*`, which IAM reaches into every workspace of the org
   (RFC §3.4, "org-wide roles"). `Memberships.mirror_org_wide` keeps the two together in `grant`, `seed` and
   `revoke`; `Memberships.sync_org_wide_roles` makes the missing ones at start (and, for one person, after the
   sign-in that claims their invitation). Members and viewers of an organization inherit nothing.
2. **Only the system makes them.** IAM refuses an org admin an organization-wide attachment (so that an admin cannot
   attach itself everywhere), so the mirror is written as `api` for no user, after the change that asked for the org
   role was authorized at the organization's own scope. The sync only adds: an organization-wide role someone
   attached on purpose is never removed by it.
3. **Reads follow IAM.** A workspace's effective role is the highest of the role held there and the organization-wide
   one (`WorkspaceService.get_workspace_role`, `effective_roles`); the workspace's members list shows the
   organization-wide holders as `source: "organization"`, read-only; a member's workspace access
   (`OrganizationService.get_member_workspace_access`) and the providers' reach (`org_wide_orgs_of`) the same way.
4. **Creating a workspace is an admin's.** `CreateWorkspace` is an `admin` action on the organization: only org
   owners and admins add a workspace to it (ADR `20261014`, 7).
5. **Owners.** The rule of `20261014` that owners come from the configuration only is not kept: IAM already lets an
   owner grant `owner` and nobody else (`20261019_nexus-authorization-on-iam.md`).

## Consequences

- An org admin reaches, and may administer, every workspace of the organization, as before this branch; grant org
  `admin` only to people who should have that reach.
- Demoting or removing an org owner or admin takes the reach with it (the same call detaches the organization-wide
  attachment); deleting an organization detaches both.
- The organization-wide attachment is visible in the IAM admin pages next to the role it mirrors.
- The Nexus resolution of effective roles (`core/workspace_access.py`) is gone.
