# Invitations are pending grants; a provisioning port makes the person exist at their provider

Status: Accepted

Date: 2026-10-19

Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §12.2.

## Context

An invite created the Nexus user and the membership row directly and sent a magic link. With
login moving to OIDC identity providers, a person is `(issuer, sub)` and their account exists at
their provider, so an admin cannot create it in Nexus, and the roles cannot attach to an account
that does not exist yet. The built-in IdP, Zitadel and Keycloak can create users through an admin
API; Okta and Entra are managed by their own admins. Admins also want to give a role to a whole
group of a provider without inviting its members one by one.

## Decision

- **IAM holds invitations as pending grants.** A pending grant is a policy at a scope for an
  email on one provider. It becomes an attachment of the first user of that provider whose record
  has that email **verified**, claimed by `claim_pending_grants` from the user's own record (never
  from a supplied address), once per grant. Creating and revoking one is authorized as the
  attachment it stands for (`iam:AttachPolicy` / `iam:DetachPolicy` on the invitee's name at the
  scope), so a workspace admin invites to their workspace and cannot make an owner.
- **A `ProvisioningPort`** in the identity service, one adapter per provider's `provisioning`
  setting: `builtin` calls the IdP's admin app over NATS, `zitadel` and `keycloak` their admin
  APIs, `none` raises `NotImplementedError` and the UI says the provider manages its users.
  New users have an unverified email that the provider's own mail verifies (the built-in IdP
  verifies at every sign-in with a code), so a mistyped address gives access to nobody.
  Credentials are `identity.providers[].admin`.
- **The IdP's admin app checks the verified actor itself.** Discovery's `OpenApp` is read-level
  and held by any service account with a workspace role (`builtin.platform.viewer`); once
  workspace admins can attach roles to service accounts, that would be IdP admin, and through
  `PATCH /users/{id}` anyone's account. The app host now passes the verified principal to the
  app (`AuthorizeAppResponse.caller_principal_*`, `HttpRequest.principal_*`), and the admin
  app serves `api` and `engine` only.
- **Nexus records the invitation** (`invitations`) for the people-management UI: pending list,
  resend, revoke. At the first sign-in it makes the memberships it stores, until subtask 11
  (#65) makes the claimed attachments the memberships. The invitation email carries a link and
  no secret.
- **IdP group bindings** (`bind_idp_group`): IAM finds or creates the ABI group
  `idp:<provider>:<claim value>`, maps the claim to it and attaches the role at the scope. The
  caller is authorized for the attachment alone.
- **Who authorizes the inviting person.** Nexus checks their membership today and calls IAM and
  the provider as `api` for nobody (a Nexus user holds no `iam:*` right yet); `abi iam invite`
  runs as `engine`. After #65, IAM's own check of the attachment replaces the membership check.

## Consequences

- The demo flow (invite Bob, the IdP creates him, he signs in with a code, he is a member of W)
  runs without Docker and is an automated test (`invitation_demo_test.py`).
- With `provisioning: none`, an invitation is a pending grant only; nothing is created at the
  provider and the invitee must have an account there before they sign in.
- An invitee who already has a Nexus account is added directly as before, and a person whose
  verified email another Nexus account holds is still refused at sign-in ("accounts are never
  linked automatically").
- Withdrawing an invitation withdraws its pending grants, but not a membership already made.
- Provisioning needs the provider's admin credentials in the engine's configuration; the
  Zitadel adapter is tested against the pinned Zitadel binary, the Keycloak adapter against a
  fake admin API.
