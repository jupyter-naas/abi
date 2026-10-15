# IAM Service - AGENTS.md

## Purpose

Who may do what, for every kernel service: principals (users, groups, service
accounts), AWS-style policies, attachments, built-in roles, placements, scopes,
action catalogs, and the evaluator that decides. It is the authorization half of
the identity and authorization RFC
([`docs/specs/rfcs/20261013_identity-and-authorization.md`](../../../../../docs/specs/rfcs/20261013_identity-and-authorization.md),
§2 to §7 and §11); authentication stays with the identity providers.

- **Deny by default.** Nothing is allowed without a matching Allow, for every
  principal, `engine` and `api` included. An explicit Deny always wins.
- **One check for every caller.** Domain services call `iam.require` and
  `iam.filter`; both read the caller from the current `CallContext`
  (`engine/call_context.py`), set by primary adapters from verified credentials.
  Never take identity from a request field.
- **IAM authorizes itself** with its own `iam:*` catalog (`iam_catalog.py`).

No service enforces yet: subtasks 4 and 5 of #44 add the checks.

## Files

| File | Role |
|---|---|
| `names.py` | Canonical names `abi:<org>:<ws>:<service>:<type>/<id>`, id encoding, `*`/`?` matching, variables |
| `catalog.py` | `ActionCatalog`, `ResourceType`, `ActionSpec`, `CatalogRegistry` (RFC §6.2 format) |
| `policy.py` | Policy documents: schema, validation (every error listed), `Statement` |
| `evaluator.py` | The algorithm of RFC §5.3: `check`, `filter`, `explain` over a `PolicySource` |
| `roles.py` | Built-in managed policies generated from the catalogs, and the TRANSITIONAL ones |
| `iam_catalog.py` | IAM's own `iam:*` catalog and the code-declared seals (§11.3) |
| `IAMPorts.py` | Records, errors, `IAMStore`, `IAuthorizer`, `PolicySource`, `IIAMService` |
| `IAMService.py` | The domain service: decisions, cached effective policies, self-authorized CRUD, bootstrap |
| `IAMFactory.py` | Composition: store + authorizer + bootstrap; SQLite/PostgreSQL/memory helpers |
| `adapters/secondary/iam_sql.py` | The SQL store on SQLAlchemy Core, shared by SQLite and PostgreSQL |
| `adapters/secondary/IAMStoreSQLite.py`, `IAMStorePostgreSQL.py`, `IAMStoreMemory.py` | Store adapters |
| `adapters/secondary/authorizer__policy.py`, `authorizer__allow_all.py` | Authorizer adapters |
| `adapters/secondary/IAMSecondaryAdapterNATSClient.py` | `IIAMService` over NATS, for client-role engines |
| `adapters/primary/iam__primary_adapter__NATS.py` | `abi.iam.v1.*` endpoints and `abi.iam.v1.changed` |
| `adapters/iam_nats_codec.py` | Records and errors on the wire, shared by both NATS sides |
| `tests/iam__secondary_adapter__generic_test.py` | The `IAMStore` contract every adapter passes |
| `tests/iam_harness.py`, `conftest.py` | A bootstrapped service on the memory store, and helpers |

## Ports

**`IAMStore`** (secondary): principals (unique `(issuer, subject)` for users,
unique service-account names), static group members, IdP group mappings,
policies with optimistic revisions, attachments (unique per policy, principal
and scope), placements, scopes and catalogs. Every write bumps `revision()` in
the same transaction; `install_id()` is generated once. Errors:
`IAMNotFoundError`, `IAMConflictError`, `RevisionConflictError`. The store is not
the Document Service: IAM authorizes that.

**`IAuthorizer`** (shaped like OpenFGA): `check(ctx, action, resource)` →
`Decision(allowed, visible, reason)`, `filter(ctx, action, resources)` →
`FilterResult(allowed, prefix_hints)`, `explain(ctx, action, resource)` →
`Explanation` naming the deciding statement (side, policy, statement index or
`sid`, attachment, scope, group). The `policy` adapter reads a `PolicySource`
(implemented by `IAMService`); a relationship-based adapter can replace it
without touching callers.

**`IIAMService`**: what callers use, implemented in process by `IAMService` and
over NATS by `IAMSecondaryAdapterNATSClient`. `require` is defined once, on the
port, from `authorize`.

## Evaluation

- Reasons: `allow`, `explicit_deny`, `implicit_deny`, `suspended`, `sealed`.
- An inactive actor or OBO user (`suspended`, `deleted`) is denied everything.
- A sealed resource opens to its owner only (the actor, never through OBO).
- On behalf of a user both sides must be allowed; a token's `abi_scope`
  (`CallContext.scope`, Allow statements whose `actions` and `resources` are
  lists of strings; anything else matches nothing) narrows further.
- Variables: `${scope}` (the attachment's), `${principal.id}` (the principal
  being evaluated, never a group, percent-encoded as one segment), `${user.id}`
  (the call's user). An unresolved variable makes its pattern match nothing.
- `require` raises `PermissionDeniedError` when the caller can see the resource
  (some action of its service on its type is allowed), otherwise the caller's
  `not_found()` (the service's own not-found error), else `ResourceNotFoundError`.
- `filter` keeps input order; `prefix_hints` are literal prefixes every allowed
  item starts with (`[""]` means no push-down, `[]` means nothing is allowed).
  Denies apply after the push-down.

## Service API

```python
iam = engine.services.iam  # IIAMService, no dependency declaration needed

iam.require("triple_store:Query", name, not_found=lambda: GraphNotFound(iri))
allowed = iam.filter("triple_store:ListGraphs", names).allowed
iam.authorize(action, resource)  # Decision
iam.explain(action, resource, principal_id=...)  # needs iam:Explain on the principal
```

Administration (each needs its `iam:*` action): `ensure_user`,
`create_service_account`, `get_principal`, `list_principals`,
`suspend_principal`, `resume_principal`, `delete_principal` (keeps the id, drops
attachments and memberships), groups (`create_group`, `add_group_member`,
`map_idp_group`, ...; groups cannot contain groups), policies (`create_policy`
validated against the registered catalogs, `update_policy(expected_revision=)`;
managed policies are IAM's alone), `attach_policy`/`detach_policy` (idempotent;
a policy naming `${scope}` needs a scoped attachment, and only a policy whose
every Allow resource pattern starts with `${scope}:` may be attached at a scope,
so whoever may attach at a scope cannot grant beyond it; `update_policy` refuses
to widen a policy attached at a scope, and evaluation enforces the rule anyway:
a statement reached through a scoped attachment keeps only its `${scope}:`
Allow patterns, `policy.within_scope`), placements
(`put_placement`, `resolve_placement`: exact key, then the longest prefix, else
platform), scopes (`put_scope`, `workspace_org`), `register_catalog` (highest
version wins; refuses dropping an action a policy names).

Lists page after filtering. Names: `principal_resource`, `group_resource`,
`policy_resource`, `attachment_resource` (at the attachment's scope; an org-wide
one in workspace `%2A`, `names.ALL_WORKSPACES`, which `abi:<org>:*` grants reach
and org-level `abi:<org>:-` ones do not; an unscoped one is `abi:%2A:%2A:…`,
`names.ALL_ORGS`, which no `${scope}` expands to, `abi:-:-` included, so only
the platform admin's grants reach it; no other resource may use `%2A`), `placement_resource`, `scope_resource`,
`catalog_resource`.

**Caching.** Effective statements per principal, policies and placements are
cached for at most `cache_ttl_seconds` (60) and dropped on every change made
through the service. Listeners (`add_change_listener`) hear each new revision;
the NATS primary publishes it on `abi.iam.v1.changed` (`ChangeEvent`).

## Built-in policies (`roles.py`)

- `builtin.viewer` ⊆ `member` ⊆ `admin` ⊆ `owner`, generated by access level for
  every placed resource type of every registered catalog, at `${scope}`; personal
  types through `${principal.id}`; never the `nexus` `feature` type. Admins
  attach and detach every role but owner. Regenerated when a catalog changes.
- `builtin.platform_admin`: `*` on `*` (seals still hold).
- `builtin.self`: held implicitly by every user (RFC §7 "Self" column).
- `builtin.platform.viewer` / `.member`: attached and detached by IAM in step
  with workspace and org-wide role attachments.
- `builtin.idp`: the built-in IdP's own namespace, secrets and sender.
- Feature policies (`builtin.features.*`) come with the Nexus catalog (#65).

**TRANSITIONAL** (named so in the code and in
[ADR 20261015_iam-transitional-bootstrap](../../../../../docs/adr/20261015_iam-transitional-bootstrap.md)):

- `builtin.engine`, `builtin.api`: one `TransitionalBroadAccess` statement each,
  until subtask 11 (#65) enumerates them.
- `builtin.transitional.module`: held implicitly by a service account IAM has no
  record of (a remote module, whose token names it): its own document and
  dataset namespaces, and the kernel services a module can declare. Replaced by
  approved manifests in subtask 6 (#60).
- `LEGACY_NEXUS_ISSUER` (`urn:abi:nexus`): a Nexus user named on a call by its
  Nexus id resolves to IAM's user of that issuer, until OIDC providers (#61).

## Adapters and configuration

```yaml
services:
  iam:
    store:
      adapter: sqlite              # sqlite (default) | postgres | memory
      path: storage/iam/iam.sqlite
      # dsn: "postgresql://..."   # postgres: an existing database
      # schema: abi_iam
    authorizer: policy             # policy (default) | allow_all (explicit opt-out; warns at boot)
    modules:                       # reserved for #60: validated, not read yet
      auto_approve: false
    tokens:                        # reserved for #60 and #62: validated, not read yet
      access_ttl_seconds: 600
      key_rotation_days: 30
    cache_ttl_seconds: 60
```

- SQLite: WAL, a busy timeout, `BEGIN IMMEDIATE` for writes. The default for
  `abi dev`.
- PostgreSQL: SQLAlchemy on psycopg 3, tables in their own schema, created at
  boot. The Docker templates reuse the deployment's `POSTGRES_*` secrets.
- Memory: tests.
- `allow_all` is selected only by writing it; `AllowAllAuthorizer` warns when built.

The engine loads IAM before every other service and bootstraps it
(`IAMService.bootstrap`: catalog, managed policies, the `engine`, `api` and `idp`
service accounts and their policies). A serving engine gives its modules the IAM
owner itself, never a NATS facade: a check reads the caller's `CallContext` in
this process. A client-role engine gets `IAMSecondaryAdapterNATSClient`.
Nexus seeding turns `users[].is_superadmin` into a `builtin.platform_admin`
attachment (`org_seed.sync_platform_admins`).

## NATS and SDK

Proto `naas-abi-proto/naas_abi_proto/iam/v1/iam.proto`, subjects
`abi.iam.v1.<operation>`. Wire codes: `PERMISSION_DENIED`, `NOT_FOUND`,
`CONFLICT`, `REVISION_CONFLICT`, `INVALID_ARGUMENT`. The SDK facade is
`engine.services.iam` (`naas_abi_sdk/services/iam.py`), reachable without a
dependency declaration; records are dictionaries.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/iam -q
uv run pytest libs/naas-abi-core/naas_abi_core/engine/engine_configuration/EngineConfiguration_IAMService_test.py -q
IAM_TEST_POSTGRES_DSN='postgresql://localhost/test' uv run pytest libs/naas-abi-core/naas_abi_core/services/iam -q
```

PostgreSQL tests use `IAM_TEST_POSTGRES_DSN` (or `DOCUMENT_TEST_POSTGRES_DSN`),
create a random schema and drop it; without either they skip. NATS tests need
`nats-server` on `PATH` and skip otherwise.

## Adding a new adapter

A store: implement every `IAMStore` method, subclass `IAMStoreContract` with a
`store` fixture, run it against a real backend, then add it to
`IAMStoreConfiguration` and this guide. An authorizer: implement `check`,
`filter` and `explain` of `IAuthorizer`, keep `visible` and the prefix hints
meaningful, and wire it through `IAMFactory.authorizer_factory`.
