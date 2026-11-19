# People - AGENTS.md

## Purpose

One platform directory of people: the `users` table. A person is a row from the moment they are invited
(`status: invited`) until their first sign-in makes it `active` (`services/oidc`). `PeopleService` creates or
links them and attaches the roles and policies the inviting person chose (epic #1566, "API contract": the
interface the organization and workspace routes code against).

## Files

| File | Role |
|---|---|
| `port.py` | The contract's records (`UserStatus`, `Grant`, `PlatformUser`, `CreateOrLinkResult`), its errors, and the ports: `PeopleStorePort` (rows), `IdentityGateway` (providers), `AccessGateway` (IAM), `PeopleMailer` |
| `service.py` | `PeopleService`: `create_or_link`, `add_existing`, `get`, `by_email`, `search`, `resend`, `activate` |
| `runtime.py` | `RUNTIME`, `get_people_service` (the route dependency); tests `configure` another |
| `adapters/secondary/postgres.py` | `users` (`migrations/0074_users_status.sql`: `status`, `activated_at`), the organization profile, `provisioned_identities` |
| `adapters/secondary/engine.py` | The engine's identity (provisioning as `api`) and IAM (pending grants, roles and policies as `api` on behalf of the inviting person; principals and take-backs as `api`) |
| `adapters/secondary/mailer.py` | The invitation mail and the "you were added" notice of `services/invites` |

## Rules

- **Authorize before anything exists.** `create_or_link` first writes the grants as IAM pending grants for the
  email, on behalf of the inviting person (IAM: may attach it there, holds what it grants; `owner` only with
  `may_grant_owner`). A refusal (`GrantNotHeldError`, `OwnerGrantRefusedError`) makes nothing anywhere. That
  accepted warrant is what lets Nexus make the account at the provider as `api`
  (`docs/adr/20261118_invitation_provisions_the_account.md`). A platform invitation (no grant) provisions on the
  inviting user's own right (`provisioning_skipped` when IAM refuses it).
- **Then**: provision → `iam.ensure_user(issuer, subject)` → the row (`invited`, id = the principal id) → the roles
  and policies, attached on behalf of the inviting person (policies first, roles through `MEMBERSHIPS.grant`) →
  the pending grants withdrawn → the mail (never failing the call).
- **All or nothing.** A failure after the warrant takes back the attachments, the provider's account (only if
  this call made it), the principal (best effort: `api` holds no `iam:DeletePrincipal`, so the principal of a
  deleted account stays, holding nothing), and the row.
- **No duplicate.** An email that has a row is linked: the grants are attached to it, an active person gets the
  "added" notice, an invited one the invitation again. So is a row made meanwhile (`EmailTakenError` on insert)
  and the row of the provider's identity found under another email (signed in before with an unverified or
  changed one). `created` is internal: routes answer both the same way. A role already held at a grant's scope
  is `AlreadyMemberError` (409). The profile is written only with a grant (never about someone the call gave
  nothing).
- **The routes keep the limits**: the per-inviter and per-address rate limits and the organization's
  `invitation_mails_per_day` are checked by the routes before they call; `resend` and `add_existing` check no
  scope, the route does (the target is in its directory).
- **A provider that makes no account** (`provisioning: none`, or a refused platform invitation): the row is
  `invited` and unbound (id `user-<hex>`, no principal, `idp_provider` the provider). Its roles are attached to
  IAM's user of that id (made on first sight, as for the old login's rows), so the person is listed as invited
  everywhere. Their first sign-in through that provider, email verified, binds the row (`iam.link_user`, which
  keeps the roles): the trust IAM's pending grants have. ADR: `docs/adr/20261119_people_rows_from_invitation.md`.
- **Search** needs 2 characters, matches name or email (any case), stays among the ids the caller passes (the
  route's directory), and returns at most 20.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/people --no-cov -q
```

`service_test.py` drives the service with fakes (order, take-back, link, `provisioning: none`, search, resend);
`adapters/secondary/engine_test.py` runs it on a real IAM and SQLite. The sign-in side (activation, binding) is in
`services/oidc/oidc_sign_in_test.py` (`TestInvitedPeopleSignIn`).
