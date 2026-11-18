# An authorized invitation makes the account at the identity provider

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

An invitation to an address with no Nexus account does three things: IAM keeps the
roles as pending grants, the identity provider makes the person exist (the
provisioning port), and Nexus records and mails the invitation
(`services/invites/AGENTS.md`).

Until now the provider's admin API was called as `api` on behalf of the inviting
user, so IAM asked them for `identity:ProvisionUser`. Only a platform admin holds
it by default. When an organization admin or a workspace owner invited someone, the
call was refused and the invitation went on without an account
(`"provisioning_skipped": true`). The mail still said "you will be asked for a
sign-in code".

With the built-in provider's self-signup off (no `ABI_IDP_SIGNUP`, as a production
deployment runs), the provider has no user for that address. `send_code` takes its
decoy path and no code is ever mailed, so the person can never sign in. `abi dev up`
turns signup on, which hid the problem. On a real deployment, all six people
invited by an organization admin and a workspace owner were skipped (#1520).

The rule was there to stop accounts being made at the provider on a user's
say-so. Any platform member may create an organization and invite from it.

## Decision

1. **The authorized invitation is the warrant.** The route authorizes the
   invitation (`InviteOrganizationMember` or `InviteWorkspaceMember` at its scope).
   IAM then accepts its pending grants on the inviting person's behalf ("Grant only
   what you hold", the owner rule). After both, Nexus makes the account at the
   provider as `api` for nobody (`builtin.api` holds `identity:ProvisionUser`). The
   inviting person needs no right at the provider. No new policy is added.
2. **Nothing outside such an invitation.** Grants come first, so an invitation the
   route or IAM refused makes nobody. If `api` itself is refused (a deployment that
   withholds the right), the invitation fails: the grants it made are taken back
   and the route answers 502. The mail is sent last.
3. **The platform-level invite keeps its rights.** Platform Settings › Users invites
   with no organization, no workspace and no grant, so it has no warrant other than
   the inviter's own right. It is still made on behalf of the inviter, who needs
   `identity:ProvisionUser`. Without it, nothing is made, the answer says
   `provisioning_skipped`, and the mail promises no code: it says to sign in with
   an account they have, or to ask an administrator to create one.
4. **`provisioning: none` is never called.** A provider whose people are managed in
   the provider stays as it was: the invitation is pending grants only.
5. **`provisioning_skipped` stays** in the invite answers for compatibility. For an
   organization's or a workspace's invitation it is now always false.

## Consequences

- Organization admins and workspace owners onboard people themselves. The people
  they invite can sign in on a provider without self-signup.
- Whoever may invite at a scope makes accounts at the provider for the addresses
  they invite. Every platform member may create an organization, so in effect any
  platform member can. The invite routes' rate limits (per inviting user, per
  address) and the organization's `invitation_mails_per_day` bound it.
- Such an account gives the inviter no access to it. Its email is unverified, and
  the built-in provider proves it at each sign-in with a code mailed to the
  address. Accounts are never linked across providers. Zitadel and Keycloak mail
  their own verification.
- An account the invitation made is recorded (`provisioned_identities`), so it is
  changed or deleted at the provider together with the person's Nexus account
  (`services/accounts`).
- If `api` is refused `identity:ProvisionUser` (a Deny on it), every organization
  or workspace invitation fails with a 502. It no longer leaves an invitee who
  cannot sign in.
- A resend mails the generic text, which promises a code. For a platform invitation
  that was skipped, that is still wrong: the skip is not stored on the invitation.
