# One platform user directory: the org directory is derived, workspace add grants no org role, create-or-link

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Before epic #1566, a person became a Nexus `users` row only at their first sign-in. Until then, an invitation was an `invitations` row, IAM pending grants and, usually, an account at the identity provider. This caused several problems:

- Invitees appeared in no user list.
- The workspace invite asked for a raw email, with no search of the people who already exist.
- Adding someone who already had an account to a workspace also gave them the organization `member` role. That role carries real permissions: `GetOrganization`, the organization drive, and the "<org> members" group. Someone invited by email, on the other hand, never joined the organization.
- Three "create user" flows answered in three different ways.

The sub-issues S1 to S3 (#1567, #1568, #1569) build the people service, the derived directory and the UI. This record states the decisions they share. It also covers the move of the pending invitations and of the configuration's people (S4, #1570).

## Decision

1. **One user database: the platform's `users` table.** Every person is a row from the moment they are invited (`status: invited`), and their first sign-in makes the row `active` (ADR `20261119_people_rows_from_invitation.md`). `services/people` `PeopleService` is the only code that makes a person:
   - the platform invitation,
   - the organization and workspace invitations,
   - the agent tools,
   - the CLI,
   - the configuration's people (`core/org_seed.py`, `core/users_import.py`). Their rows are unbound and `invited`, and they name the provider the person signs in through. `PeopleService.provision` then makes their account at that provider, as Nexus.
2. **The organization directory is derived, with no new storage.** An organization's people are everyone who holds a role at the organization's container, below it (`org_below`), or at any of its workspaces' containers. `Memberships.org_directory` reads them in one `members_by_scope` pass, so IAM stays the only record of memberships. A row carries:
   - `role`: the organization role, or `null`;
   - `source`: `organization` or `workspace`;
   - `status`: `active` or `invited`.
3. **Adding someone to a workspace grants no organization permission.** The organization `builtin.member` grant that the old workspace-add path made is removed. A person with a role in one of the organization's workspaces is *linked* to the organization: they are listed in its directory ("Workspace access only") and counted in its analytics, but the link grants nothing. Their only access is the workspace role and the policies the workspace admin chose. People who got the organization `member` role through the old path **keep it**, because they cannot be told apart from deliberate members.
4. **Create or link.** `create_or_link(email, …)` makes the person if no row holds the email. Otherwise it **links** that row: the grants are attached to it, and no duplicate is ever made. The order of authorization comes from ADR `20261118_invitation_provisions_the_account.md`: IAM accepts the grants on the inviting person's behalf before the provider is asked. Created and linked people get **the same answer shape**, and the routes never return `created`.
5. **Search stays inside the organization.** A workspace admin searches only the directory of the workspace's organization:
   - the query needs at least 2 characters;
   - it returns at most 10 results by default, 20 at most;
   - it is guarded by `InviteWorkspaceMember`;
   - a workspace with no organization gets the same empty answer.
   Someone from another organization is added with "Create user" by typing their exact email.
6. **The pending invitations become people** (`services/invites/migration.py`). The move runs once, in the background after the API starts, under an advisory lock, and is recorded in `iam_migrations` (`invitations_to_people_v1`). `abi user migrate-invitations --apply` runs it again. For each person (an email at one provider):
   - A row that already holds the email is linked.
   - Otherwise, an account the provider proves at each sign-in (`builtin`) or one Nexus made (`provisioned_identities`) is bound now: its IAM user is the row's id.
   - Anything else is an **unbound** row naming the invitation's provider: `provisioning: none`, an account the person made at Zitadel or Keycloak themselves, or no account at all.
   - The pending grants the invitation held are attached as `api` for nobody, because they were authorized when the invitation was made. A role never lowers one that is already held.
   - The grants are then withdrawn, the invitation's organization profile is written, and the invitation is marked `migrated`.
   - A provider that does not answer keeps its invitations pending. They work as before and move at the next attempt.
   - Revoked and accepted invitations are left alone.
7. **A row that names its provider is bound by a verified sign-in there**, whatever the provider (`services/oidc` `_may_bind`). This covers an invitation's unbound row, a moved invitation, and the configuration's people. It amends the "built-in provider only" rule for the old login's rows: a row that names no provider still links only through the built-in provider. A seeded person who signs in through Zitadel or Keycloak used to get `email_in_use`. Now they open their account there.

## Consequences

- **Privacy: linking another organization's account.** Inviting an email that already has a platform account links it. The person is then in the inviting organization's directory, so that organization's admins see their **name and email**, and their avatar. Nothing else about them is shared: not their other organizations, and not their workspaces elsewhere. The inviting admin learns only that the address is valid, which they knew already, since they typed it. This is accepted because the alternative, a second account for the same address, splits a person's access and breaks sign-in.
- **No account discovery through the answers.** Created and linked people get the same answer shape. A route never says whether an account existed. Search returns only people who are already in the caller's organization directory. Someone outside the directory gets the same 404 as an unknown id.
- **Rate limits are kept.** The per-inviter and per-address limits of the invite routes, and the organization's `invitation_mails_per_day`, bound how many addresses an admin can probe or mail. Resend counts against them too. `PeopleService` applies no limit itself, so the routes do (`services/people/AGENTS.md`).
- **The trust of a binding equals a pending grant's claim:** a verified email at the provider the row names. The move binds an account at once only when no sign-in is needed to trust it: one the built-in provider proves with a code at each sign-in, or one Nexus made, whose address only its owner verifies. A Zitadel or Keycloak account that someone else made waits for a verified sign-in, as its pending grant did. The configuration's people are never bound before their sign-in.
- **The organization directory is as large as the workspaces' membership.** Org analytics (#1553) must read it, which happens at the epic → main merge.
- The `invitations` table and `services/invites` stay for the transition: listing, resending and revoking what the move left pending, the IdP group bindings, and the sign-in claim of pending grants made by `abi iam invite`. A later release can remove them once no deployment has pending invitations.
- Upgrading changes what admins see. Pending invitations become invited users (release notes in `libs/naas-abi/CHANGELOG.md`). Adding a person to a workspace no longer makes them an organization member.
