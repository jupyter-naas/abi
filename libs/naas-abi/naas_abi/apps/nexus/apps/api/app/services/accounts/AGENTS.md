# Accounts (Platform Settings > Users) - AGENTS.md

## Purpose

Every account of the platform, and its lifecycle, for the platform admin: the directory behind Platform
Settings › Users (web: `apps/web/src/app/settings/users/`, Nexus `AGENTS.md`, "Platform Settings").

- **The directory**: every Nexus account (a `users` row) and everyone invited who has none yet (their pending
  invitations, by email; id `invited:<email>`), each with their IAM id, whether they signed in at least once
  ("invited, not yet": a row of the old login or one the configuration seeds, never linked to a provider; an
  invitee), whether they are deactivated (IAM suspended the user; for an invitee, their provider disabled the
  account), whether they are a platform admin (IAM's `builtin.platform_admin`) and their organizations.
- **Invite** through Nexus's invitations (`services/invites`), the one way someone is invited: an invitation to
  the platform alone (no organization, no role, no grant). The provider makes the person exist; their access is
  attached once they have an account (Roles & permissions).
- **Rename** (Nexus's row and the provider's account ABI made: a sign-in refreshes the name from the provider), and
  **superadmin** on or off.
- **Deactivate / reactivate**: IAM suspends the user (no sign-in through `identity.authenticate`, no API call: a
  session ends within 5 s, a key is refused, the kernel denies), the provider disables the account (no sign-in
  there, its sessions end), Nexus revokes the browser sessions. Data, memberships and keys stay: reactivating
  gives everything back.
- **Delete**: the account at the provider, the IAM user (every token revoked, its keys, personal ones too;
  IAM's `delete_principal` takes its attachments, so its memberships, and its group memberships; its id stays
  for the audit), its browser sessions, its organization profiles, its pending invitations. The `users` row
  stays as the author of what the person wrote in workspaces (conversations, files, graphs...), retired:
  `deleted_at` set, its email released (`<id>@deleted.internal`, never matched by a lookup, an invitation or a
  sign-in), and every read of `services/auth` and of the sign-in skips it.

Access is not shown or changed here: a row opens the person's page in Roles & permissions.

## Files

| File | Role |
|---|---|
| `port.py` | Records (`Account`, `NexusUser`, `DeletionPlan`, ...), errors, `AccountStorePort` (Nexus rows), `AccessGateway` (IAM), `IdentityGateway` (the providers), `InvitationsGateway` |
| `service.py` | `AccountService`: `list`, `invite`, `rename`, `set_superadmin`, `deactivate` / `reactivate`, `deletion` (the plan), `delete`; the rules; the audit |
| `runtime.py` | `RUNTIME`: the service of a request from the engine's IAM and identity, Nexus's database, invitations and the IAM admin's audit log; tests `configure` another |
| `adapters/primary/accounts__primary_adapter__FastAPI.py` | `/api/admin/users`, each route `guard`ed by its `nexus` action |
| `adapters/secondary/postgres.py` | `users`, `auth_sessions`, `organization_members` (profiles), `workspace_members` (`migrations/0067_users_deleted.sql`: `deleted_at`) |
| `adapters/secondary/engine.py` | `EngineAccessGateway` (IAM: reads as `api`, changes as the caller through `EngineIamGateway.bind`, the platform admin's role through `MEMBERSHIPS`), `EngineIdentityGateway` (identity as `api` on behalf of the caller) |
| `adapters/secondary/invitations.py` | `InvitationsAdapter`: `services/invites`' `InvitationService`, every pending invitation, a platform invitation |

## Routes

`/api/admin/users` (a session or a personal API key, like the rest of `/api/admin`):

- `GET ""` → `[{id, kind: account|invitation, email, name, avatar, principal_id, status: signed_in|invited,
  deactivated, is_superadmin, created_at, organizations: [{id, name, role}], provider, warning}]` (`ListUsers`)
- `POST /invite` `{email, name?, provider?}` → `{user, user_created, sign_in_email_sent, provisioning_skipped,
  renewed, warning}` (`InviteUser`); 409 when an account holds the address, or when a deleted account is still
  bound to the address's account at its provider; 400 no provider, or an address the provider will not take;
  502 a provider that could not make the person (`invites.views.PROVIDER_FAILURES`, as the organization's and
  the workspace's invitations answer it)
- `PATCH /{id}` `{name?, is_superadmin?}` → the row (`UpdateUser`): every rule of both is checked before
  either is made, and the superadmin change (IAM's) goes first, so a refusal leaves the name as it was
- `POST /{id}/deactivate`, `POST /{id}/reactivate` → the row (`SuspendUser`, `ResumeUser`)
- `GET /{id}/deletion` → `{user, blocked, warning, goes: {provider_account, iam_user, attachments, memberships:
  [{scope, label, role}], groups, sessions, api_keys, invitations}, stays: {workspaces: [{id, name}]}}`
  (`DeleteUser`); `warning` says when the provider keeps the person's account (`provisioning: none`)
- `DELETE /{id}?confirm=<email>` → `{deleted, warning}` (`DeleteUser`); 400 when the email typed back is not
  theirs, 409 when the plan is `blocked`

Answers: 404 an unknown account, 400 a rule (yourself, the last platform admin) or a provider that manages its
people where nothing else can be done, 403 IAM's refusal (its words), 409 as above, 502 a provider that could not
do it, 503 the audit log unavailable (nothing changed). A change answers the row as it now is, with `warning`
when a provider could not follow (the IAM side holds: the account is deactivated or deleted in ABI, do the same
at the provider).

## Rules

- **The route asks the `nexus` action, IAM decides the change inside.** Each route declares its action on the
  account (`abi:nexus:user/<id>`, `-` for the list and an invitation: `services/iam/catalog/users.py`), a platform
  type no role reaches, so only the platform admin holds them, or whoever a policy grants them. The change is then
  made as the caller: IAM's own `iam:SuspendPrincipal`, `iam:ResumePrincipal`, `iam:RevokeTokens`,
  `iam:DeletePrincipal`, the attachment of `builtin.platform_admin`, and the provider's `identity:ProvisionUser`,
  `identity:FindProvisionedUser`, `identity:UpdateProvisionedUser`, `identity:DeleteProvisionedUser` (as `api` on
  behalf of the caller: `builtin.api` holds them, the caller must too). A refusal is a 403 and changes nothing.
- **Nothing on yourself.** Renaming, superadmin, deactivating and deleting one's own account are refused (one's
  profile is the account page); the plan says it as `blocked`.
- **Never the last active platform admin.** Demoting, deactivating or deleting a platform admin is refused when no
  other active one remains (a suspended admin does not count). A platform admin acting is one, so this holds
  against someone a policy lets manage accounts without being one.
- **Never an organization's only owner.** Deleting them is refused (`blocked`) until someone else is an owner there:
  an organization is never left unadministered. A workspace is kept by its organization's owners and admins.
- **Audited first, fail-closed.** Every change goes through `run_audited` into the IAM admin's log (`audit_logs`,
  `iam.<operation>`, service `iam`): `invite_user`, `rename_user`, `grant_platform_admin`, `revoke_platform_admin`,
  `suspend_user`, `resume_user`, `delete_user`, each `requested` then `succeeded` or `failed`, with the actor, the
  account's id and its email. Roles & permissions › Audit shows them.
- **IAM first, then the provider.** Deactivating, reactivating and deleting an account change IAM first (its
  refusal stops everything); the provider follows, and what it could not do is the answer's `warning`, as is a
  lookup of the person's account at a provider that failed (it was not changed there). An invitee has no IAM
  user: the provider is the change, and its refusal stops it.
- **Only an account ABI made is changed at the provider.** At ABI's own provider (`provisioning: builtin`)
  every account is ABI's. At a shared realm (Keycloak, Zitadel), an invitation may find an account that already
  existed there (`ensure_user`'s existing-account path: nothing created); only one an invitation created is
  recorded (`provisioned_identities`, migration `0068`, written by `services/invites`) and is ABI's
  (`AccountService._split`). Renaming, deactivating and deleting change ABI's accounts only: the person's own
  account stays as it is, used by their other applications, and the answer and the deletion plan say so ("Their
  account at <provider> is theirs, not ABI's"); their access to ABI is what ends (IAM, sessions, keys). An
  invitee whose only account is theirs is not deactivated (there is nothing of ABI's to stop: delete the
  invitation). Accounts invitations made before `0068` are not recorded: they count as the person's.
- **One operation at a time on the request's session.** The store and the invitations share the request's
  `AsyncSession`, which takes one operation at a time (asyncpg refuses a second): their reads are awaited in
  turn; only IAM's and the providers' calls run together (`asyncio.gather`). The route test wraps the session
  so a second operation while one runs fails, as Postgres would.
- **Deleting finishes on a retry.** A principal an earlier attempt already deleted (the row's retirement failed
  after IAM's part) is not deleted again: the retirement goes on. An invitee at a provider that manages its
  people has nothing to delete there: deleting revokes the invitations.
- **An identity a deleted account keeps.** IAM keeps `(issuer, sub)` on the deleted user, so a provider account
  that survives the deletion (`provisioning: none`, or a provider delete that failed) can never sign in again.
  The plan's `warning` and the deletion's answer say so; inviting that address again is refused (409) where the
  provider tells its account (`AccountStorePort.retired_identity`). Under `provisioning: none` it cannot tell:
  the plan's warning is the only notice.
- **One invitation path.** A platform invitation is `InvitationService.invite` with no organization, no workspace
  and no role (no grant, no policy: `InvalidPolicyError` for one); the address must have no account (409).

## Decisions

- **The directory is Nexus's rows and invitations; the states are IAM's and the provider's.** *Decision:* who is
  an account is a `users` row (not deleted), who is invited is a pending invitation whose address has no row;
  deactivated is IAM's suspension (the provider's disabled account for an invitee), superadmin IAM's
  `builtin.platform_admin`. *Consequences:* no new state is stored for deactivation; reactivating restores it
  all; a sign-in refused by a suspension says `suspended`.
- **A deleted account's row stays, retired.** *Decision:* deleting never removes the `users` row: its foreign keys
  (authors of conversations, files, owners of organizations and workspaces) cascade, and what the person wrote
  stays. The row gets `deleted_at` and a released email. *Consequences:* the same address can be invited again
  (a new IdP account, a new `(issuer, sub)`, a new row); `services/auth` and the sign-in never find a retired row;
  the raw `users` table (Nexus tables) still shows it.
- **ABI changes at a provider only what ABI made there.** *Decision:* an account found at a shared realm when
  the person was invited is theirs; deleting or deactivating their Nexus account ends their access to ABI and
  never deletes or disables that account (`provisioned_identities`). *Consequences:* deleting someone at a
  shared realm can leave their account there, which then cannot sign in to ABI again with that address (the
  identity stays with the deleted account), and the plan says so; the owner may decide otherwise (deleting the
  person in the realm too), which would make the plan say it plainly instead.
- **Lifecycle at the provider is the provisioning port's.** *Decision:* the engine's identity service changes and
  deletes the person at their provider (`update_provisioned_user`, `delete_provisioned_user`, keyed by the
  provider's subject; core `services/identity/AGENTS.md`). *Consequences:* the built-in IdP disables (its sessions
  and refresh tokens end) and deletes; Zitadel and Keycloak through their admin APIs; a provider with
  `provisioning: none` manages its people, so ABI's side is done and the answer says to do the same there.

## Tests

```bash
uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/accounts --import-mode=importlib --no-cov -q
```

`adapters/primary/accounts__primary_adapter__FastAPI_test.py` runs the routes on a real IAM (the `team`
fixture, `root` a platform admin), Nexus's tables on SQLite and a provider in memory: who sees the directory (an
organization's owner or admin does not), an invitation listed, deactivated at the provider and deleted, an
account deactivated (IAM suspended, provider disabled, sessions revoked) and reactivated, renamed and made a
platform admin, the deletion's plan and the deletion (IAM user deleted, attachments gone, row retired, session
gone), and the rules (yourself, the last active platform admin against a delegated operator, an organization's
only owner, IAM's refusal inside audited as failed with nothing changed).
