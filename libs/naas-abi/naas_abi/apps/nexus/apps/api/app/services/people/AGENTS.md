# People - AGENTS.md

## Purpose

One platform directory of people: the `users` table. A person is a row from the moment they are invited
(`status: invited`) until their first sign-in makes it `active` (`services/oidc`). `PeopleService` creates or
links them and puts them where the inviting person chose: a level, groups at the organization and its workspaces,
capability groups (epic #1566, "API contract"; #1589: levels and groups, the interface the organization and
workspace routes code against).

## Files

| File | Role |
|---|---|
| `port.py` | The contract's records (`UserStatus`, `Grant`, `WorkspaceAccess`, `Level`, `Seat`, `PlatformUser`, `CreateOrLinkResult`), its errors, and the ports: `PeopleStorePort` (rows), `IdentityGateway` (providers), `AccessGateway` (IAM: seats, join and leave, levels), `PeopleMailer` |
| `service.py` | `PeopleService`: `create_or_link`, `add_existing`, `set_level`, `set_workspace_admin`, `change_access`, `get`, `by_email`, `search`, `resend`, `activate`, `provision` (the configuration's people) |
| `runtime.py` | `RUNTIME`, `get_people_service` (the route dependency); tests `configure` another |
| `adapters/secondary/postgres.py` | `users` (`migrations/0074_users_status.sql`: `status`, `activated_at`), the organization profile, `provisioned_identities` |
| `adapters/secondary/engine.py` | The engine's identity (provisioning as `api`) and IAM (`EngineAccessGateway`: the seats of `iam/memberships`, checked as the inviting person and written as `api`; principals and take-backs as `api`) |
| `adapters/secondary/mailer.py` | The invitation mail and the "you were added" notice of `services/invites` |

## Rules

- **A grant is a level and groups** (#1589, ADR `docs/adr/20261120_access_levels_and_groups.md`). `Grant` names one
  organization: `level` (`viewer` | `member`, one choice for all the person's workspaces; None keeps theirs, someone
  with none who joins a workspace is a Member), `org_admin` ("<O> admins"), `workspaces` (`WorkspaceAccess(id,
  admin)`: "<W> workspace", and "<W> admins" for an admin, who is a Member) and `capabilities` (capability group
  ids of the organization or the platform, `MEMBERSHIPS.capability_groups`). With no workspace and no org admin the
  person joins "<O> people". Nothing is attached to the person and Owner is not assigned (a `role` body of before
  is mapped by the routes, `owner` is a 400). Customer policies are no longer given to a person (`policy_ids`: 400).
- **Authorize before anything exists.** `create_or_link` first asks `AccessGateway.check` for every seat and the
  level, as the inviting person (IAM decides each group's member change, the level by its level-group rule). A
  refusal (`GrantNotHeldError`) makes nothing anywhere. In a container recorded before #1585 the seat is the role
  attachment it stands for, and the held check is probed on a pending grant withdrawn at once
  (`Memberships._probe_held`). That accepted check is what lets Nexus make the account at the provider as `api`
  (`docs/adr/20261118_invitation_provisions_the_account.md`). A platform invitation (no grant) provisions on the
  inviting user's own right (`provisioning_skipped` when IAM refuses it).
- **Then**: provision → `iam.ensure_user(issuer, subject)` → the row (`invited`, id = the principal id) → the
  membership groups, the level, the admins groups and the capability groups, joined as `api` after the check on
  behalf of the inviting person → the mail (never failing the call).
- **All or nothing.** A failure after the check leaves the groups this call joined, takes back the provider's
  account (only if this call made it), the principal (best effort: `api` holds no `iam:DeletePrincipal`, so the
  principal of a deleted account stays, holding nothing), and the row.
- **No duplicate.** An email that has a row is linked: the grant is applied to it, an active person gets the
  "added" notice, an invited one the invitation again. So is a row made meanwhile (`EmailTakenError` on insert)
  and the row of the provider's identity found under another email (signed in before with an unverified or
  changed one). `created` is internal: routes answer both the same way. Someone already in every membership group
  a grant names is `AlreadyMemberError` (409). The profile is written only with a grant (never about someone the
  call gave nothing).
- **Levels and admins.** `set_level` changes a person's level everywhere; IAM allows it to org admins, platform
  admins and the admins of any of the person's workspaces, and audits it. `set_workspace_admin` joins or leaves
  "<W> admins" (a Viewer made admin becomes a Member). `change_access` changes org admin, the level, the workspaces
  (among a set: those left out are left) and the capability groups in one call, all or nothing. The last org
  admin of an organization is `LastOrgAdminError` (409).
- **Audited.** Every join and leave `iam/memberships` makes for someone is a `GroupChange` naming who asked
  (`Memberships.audit_sinks`; the app logs them, `services/audit.audit_group_change`); IAM audits level-group
  changes itself with `on_behalf_of`.
- **The routes keep the limits**: the per-inviter and per-address rate limits and the organization's
  `invitation_mails_per_day` are checked by the routes before they call; `resend` and `add_existing` check no
  scope, the route does (the target is in its directory).
- **A provider that makes no account** (`provisioning: none`, or a refused platform invitation): the row is
  `invited` and unbound (id `user-<hex>`, no principal, `idp_provider` the provider). Its roles are attached to
  IAM's user of that id (made on first sight, as for the old login's rows), so the person is listed as invited
  everywhere. Their first sign-in through that provider, email verified, binds the row (`iam.link_user`, which
  keeps the groups and roles): the trust IAM's pending grants have. ADR: `docs/adr/20261119_people_rows_from_invitation.md`.
- **The configuration's people** (`users:`, `core/org_seed.py`; `config.users.yaml`, `core/users_import.py`) are
  rows of the same shape: `invited`, unbound, naming the provider they sign in through (`users[].provider`, else
  the default, else the built-in one; none known: the old login's row, `active`, no provider). The seeds make the
  rows themselves (in their transaction, with the profile and superadmin flag), then ask `provision(user_id)`
  in the background: the account at the row's provider, as Nexus (the operator's configuration is the warrant,
  as an authorized invitation is), recorded as ABI's when made; never a binding (their first verified sign-in
  there binds the row) and never a mail. A configured row no provider signs in yet is given its provider.
- **The pending invitations of before** became rows of the same shapes once (`services/invites/migration.py`):
  bound when the built-in provider or Nexus made the account, else unbound naming the invitation's provider,
  with the grants the invitation held attached as `api`. ADR: `docs/adr/20261119_platform_user_directory.md`
  (one user database, the derived directory, no org role on workspace add, create-or-link and its privacy).
- **Search** needs 2 characters, matches name or email (any case), stays among the ids the caller passes (the
  route's directory), and returns at most 20.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/people --no-cov -q
```

`service_test.py` drives the service with fakes (order, take-back, link, `provisioning: none`, search, resend);
`adapters/secondary/engine_test.py` runs it on a real IAM and SQLite. The sign-in side (activation, binding) is in
`services/oidc/oidc_sign_in_test.py` (`TestInvitedPeopleSignIn`).
