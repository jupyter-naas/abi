# IAM Service - AGENTS.md

## Purpose

Who may do what, for every kernel service: principals (users, groups, service
accounts), AWS-style policies, attachments, built-in roles, placements, scopes,
action catalogs, and the evaluator that decides. It is the authorization half of
the identity and authorization RFC
([`docs/specs/rfcs/20261013_identity-and-authorization.md`](../../../../../docs/specs/rfcs/20261013_identity-and-authorization.md),
§2 to §11). It also authenticates service accounts: their keys, the engine's
ES256 tokens and JWKS, module permission manifests and the broker permissions
derived from them (§8, §9.1). User login stays with the identity providers.

- **Deny by default.** Nothing is allowed without a matching Allow, for every
  principal, `engine` and `api` included. An explicit Deny always wins.
- **One check for every caller.** Domain services call `iam.require` and
  `iam.filter`; both read the caller from the current `CallContext`
  (`engine/call_context.py`), set by primary adapters from verified credentials.
  Never take identity from a request field.
- **IAM authorizes itself** with its own `iam:*` catalog (`iam_catalog.py`).

Every kernel service enforces. The data services (object storage, document,
key-value, secret, cache, vector store, triple store and dataset; subtask 4 of
#44) use `enforcement.py`; the runtime services (event, activity_log, email,
model_registry, discovery, source_control, coding_environment; subtask 5) use
`guard.py`. Each has its catalog in `services/<name>/iam_catalog.py` (see
"Enforcing in a domain service" and "Enforcing in a data service").

## Files

| File | Role |
|---|---|
| `names.py` | Canonical names `abi:<org>:<ws>:<service>:<type>/<id>`, id encoding, `*`/`?` matching, variables |
| `catalog.py` | `ActionCatalog`, `ResourceType`, `ActionSpec`, `CatalogRegistry` (RFC §6.2 format) |
| `policy.py` | Policy documents: schema, validation (every error listed), `Statement` |
| `evaluator.py` | The algorithm of RFC §5.3: `check`, `filter`, `explain` over a `PolicySource` |
| `roles.py` | Built-in managed policies generated from the catalogs, and the TRANSITIONAL ones |
| `iam_catalog.py` | IAM's own `iam:*` catalog and the code-declared seals (§11.3) |
| `guard.py` | `ServiceGuard`: how a runtime service checks (names, require, filter, create rule, placements) and the shared wire codes |
| `enforcement.py` | `ResourceGuard`, what a data service enforces with; `scan_allowed`, `own_storage`, `internal_call`, wire codes |
| `kernel_catalogs.py` | The kernel services' catalogs (`services/<name>/iam_catalog.py`), registered at boot |
| `keys.py` | Keys `abi_sk_` (service accounts), `abi_pk_` (personal), `abi_gk_` (link grants): generation, parsing, hashing |
| `exchange.py` | `TokenExchanger`: RFC 8693 token exchange (§9.4): subjects, audiences, actors, scopes, renewal |
| `tokens.py` | `TokenIssuer`: ES256 signing keys, their rotation, the JWKS and the tokens it signs |
| `modules.py` | Module accounts `module/<project>/<module_id>`, manifest hashing, variable binding, namespace placements |
| `broker.py` | `BrokerPermissions` of an account, derived from its effective policy (§8.4) |
| `IAMPorts.py` | Records, errors, `IAMStore`, `IAuthorizer`, `PolicySource`, `IIAMService` |
| `IAMService.py` | The domain service: decisions, cached effective policies, self-authorized CRUD, bootstrap |
| `IAMFactory.py` | Composition: store + authorizer + bootstrap; SQLite/PostgreSQL/memory helpers |
| `adapters/secondary/iam_sql.py` | The SQL store on SQLAlchemy Core, shared by SQLite and PostgreSQL |
| `adapters/secondary/IAMStoreSQLite.py`, `IAMStorePostgreSQL.py`, `IAMStoreMemory.py` | Store adapters |
| `adapters/secondary/authorizer__policy.py`, `authorizer__allow_all.py` | Authorizer adapters |
| `adapters/secondary/IAMSecretsSecretService.py`, `IAMSecretsMemory.py` | `IAMSecrets`: signing keys and the engine's key, under `iam/` |
| `adapters/secondary/IAMSecondaryAdapterNATSClient.py` | `IIAMService` over NATS, for client-role engines |
| `adapters/primary/iam__primary_adapter__NATS.py` | `abi.iam.v1.*` endpoints and `abi.iam.v1.changed` |
| `adapters/iam_nats_codec.py` | Records and errors on the wire, shared by both NATS sides |
| `tests/iam__secondary_adapter__generic_test.py` | The `IAMStore` contract every adapter passes |
| `tests/iam_harness.py`, `conftest.py` | A bootstrapped service on the memory store, and helpers |
| `tests/authorization_contract.py` | The contract every runtime service passes per operation: no policy, granted, denied, in process and over NATS |
| `tests/data_service_contract.py` | The data services' contract: a table of cases for no policy, granted and denied principals, list filtering, in process and over NATS |

## Ports

**`IAMStore`** (secondary): principals (unique `(issuer, subject)` for users,
unique service-account names), static group members, IdP group mappings,
policies with optimistic revisions, attachments (unique per policy, principal
and scope), placements, scopes, catalogs, keys (hashed), manifests (one row
per submitted version) and signing keys (public half and schedule). Every write bumps `revision()` in
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

**`IAMSecrets`** (secondary): IAM's own secrets, `get`/`put`/`delete` under
`iam/`: signing keys' private halves (`iam/signing-keys/<kid>`) and the engine
account's key for client-role engines (`iam/service-keys/engine`). The engine
passes the secret service built from its local adapters, never `nats_rpc`.

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
iam.allows_every(action, "triple_store", "graph")  # a safe shortcut: False when unsure
iam.explain(action, resource, principal_id=...)  # needs iam:Explain on the principal
iam.placement_of(
    service, canonical_id
)  # the covering placement, or None (serving engine)
```

`allows_every` is True only when nothing can deny: no seal on the type, no
narrowing token, no Deny naming the action, and on each side an Allow spanning
every org, workspace and id of the type (`engine`, `api` and the transitional
grants today). Services use it to skip per-item work.

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
(`put_placement`, `placement_of`: exact key, then the longest prefix, else
None; `resolve_placement`: its org and workspace, else platform), scopes (`put_scope`, `workspace_org`), `register_catalog` (highest
version wins; refuses dropping an action a policy names).

Lists page after filtering. Names: `principal_resource`, `group_resource`,
`policy_resource`, `attachment_resource` (at the attachment's scope; an org-wide
one in workspace `%2A`, `names.ALL_WORKSPACES`, which `abi:<org>:*` grants reach
and org-level `abi:<org>:-` ones do not; an unscoped one is `abi:%2A:%2A:…`,
`names.ALL_ORGS`, which no `${scope}` expands to, `abi:-:-` included, so only
the platform admin's grants reach it; no other resource may use `%2A`), `placement_resource`, `scope_resource`,
`catalog_resource`.

## Token exchange, personal keys and links (§9.3, §9.4)

```python
issued = iam.exchange_token(
    TokenExchange(subject_token, subject_token_type, audience, resource=None, scope=None)
)  # IssuedToken, 10 minutes at most
iam.revoke_tokens(user_id, include_keys=False)
iam.create_key(user_id, audience=..., resource=..., scope=..., kind=...)  # personal / grant
iam.identity_authenticator = ...  # engine wiring: IdP tokens (`IdentityAuthenticator`, services/identity/token_authenticator.py)
```

- **Requester.** The caller needs `iam:ExchangeToken` on `abi:-:-:iam:audience/<audience>`
  (only `api` and `engine` hold it, through their broad policies); the user it acts
  for, when there is one, does not decide. A module renewing the delegation it
  holds needs nothing: it only keeps what it was given.
- **Subjects** (`subject_token_type`): `id_token` / `access_token` (an IdP's, only
  for `abi:session`, via `identity_authenticator`); `…:jwt` (an engine token);
  `urn:abi:params:oauth:token-type:api_key` (`abi_pk_` or `abi_gk_`);
  `urn:abi:params:oauth:token-type:session`: a signed-in user a **first-party**
  (`api`, `engine`) vouches for, the subject token being the user's principal id,
  plus `groups` and `session_id`. Nexus names its users this way, because its
  sessions are not engine tokens.
- **Audiences.** `abi:session` and `abi:delegated:{agent,app,preview,coding,api-key}`
  (`nats_auth.EXCHANGE_AUDIENCES`). Never back to `abi:session` (an IdP's token
  only); never from one delegated audience to another; an `abi:session` token goes
  to every delegated one; a key goes to its own audience only. Key exchange
  (`exchange_key`, `abi.iam.v1.token`) still issues `abi:nats` and host tokens
  only.
- **Agent tokens** (`abi:delegated:agent`): `sub` the user, `act` the actor with
  its account name, `abi_res` the target. The actor is the module that owns
  `resource` (a discovery module, agent, app, model or job, or the module's account
  `abi:-:-:iam:principal/<sa id>`), else the requester; never a request field. Kernel
  endpoints accept `abi:nats` and this audience (`nats_auth.KERNEL_AUDIENCES`), and
  evaluate it as the module for the user: both sides must allow. The module's side
  of what it hosts is `builtin.module_bootstrap`'s `OwnHosted` / `OwnRuns`
  (`roles.DELEGATION_SIDS`), which `_derive` keeps out of its broker permissions.
  A module renews its delegation with its own token (same audience, `abi.iam.v1.exchange_token`
  is in `broker.IAM_ALWAYS`), an expired one too, until `abi_since` + 8 hours
  (`MAX_DELEGATION_SECONDS`); then it is refused.
- **Scope** (`abi_scope`, `tokens.normalize_scope`): a list of Allow statements (at most
  32, 64 patterns each). An exchange only narrows: the subject's own scope is kept,
  and a scope is not narrowed twice (a statement list has no intersection).
- **Personal keys** (`kind=personal`, user principals): `audience` `abi:delegated:api-key`
  (default; five active, a year at most, a year by default) or `abi:delegated:coding`
  with its environment as `resource` (fifty active). **Grants** (`kind=grant`,
  `abi_gk_`): `audience` app or preview, always expiring in 8 hours at most
  (a thousand active): the links of apps and previews. A key may carry `scope`.
  `iam.list_keys(owner)` lists every kind; callers filter. Users manage their own
  keys (`builtin.self`: `iam:CreateKey`, `ListKeys`, `RevokeKey` on `key/${principal.id}/*`),
  a user of the built-in login named by its Nexus id included (recorded on demand).
- **Revocation.** `revoke_tokens(principal)` sets a floor (`iam_token_floors`): every
  token of that principal issued at or before it is refused, by the verifier
  (`iam.verifier()`, `token_revoked`) and by the authorizer (a context whose
  `token_issued_at` is at or before it is `suspended`), and the principal's grants
  and coding keys are revoked (their personal API keys too with `include_keys`).
  A token made after it carries `iat` past the floor (`issue_after_floor`). Suspension
  and deletion deny a principal's tokens at once as before. `iam:RevokeTokens` is in
  `builtin.self`.
- **Groups in a token** (`grp`) are only ids of active groups (`active_groups`,
  `_is_group`): an id of a user or an account never lends its policies.

## Service accounts, keys, tokens and manifests

```python
created = iam.create_key(account_id, description="prod")  # CreatedKey: value shown once
iam.list_keys(account_id)
iam.revoke_key(account_id, key_id)
iam.rotate_key(account_id, key_id)
iam.exchange_key(value)  # IssuedToken (abi:nats, ≤ 10 min); KeyRefusedError
iam.issue_service_token("api")  # in process only: the engine's own accounts
iam.jwks()
iam.verifier()  # what every NATS primary verifies with
iam.submit_manifest(
    module_id, project, document
)  # ManifestSubmission(manifest, approved_now, in_force)
iam.approve_manifest(account_id, document=None)  # narrowed when a document is given
iam.reject_manifest(account_id, reason="...")
iam.broker_permissions(principal, key)  # records from authenticate_key; never cached
```

- **Keys.** At most five active per account; `ci/*` keys expire in 90 days by
  default. Only `sha256(secret)` is stored. Revocation takes effect at the next
  exchange and the next broker connection, which is within five minutes: the
  callout's user JWT lasts that long (ten at most) and the SDK reconnects every
  two minutes. `rotate_key` gives the new key a fresh default life and, at the
  limit of five, revokes the old key first. `last_used_at` is written at most
  once a minute.
- **Host tokens** (`abi:host:<sa>`). A call to a module host carries the
  caller's identity under the audience of that host, never its `abi:nats`
  token: a host reads the token of every request and `api` may do everything,
  and a token that named no host could be replayed at the others. Kernel
  primaries verify `abi:nats` only; discovery's `authorize_*` verifies the
  family (`for_audiences((), prefixes=(HOST_AUDIENCE_PREFIX,))`) and then
  requires the audience to be the calling host's own; the engine's job loader
  likewise for the engine; the overflow host accepts both. `exchange_key(key,
  audience)` and `issue_service_token(name, audience=...)` mint them
  (`nats_auth.host_audience(sa)`), `issue_host_token(principal, sa)` is what the
  broker control stores in a trigger (the job's host, else the engine).
- **Signing keys** retire 20 minutes after the next one signs, but their public
  half stays in the JWKS 169 hours more (`abi_retired_at`), so job triggers
  stored meanwhile still verify `at` their stored time; a retired key is never
  accepted for a token presented later. Its private half is deleted.
- **Module accounts** are `module/<project>/<module_id>` and start with
  `builtin.module_bootstrap` only: their own discovery record and their own
  manifest. Approval writes the managed policy `module.<project>.<module_id>`
  (`${module.id}`, `${module.project}` bound), attaches it, and places the
  module's document and dataset namespaces at platform level. A changed manifest
  is a new pending version while the approved one stays in force.
  `modules.auto_approve` approves on submission (the `abi dev` overlay only).
- **Signing keys** rotate every `tokens.key_rotation_days`, checked whenever a
  token is issued or the JWKS read. The JWKS names the issuer
  `urn:abi:engine:<install id>`.
- **Engine key.** `engine_service_key()` returns the key client-role engines
  exchange, kept in `IAMSecrets`; a lost one is replaced, not added to.

**Caching.** Effective statements per principal, policies and placements are
cached for at most `cache_ttl_seconds` (60) and dropped on every change made
through the service. Listeners (`add_change_listener`) hear each new revision;
the NATS primary publishes it on `abi.iam.v1.changed` (`ChangeEvent`).

## Enforcing in a domain service (`guard.py`)

```python
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.<name>.iam_catalog import CATALOG

class MyService(ServiceBase):
    def __init__(self, adapter):
        super().__init__()
        self._guard = ServiceGuard.of(CATALOG, self)

    def get(self, id):
        self._guard.require("Get", "thing", id, not_found=lambda: ThingNotFound(id))
        return self._adapter.get(id)
```

- **The owner checks, once.** The guard reads IAM from the services its domain
  service is wired with. Owners are always wired with IAM (in process and on the
  serving engine). NATS facades (the dependency container, a client engine) are
  not, so they check nothing and the owner they call checks the caller the
  request's credentials name.
- `name(type, parts)`: the canonical name, placed by `placement_of` (platform
  types are never looked up).
- `require` before the backend is touched; `allowed` without raising;
  `filter(action, type, items, parts)` for lists (limit after filtering).
- `create(action, type, parts)`: the §4.4 rule. A name an existing placement
  covers keeps it, and the call's `workspace_id` must be empty or match;
  otherwise `workspace_id` places it (`workspace_org` maps it to its org; an
  unknown workspace is "not found"). Call `.record()` once the create succeeded:
  the placements are written as `engine`, so the caller never needs
  `iam:PutPlacement`. `place_new` places a resource whose id the backend chose
  (a sent message); `forget` drops a deleted resource's placements.
- Wire: a NATS primary maps `PermissionDeniedError` and `ResourceNotFoundError`
  with `authorization_error_code`; its client raises them back with
  `raise_authorization_error`. A service's own not-found keeps its own code.
- A kernel service's own audit events go through `EventService.emit`: stamped
  with the call's user, appended as `engine`. The caller was authorized for the
  operation, not for writing the event log.
- Boot (`Engine.load`) runs as `engine`. Code that runs for no caller uses
  `as_service_account`; anything else with no context is anonymous, and denied.

## Invitations and IdP group bindings (RFC §12.2)

```python
grant = iam.create_pending_grant("builtin", "bob@example.com", "builtin.member", "abi:acme:ws1")
iam.list_pending_grants(provider=None, email=None, policy_id=None)
iam.revoke_pending_grant(grant.id)
iam.claim_pending_grants(principal_id)  # the identity service, at a sign-in

binding = iam.bind_idp_group("acme", "Data readers", "builtin.viewer", "abi:acme:ws1")
iam.unbind_idp_group("acme", "Data readers", "builtin.viewer", "abi:acme:ws1")
iam.list_idp_bindings(provider=None, policy_id=None)
```

- **A pending grant** attaches a policy at a scope to an email on one provider
  before its user exists (`PendingGrant`; table `iam_pending_grants`, unique per
  provider, email, policy and scope; the email is lower case). It is claimed at the
  first sign-in of a user **of that provider whose record has that email verified**
  (`PrincipalRecord.provider`, `email`, `email_verified`, written by `ensure_user`
  from the token): never on another provider, never on an unverified address, and
  never from an email the caller supplies, since `claim_pending_grants` reads the
  user's own record. The claim is one store step per grant
  (`IAMStore.claim_pending_grant`: delete the grant and attach, so racing sign-ins
  attach it once) and keeps the platform companions of the roles in step.
- **Authorized as the attachment it stands for.** Creating one needs
  `iam:AttachPolicy` and revoking one `iam:DetachPolicy` on
  `abi:<org>:<ws>:iam:attachment/<policy>/pending:<provider>:<email>`, so a
  workspace admin invites to that workspace and no further, nobody makes an owner
  they could not attach, and the rules of `attach_policy` (a `${scope}` policy needs
  a scope, a scoped policy stays within it) hold. Listing is filtered by
  `iam:ListAttachments` on the same names. `iam:ClaimPendingGrants` (admin on a
  principal) is the identity service's, as the engine.
- **A binding** gives the members of an IdP group a role at a scope: IAM finds or
  creates the ABI group `idp:<provider>:<claim value>` (org of the scope), maps the
  claim to it and attaches the policy to it. The caller is authorized for the
  attachment alone (`attachment/<policy>/idp:<provider>:<claim value>`): creating
  the group and its mapping is part of that one operation, so a workspace admin never
  needs `iam:CreateGroup` or `iam:MapIdpGroup`. One group serves every binding of a
  claim value; unbinding detaches at that scope only. IAM's companions of the roles
  (`builtin.platform.*` on the group) are not listed as bindings.
- A policy a pending grant names cannot be deleted. NATS: `create_pending_grant`,
  `list_pending_grants`, `revoke_pending_grant`, `claim_pending_grants`,
  `bind_idp_group`, `unbind_idp_group`, `list_idp_bindings`; the broker offers each
  with the action it needs (`AttachPolicy`, `ListAttachments`, ...).

## Built-in policies (`roles.py`)

- `builtin.viewer` ⊆ `member` ⊆ `admin` ⊆ `owner`, generated by access level for
  every placed resource type of every registered catalog, at `${scope}`; personal
  types through `${principal.id}`; never the `nexus` `feature` type. Admins
  attach and detach every role but owner. Regenerated when a catalog changes.
- `builtin.platform_admin`: `*` on `*` (seals still hold).
- `builtin.self`: held implicitly by every user (RFC §7 "Self" column).
- `builtin.platform.viewer` / `.member`: attached and detached by IAM in step
  with workspace and org-wide role attachments.
- `builtin.idp`: the built-in IdP's own namespace, secrets and sender, for the
  built-in account `idp`. By default the IdP (`libs/naas-abi-idp`) runs as the
  module account `module/<project>/idp` with its approved manifest instead; the
  seals (`Seal.module_id`) and the secret endpoint (`secret_nats_contract.is_idp`)
  name both, so the module id `idp` is reserved: an admin creates its account,
  nothing else does.
- Feature policies (`builtin.features.*`) come with the Nexus catalog (#65).

- `builtin.module_bootstrap`: a module account before approval (above).

**TRANSITIONAL** (named so in the code and in
[ADR 20261015_iam-transitional-bootstrap](../../../../../docs/adr/20261015_iam-transitional-bootstrap.md)):

- `builtin.engine`, `builtin.api`: one `TransitionalBroadAccess` statement each,
  until subtask 11 (#65) enumerates them.
- `builtin.transitional.nexus_user`: held implicitly by a user Nexus names on
  a call (IAM's user of issuer `urn:abi:nexus`, or a Nexus id IAM has no
  record of; on a Nexus call, `api` on behalf of that user). Nexus
  still decides what such a user may do, so the user side of the intersection
  allows every kernel service, document and dataset included; never `iam:*` or
  `dataset:QueryUnchecked` (a Nexus user's dataset SQL is always checked).
  It reaches discovery's modules, agents, models, apps and jobs, but only its
  holder's own agent runs. Seals and explicit Denies hold. Removed by
  subtask 11 (#65), which attaches the roles of each membership.
- `LEGACY_NEXUS_ISSUER` (`urn:abi:nexus`): a Nexus user named on a call by its
  Nexus id resolves to IAM's user of that issuer, until the built-in login's
  users move to the built-in IdP (#67). Users of an identity provider are IAM
  users named by their principal id (`services/identity`, #61); Nexus attaches
  `builtin.transitional.nexus_user` to each at sign-in, for #65 to detach.

## Enforcing in a data service (`enforcement.py`)

The data services use `ResourceGuard`, kept close to `ServiceGuard` above. A
domain service builds `ResourceGuard.of(CATALOG, self)`
(`ServiceBase.wired_iam`: the engine's IAM once the service is wired, else
None, and a service without IAM does not check: a library use, or a NATS
facade whose server checks). Then:

- `guard.require(action, type, parts, not_found=...)` before the backend is
  touched (`require_all` for a batch, one `filter`); `guard.name(type, parts)`
  places the name (`placement_of`, indexed by service).
- `guard.filter(action, type, items, parts_of)` for lists; `guard.id_prefixes`
  and `scan_allowed(...)` push the caller's prefixes down to a key scan and page
  after filtering; `guard.require_visible` checks a container before listing it.
- `guard.create(action, type, parts, container=..., exists=...,
  container_exists=...)` applies the create rule of §4.4 and returns `commit()`,
  which records the placement once the backend created the resource;
  `guard.forget` drops it on drop.
- A service's own storage in another service (the cache's entries, the activity
  log's and the agent memory's namespaces) is used through `own_storage(...)`,
  as the engine for no user and no target workspace.
- NATS primaries answer `PermissionDeniedError` as `PERMISSION_DENIED` and
  `ResourceNotFoundError` as `NOT_FOUND` (`authorization_error_code`); clients raise
  them back (`raise_authorization_error`); transfer streams map them for every
  service.
- Register the catalog: add it to `kernel_catalogs()`, which the engine
  registers at boot. Boot (`Engine.load`) runs as `engine`.
- Work that runs for no caller needs an identity, or every data service denies
  it: Nexus startup tasks and its chat ingestion jobs run as `api`, `abi chat`
  and `abi run script` as `engine` (`naas_abi_cli.cli.local_operator.as_local_operator`),
  and bus consumer threads, worker-pool jobs and the intent-index warmup as
  whoever subscribed, submitted or started them (they copy the context).
- Prove it with `tests/data_service_contract.py`: a subclass beside the domain
  service (`<Service>_authorization_test.py`) gives the hooks and the cases.

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
    modules:
      auto_approve: false          # true only in the abi dev overlay
    tokens:
      access_ttl_seconds: 600      # capped at 600
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
service accounts and their policies), then registers every kernel catalog
(`kernel_catalogs.register_kernel_catalogs`). A serving engine gives its modules the IAM
owner itself, never a NATS facade: a check reads the caller's `CallContext` in
this process. A client-role engine gets `IAMSecondaryAdapterNATSClient`.
Nexus seeding turns `users[].is_superadmin` into a `builtin.platform_admin`
attachment (`org_seed.sync_platform_admins`).

## NATS and SDK

Proto `naas-abi-proto/naas_abi_proto/iam/v1/iam.proto`, subjects
`abi.iam.v1.<operation>`. `token` (key exchange) and `jwks` need no token;
every other operation authorizes its caller. The primary also listens to
`abi.iam.v1.changed` from other processes (`abi iam`, another engine) and drops
its cache. The engine's auth callout (`engine/nats_auth_callout.py`) admits
module connections with `broker_permissions`, without response permissions.
The engine's broker control (`engine/nats_broker_control.py`,
`abi.broker.v1.<operation>`) creates the streams and consumers modules use
and writes the jobs stream for them, checked against `broker_grants`:
modules never create or change a stream or a consumer. `broker.py` documents what each grant
reaches; a bus topic under `abi`, `evt`, `_INBOX`, `triple_store`, `$` or `_` is
refused at submission and approval. A module's connection is offered `broker.IAM_ALWAYS`
only (`token`, `jwks`, `submit_manifest`, `get_manifest`,
`find_service_account`, `authorize`, `filter`); the other IAM operations need
the matching `iam:` action. Bus and event grants follow the action
(`bus:Publish` vs `bus:Consume`; `event:Append` publishes, the read actions
subscribe) and a Deny of an action on a topic is honoured. The secrets IAM keeps
(`iam/...`) are readable only by `engine` over the secret service's NATS
endpoint. Wire codes: `PERMISSION_DENIED`, `NOT_FOUND`,
`CONFLICT`, `REVISION_CONFLICT`, `INVALID_ARGUMENT`, `UNAUTHENTICATED` (a
refused key). The SDK facade is
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
