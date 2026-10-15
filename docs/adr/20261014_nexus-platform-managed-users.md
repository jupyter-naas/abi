# Nexus users are managed in the platform, not in config

- **Status:** Accepted
- **Date:** 2026-10-14

## Context

The startup seeder (`core/org_seed.py`) provisioned people from three config
lists:

- `users:` created accounts and reconciled `is_superadmin` both ways on every boot;
- `organizations[].members` upserted org roles on every boot;
- `workspaces[].members` upserted workspace roles on every boot.

Because member lists only resolved emails that already existed, deploys had to
list everyone twice (a Forvis Mazars deploy listed 92 people in both `users:`
and the org members, and repeated its core team in ~25 workspaces). Roles
changed in the UI were overwritten on the next boot, so the UI and the yaml
fought over the same rows. Org owners and admins also had no workspace access
unless they were listed in every workspace.

The platform already had what is needed to manage people: org and workspace
invites (account created on invite plus a magic link), role updates, removal,
and per-member workspace assignment.

## Decision

1. **Effective workspace role = max(explicit row, `workspaces.owner_id`,
   role inherited from the org).** Org owners (`organizations.owner_id` or an
   `owner` membership) inherit `owner`, and org admins inherit `admin`, on every
   workspace of their org. Org `member` inherits nothing. Resolution lives
   in `core/workspace_access.py` (`resolve_workspace_role`,
   `accessible_workspace_ids`) and is used by the workspaces, IAM, maps
   permissions and providers adapters.
2. **The config only bootstraps.** `users:` creates missing accounts, and its
   `is_superadmin` only promotes, never demotes. Orgs and workspaces still
   upsert by slug with their owner membership. `members` lists are deprecated:
   they are still accepted, so older configs load, but ignored with a warning.
   Existing membership rows are never deleted.
3. **Superadmins are managed in the platform** through `GET/PATCH /api/admin/users`.
   The API refuses self-demotion and removing the last superadmin. Platform
   Settings (`/settings`, linked from the account menu for superadmins only)
   has a dashboard of the database tables. It shows row and column counts per
   table, and clicking a table shows its schema. Each table also has a read-only
   page at `/settings/<table>` (`GET /api/admin/tables/{name}` and
   `.../schema`). Each row has its own page at `/settings/<table>/<row id>`
   (`.../rows/{id}`). The row id is the primary key, with values joined by `~`
   when the key has several columns. The superadmin toggle is on the user's
   row page. Only a fixed allowlist of tables can be read: every Nexus
   table, grouped in sections. Credentials are masked: password and token
   hashes, sign-in tokens, API keys, sidecar secrets, encrypted secret values
   and provider configs.
4. **The organization is the people directory.** A workspace invite also adds
   the invitee to the workspace's org as `member`. The workspace Members list
   shows inherited org owners/admins as `source: "organization"`. They are
   read-only there, because that access is managed in Organization > Users.
5. **Owners come only from the config.** Invites and role changes accept
   `admin` or `member` (and `viewer` on workspaces). The organizations service
   refuses `owner` with `OrganizationRoleNotAssignableError`.
6. **Member profiles are per organization, and flow org -> account only.**
   Org admins set a member's organization, job title, service line,
   country, interest, bio and picture on `organization_members` (migrations
   0052, 0055). Members cannot edit them. When the account (`users`) has no
   picture, organization or job title, the account shows the member value
   from the organization the person joined first. An organization never shows
   the account's values for these fields. The full name is always the account
   name (`users.name`), and bio still falls back to the account. The picture is stored in the person's drive as
   `.settings/avatar/avatar_org.<ext>`, next to the account picture
   `avatar.<ext>`.
7. **Profile files in the personal drive.** After each profile change,
   `naas_abi/my-drive/<user_id>/` gets `.settings/user/user.json` (the
   account), `.settings/user/org_member.json` (the memberships) and `.USER.md`
   (a summary built from both files, plus the picture URL). The JSON files and
   pictures keep previous versions in `archives/<ts>_<name>`, and an upload
   identical to the current file (same SHA-256 hash) changes nothing. The
   database stays the source of truth: a storage failure is logged and never
   fails the request.
   Workspace logos follow the same logic in the workspace drive:
   `naas_abi/workspace-drive/<workspace_id>/.settings/logos/logo.<ext>`, served
   at `GET /api/workspaces/{id}/logo` (SVGs with a sandboxing CSP). Only org
   owners and admins can create a workspace in their organization.
8. **Snapshots replace the yaml lists.** `config.users.yaml` (one entry per
   person: account fields, org roles, workspace roles) is not read on boot.
   `python -m naas_abi.apps.nexus.apps.api.app.core.users_import <file>`
   replays it create-only: missing accounts and memberships are inserted,
   existing roles are kept, and nothing is deleted.
9. **Workspace group.** `workspaces.workspace_group` (migration 0056, with
   `description`) groups the workspace lists: the sidebar switcher shows one
   section per group, in alphabetical order, followed by "Others" for
   workspaces with no group. The org Workspaces table has a Group column. The
   group is edited in Workspace Settings > General, and a blank value clears
   it. The config `group:` key is bootstrap only: it is applied when a
   workspace has no group yet, so a group changed in the UI stays.
   Create workspace (Organization Settings > Workspaces > Create) uses the
   General layout and sets the group, description and colours at creation.
   The slug is chosen there and is read-only in General afterwards, because
   the seed and graph policies match workspaces by slug. `/workspace/<slug>`
   opens a workspace like its id. Org owners and admins can set the group of
   several workspaces at once (`POST /api/organizations/{org}/workspaces/bulk-update`).
11. **Workspace feature overrides are bootstrap only.** The org Workspaces
   table lists each workspace's features (on for at least one role). Clicking
   them edits the overrides (Default / On / Off per feature), saved in
   `workspaces.feature_overrides` (JSON, migration 0056) via
   `PUT /api/organizations/{org}/workspaces/{id}/features`. Once saved, they
   replace the config `feature_flags.workspace_overrides` entry for that
   workspace. Saving `null` ("Use config") applies the config again. Settings
   cannot be overridden.
12. **Config workspaces only seed resources.** The bob configs keep, per
   workspace, `slug` plus the seeding keys (`default_agent`, `agents`, `apps`,
   `ontologies`, `graphs`, `maps`). Name, owner, group, description, branding
   and feature overrides are managed in the app. `feature_flags.workspace_overrides`
   is removed from the configs (still accepted, as a deprecated fallback).
   `config.workspaces.yaml` (and `.base` / `.remote`) snapshot those values.
   They are not read on boot: `python -m
   naas_abi.apps.nexus.apps.api.app.core.workspaces_import <file>` replays one
   fill-only. It creates missing workspaces and fills only empty values (a
   name equal to the slug counts as empty). It writes feature overrides only
   where none were saved, and never deletes anything. A workspace the seed
   creates without a name is named after its slug.
10. **Workspace name and branding are bootstrap only.** On an existing
   workspace the seed fills `name`, `logo_url`, `logo_emoji`, the colours,
   `background_image_url` and `font_family` only where the workspace has no
   value yet. Renames, logos and colours changed in the app survive restarts.
   To re-apply a config value, clear the field in the app and restart. The
   workspace `owner_id` and `organization_id` follow the same rule, and the
   owner membership the seed ensures is the workspace's actual owner.

## Consequences

- People and roles changed in the UI survive restarts.
- Removing `members:` from a config does not revoke access. Revoke access in the
  platform.
- A fresh database gets only the bootstrap users, and workspaces named after
  their slugs. Run `users_import` and `workspaces_import` to restore the
  snapshots.
- A config-listed superadmin who is demoted in the UI is promoted again on the
  next boot. This is intended as a lock-out guard, and the way to demote them
  for good is to remove them from `users:`.
- Org admins now reach every workspace of their org. Grant org `admin` only
  to people who should have that reach.
