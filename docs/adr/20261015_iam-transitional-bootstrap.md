# IAM starts enforcing-ready, with named transitional grants

**Final state.** None of the transitional grants below exists any more; this ADR is kept as the history of
how the branch moved to zero trust.

- `builtin.engine` and `builtin.api` are enumerated statements, each with a `sid` that says what needs it
  (`services/iam/roles.py`). Neither is `*` on `*`.
- `builtin.transitional.module` and `builtin.transitional.nexus_user` are retired: IAM drops them, and what
  was attached, at boot (`RETIRED_POLICIES`). A remote module is a service account that holds
  `builtin.module_bootstrap`, then the managed policy of its approved manifest. A Nexus user holds the roles
  of its memberships only.
- The one thing kept is the legacy issuer `urn:abi:nexus` (`LEGACY_NEXUS_ISSUER`): the issuer of the accounts of
  the old Nexus login, kept while they link to an identity provider at their first sign-in.

Status: Accepted. Amended 2026-10-15 (step 6): `builtin.transitional.module` and the implicit module policy
are removed. A remote module is a service account `module/<project>/<module_id>`, holds
`builtin.module_bootstrap` until its manifest is approved, and then its managed policy
`module.<project>.<module_id>` (see
[`20261013_engine-tokens-service-accounts-broker.md`](20261013_engine-tokens-service-accounts-broker.md)).

Amended 2026-10-19 (step 11): `builtin.engine` and `builtin.api` are enumerated statements, and
`builtin.transitional.nexus_user` is removed (IAM retires it at boot): a Nexus user holds the roles of its
memberships only. See [`20261019_nexus-authorization-on-iam.md`](20261019_nexus-authorization-on-iam.md).

Date: 2026-10-15

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §7, §11 and §13.
Builds on: [`20261013_iam-kernel-service.md`](20261013_iam-kernel-service.md), [`20261013_authorization-policy-model.md`](20261013_authorization-policy-model.md).

## Context

**Step 3 builds the IAM service; later steps make services enforce it.** Once steps 4 and 5
add checks, every caller is denied unless a policy allows it. At that point:

- **Nexus and the engine call as `api` and `engine`.** Their enumerated policies come with step 11,
  after the Nexus catalog exists.
- **Remote modules call as their module name.** Stage 1 tokens carry `sub` = the module name, and IAM has
  no record of them. Service accounts, keys and approved manifests come with step 6. The engine
  never sees a remote module's declared services: they stay in the SDK process.
- **Nexus users are named by their Nexus id.** Nexus calls `api` on behalf of `user-<12 hex>`. Users keyed by
  `(issuer, sub)` come with the OIDC providers of step 7.
- **`users[].is_superadmin` lives in the Nexus module's configuration**, which core does not read.

Without grants for these callers, the branch would stop working the moment a service enforces.

## Decision

**Zero trust holds in the evaluator: no code path bypasses it.** The callers above get managed policies,
attached or implicit, each named TRANSITIONAL in the code and its description while it lasted.

1. **`builtin.engine` and `builtin.api` (TRANSITIONAL, removed by step 11).**
   - One statement each, sid `TransitionalBroadAccess`: `*` on `*`.
   - They are attached at boot to the `engine` and `api` service accounts.
   - Seals still hold. On behalf of a user, the user still bounds every call (§5.3).
2. **`builtin.transitional.module` (TRANSITIONAL, replaced by approved manifests in step 6).**
   - It is held implicitly by a service account IAM has no record of and that is not a built-in one: today,
     a remote module.
   - It allows the module's own document namespace: `document:*` on
     `abi:-:-:document:{namespace,collection,document}/${principal.id}…`, and the shared dataset namespace below.
   - It allows every action of the kernel services a module can declare (object storage, key-value, secret,
     cache, vector store, triple store, event, activity log, email, model registry, source control, coding
     environment), on any resource, and discovery as item 4 says. Its declared services are not visible to the
     engine, so it gets all of them. Step 5 denies it `discovery:Evict`: evicting another module's
     registration is the platform's.
   - **Step 4** (data services) made it hold while it lasted, and what it learned carries over to the
     approved manifests of step 6: a module's only dataset namespace is the shared `default` one (a `module_id`
     is not a dataset identifier), and unchecked dataset SQL (`dataset:QueryUnchecked`) is denied to it,
     since it reads files on the engine host. step 6's default dataset manifest says the same, with the Deny
     `NoDatasetAdmin`.
   - It allows nothing on `iam:*`.
   - Once IAM records the account (step 6 creates it), the implicit policy stops: the account holds what
     is attached to it.
   - Engine-hosted modules have no identity of their own: in process they act as their caller, and over
     NATS as `engine`. So they need nothing more.
3. **Nexus users through a legacy issuer (TRANSITIONAL, until step 13).** Users of an identity provider
   are IAM users named by their principal id since step 7
   ([`20261015_nexus-oidc-sessions.md`](20261015_nexus-oidc-sessions.md)); the built-in login's users keep
   this issuer until they move to the built-in IdP.
   - A user named on a call by an id that is not an IAM id resolves to IAM's user of issuer
     `urn:abi:nexus` (`LEGACY_NEXUS_ISSUER`) with that id as subject.
   - Nexus seeding records its configured users that way. It attaches `builtin.platform_admin` to each
     `users[].is_superadmin` and detaches it when the flag goes, as `is_superadmin` itself is reconciled.
4. **`builtin.transitional.nexus_user` (TRANSITIONAL, removed by step 11). Added by steps 4 and 5.**
   - Nexus calls run as `api` on behalf of the user, so the user must be allowed too (§5.3). A Nexus user
     holds no role until step 11 attaches the roles of its memberships, so without this every Nexus call
     of a user who is not a platform admin would be denied once a service enforces.
   - It is held implicitly by a user Nexus names on a call: IAM's user of issuer `urn:abi:nexus`, or a Nexus
     id IAM has no record of. These are the legacy users of item 3.
   - A user of an identity provider holds it by attachment: Nexus attaches it at each sign-in (step 7),
     and step 11 detaches it with the rest.
   - It allows every action of the kernel services a module can declare, plus document and dataset, on any
     resource: Nexus keeps deciding what such a user may do, with its own membership checks, as before
     IAM. It allows nothing on `iam:*`. Seals and explicit Denies hold. It denies `dataset:QueryUnchecked`
     (sid `TransitionalNoUncheckedSql`), as step 6's default dataset manifest does: a Nexus user's dataset SQL is
     always checked.
   - Discovery is the exception, for both transitional grants: they reach every module, agent, model, app
     and job, but agent runs only on `run/${principal.id}/*` and `run/${user.id}/*` (its own, and those of
     the user it acts for, whom a run started for a user belongs to), so no holder reads or cancels another
     principal's run. Discovery is therefore not in the list of kernel services granted `<service>:*`; both
     policies take it from `_transitional_discovery()` alone, and adding `discovery` back to that list would
     grant every run again.
   - Registering is bound by discovery itself: a live module id belongs to the principal of its instances,
     and renewing or unregistering needs the instance's lease. A module id nobody holds can still be
     registered by any transitional module, until step 6's `module/<project>/<module_id>` accounts
     register only their own module and this grant goes.
   - Users with IAM ids (OIDC users from step 7, test principals) never hold it: they get only what is
     attached, so the user side of a call is real for them today.
5. **`builtin.self` is implicit.** Every user holds it without an attachment row, unknown users included.
   `explain` shows such a statement with no attachment id.
6. **Storage as built.**
   - One SQL implementation on SQLAlchemy Core serves SQLite and PostgreSQL.
   - The Docker templates reuse the deployment database through its `POSTGRES_*` secrets, in schema
     `abi_iam`, as the document service does. A deployment that predates this change then needs no new
     secret. `IAM_POSTGRES_DSN` stays possible, through `services.iam.store.dsn`.
7. **IAM creates users with `iam:CreateUser`.** This admin action is added to the `iam` catalog (RFC §6.4).
   Token exchange (step 8) will hold it as `engine`.

## Consequences

- **Steps 4 and 5 can enforce without breaking anything.** Existing remote modules, Nexus and engine
  jobs keep working, and `make demo-sdk` keeps passing.
- **Removing the grants was mechanical.** It was done by searching for `TRANSITIONAL`, `TransitionalBroadAccess`,
  `builtin.transitional.module`, `builtin.transitional.nexus_user` and `LEGACY_NEXUS_ISSUER`:
  - step 6 deletes the implicit module policy;
  - step 7 deletes the legacy issuer and migrates its users;
  - step 11 replaces `builtin.engine` and `builtin.api`, and deletes `builtin.transitional.nexus_user` once
    memberships are role attachments.
- **Until step 6 a remote module was broader than its declared services.** Any token holder could already sign
  as `api` with the shared Stage 1 secret, so this widened nothing that was not already open. Step 6
  closed both.
- **Zero trust is visible today.**
  - A known principal with no policy is denied.
  - A remote module is refused every IAM administration endpoint; the standalone module demo checks it.
