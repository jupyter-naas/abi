# A person is a users row from the moment they are invited

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Until now, a person became a Nexus `users` row only at their first sign-in. Before that, an invitation was spread over three places: an `invitations` row, IAM pending grants, and usually an account at the identity provider. As a result, invitees appeared in no user list, organization directories derived from IAM roles missed them, and each flow (platform, organization, workspace) answered differently (epic #1566).

## Decision

1. **The invitation makes the row.** `services/people` `PeopleService.create_or_link` follows the order of ADR `20261118_invitation_provisions_the_account.md`. IAM authorizes the grants first, as pending grants written on behalf of the inviting person. Only then does it make the account at the provider (as `api`), get the IAM user of `(issuer, subject)`, and insert a `users` row whose id is that principal id and whose status is `invited`. The roles and policies are then attached directly, still on behalf of the inviting person, and the pending grants are withdrawn. If any step fails after authorization, the call takes back:
   - the attachments,
   - the provider account, only if this call created it,
   - the principal, best effort, because `api` does not hold `iam:DeletePrincipal`,
   - the row.
2. **The first sign-in activates.** The new column `users.status` (`invited` → `active`, with `activated_at`, migration `0074`) is set to active in `services/oidc` on that first sign-in.
3. **No duplicates.** An email that already has a row is linked: the grants are attached to that row. The answer has the same shape whether the call created or linked.
4. **A provider that makes no account** (`provisioning: none`, or a platform invitation whose inviter may not provision): the row is `invited` and **unbound**.
   - It gets a stable id `user-<hex>`, no identity, and `idp_provider` set to that provider.
   - Its roles are attached to IAM's user of that id (made on first sight, as for the rows of the old built-in login) instead of waiting as pending grants. This amends decision 4 of `20261118_invitation_provisions_the_account.md`.
   - The first sign-in through **the provider the row names**, with the email verified, binds the row with `iam.link_user`. The roles are kept and the id is unchanged.

## Consequences

- Every invitee is a member with `status: invited` in each list derived from IAM roles. Admins can change their role, remove them, or resend the invitation like any member. The pending-invitations list becomes unnecessary once #1570 has moved the remaining invitations.
- Binding an unbound row trusts the named provider's `email_verified` claim. That is the same trust as IAM's `claim_pending_grants`. A different provider's verified email still gets "email already belongs to another account", and accounts of the old login still link through the built-in provider only.
- A failed invitation at a provider that provisions can leave an IAM user that holds nothing, bound to a provider account that no longer exists.
- An unbound row made by a refused platform invitation is not provisioned by a later invitation that is warranted; that invitation only links it. An administrator who holds `identity:ProvisionUser` re-invites the person. This is a follow-up item.
