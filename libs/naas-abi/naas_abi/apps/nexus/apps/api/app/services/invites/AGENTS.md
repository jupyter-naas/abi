# Invitations - AGENTS.md

## Purpose

Admins give access to people who do not exist yet. An invitation to an
email, through one identity provider, does three things:

1. **IAM keeps the roles** as pending grants (`builtin.<role>` at `abi:<org>:-` for the
   org's own role, `abi:<org>:<workspace>` for a workspace's) that attach to whoever first
   signs in through that provider with the email verified (core's `services/iam/AGENTS.md`).
2. **The provider makes the person exist**: the engine's provisioning port (`builtin`,
   `zitadel`, `keycloak`; `none` makes nobody, the provider manages its people).
3. **Nexus records the invitation** (`invitations` table: `pending`, `accepted`,
   `revoked`) so admins list, resend and revoke it, mails the invitee a sign-in link (no
   code, no secret), and, at the first sign-in, makes the memberships Nexus still stores
   (`claim`).

IdP group bindings are the same idea for a whole group of a provider: the members of
`group` hold `role` at a scope (`IAMService.bind_idp_group`).

## Files

| File | Role |
|---|---|
| `port.py` | Records (`Invitation`, `ProviderChoice`, `Directory`), `InvitationPersistencePort`, `DirectoryGateway` (providers, provisioning), `GrantsGateway` (IAM), `InvitationMailer` |
| `service.py` | `InvitationService`: `choose` a provider, `invite`, `resend`, `revoke`, `claim`, group bindings |
| `names.py` | Scopes of orgs and workspaces (`_none` for a workspace with no org) |
| `invitation_email.py` | The invitation mail's text |
| `views.py` | The answers of the routes (no service behind them, so the org and workspace routers can import them) |
| `runtime.py` | `RUNTIME`: builds the service from the engine's, `claimer` (the sign-in hook), `get_invitation_service` (the route dependency); tests `configure` another |
| `adapters/primary/invites__primary_adapter__FastAPI.py` | `/api/invitations/...` and `/api/idp-groups/...` |
| `adapters/secondary/postgres.py` | The `invitations` table (`migrations/0060_add_invitations.sql`) |
| `adapters/secondary/engine.py` | The engine's identity and IAM: grants and bindings as `api` on behalf of the inviting person, reads and withdrawals as `api` for nobody |
| `adapters/secondary/mailer.py` | The invitation mail through the engine's email service |
| `mail.py` | The email service, the dev-frontend subject mark, and the notice mailed to someone who already had an account (`send_added_notice`) |

## Routes

- `POST /api/organizations/{org}/members/invite` and
  `POST /api/workspaces/{ws}/members/invite` (optional `provider`). For an email with no
  Nexus account they answer `{"status": "invited", "invitation", "provider", "user_created",
  "sign_in_email_sent", "renewed"}`; someone who already has an account is added directly and
  mailed a notice with a sign-in link (`sign_in_email_sent`); with no provider configured an invite of
  someone with no account answers 400: Nexus has no login of its own to fall back to.
- `GET /api/invitations/providers` → `{enabled, default_provider, providers:[{name,
  display_name, provisioning, managed_in_provider}]}`; `managed_in_provider` is
  `provisioning: none`, which the UI explains.
- `GET /api/invitations/organizations/{id}`, `/workspaces/{id}` (pending), `POST
  /api/invitations/{id}/resend`, `DELETE /api/invitations/{id}` (also withdraws the pending
  grants).
- `GET|PUT|DELETE /api/idp-groups/organizations/{id}` and `/workspaces/{id}`: the bound
  groups, `{provider, group, role}`.

## Rules

- **The route authorizes the inviting person, the service never does.** The check is IAM's
  (`InviteOrganizationMember` / `InviteWorkspaceMember`, an admin's level: `declares(...)` on each
  route, so the route matrix sees it). The pending grants and IdP bindings are then written as `api` on behalf of
  the inviting person (`by`), so IAM also checks that they may attach the role there and hold what it grants
  ("Grant only what you hold" in core's `services/iam/AGENTS.md`: `GrantNotHeldError`, a 403 naming what they lack);
  reads and withdrawals are Nexus's own (`as_service_account("api")`, no user). The owner rule is also kept here
  (`may_grant_owner`). The claimed attachments are the memberships: Nexus keeps no membership row.
- **Making the person at the provider needs the right to.** The provider's admin API is called as `api` on behalf of
  the inviting user, so IAM checks `identity:ProvisionUser` for them (not an organization role's); without it, or
  for an address that is not on a domain the organization verified and routed to that provider, the invitation is
  pending grants only (`provisioning_skipped`). Never call `provision` for nobody on a user's say-so.
- **Authorize an invitation at the scope of its roles.** One with an `org_role` is the organization
  administrators' (`require_invitation_admin`), and a workspace-only invite never rewrites it
  (`OrgInvitationExistsError`).
- **Grants first, then the provider.** A failed grant or provisioning call takes back what
  the call made; the email is last and never fails the invitation.
- **Claim only a verified email.** `runtime.claimer` runs after the sign-in resolved the
  user and checks that the provider verified the address Nexus stored; IAM's own claim
  checks the same on its side.
- **Only an owner invites an owner.** IAM refuses an owner's grant to anyone else; the route also passes
  `may_grant_owner` (the caller is an org owner) and the service refuses `owner` otherwise
  (`OwnerGrantRefusedError`, 403) before anything is written, a system invitation (no `by`) included.
- **Grants are shared, so they are counted.** IAM keeps one pending grant per provider, email, role
  and scope, so invitations of one person to two workspaces share the org-level grant. Revoking an
  invitation, renewing it, or rolling a failed one back withdraws only grants that no other pending
  invitation of that person lists, and a failed call takes back only the grants it made
  (`GrantMade.created`). The invitation row and the grants are written together or not at all.
- Re-inviting the same email at the same place renews the invitation (roles may change; the
  grants it no longer needs are withdrawn).

## Decisions

- **An invitation is a pending grant, not an account.** A person is `(issuer, sub)` and their account exists at
  their provider, so an admin cannot create it in Nexus, and roles cannot attach to an account that does not exist
  yet. IAM holds the roles as **pending grants**: a policy at a scope for an email on one provider
  (`create_pending_grant`, `list_pending_grants`, `revoke_pending_grant`). It becomes an attachment of the first
  user of that provider whose record has that email **verified**, claimed by `claim_pending_grants` inside
  `identity.authenticate` from the user's own record (never from a supplied address), once per grant. Creating and
  revoking one is authorized as the attachment it stands for (`iam:AttachPolicy` / `iam:DetachPolicy` on the
  invitee's name at the scope), so a workspace admin invites to their workspace and cannot make an owner. Details:
  [`services/iam/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/iam/AGENTS.md) and
  [`services/identity/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/identity/AGENTS.md).
- **A provisioning port makes the person exist at their provider.** One adapter per provider's `provisioning`
  setting (`ProvisioningPort`: `ensure_user`, `find_user`; `abi.identity.v1.provision_user` and
  `find_provisioned_user`, `identity:ProvisionUser` and `FindProvisionedUser`): `builtin` calls the IdP's admin
  app over NATS, `zitadel` and `keycloak` their admin APIs (credentials in `identity.providers[].admin`), `none`
  raises `NotImplementedError` and the UI says the provider manages its people (an invitation is then a pending grant
  only: the invitee must have an account there before they sign in). New users have an unverified email that the
  provider's own mail verifies (the built-in IdP verifies at every sign-in with a code), so a mistyped address gives
  access to nobody.
- **The IdP's admin app checks the verified actor itself.** Discovery's `OpenApp` is read-level and held by any
  service account with a workspace role; the app host passes the verified principal to the app and the admin app
  serves `api` and `engine` only (`libs/naas-abi-idp/AGENTS.md`).
- **Nexus records the invitation** (`invitations`) for the people-management UI (pending list, resend, revoke), and
  at the first sign-in makes the memberships it still stores; the claimed attachments are the memberships. The mail
  carries a link and no secret.
- **IdP group bindings** (`bind_idp_group`): IAM finds or creates the ABI group `idp:<provider>:<claim value>`, maps
  the claim to it and attaches the role at the scope. The caller is authorized for the attachment alone and must hold
  what the role grants there; a refused binding makes no group. `abi iam group bind` and `abi iam invite` are the
  lower levels.
- **Who authorizes the inviting person.** The route's IAM check (`InviteOrganizationMember` /
  `InviteWorkspaceMember`); then the grants are written as `api` on behalf of the inviting person, whom IAM checks
  for the attachment and for holding what it grants (the owner rule is kept here too), and the provisioning call is made as `api` on behalf of the inviting user, which asks `identity:ProvisionUser`.
  Platform members and organization admins do not hold it by default; an operator grants it (or is a platform
  admin). The one exception is an address on a domain the organization verified (`organization_domains`, its own,
  routed to that provider): provisioned as Nexus's own call.
- Withdrawing an invitation withdraws its pending grants, but not a membership already made. An invitee who
  already has a Nexus account is added directly; a person whose verified email another Nexus account holds is still
  refused at sign-in (accounts are never linked across providers: `services/oidc/AGENTS.md`).

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/invites --import-mode=importlib --no-cov -q
```

`invitation_demo_test.py` is the demo end to end (invite Bob, the IdP creates him, he signs in with a code, he is a member of the workspace): Nexus's migrations on SQLite, its
middleware and routers, the engine's identity service and IAM, the built-in IdP over real HTTP
and the filesystem email adapter. `service_test.py` drives the service with fakes.
