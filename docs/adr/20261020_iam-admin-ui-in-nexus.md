# The IAM admin pages in Nexus

Status: Accepted

Date: 2026-10-20

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §3, §8 and §11.
Builds on: [`20261019_nexus-authorization-on-iam.md`](20261019_nexus-authorization-on-iam.md), [`20261019_delegated-tokens-and-api-keys.md`](20261019_delegated-tokens-and-api-keys.md).

## Context

Step 12. IAM can create, read, update and delete principals, groups, service accounts, policies and
attachments, explain a decision, and approve module permission manifests, but only the CLI and the SDK reach those
operations. Admins need them in Nexus: policies, who holds them, groups, service accounts and their keys, the
approvals modules wait for, an access simulator and the history of every change.

## Decision

1. **The pages are IAM calls made as the signed-in user.** `services/iam_admin` binds the engine's IAM service to
   the user's own `CallContext` (their IdP groups included) and calls it in process. IAM's `iam:*` actions decide each
   page and button; Nexus adds no role check and no list of "who is an admin". `GET /api/iam/admin/access` asks IAM
   which actions the caller holds, so the pages show only what will answer. `api` keeps its enumerated statements:
   acting as the user is what keeps `api` out of IAM's administration.
2. **Two places, one API.** Attachments are the one IAM type placed in an org and workspace, so an org admin holds
   `iam:ListAttachments`, `AttachPolicy` and `DetachPolicy` at their scope and nothing else of IAM. Org settings →
   Access manages attachments at the org and its workspaces (the policies offered are the ones the caller may attach
   there: `GET /attachable-policies`). Everything else (policies, groups, service accounts and keys, approvals,
   simulator, audit) is platform-level and lives in the System app's Access tab, available to whoever holds the
   matching actions. Both use the same routes; the scope is a parameter.
3. **Every change is audited, fail-closed.** The System app's `run_audited` and `audit_logs` table are reused: a
   `requested` record is written first and nothing changes if it cannot be (503); `succeeded` or `failed` (the
   exception type only) follows. IAM's records are the rows `iam.<operation>` (`SqlAdminAuditLog` takes the action
   prefix), with the actor, the operation, the resource and a short detail (a name, a scope), never a key's value
   or a policy's text. A refused attempt is a record too. The history is read by whoever may read the System app
   (`nexus:ReadSystem`).
4. **Policies are edited visually or as text, and IAM validates both.** The editor autocompletes actions from the
   registered catalogs and resources from the name grammar; the text view takes YAML or JSON. `POST
   /policies/validate` returns every error IAM lists (and the normalized document), so the editor shows them as
   the user types and a save refused for them says the same.
5. **Keys are shown once.** Creating or rotating a service account's key returns its value in that one answer
   (`Cache-Control: no-store`); IAM keeps a hash, the audit and every list never carry it, and the page holds it in
   component state until dismissed.
6. **A manifest is approved as submitted, narrowed or rejected, never widened.** IAM's `approve_manifest` accepts any
   valid document, so the API checks the narrowing itself (`narrowing.py`): an Allow statement may lose actions and
   resources, none may gain or appear, and Deny statements stay exactly as submitted (dropping one widens).
7. **The simulator is `explain`.** "Can X do Y on Z" is IAM's `explain` on the principal (`iam:Explain`): the answer
   names the deciding side, policy, statement, attachment, scope and group, and shows the statement when the caller
   may read its policy.
8. **The routes take a session only** (the `/api/iam/` prefix): an API key cannot administer permissions.

## Consequences

- A user holding a custom role with only `iam:ListPolicies` gets exactly that page; a stranger gets 403 on all of them.
  The API tests prove each page against the matching action, and the route matrix reads every route's declared action.
- The System app tab is reached through the System app, which still requires `nexus:ReadSystem`; a delegated IAM
  admin without it has the API and the CLI but not the tab.
- A page's list is empty-or-403: a caller who may list nothing is told so instead of seeing an empty page.
- Group and service-account deletion keep the id (IAM's rule); the lists hide deleted ones.
- Membership changes made from the Users page (`MEMBERSHIPS`) and invitations are audited by their own routes, not
  by this log; every change made through the IAM admin pages is.
