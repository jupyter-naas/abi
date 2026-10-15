# IAM starts enforcing-ready, with named transitional grants

Status: Accepted

Date: 2026-10-15

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §7, §11 and §13.
Builds on: [`20261013_iam-kernel-service.md`](20261013_iam-kernel-service.md), [`20261013_authorization-policy-model.md`](20261013_authorization-policy-model.md).

## Context

**Subtask 3 of #44 builds the IAM service; later subtasks make services enforce it.** Once subtasks 4 and 5
add checks, every caller is denied unless a policy allows it. At that point:

- **Nexus and the engine call as `api` and `engine`.** Their enumerated policies come with subtask 11 (#65),
  after the Nexus catalog exists.
- **Remote modules call as their module name.** Stage 1 tokens carry `sub` = the module name, and IAM has
  no record of them. Service accounts, keys and approved manifests come with subtask 6 (#60). The engine
  never sees a remote module's declared services: they stay in the SDK process.
- **Nexus users are named by their Nexus id.** Nexus calls `api` on behalf of `user-<12 hex>`. Users keyed by
  `(issuer, sub)` come with the OIDC providers of subtask 7 (#61).
- **`users[].is_superadmin` lives in the Nexus module's configuration**, which core does not read.

Without grants for these callers, the branch would stop working the moment a service enforces.

## Decision

**Zero trust holds in the evaluator: no code path bypasses it.** The callers above get managed policies,
attached or implicit, each named TRANSITIONAL in the code, in its description and here.

1. **`builtin.engine` and `builtin.api` (TRANSITIONAL, removed by subtask 11).**
   - One statement each, sid `TransitionalBroadAccess`: `*` on `*`.
   - They are attached at boot to the `engine` and `api` service accounts.
   - Seals still hold. On behalf of a user, the user still bounds every call (§5.3).
2. **`builtin.transitional.module` (TRANSITIONAL, replaced by approved manifests in subtask 6).**
   - It is held implicitly by a service account IAM has no record of and that is not a built-in one: today,
     a remote module.
   - It allows the module's own namespaces: `document:*` on `abi:-:-:document:{namespace,collection,document}/${principal.id}…`
     and `dataset:*` on its dataset namespace. `${principal.id}` is the module's name until subtask 6.
   - It allows every action of the kernel services a module can declare (object storage, key-value, secret,
     cache, vector store, triple store, event, activity log, email, model registry, discovery, source control,
     coding environment), on any resource. Its declared services are not visible to the engine, so it gets
     all of them.
   - It allows nothing on `iam:*`.
   - Once IAM records the account (subtask 6 creates it), the implicit policy stops: the account holds what
     is attached to it.
   - Engine-hosted modules have no identity of their own: in process they act as their caller, and over
     NATS as `engine`. So they need nothing more.
3. **Nexus users through a legacy issuer (TRANSITIONAL, until subtask 7).**
   - A user named on a call by an id that is not an IAM id resolves to IAM's user of issuer
     `urn:abi:nexus` (`LEGACY_NEXUS_ISSUER`) with that id as subject.
   - Nexus seeding records its configured users that way. It attaches `builtin.platform_admin` to each
     `users[].is_superadmin` and detaches it when the flag goes, as `is_superadmin` itself is reconciled.
4. **`builtin.transitional.user` (TRANSITIONAL, removed by subtask 11). Added by subtask 5.**
   - Nexus calls run as `api` on behalf of the user, so the user must be allowed too (§5.3). A Nexus user
     holds no role until subtask 11 attaches the roles of its memberships, so without this every Nexus call
     of a user who is not a platform admin would be denied once a service enforces.
   - It is held implicitly by a user named by a Nexus id rather than an IAM id (`usr_…`): the legacy users
     of item 3, recorded or not.
   - It allows every action of the kernel services a module can declare, plus document and dataset, on any
     resource: Nexus keeps deciding what such a user may do, with its own membership checks, as before
     IAM. It allows nothing on `iam:*`. Seals and explicit Denies hold.
   - Users with IAM ids (OIDC users from subtask 7, test principals) never hold it: they get only what is
     attached, so the user side of a call is real for them today.
5. **`builtin.self` is implicit.** Every user holds it without an attachment row, unknown users included.
   `explain` shows such a statement with no attachment id.
6. **Storage as built.**
   - One SQL implementation on SQLAlchemy Core serves SQLite and PostgreSQL.
   - The Docker templates reuse the deployment database through its `POSTGRES_*` secrets, in schema
     `abi_iam`, as the document service does. A deployment that predates this change then needs no new
     secret. `IAM_POSTGRES_DSN` stays possible, through `services.iam.store.dsn`.
7. **IAM creates users with `iam:CreateUser`.** This admin action is added to the `iam` catalog (RFC §6.4).
   Token exchange (subtask 8) will hold it as `engine`.

## Consequences

- **Subtasks 4 and 5 can enforce without breaking anything.** Existing remote modules, Nexus and engine
  jobs keep working, and `make demo-sdk` keeps passing.
- **Removing the grants is mechanical.** Search for `TRANSITIONAL`, `TransitionalBroadAccess`,
  `builtin.transitional.module`, `builtin.transitional.user` and `LEGACY_NEXUS_ISSUER`:
  - subtask 6 deletes the implicit module policy;
  - subtask 7 deletes the legacy issuer and migrates its users;
  - subtask 11 replaces `builtin.engine` and `builtin.api`, and deletes `builtin.transitional.user` once
    memberships are role attachments.
- **Until then a remote module is broader than its declared services.** Any token holder can already sign
  as `api` with the shared Stage 1 secret, so this widens nothing that is not already open. Subtask 6
  closes both.
- **Zero trust is visible today.**
  - A known principal with no policy is denied.
  - A remote module is refused every IAM administration endpoint; the standalone module demo checks it.
