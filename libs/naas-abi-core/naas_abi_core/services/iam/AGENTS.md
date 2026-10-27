# IAM Service - AGENTS.md

## Purpose

Who may do what, for every kernel service: principals (users, groups, service
accounts), AWS-style policies, attachments, built-in roles, placements, scopes,
action catalogs, and the evaluator that decides. It also authenticates service
accounts: their keys, the engine's ES256 tokens and JWKS, module permission
manifests and the broker permissions derived from them. User login stays with
the identity providers (`services/identity`). This file is the canonical
specification of the policy engine: grammar, names and evaluation rules are
defined here, and a change to one of them changes this file in the same pull
request.

- **Deny by default.** Nothing is allowed without a matching Allow, for every
  principal, `engine` and `api` included. An explicit Deny always wins. There is
  no superuser bypass in code: `engine`, `api` and the platform admin hold
  attached policies like anyone else.
- **One check for every caller.** Domain services call `iam.require` and
  `iam.filter`; both read the caller from the current `CallContext`
  (`engine/call_context.py`), set by primary adapters from verified credentials
  (see `engine/AGENTS.md`). Never take identity from a request field.
- **IAM authorizes itself** with its own `iam:*` catalog (`iam_catalog.py`).

Every kernel service enforces. The data services (object storage, document,
key-value, secret, cache, vector store, triple store and dataset) use `enforcement.py`; the runtime services (event, activity_log, email,
model_registry, discovery, source_control, coding_environment) use
`guard.py`. Each has its catalog in `services/<name>/iam_catalog.py` (see
"Enforcing in a domain service" and "Enforcing in a data service").

## Contents

- [Files](#files), [Ports](#ports)
- The model: [Vocabulary](#vocabulary), [Principals](#principals),
  [Policy language](#policy-language), [Resource names](#resource-names),
  [Placements](#placements), [Evaluation](#evaluation),
  [Action catalogs](#action-catalogs), [Sealed resources](#sealed-resources),
  [Built-in policies](#built-in-policies), [Module scopes](#module-scopes)
- Using it: [Service API](#service-api),
  [Enforcing in a domain service](#enforcing-in-a-domain-service-guardpy),
  [Enforcing in a data service](#enforcing-in-a-data-service-enforcementpy)
- Credentials: [Tokens](#tokens),
  [Token exchange, personal keys and links](#token-exchange-personal-keys-and-links),
  [Service accounts, keys, tokens and manifests](#service-accounts-keys-tokens-and-manifests),
  [Broker permissions](#broker-permissions)
- [Invitations and IdP group bindings](#invitations-and-idp-group-bindings)
- [Adapters and configuration](#adapters-and-configuration), [NATS and SDK](#nats-and-sdk)
- [Migrating an existing install](#migrating-an-existing-install), [Decisions](#decisions),
  [Known limits and open questions](#known-limits-and-open-questions)
- [Tests](#tests), [Adding a new adapter](#adding-a-new-adapter)

## Files

| File | Role |
|---|---|
| `names.py` | Canonical names `abi:<org>:<ws>:<service>:<type>/<id>`, id encoding, `*`/`?` matching, variables |
| `catalog.py` | `ActionCatalog`, `ResourceType`, `ActionSpec`, `CatalogRegistry` (catalog format) |
| `policy.py` | Policy documents: schema, validation (every error listed), `Statement` |
| `evaluator.py` | The evaluation algorithm: `check`, `filter`, `explain` over a `PolicySource` |
| `grants.py` | Grant only what you hold: glob containment of resource patterns, `Holdings` (what a caller holds, side by side), `grantable` |
| `roles.py` | Built-in managed policies generated from the catalogs, and the enumerated ones of `engine`, `api` and engine jobs |
| `iam_catalog.py` | IAM's own `iam:*` catalog and the code-declared seals |
| `guard.py` | `ServiceGuard`: how a runtime service checks (names, require, filter, create rule, placements) and the shared wire codes |
| `enforcement.py` | `ResourceGuard`, what a data service enforces with; `scan_allowed`, `own_storage`, `internal_call`, wire codes |
| `kernel_catalogs.py` | The kernel services' catalogs (`services/<name>/iam_catalog.py`), registered at boot |
| `module_scopes.py` | The `module` catalog (what modules expose, per workspace) and the checks of a catalog a module declares |
| `keys.py` | Keys `abi_sk_` (service accounts), `abi_pk_` (personal), `abi_gk_` (link grants): generation, parsing, hashing |
| `exchange.py` | `TokenExchanger`: RFC 8693 token exchange: subjects, audiences, actors, scopes, renewal |
| `tokens.py` | `TokenIssuer`: ES256 signing keys, their rotation, the JWKS and the tokens it signs |
| `modules.py` | Module accounts `module/<project>/<module_id>`, manifest hashing, variable binding, namespace placements |
| `broker.py` | `BrokerPermissions` of an account, derived from its effective policy |
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
| `tests/grant_contract.py` | Grant only what you hold: the refusals and what keeps working, in process and over NATS |

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
without touching callers. `allow_all` is an explicit opt-out that warns at boot.

**`IAMSecrets`** (secondary): IAM's own secrets, `get`/`put`/`delete` under
`iam/`: signing keys' private halves (`iam/signing-keys/<kid>`), the engine
account's key for client-role engines (`iam/service-keys/engine`) and the job
trigger seal key (`iam/job-trigger-seal`). The engine
passes the secret service built from its local adapters, never `nats_rpc`.

**`IIAMService`**: what callers use, implemented in process by `IAMService` and
over NATS by `IAMSecondaryAdapterNATSClient`. `require` is defined once, on the
port, from `authorize`.

## Vocabulary

| Term | Meaning |
|---|---|
| **Principal** | Who acts. A user, a group or a service account. |
| **Actor** | The principal that holds the credential on a call. |
| **On behalf of (OBO)** | The user an actor acts for. Optional. |
| **Action** | `<service>:<Action>`, one per operation, for example `triple_store:Query`. |
| **Resource name** | `abi:<org>:<workspace>:<service>:<type>/<id>`. |
| **Policy** | A versioned document of statements. Attached to principals. |
| **Attachment** | (principal, policy, optional scope). |
| **Placement** | The org and workspace that own a kernel resource. Recorded by IAM. |
| **Catalog** | A service's list of actions and resource types, registered at load time. |
| **Sealed resource** | A resource only one named principal can ever be allowed on. |

Authorization is identity-based only. There are no resource-based policies: a
resource never carries a policy of its own. Sharing is a statement attached to
the receiving principal.

## Principals

Three kinds. Ids are a kind prefix plus a lowercase ULID, for example
`usr_01jabcdefghjkmnpqrstvwxyz0` (`usr_`, `grp_`, `sa_`; policies are `pol_`,
attachments `att_`). Ids never change and are never reused.

**Users**

- A user is the pair `(issuer, sub)` from a verified IdP token, never an email.
  IAM creates the user on first sign-in (`ensure_user`, `iam:CreateUser`; the
  token exchange and the identity service do it as `engine`). It holds no password.
- It stores `issuer`, `sub`, the provider `name`, and the last seen `email`,
  `email_verified` and display name. Those fields are informational, except that
  a pending grant is claimed through the provider and the verified email (see
  "Invitations and IdP group bindings").
- `(issuer, sub)` is unique. Accounts are never linked automatically across
  providers: the same person through two IdPs is two principals unless an admin
  links them (`iam:LinkUser`).

**Groups**

- A group has a `name` and an **owner scope** (`owner_scope`): the platform
  (`abi:-:-`), an org (`abi:<org>:-`) or a workspace (`abi:<org>:<ws>`). Its name
  carries it (`abi:<org>:<ws>:iam:group/<id>`, see "Resource names"), so the admins
  of that level manage it. `org` is the owner's org (null for a platform group; a
  group made before owner scopes may still name one while the platform owns it).
  Groups cannot contain groups.
- **Static members** are users or service accounts, kept in IAM. A group owned by
  an org or a workspace holds only **users of that org**: users with an attachment
  of their own under `abi:<org>:…` (a role at the org, org-wide or at one of its
  workspaces). Service accounts never join one: a module's account is approved by
  its manifest. A user whose last attachment under the org is detached
  (`detach_policy`, or `delete_scope` of the workspace or org it was at) leaves the
  org's groups and its workspaces' groups. Platform
  groups take any user or service account.
- **Where it is attached.** A group owned by an org or a workspace receives
  attachments only at its owner's scope or below (an org's at the org, org-wide or
  at any of its workspaces; a workspace's at that workspace), always at a scope.
  IAM's own companions (`builtin.platform.*`, feature policies) follow its roles as
  for any principal. Platform groups receive attachments anywhere.
- **Mapped members** come from IdP group claims: a mapping `(provider name,
  claim value) -> group id` is set with `iam:MapIdpGroup`. Mappings stay the
  platform admin's, whatever owns the group: `MapIdpGroup` and `UnmapIdpGroup`
  are decided on the group's platform name, which no role reaches. At a token exchange
  IAM reads the provider's `groups_claim`, maps each value and writes the group ids
  into the engine token's `grp` claim. Mapped membership lasts as long as the
  token, ten minutes at most.
- A user's effective groups are their static groups plus the token's `grp`. A
  service account has static groups only.

**Service accounts**

A service account has a unique `name` and an optional owner (the user who
created it, for scripts and CI).

| Form | Example | Used by |
|---|---|---|
| `engine` | | Built-in, the engine process |
| `api` | | Built-in, Nexus |
| `idp` | | Built-in, the built-in IdP (when it does not run as a module) |
| `module/<project>/<module_id>` | `module/acme/people` | One per remote module |
| `ci/<name>` | `ci/nightly-export` | Scripts and CI |
| `job/<module_id>` | | The jobs of an engine module (`builtin.job`) |

Keys and manifests: "Service accounts, keys, tokens and manifests".

**Status.** Every principal is `active`, `suspended` or `deleted`. Suspending
takes effect at once: every check for that principal, as actor or as OBO user,
is denied; token exchange refuses it; the NATS auth callout refuses its
connections. `deleted` keeps the id so audit records stay readable; nothing can
be attached to it.

**On behalf of.** A call carries an actor and, optionally, a user it acts for
(Nexus serving a signed-in user; an agent module serving the user who chats).
Both must be allowed. OBO never unlocks a sealed resource.

## Policy language

The same schema in YAML and JSON (`policy.py`):

```yaml
version: "2026-10-13"
statements:
  - sid: ReadSalesGraph            # optional
    effect: Allow                  # Allow | Deny
    actions:
      - triple_store:Query
      - triple_store:ListGraphs
    resources:
      - "abi:org-1a2b3c4d5e6f:ws-0f1e2d3c4b5a:triple_store:graph/http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fsales-*"
  - effect: Deny
    actions: ["triple_store:DropGraph", "triple_store:ClearGraph"]
    resources: ["*"]
```

Validation rejects the whole document on any failure and lists every error:

| Field | Rule |
|---|---|
| `version` | Required. `"2026-10-13"` is the only version. |
| `statements` | Required, 1 to 100 items. |
| `sid` | Optional. `^[A-Za-z0-9]{1,64}$`, unique within the document. |
| `effect` | Required. Exactly `Allow` or `Deny`. |
| `actions` | Required, 1 to 100 action patterns. A pattern without a wildcard must name a registered action; one with a wildcard must match at least one registered action. |
| `resources` | Required, 1 to 100 resource patterns. Each is `*` or starts with `abi:`. |
| `conditions` | Reserved: rejected in this version. |
| anything else | Rejected. |

The serialized document is at most 32 KiB. Managed policies are generated by IAM
and validated without catalogs, since they may name services that register later.

**Stored policies**: `id` (`pol_<ulid>`, or `builtin.<name>` / `module.<project>.<module_id>`
for managed ones), `name`, `description`, `document`, `managed` (only IAM rewrites
it), `revision` (increments on every change; `update_policy(expected_revision=)`
is optimistic concurrency) and `owner_scope`.

**Owner scopes.** Every policy is owned by the platform (`abi:-:-`, the default and
every managed policy's), an org (`abi:<org>:-`) or a workspace (`abi:<org>:<ws>`),
never an org-wide scope; it never changes. Its name carries it,
`abi:<org>:<ws>:iam:policy/<id>`, so whoever holds `iam:CreatePolicy` (and the
rest) there manages it. An org or a workspace owns something only once Nexus
registered it (`iam:PutScope`). A policy owned by an org or a workspace:

- is written for its scope: **every** resource pattern, a Deny's included, starts
  with `${scope}:` (refused at create and update with `PolicyValidationError`;
  `policy.check_owned_document`, which Nexus's validate route calls too), so
  attached to anyone it neither grants nor refuses anything beyond its scope;
- is attached only at its owner's scope or below, always at a scope: an org's at the
  org, org-wide or at any of its workspaces, a workspace's at that workspace
  (`names.within_owner`). No unscoped attachment of it exists.

A refusal names the owner to whoever may read the policy or the group, and is "not
found" for anyone else.

**Action patterns.** An action is `<service>:<Action>`: `service` is the catalog
name `^[a-z][a-z0-9_]*$`, `Action` is PascalCase `^[A-Z][A-Za-z0-9]*$`. Patterns
use `*` (any characters, including none) and `?` (exactly one); matching is
case-sensitive. Examples: `triple_store:*`, `triple_store:List*`, `*`.

**Attachments and scope.** An attachment binds a policy to a principal (user,
group or service account) with an optional `scope`:

| `scope` | Meaning | `${scope}` expands to |
|---|---|---|
| `abi:<org>:<workspace>` | One workspace | `abi:<org>:<workspace>` |
| `abi:<org>:-` | The org's own resources only (members, domains, billing) | `abi:<org>:-` |
| `abi:<org>:*` | The org and every workspace in it | `abi:<org>:*` |
| `abi:-:-` | Platform resources | `abi:-:-` |
| none | The policy uses no `${scope}` | none |

A policy attached at a scope must start every Allow resource pattern with
`${scope}:` (a Deny only narrows, so it may name anything): the scope only fills
`${scope}`, so any other pattern would let whoever may attach at that scope
grant beyond it. IAM refuses such an attachment, refuses to update a policy
attached at a scope beyond it, and enforces the rule when it evaluates: a
statement reached through a scoped attachment keeps only its `${scope}:` Allow
patterns, whatever the policy says (`policy.within_scope`).

A Deny is kept whole, so a policy with a Deny outside `${scope}:` refuses beyond the
scope it is attached at. Such a policy (`confined_to_scope` but not
`wholly_within_scope`, only ever the platform's) is attached at a scope, invited to
(`create_pending_grant`) or bound
(`bind_idp_group`) only by whoever may also attach it unscoped, `iam:AttachPolicy` on
`abi:%2A:%2A:iam:attachment/<policy>/<principal>`: the platform admin. A scope's admins
and owners are refused with `PermissionDeniedError`, and lists at a scope
(`list_policies(scope=)`, Nexus `/attachable-policies`) do not offer it to them.

**Variables** are substituted into resource patterns before matching, against
the principal whose policies are being evaluated (`X` in `principal_decision(X)`
below): the actor when computing the actor's decision, the OBO user when
computing the user's.

| Variable | Value |
|---|---|
| `${scope}` | The attachment's scope. Invalid in a policy attached without one. |
| `${principal.id}` | `X`'s principal id. A policy reached through a group resolves to the member being evaluated, never to the group; percent-encoded as one segment. |
| `${user.id}` | The call's user: the OBO user if the call is on behalf of one, else the actor if it is a user, else unresolved. The same on both sides, so an actor's policy can name the user it serves. |
| `${module.id}`, `${module.project}` | Manifest-only: bound when a module's manifest is approved; they match nothing for any other principal. |

A statement with an unresolved variable matches nothing. Variables are not
allowed in actions. On a Nexus call the actor is `api` and the user is the
signed-in one: `builtin.self` is attached to the user, so in the user's decision
its `${principal.id}` is the user; `api`'s policies never see the user as
`${principal.id}`.

## Resource names

```abnf
resource-name = "abi:" org ":" workspace ":" service ":" type "/" id
org           = scope-id / "-" / "%2A"                    ; %2A: every org, unscoped attachments only
workspace     = scope-id / "-" / "%2A"                    ; %2A: every workspace, org-wide attachments only
scope-id      = 1*64( %x61-7A / DIGIT / "-" / "_" )       ; lowercase id, never exactly "-"
service       = %x61-7A *( %x61-7A / DIGIT / "_" )        ; catalog name
type          = %x61-7A *( %x61-7A / DIGIT / "_" )        ; declared in the service catalog
id            = "-" / segment *( "/" segment )
segment       = *( unreserved / pct-encoded )             ; RFC 3986; empty only inside path ids
unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
pct-encoded   = "%" 2HEXDIG                               ; uppercase hex
```

- `org` and `workspace` are the stable Nexus ids (`org-<12 hex>`, `ws-<12 hex>`),
  never slugs: renames change no names. `-` means "none".
- **Levels**: workspace `abi:<org>:<ws>:…`; org `abi:<org>:-:…` (the org's own
  resources: members, domains, billing); platform `abi:-:-:…` (models, discovery,
  IAM itself); a workspace in no org `abi:-:<ws>:…` (legacy workspaces with a null
  `organization_id`).
- `%2A` as the workspace names what spans every workspace of an org, and `%2A` as
  both org and workspace what spans every org (`names.EVERY_ORG_TYPES`):
  - `abi:<org>:%2A:iam:attachment/…`, an org-wide attachment, which an
    `abi:<org>:*` grant reaches and an org-level `abi:<org>:-` one does not, so an
    org admin cannot attach itself to every workspace;
  - `abi:%2A:%2A:iam:attachment/…`, an unscoped attachment, and
    `abi:%2A:%2A:iam:policy/…` and `…:iam:group/…`, the **platform's** policies and
    groups: no `${scope}` expands to them, the platform scope `abi:-:-` included,
    so only grants written for every org (`*` and `abi:*:…`, the platform admin's,
    `engine`'s, `api`'s) reach them. A role attached at `abi:-:-` therefore never
    edits a platform policy, which may be attached unscoped.

  No other resource may use `%2A`. An org's or a workspace's policies and groups
  are named at their owner, `abi:<org>:-:iam:policy/…`, `abi:<org>:<ws>:iam:group/…`.
- `-` as the whole `id` names a singleton (`service/-`).

**Encoding ids.** The id is percent-encoded UTF-8: every octet outside
`unreserved` is encoded, including `:`, `/`, `*`, `?`, `%` and spaces. Each
resource type declares its id kind in its catalog:

- **`opaque`**: one segment, the whole value encoded (a `/` becomes `%2F`): graph
  IRIs, key-value, cache and secret keys, event types, model ids.
  `http://ontology.naas.ai/graph/x` becomes `http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fx`.
- **`path`**: a hierarchy; each part is encoded on its own and the parts joined with
  a raw `/`: object paths, document namespace/collection/id, dataset
  namespace/name, vector collection/id. Object storage joins `prefix` and `key`
  with one `/` after stripping leading and trailing `/` from the prefix: prefix
  `workspaces/ws-1/files`, key `q3 report.pdf` is `object/workspaces/ws-1/files/q3%20report.pdf`.
- **`singleton`**: `-`, for service-wide resources.

Canonical names are built and parsed only by `names.resource_name(...)` and
`names.parse_resource_name(...)`, never by string formatting in callers
(SDK modules do not build names: the engine's services do).

**Wildcards.** A resource pattern is matched against the whole canonical name.
`*` matches any sequence of characters, including none and including `:` and `/`
(it crosses segments); `?` matches exactly one character of the encoded form
(so it can match one character of `%2F`); everything else is literal. There is no
escaping and there are no regular expressions: canonical names never contain a raw
`*` or `?` (they are `%2A`, `%3F`), so a wildcard is never confused with a
literal. `*` alone matches every resource. End a field before the wildcard:
`abi:org-1:*` matches org `org-1` only, `abi:org-1*` also matches `org-10`.

| Pattern | Matches |
|---|---|
| `abi:org-1:ws-2:*` | everything in workspace `ws-2` |
| `abi:org-1:*` | the org's own resources and all its workspaces |
| `abi:*:*:triple_store:graph/*` | every graph |
| `abi:-:-:document:namespace/people`, `…:collection/people/*`, `…:document/people/*` | the `people` document namespace, its collections and documents. Not `document:*/people*`: that also matches another namespace's collection named `people`. |

## Placements

A kernel service builds `<service>:<type>/<id>` from the request. It cannot take
the org and workspace from the request (anyone could claim a workspace they
belong to while addressing another workspace's data), and data ids rarely encode
a workspace (Nexus graph IRIs are `…/graph/<slug>-<uuid>`). So IAM keeps
**placements**: `(service, id-key) -> (org, workspace)`.

- Both may be `-`. `id-key` is an exact canonical id, or a prefix ending in `*`
  (plain string prefix matching on the canonical id, covering every type of that
  service whose id starts that way: a document placement on `nexus-ws-1` plus
  `nexus-ws-1/*` covers the namespace, its collections and its documents).
- **Resolution** (`IAMService.placement_of`): an exact key beats a prefix, a longer
  prefix beats a shorter one; no match means the resource is platform-level,
  `abi:-:-:…`. A resource type a catalog declares `placement: platform`
  (model_registry models, discovery modules) always resolves to platform.
- **Containers.** A resource type marked `container: true` holds children whose
  ids extend its own (`<container id>/<rest>`): document `namespace` and
  `collection`, vector_store `collection`, source_control `repo`, dataset
  `namespace`. A placement on a container is written as a pair, the exact id and
  the prefix `<id>/*`, so its children resolve to the container's placement,
  platform included.
- **Every existing container has a placement.** Containers created through a
  service record one at creation; approving a module's manifest records platform
  placements for the module's own `<module_id>` document and dataset namespaces
  unless already placed (`modules.py`); Nexus places its per-workspace prefixes
  and namespaces when it creates a workspace. "No placement covers this name"
  therefore means a new top-level resource or a new container.

**Writing placements**

1. **On creation.** A create operation is marked `creates: true` in the catalog.
   Before it runs, the service resolves the placement of the would-be name
   (`ServiceGuard.create`, `ResourceGuard.create`). The create always needs its
   action allowed on the name *as placed*.
   - A child of an existing container, or any name an existing placement covers,
     takes that placement. `CallContext.workspace_id` must be empty or equal to its
     workspace (for a platform container: empty); on a mismatch the call is denied
     with the "not found or permission denied" outcome computed on the name as
     placed. Nothing new is recorded. So a member of ws-A cannot claim a name inside
     ws-B's namespace or a module's platform namespace by passing `workspace_id=ws-A`.
   - `workspace_id` decides only for a name no placement covers. With it set the
     name is placed in that workspace (IAM maps the workspace to its org with the
     scope registry that Nexus fills with `iam:PutScope`; a workspace IAM has no
     scope for places the resource on the platform, where no workspace role reaches
     it, so the create is denied). With it empty the name is platform-level. On
     success `Creation.record()` writes the placement: exact for a top-level
     resource (none when platform-level), exact plus `<id>/*` for a container,
     platform included.
   - **Implicit containers**: a create whose name sits in a container that does not
     exist yet (the first `dataset:Create` in a new namespace) first places that
     container by the rule above, then creates the child inside it.
2. **Explicitly**, with `iam:PutPlacement`, mainly for prefixes.
3. **On delete.** Deleting a container or placed resource drops the placements the
   create recorded (`forget`).

`workspace_id` never renames an existing resource or overrides a placement: for
an operation on an existing resource it is ignored. Placements are cached like
policies. Placements are written as `engine` (`PLACEMENT_WRITER`), so a caller
never needs `iam:PutPlacement` to create.

## Evaluation

**Inputs**: the context (the actor `P`, the optional OBO user `U`, the effective
groups of each, the token's narrowing statements `T`), an action and a canonical
resource name. A statement matches when at least one action pattern matches the
action and at least one resource pattern (after substitution) matches the
resource.

```text
decide(ctx, action, resource):
  1. if P.status != active, or U set and U.status != active:  DENY (suspended)
  2. if resource is sealed and its owner != P:                DENY (sealed)
  3. d_P = principal_decision(P)
     d_U = principal_decision(U) if U set else ALLOW
  4. if d_P == EXPLICIT_DENY or d_U == EXPLICIT_DENY:         DENY (explicit_deny)
  5. if d_P != ALLOW or d_U != ALLOW:                         DENY (implicit_deny)
  6. if T set and no statement of T matches:                  DENY (implicit_deny)
  7. ALLOW

principal_decision(X):
  S = statements of every policy attached to X and to each of X's effective groups
  if any Deny statement in S matches:   EXPLICIT_DENY
  if any Allow statement in S matches:  ALLOW
  otherwise:                            IMPLICIT_DENY
```

- An explicit Deny wins over any number of Allows, including Allows reached
  through another group.
- **OBO is an intersection**: an agent module that may write graph G, acting for
  a user who may only read G, cannot write G.
- **Token narrowing (`T`) only narrows.** It holds Allow statements only (a
  Deny is rejected when the token is issued; a statement's `actions` and
  `resources` must be lists of strings, anything else matches nothing).
- Reasons: `allow`, `explicit_deny`, `implicit_deny`, `suspended`, `sealed`.
  `explain` returns the outcome, the reason and the deciding statement (side,
  policy id, statement index or `sid`, attachment, scope, group).
- An inactive actor or OBO user (`suspended`, `deleted`) is denied everything.
- A sealed resource opens to its owner only (the actor, never through OBO).
- The built-in IdP's admin app (`discovery:app/*/idp/admin`) is denied `OpenApp` by `builtin.platform.viewer`,
  `builtin.platform.member` and `builtin.module_bootstrap` (`roles._no_idp_admin_app`): whoever holds a workspace role
  reaches the platform's apps, never the one that edits who a `sub` is. Only the engine opens it.
- Variables: `${scope}` (the attachment's), `${principal.id}` (the principal
  being evaluated, never a group, percent-encoded as one segment), `${user.id}`
  (the call's user). An unresolved variable makes its pattern match nothing.

**Not found or permission denied.** When `decide` denies, the service computes
`visible(ctx, resource)`: true when some action of the same service whose catalog
lists the resource's type is allowed on it.

- `require` raises `PermissionDeniedError` (wire code `PERMISSION_DENIED`) when the
  caller can see the resource, otherwise the caller's `not_found()` (the service's
  own not-found error and wire code, with the same message shape: `GRAPH_NOT_FOUND`,
  `DatasetNotFoundError`, `KV_NOT_FOUND`, ...), else `ResourceNotFoundError`
  (`NOT_FOUND`).
- **Order.** The check runs before the backend is touched; a denied call never
  reveals existence through timing, side effects or error text.
- **Create.** A create on a name that does not exist yet uses the same rule on the
  name as placed: a caller who can see that name gets `PERMISSION_DENIED`, anyone
  else the not-found of the type being created (`GRAPH_NOT_FOUND` for `CreateGraph`),
  or the generic `NOT_FOUND`. The error never says whether the name, its container
  or its workspace is the missing part.
- **Credentials.** Missing, invalid or expired credentials are `UNAUTHENTICATED`:
  authentication, not authorization.

**Lists.** A list action is checked against each item, with the list action
itself (`triple_store:ListGraphs` on each `graph/…`).

- A list returns the items an Allow covers and no Deny excludes, and nothing
  else, counts derived from hidden items included. `filter` keeps input order.
  `limit` and cursors apply after filtering (adapters over-fetch or push down).
- Container-scoped lists (`ListObjects(prefix)`, `ListVectors(collection)`,
  `ListKeys(prefix)`, `document:Collections(namespace)`): when the container is
  itself a resource (a vector or document collection) it first gets the visibility
  rule above (not found if invisible), then its items are filtered.
- Engine-wide lists (`ListGraphs`, `ListCollections`, secret `List`) never fail for
  authorization: they return the allowed subset, possibly empty.
- Container-level reads (`document:Find`, `document:Count`, `vector_store:Search`,
  `vector_store:CountVectors`, `dataset:InlinedRowCount`) are checked once, on their
  container, and their results are not item-filtered: grant them only where the
  whole container may be read.
- **Push-down.** `filter` also returns `prefix_hints`, the literal prefixes of the
  matching Allow patterns, so storage can push them down (a SPARQL `VALUES` list, a
  key-prefix scan, a SQL `LIKE` on ids): `[""]` means no push-down, `[]` means
  nothing is allowed. Denies apply after the push-down.

**Freshness.** Policy, attachment, group, placement and status changes take effect
at the next check after IAM's change event reaches the checking process: at once
in process, within the event's delivery over NATS. Cached state also expires after
60 seconds, so a missed event cannot keep stale grants for long. Group membership
carried in a token's `grp` lasts until the token expires (ten minutes at most).

## Action catalogs

**Access levels.** Every action has a level; the built-in roles are defined by
level, so it is part of the contract:

| Level | Meaning |
|---|---|
| `list` | Enumerate resources or their names. |
| `read` | Read content or metadata, run read-only queries, invoke a model. |
| `write` | Create resources, change or delete data inside a container, invoke an agent or job. |
| `admin` | Drop or clear containers, maintenance, service lifecycle, permission changes, cross-user views. |

**Format.** Each service declares its catalog next to its domain code
(`services/<name>/iam_catalog.py` in core, `iam_catalog.yaml` in a module package)
and registers it when it loads: in process with `iam.register_catalog(catalog)`
during engine boot, before the service serves; over NATS with
`abi.iam.v1.register_catalog`, from a module whose approved policy allows
`iam:RegisterCatalog` on `abi:-:-:iam:catalog/<service>`.

```yaml
service: triple_store
version: 1                      # bumped on every change; IAM keeps the highest
resource_types:
  - name: graph
    id: opaque                  # opaque | path | singleton
    placement: placed           # placed | platform
    container: false            # true: children's ids extend this id
    personal: false             # true: the id starts with the owner's principal id
    description: A named graph, by IRI. `default` is the default graph.
actions:
  - name: Query
    level: read
    resource_types: [graph]
    subjects: ["abi.svc.triple_store.v1.query"]
    description: Run a SPARQL query over the graphs the caller may query.
  - name: CreateGraph
    level: write
    resource_types: [graph]
    creates: true               # records a placement from CallContext.workspace_id
    subjects: ["abi.svc.triple_store.v1.create_graph"]
```

`iam/v1/iam.proto` defines `ActionCatalog`, `ResourceType` and `ActionSpec` with the
same fields. Rules: action names are unique within a service; a new version may only
add actions or resource types, and removing one is refused while a policy still names
it explicitly; `subjects` drives broker permissions (stream actions list their
service's transfer subjects, in-process-only actions list none).

**Request-to-resource rules shared by every service**

- **Ids are canonical**; the org and workspace come from placement, never from the
  request.
- **"All" calls.** An operation that takes an optional container and means "all" when
  it is empty (`event:Query` with no type, `triple_store:Get`) is filtered per item.
- **Several resources.** An operation naming several resources
  (`vector_store:DeleteVectors`, SQL touching several tables) requires the action on
  each: one denial fails the whole call, with the outcome of the first denied
  resource.
- **Personal resources.** A type with `personal: true` has an id whose first segment
  is its owner's principal id: the owner id alone (`actor/<owner>`,
  `forge_user/<owner>`, `coder_user/<owner>`) or `<owner>/<rest>`
  (`conversation/<owner>/<id>`, `environment/<owner>/<id>`, `run/<owner>/<project>/<invocation>`,
  `key/<owner>/<key id>`). Services read the owner from their own records, never from
  the request. A role reaches a personal type only through its owner, with both forms:
  `<type>/${principal.id}` and `<type>/${principal.id}/*`.

**Kernel catalogs** (`services/<name>/iam_catalog.py`, registered by
`kernel_catalogs.register_kernel_catalogs`; the action list and its resources are
the catalog file, each service's AGENTS.md "Authorization" section says how its
operations map):

| Service | Resource types (id kind; `placed` unless noted) |
|---|---|
| `object_storage` | `object` (path) |
| `document` | `namespace`, `collection` (containers), `document` (path) |
| `keyvalue`, `secret` | `key` / `secret` (opaque) |
| `cache` | `key` (opaque), `service` (singleton, platform) |
| `vector_store` | `collection` (container), `vector` (path), `service` (singleton, platform) |
| `triple_store` | `graph` (opaque), `view` (opaque, platform), `schema` (path, platform: a schema of the schema graph by its source) |
| `dataset` | `namespace` (container), `dataset` (path), `catalog` (singleton, platform) |
| `event` | `event_type` (opaque), `cursor` (path) |
| `activity_log` | `actor` (opaque, personal, platform), `service` (singleton, platform) |
| `email` | `sender` (opaque, platform), `message` (opaque, placed on send) |
| `model_registry` | `model` (opaque, platform) |
| `discovery` | `module`, `agent`, `model`, `app`, `job`, `job_run` (path, platform), `run` (path, personal, platform) |
| `source_control` | `repo` (container), `branch`, `proposal` (path), `forge_user` (personal, platform) |
| `coding_environment` | `environment` (path, personal, placed), `template` (platform), `coder_user` (personal, platform) |
| `identity` | `provider` (opaque, platform) |
| `iam` | `principal`, `group`, `policy`, `attachment`, `key` (personal for personal keys), `manifest`, `placement`, `scope`, `catalog`, `audience`: platform unless scoped |
| `module` | `agent`, `app`, `workflow`, `pipeline` (path, module scopes): see "Module scopes" |
| `<module service>` | a module's own catalog (`acme_people` for `acme.people`), every type a module scope: see "Module scopes" |
| `nexus` | registered by Nexus at start, not by core: see `libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam_admin/AGENTS.md` |

Rules that cut across services and are easy to get wrong:

- **Triple store.** `Query`, `QueryStream` and `QueryView` run over a dataset
  restricted to the graphs the caller may `Query`: a graph named in `FROM`,
  `FROM NAMED` or `GRAPH <iri>` must be allowed (an invisible one is
  `GRAPH_NOT_FOUND`), `GRAPH ?g` ranges over the allowed graphs, and the default
  graph is `graph/default` limited to the allowed ones. SPARQL Update through
  `query` needs the matching action on each target graph (`INSERT DATA` `Insert`,
  `DELETE DATA` `Remove`, `CLEAR` `ClearGraph`, `DROP` `DropGraph`, `CREATE`
  `CreateGraph`, `ADD`/`MOVE`/`COPY` `Query` on the source and `Insert` on the target,
  `DropGraph` on the source for `MOVE`); `DEFAULT`, `NAMED` and `ALL` need it on every
  graph they cover; a request the parser cannot classify is refused
  (`INVALID_ARGUMENT`). Adapters that cannot confine a dataset (filesystem, object
  storage, Neptune) refuse a confined caller. See `services/triple_store/AGENTS.md`.
- **Dataset.** `Query` takes its table references from DuckDB's parser and needs
  `dataset:Query` on each; unresolvable tables, file-reading table functions and
  `ATTACH` are refused (`INVALID_ARGUMENT`). `dataset:QueryUnchecked` (admin, on
  `catalog/-`) skips the per-dataset check for the engine's own catalog maintenance;
  `builtin.api` and every default module manifest deny it. See
  `services/dataset/AGENTS.md`.
- **Discovery.** `AuthorizeAgent`, `AuthorizeModel` and `AuthorizeApp` are lease
  checks only: the hosting module asks IAM `check` with the caller's context.
  `Register` can be held only by the module's own service account. Its grants
  are the broker-side check of using a module's agent, app or job; which one a
  user uses in a workspace is the module scope's, which Nexus checks first
  ("Module scopes").
- **Source control.** `AddCollaborator` is an admin action that grants write on any
  repository: no default manifest allows it. A `repo_id` of another workspace has
  another placement, so the caller gets `REPO_NOT_FOUND`. Nexus grants a member write
  on a workspace repo by checking `source_control:UpsertFile` for the user, then calling
  `AddCollaborator` as `api`.
- **Coding environment, source control.** The owner and the user are read from
  `CallContext` and the service's own records, never `request.user_id`.
- **Secrets.** `secret/iam%2F*` is sealed to `engine` and `secret/idp%2F*` to `idp`.

## Sealed resources

A sealed resource is a resource pattern bound to one principal. No other principal
is ever allowed on it, whatever its policies say, `engine`, `api` and the platform
admin included, and acting on behalf of a user never opens one. Seals are declared
in code by the service that owns them (`iam_catalog.py`, next to each service's
catalog) and loaded at boot; no API changes them, so editing policies cannot open
them. The seals: the built-in IdP's document namespace `idp` (namespace, collections
and documents) and secrets `idp%2F*`, sealed to `idp` (and to the module id `idp`,
`Seal.module_id`); `secret/iam%2F*`, sealed to `engine`. Seals match at any placement
(`abi:*:*:…`). An operator who needs the IdP's data back uses the IdP's own admin API
or the database directly, outside ABI's authorization by design.

## Built-in policies

Built-in policies are managed: IAM generates their documents from the registered
catalogs (so a new service's actions join the roles automatically), stores them with
explicit action lists (so `explain` shows real statements), and regenerates them when
a catalog version changes (`roles.py`). Roles are attached at a scope: "viewer on
workspace W" is `builtin.viewer` attached with scope `abi:<org>:W`.

For each catalog resource type that can be placed in a workspace, the role's
statement covers `${scope}:<service>:<type>/*`; a personal type covers
`${scope}:<service>:<type>/${principal.id}` and `…/${principal.id}/*` instead
(`${principal.id}` is the member being evaluated, so on a Nexus call it is the user,
not `api`). **The roles are cumulative**: `viewer` ⊆ `member` ⊆ `admin` ⊆ `owner`;
each holds every statement of the role below it, so a principal needs one role
attachment per scope.

| Policy | Allows on the scope's types | Excludes |
|---|---|---|
| `builtin.viewer` | every `list` and `read` action | the nexus `feature` type; every module scope type |
| `builtin.member` | viewer, plus every `write` action | the `feature` type; every module scope type |
| `builtin.admin` | member, plus every `admin` action, except on the `iam` `attachment` type; plus `iam:ListAttachments` on `${scope}:iam:attachment/*`, and `iam:AttachPolicy` and `iam:DetachPolicy` on `${scope}:iam:attachment/builtin.admin/*`, `…/builtin.member/*`, `…/builtin.viewer/*` | the `feature` type; anything on `attachment/builtin.owner/*`; `nexus:DeleteWorkspace`; `nexus:DeleteOrganization` |
| `builtin.owner` | admin, plus every action on every `attachment/…` (owner included), `nexus:DeleteWorkspace` and `nexus:DeleteOrganization` | the `feature` type |
| `builtin.platform_admin` | `*` on `*` (attached without scope) | sealed resources |
| `builtin.self` | held implicitly by every user (no attachment row, unknown users included; `explain` shows it with no attachment id) | none |

- **IAM administration is the admins' and owners'.** Viewers and members hold nothing
  of the `iam` catalog at their scope (no list, no read): every IAM administration
  call refuses them. Owners and admins at a scope manage that scope's policies and
  groups and attach them there; an org's owners and admins reach its workspaces'
  through their org-wide role (`abi:<org>:*`, which Nexus mirrors). They also see,
  in a list at their scope, what they may attach there from above (see "Service API").
- **Owner protection.** An admin cannot attach or detach `builtin.owner`; demoting or
  removing an owner means detaching their owner attachment, so only an owner can, at
  org and workspace scope alike.
- **Org roles.** Org roles (owner, admin, member) are attached with scope
  `abi:<org>:-`, the org's own resources: org membership never grants workspace
  access. Org-wide roles (`abi:<org>:*`) exist but are never created by default.
- **Platform types.** A workspace-scoped role never reaches a platform-level
  resource (`abi:-:-:…`). Two more managed policies, kept in step with role
  attachments by IAM, carry what members need there (`roles.PLATFORM_TYPES` is the
  table: models, discovery modules/agents/apps/runs, views, coding templates, the
  user's own forge/coder/activity/key/principal resources, provider models, drives):
  `builtin.platform.member` while the principal has a `member`, `admin` or `owner`
  attachment at a workspace scope or an org-wide scope, `builtin.platform.viewer`
  while it has only `viewer` attachments there. Org-level attachments (`abi:<org>:-`)
  bring neither. Because Nexus calls as `api` on behalf of the user, the user must
  hold these, not only `api`. A member holds `discovery:TriggerJob` on
  `workflow/*`, the second name of every job of kind `workflow` (a viewer
  nothing), as it holds `InvokeAgent` on `agent/*`: which workflow it starts is
  the module scope's. An explicit Deny on a workflow's `job/…` name still refuses
  it (discovery `trigger_decision`). Not reached by any role (platform admin, built-in accounts
  and explicit policies only): plain jobs and job runs, email senders and messages,
  `dataset:catalog`, `cache:service`, `vector_store:service`, `activity_log:service`,
  and unplaced data until placed or granted.
- **Features.** `nexus:UseFeature` comes only from feature policies
  `builtin.features.<role>` (`<role>`, `<org>.<role>` or `<org>.<ws>.<role>`), set as
  a whole by `iam.put_feature_policies({key: [feature, ...]})` (needs
  `iam:RegisterCatalog` on `nexus`; Nexus computes them from its `feature_flags`).
  Each allows `UseFeature` on `${scope}:nexus:feature/<key>` for the role's features
  that are also enabled: a feature outside `enabled_features` is reachable by no role,
  only by the platform admin's `*`. A role attached at a workspace scope brings the
  most specific policy that exists, attached at the same scope (detached with the
  role); org-level roles bring none. No role reaches `UseFeature` through its scope
  pattern, and no one grants a feature they do not hold (see "Grant only what you hold"),
  so a custom policy cannot bring back one the deployment turned off.
- **First-party accounts.** `builtin.engine`, `builtin.api` and `builtin.job` are
  enumerated: one statement per service, each with a `sid` saying what needs it. The
  engine holds IAM's administration and the kernel services; `api` holds `nexus:*`, the
  kernel services it calls for its users (each user bounds the call), the sign-in identity
  actions, `iam:ExchangeToken` and the IAM actions that keep memberships, scopes and
  placements, and denies `dataset:QueryUnchecked`; `builtin.job` is what the account
  `job/<module_id>` of an engine module's jobs holds. The three hold every module scope,
  `module:*` and each module's own catalog (`<service>:*`, generated as modules
  register), on behalf of users who must hold it too. Nobody holds `*` but the platform
  admin. A retired policy (`roles.RETIRED_POLICIES`: the old `builtin.transitional.*`) is
  dropped, with what was attached to it, at boot.
- **`builtin.idp`**: the built-in IdP's own namespace, secrets and sender, for the
  built-in account `idp`. By default the IdP (`libs/naas-abi-idp`) runs as the
  module account `module/<project>/idp` with its approved manifest instead; the
  seals and the secret endpoint (`secret_nats_contract.is_idp`)
  name both, so the module id `idp` is reserved: an admin creates its account,
  nothing else does.
- **`builtin.platform.viewer` / `.member`**: attached and detached by IAM in step
  with workspace and org-wide role attachments (above).
- **`builtin.module_bootstrap`**: a module account before approval (see "Service accounts,
  keys, tokens and manifests").
- **`LEGACY_NEXUS_ISSUER`** (`urn:abi:nexus`): a Nexus user named on a call by its Nexus id resolves to IAM's user of
  that issuer. Nexus has no login of its own: such a user keeps that naming (its Nexus id is what every
  row and call names) and is *linked* to the built-in provider's identity at its first sign-in (`link_user`, which
  only the built-in provider's verified email triggers, in Nexus's `OidcSignInService`); a person who never
  signed in stays legacy. Users of an identity provider are IAM users named by their principal id
  (`services/identity`). Nexus holds no implicit grant for either: a user reaches what its role attachments
  reach (`services/iam/memberships` in Nexus). `api` holds `iam:LinkUser` (the sign-in rule decides when).
- Nexus seeding turns `users[].is_superadmin` into a `builtin.platform_admin`
  attachment (`org_seed.sync_platform_admins`).

## Module scopes

Everything a module exposes is grantable per workspace, one item at a time
(`module_scopes.py`). Two kinds, both marked `module_scope: true` on their resource
types (`ResourceType.module_scope`), so the UI and the sets find them:

- **The `module` catalog.** Every agent, app, workflow and pipeline of every module,
  engine or remote, is `abi:<org>:<ws>:module:<type>/<module>/<name>`
  (`scope_resource`). `<module>` is the module's stable identifier: an engine
  module's configured key (`naas_abi`, `naas_abi_marketplace.applications.github`, which is
  `BaseModule.module_key`, its class's Python module), the same in every install; a
  remote module's id (`acme.people`), the same across restarts. `<name>` is the
  agent's name, the app's folder or name, the workflow's job name (a process class's
  is `workflow.<slug>` or `pipeline.<slug>`).

  | Type | Use | Own runs |
  |---|---|---|
  | `agent` | `UseAgent` (write): chat, `/v1`, the roster, as a sub-agent | |
  | `app` | `OpenApp` (read): the listing, the iframe, links and grants | |
  | `workflow` | `RunWorkflow` (write): the listing, a start, as an agent's tool | `ReadWorkflowRuns` (read) |
  | `pipeline` | `RunPipeline` (write) | `ReadPipelineRuns` (read) |

- **Declared catalogs.** A module may ship a catalog of its own: `iam_catalog.yaml`
  beside its module class (an engine module: `BaseModule.iam_catalog`, registered by
  the engine at load, `register_module_catalogs`), or the `catalog` key of its
  manifest (an SDK module: `Module.iam_catalog` or `iam_catalog.yaml` beside it,
  `permissions.module_manifest`; registered when the manifest is approved, as part of
  what the admin approves, and hashed with it, so a changed catalog is a new pending
  version). Its service is the module's own, `module_service(<module>)` (lower case,
  every other character `_`: `acme.people` is `acme_people`); it is refused when it
  names a kernel service, `iam`, `nexus`, `module` or another module's service
  (`module_catalog`, `ModuleCatalogError`), and IAM refuses registering a catalog
  another module owns (`ActionCatalog.module`, `IAMConflictError`). Every type is
  placed in the workspace of the call. Approval adds `OwnCatalog` (`<service>:*` on
  `abi:*:*:<service>:*`) to the module's managed policy: the module's side of its own
  actions, for the users it acts for (it grants the broker nothing).

  An engine module's catalog that cannot be used (an unreadable file, a refused
  catalog, another module's service) is logged and left out (`declared_catalog`,
  `register_module_catalogs`): one module never stops the engine, and its own checks
  of the actions it declares are refused (fail closed). The service comes from the
  module id alone, so one module id declares a catalog in one project: a manifest of
  another project's module of that id declaring one is refused (`IAMConflictError`)
  while the first project's approved manifest declares it.

The module enforces a declared action on the caller's context:
`iam.require_declared("<service>:<Action>", "<type>", [parts])` in an engine module
(`BaseModule.require_action(action, type, parts)`), `await
engine.services.iam.require_declared(...)` in an SDK module (`Module.require_action`).
IAM names the resource itself (`authorize_declared`): the workspace of the call
(`CallContext.workspace_id`, or `workspace=`), its organization from the scope
table, platform level without one.

**The workspace of the call is safe.** A module scope is a permission to use
something in a workspace, not data a workspace owns, so its name is placed in the
workspace the call is made in, never looked up. The use happens there: Nexus checks
the scope in the workspace the request names after checking the user belongs to it,
and a user who claims another workspace gets what they hold there, which is what
using it there needs. A user who belongs to no workspace holds no module scope.

**Zero trust.** `builtin.viewer` and `builtin.member` hold no module scope type
(`roles.MODULE_SCOPE_ROLES` is admin and owner), on upgrade too: there is no
migration grant. `builtin.admin` and `builtin.owner` hold every one at their scope
(the sets bound them later). A member uses a module's agent, app, workflow or
pipeline in a workspace only with a policy granting it there, for example:

```yaml
statements:
  - effect: Allow
    actions: ["module:UseAgent"]
    resources: ["${scope}:module:agent/acme.people/Recruiter"]
  - effect: Allow
    actions: ["module:RunWorkflow", "module:ReadWorkflowRuns"]
    resources: ["${scope}:module:workflow/acme.people/*"]
```

attached to the member (or a group) at `abi:<org>:<ws>`. Discovery's grants stay
the broker-side check (`builtin.platform.member`: `InvokeAgent`, `OpenApp`,
`TriggerJob` on workflows); Nexus checks the module scope first, so no user reaches a module's
resource in a workspace without it. An in-process agent's sub-agents and the
workflows and pipelines it reaches as tools are bounded by the user's scopes:
Nexus binds them per turn (`agent_workspace_enabled_class_names`,
`agent_usable_module_scopes`), and the turn's copy of the agent is built without
the sub-agents the user may not use (`Agent.duplicate(keep=)`: no handoff tool,
bound tool, graph node or intent route to them; `call_tools` refuses a handoff to
an agent that is no sub-agent, `IntentAgent` an intent to one; Abi's prompt lists the kept
sub-agents alone, in the copy's own configuration, `AbiAgent.with_agents_section`), and the agent refuses a tool of a workflow outside
them (`services/agent/context.tool_scope_refused`; the engine marks each process
instance, `EngineProcessBridge.tag_process_scopes`).

## Service API

```python
iam = engine.services.iam  # IIAMService, no dependency declaration needed

iam.require("triple_store:Query", name, not_found=lambda: GraphNotFound(iri))
allowed = iam.filter("triple_store:ListGraphs", names).allowed
iam.authorize(action, resource)  # Decision
iam.allows_every(action, "triple_store", "graph")  # a safe shortcut: False when unsure
iam.explain(action, resource, principal_id=...)  # needs iam:Explain on the principal
iam.grantable(scope)  # what the caller may grant there (needs no permission)
iam.placement_of(
    service, canonical_id
)  # the covering placement, or None (serving engine)
# A module's declared action, named by IAM in the workspace of the call:
decision, resource = iam.authorize_declared("acme_people:ExportReport", "report", ["q3"])
iam.require_declared("acme_people:ExportReport", "report", ["q3"])  # PermissionDeniedError
```

`allows_every` is True only when nothing can deny: no seal on the type, no
narrowing token, no Deny naming the action, and on each side an Allow spanning
every org, workspace and id of the type (`engine` and `api` today). Services use it
to skip per-item work.

Administration (each needs its `iam:*` action): `ensure_user`, `link_user`
(`iam:LinkUser`, in process only: gives a user of the built-in login (issuer `urn:abi:nexus`) one more
identity, `iam_identity_links`, which `find_user` answers first, so its principal, roles, groups and keys follow it
to an identity provider; the user a first sign-in made for that identity is merged into it, retired, and one
holding keys refuses the link; `identity_at(principal, issuer)` names the subject by which a provider knows a
user, its own or linked), `create_service_account`, `get_principal`, `list_principals`,
`suspend_principal`, `resume_principal`, `delete_principal` (keeps the id, drops
attachments and memberships), groups (`create_group`, `add_group_member`,
`map_idp_group`, ...; groups cannot contain groups; `create_group(name, scope=)`, or
`org=` alone for `abi:<org>:-`), policies (`create_policy(name, document, scope=)`
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

Lists page after filtering. `list_policies(scope=S)` returns the policies `S` owns
(`iam:ListPolicies` on each), plus those of the levels above (its org's, the
platform's) that are confined to a scope and that the caller may attach at `S`
(`iam:AttachPolicy` on `attachment/<policy>/*` there): a workspace admin is offered
the roles below owner and the org's policies. `list_groups(scope=S)` returns the
groups `S` owns (`iam:ListGroups`), plus, at a workspace, its org's groups for whoever
may list that workspace's attachments to them (`iam:ListAttachments` on
`attachment/*/<group>`); platform groups are not offered there. Without `scope`, a
list holds every policy or group the caller may list where it is owned. Reading one
(`get_policy`, `get_group`) is decided at its owner only.

**Lifecycle.** `delete_scope(org, ws)` (Nexus, when a workspace goes) deletes the
policies and groups the workspace owns; `delete_scope(org)` those of the org and of
each of its workspaces: a policy with its attachments and invitations, a group
(marked deleted, its id kept) with its attachments, members and mappings. Then it
detaches every attachment left at the deleted workspace (or anywhere in the deleted
org), whatever its policy, so nothing grants at a scope that is gone or comes back
under the same id; a user left with no attachment in the org leaves its groups. It
is part of `iam:DeleteScope`.

Names: `principal_resource`, `group_resource(id, owner_scope)`,
`policy_resource(id, owner_scope)`, `attachment_resource` (at the attachment's scope; an org-wide
one in workspace `%2A`, `names.ALL_WORKSPACES`; an unscoped one is `abi:%2A:%2A:…`,
`names.ALL_ORGS`, see "Resource names"), `placement_resource`, `scope_resource`,
`catalog_resource`.

## Tokens

The engine (IAM) signs every engine token with **ES256** (P-256), `services/iam/tokens.py`;
verification is `engine/nats_auth.py` (see `engine/AGENTS.md`). Modules never hold a
signing key. HS256 and `NATS_JWT_SECRET` are gone, with no dual mode.

- **Signing keys.** `kid` `<yyyymmdd>-<8 hex>`; private halves in the secret service
  at `iam/signing-keys/<kid>` (sealed to `engine`), public halves and schedule in the
  store. They rotate every `tokens.key_rotation_days` (30), checked whenever a token
  is issued or the JWKS read. The next key is published at least 15 minutes before it
  signs. A key retires 20 minutes after the next one signs, but its public half stays
  in the JWKS 169 hours more (`abi_retired_at`), so job triggers stored meanwhile still
  verify as of their stored time; a retired key is never accepted for a token presented
  later. Its private half is deleted at retirement.
- **JWKS.** `abi.iam.v1.jwks` (request/reply, RFC 7517, no token needed); Nexus also
  serves it at `/.well-known/abi-jwks.json`. Verifiers cache it five minutes and refetch
  on an unknown `kid`, at most once every 30 seconds. The issuer is
  `urn:abi:engine:<install id>` (the install id is generated at first boot and stored
  in IAM).
- **Claims.**

  | Claim | Meaning |
  |---|---|
  | `iss` | The engine issuer. |
  | `sub` | Principal id. For a delegated token, the user. |
  | `act` | RFC 8693 actor: `{"sub": "<sa id>", "name": "<account name>"}`. Present when someone acts for `sub`. |
  | `aud` | Exactly one audience. |
  | `kind` | `user` or `service_account`: the kind of `sub`. |
  | `grp` | Mapped IdP group ids (users only), only ids of active groups (`active_groups`): the id of a user or an account never lends its policies. |
  | `abi_scope` | Optional narrowing: a list of Allow statements. |
  | `idp` | `{"iss", "sub"}` of the source IdP identity (users only), for audit. |
  | `sid` | The Nexus session id, so a logout ends its exchanged tokens. |
  | `abi_since`, `abi_res` | Delegation start; the target resource of a delegation. |
  | `iat`, `nbf`, `exp`, `jti` | `exp - iat <= 600`: verifiers refuse anything longer and allow 30 seconds of clock skew. |

  **No access token lives longer than ten minutes**, and the engine issues no refresh
  tokens: service accounts exchange their key again; Nexus sessions refresh at the IdP
  with the refresh token Nexus holds server-side, then exchange again.
- **Audiences.**

  | Audience | Issued for | Accepted by |
  |---|---|---|
  | `abi:session` | A Nexus session: a user, after the IdP sign-in | Every Nexus REST route and the WebSocket. Nothing else. |
  | `abi:nats` | Service accounts (key exchange); `api` and `engine` | Every kernel NATS endpoint |
  | `abi:host:<sa>` | A caller's identity addressed to one module host (below) | Discovery, as the caller a host forwards; the engine's job loader; the overflow host. Never a kernel service. |
  | `abi:delegated:agent` | A module acting for a user (`act` = the module's account); also what `api` and `engine` send the kernel for the user they serve | Kernel endpoints and module hosts, as actor plus OBO user |
  | `abi:delegated:app` | Opening a remote app or app-html link | Only the app routes, `discovery:OpenApp` on the app named in `abi_scope` |
  | `abi:delegated:preview` | App-project preview links | Only `/app-preview/…` for that project |
  | `abi:delegated:coding` | A coding environment's agent, for the user who owns the environment | Nexus's OpenAI gateway only, narrowed to the environment's workspace and repo |
  | `abi:delegated:api-key` | A personal API key | Nexus REST routes not marked session-only |

  Delegated tokens are never a session: session-only routes (account, IAM
  administration, API-key management, logout) require `abi:session` exactly.
- **Revocation.** `revoke_tokens(principal)` sets a floor (`iam_token_floors`): every
  token of that principal issued at or before it is refused, by the verifier
  (`iam.verifier()`, `token_revoked`) and by the authorizer (a context whose
  `token_issued_at` is at or before it is `suspended`), and the principal's grants
  and coding keys are revoked (their personal API keys too with `include_keys`).
  A token made after it carries `iat` past the floor (`issue_after_floor`). Suspension
  and deletion deny a principal's tokens at once. `iam:RevokeTokens` is in `builtin.self`.

## Token exchange, personal keys and links

```python
issued = iam.exchange_token(
    TokenExchange(
        subject_token, subject_token_type, audience, resource=None, scope=None
    )
)  # IssuedToken, 10 minutes at most
iam.revoke_tokens(user_id, include_keys=False)
iam.create_key(
    user_id, audience=..., resource=..., scope=..., kind=...
)  # personal / grant
iam.identity_authenticator = ...  # engine wiring: IdP tokens (`IdentityAuthenticator`, services/identity/token_authenticator.py)
```

Token exchange (RFC 8693) is the one way a narrow credential is made: in process,
over NATS (`abi.iam.v1.exchange_token`) and, for scripts, through Nexus
`POST /api/iam/token`. The result is a token of at most ten minutes with one
audience, derived from an identity that was already verified; an exchange can never
add a permission.

- **Requester.** The caller needs `iam:ExchangeToken` on `abi:-:-:iam:audience/<audience>`
  (only `api` and `engine` hold it, through their enumerated policies); the user it acts
  for, when there is one, does not decide. A module renewing the delegation it
  holds needs nothing: it only keeps what it was given.
- **Subjects** (`subject_token_type`): `id_token` / `access_token` (an IdP's, only
  for `abi:session`, via `identity_authenticator`: `iss` matches a provider, the
  signature checks against its JWKS, `aud` is its `client_id`, `exp`/`nbf` hold; then
  IAM resolves or creates the principal, maps groups and refuses a suspended one);
  `…:jwt` (an engine token);
  `urn:abi:params:oauth:token-type:api_key` (`abi_pk_` or `abi_gk_`: IAM checks the
  hash, expiry, revocation and the owner's status; the token's `sub` is the key's owner
  and `abi_scope` the key's own narrowing);
  `urn:abi:params:oauth:token-type:session`: a signed-in user a **first-party**
  (`api`, `engine`) vouches for, the subject token being the user's principal id,
  plus `groups` and `session_id`. Nexus names its users this way, because its
  sessions are not engine tokens. Service-account keys (`abi_sk_`) are not exchanged
  here: they use `abi.iam.v1.token`.
- **Audiences.** `abi:session` and `abi:delegated:{agent,app,preview,coding,api-key}`
  (`nats_auth.EXCHANGE_AUDIENCES`). Never back to `abi:session` (an IdP's token
  only); never from one delegated audience to another; an `abi:session` token goes
  to every delegated one; a key goes to its own audience only (a personal key to
  `api-key`, a coding-environment key to `coding`). Key exchange
  (`exchange_key`, `abi.iam.v1.token`) still issues `abi:nats` and host tokens
  only. A key may be exchanged with no audience (`audience=""`): the token is the one
  of the key's own audience; the requester then needs `iam:ExchangeToken` on every
  audience (`api` and `engine` do).
- **Agent tokens** (`abi:delegated:agent`): `sub` the user, `act` the actor with
  its account name, `abi_res` the target. The actor is the module that owns
  `resource` (a discovery module, agent, app, model or job, or the module's account
  `abi:-:-:iam:principal/<sa id>`), else the requester; never a request field. App,
  preview, coding and API-key tokens have no actor. Kernel
  endpoints accept `abi:nats` and this audience (`nats_auth.KERNEL_AUDIENCES`), and
  evaluate it as the module for the user: both sides must allow. The module's side
  of what it hosts is `builtin.module_bootstrap`'s `OwnHosted` / `OwnRuns`
  (`roles.DELEGATION_SIDS`), which `_derive` keeps out of its broker permissions.
  A module renews its delegation with its own token (same audience, `abi.iam.v1.exchange_token`
  is in `broker.IAM_ALWAYS`), an expired one too, until `abi_since` + 8 hours
  (`MAX_DELEGATION_SECONDS`); then it is refused. A delegation for a suspended user is
  refused at issue, and one already issued is denied at the next check.
- **Scope** (`abi_scope`, `tokens.normalize_scope`): a list of Allow statements (at most
  32, 64 patterns each). An exchange only narrows: the subject's own scope is kept,
  and a scope is not narrowed twice (a statement list has no intersection). The scope
  of the credential a call runs under travels with every delegation, so a key reaches
  no further over NATS than in process.
- **Personal keys** (`kind=personal`, user principals): `audience` `abi:delegated:api-key`
  (default; five active, a year at most, a year by default) or `abi:delegated:coding`
  with its environment as `resource` (fifty active; made for one environment, narrowed to
  its workspace and repo, revoked with the environment). A personal key is a credential of the person who made it: it can never
  do more than they can, its own `scope` (full access, read only, or custom statements)
  narrows further, and it carries no IdP groups (a role held only through a mapped group
  claim does not reach the owner's keys until it is a stored membership). **Grants**
  (`kind=grant`, `abi_gk_`): `audience` app or preview, always expiring in 8 hours at most
  (a thousand live; `LinkLimitReached` beyond): the links of apps and previews, bound to
  what they open (`resource`) and narrowed to what opening needs (`scope`:
  `discovery:OpenApp` on that app, or nothing). Each request that presents one asks IAM
  again, so revocation is immediate; making one forgets the user's links expired or
  revoked more than a day ago. `iam.list_keys(owner)` lists every kind; callers filter.
  Users manage their own keys (`builtin.self`: `iam:CreateKey`, `ListKeys`, `RevokeKey` on
  `key/${principal.id}/*`), a user of the built-in login named by its Nexus id included
  (recorded on demand).
- **Where a key may be used** (Nexus side in Nexus's AGENTS.md): a personal key is accepted on
  Nexus `/api/*` but not on the account (`/api/auth/`) or key management (`/api/iam/`)
  routes, so a key can neither make another key nor widen itself, and not on the WebSocket;
  a coding key only at the OpenAI gateway. The engine's own HTTP routes (`/agents`,
  `/pipelines`, `/workflows`, `/tools`) take the deployment's `ABI_API_KEY` only: they make
  no IAM decision of their own, so a key's limit would not bound them. A service key
  serves its account over NATS only.
- **Revocation**: see "Tokens". A password change or `revoke_all_user_tokens` revokes
  sessions, links and coding keys; API keys stay unless `include_keys`.

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

- **Keys.** `abi_sk_<key id>_<secret>` (service accounts) and `abi_pk_<key id>_<secret>`
  (personal): `key id` 16 lowercase base32 characters, `secret` 32 random bytes
  (base64url, no padding). Only `sha256(secret)` is stored (a fast hash suffices for 256
  bits of entropy), compared in constant time; the key is shown once. The value reaches
  a module as `ABI_SERVICE_KEY`. At most five active per account; `ci/*` keys expire in 90
  days by default, module keys never, personal keys within a year. Revocation takes effect at the next
  exchange and the next broker connection, which is within five minutes: the
  callout's user JWT lasts that long (ten at most) and the SDK reconnects every
  two minutes. `rotate_key` gives the new key a fresh default life and, at the
  limit of five, revokes the old key first. `last_used_at` is written at most
  once a minute. SDK and core clients renew a token at half its life.
- **Exchange.** A service account exchanges its key over NATS at `abi.iam.v1.token`
  (request `{key}`, response an `abi:nats` token of at most ten minutes); scripts use
  Nexus `POST /api/iam/token` (`grant_type=client_credentials`, the key as `client_secret`).
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
  broker control stores in a trigger (the job's host, else the engine). For a
  user `api` or `engine` acts for, it also stores the delegation the run
  executes with: a vouched exchange to `abi:delegated:agent` whose `resource` is
  the job, so the job's module is the actor (engine `AGENTS.md`, "Who a run runs as").
- **Module accounts** are `module/<project>/<module_id>` and start with
  `builtin.module_bootstrap` only: discovery `Register`, `Renew`, `Unregister`, `GetModule`
  on their own `module/<project>/<module_id>` and `iam:SubmitManifest` / `GetManifest` on
  their own manifest; `iam:RegisterCatalog` is refused. Approval writes the managed policy
  `module.<project>.<module_id>` (`${module.id}`, `${module.project}` bound), attaches it,
  and places the module's document and dataset namespaces at platform level. A changed
  manifest is a new pending version while the approved one stays in force; approving or
  rejecting without a version decides the pending one only; a superseded version submitted
  again (a rollback) is pending again.
- **The manifest flow.** A module declares its permissions either in `permissions.yaml`
  beside its `BaseModule` (a policy document) or by defaulting them from
  `ModuleDependencies` (each declared service maps to its catalog's actions on the
  module's own namespaces; `secret` is `secret/<module id>/...` only, `email` is `Send`
  alone, `triple_store` is graphs and views plus `LoadSchema` on its own ontologies
  (`schema/module/<module id>/...`; the triple store refuses direct writes to the
  shared schema graph to whoever may not load every schema, so `graph/*` does not
  reach it), `dataset` denies `QueryUnchecked`, `source_control`
  denies `AddCollaborator`: no
  default grants an admin action, and a Deny is not overridden by an Allow of the same
  policy, so a module needing one writes its own manifest).
  1. Deploy tooling creates the account and a key (`abi dev up`, `abi deploy`, or
     `abi iam service-account create module/<project>/<id> --key`).
  2. At start the SDK calls `abi.iam.v1.submit_manifest` and waits for approval before it
     registers: an unapproved module does not show in discovery, and every other call
     fails with `PERMISSION_DENIED`.
  3. An admin approves as is, narrows (edits) or rejects: `iam:ApproveManifest` /
     `RejectManifest` on `manifest/<sa>`, from `abi iam module approve|reject` or the
     IAM admin UI.
  4. Discovery refuses a registration whose `module_id` and project differ from the
     caller's account name, which binds the logical module name to its principal.
  A manifest may carry the module's own catalog under `catalog` ("Module scopes"):
  checked at submission, registered at approval.
  `modules.auto_approve` approves on submission (the `abi dev` overlay only; fresh
  configs and the Docker templates keep `false`). A manifest whose bus topics sit under a
  reserved root or nested in another approved topic is refused at submission and approval.
- **Engine key.** `engine_service_key()` returns the key client-role engines
  exchange, kept in `IAMSecrets`; a lost one is replaced, not added to. The serving engine
  signs its own tokens and verifies against its own keys, with no NATS hop.
- **Logs hold no key.** `PresentedKey`, `NewKey` and `CreatedKey` keep the key out of
  their `repr`, and failing decisions are logged by exception type.

**Caching.** Effective statements per principal, policies and placements are
cached for at most `cache_ttl_seconds` (60) and dropped on every change made
through the service. Listeners (`add_change_listener`) hear each new revision;
the NATS primary publishes it on `abi.iam.v1.changed` (`ChangeEvent`, a core NATS
fan-out with a monotonically increasing revision). An engine treats a change notice as a
hint: it reads the store's revision and drops its caches when that differs from the last it
saw, whatever the notice says (a forged or huge revision stops nothing; a restored store
counts too); a process that sees a revision gap drops its whole cache.

## Broker permissions

The NATS auth callout (`engine/nats_auth_callout.py`, see `engine/AGENTS.md`) gives each
module connection the subjects `broker.py` derives from the account's approved policy
plus its bootstrap; the broker grants at the operation level, resource-level decisions
stay in the domain services. The module docstring of `broker.py` is the exact list. In
short:

| Source | Publish | Subscribe |
|---|---|---|
| Always | IAM's read-only and self-service operations (`broker.IAM_ALWAYS`: `token`, `exchange_token`, `jwks`, `submit_manifest`, `get_manifest`, `find_service_account`, `authorize`, `filter`, `grantable`; never `abi.iam.v1.changed`), the engine's broker control `abi.broker.v1.*`, `_INBOX.>`, `abi.rpc.overflow.>` | its own inbox prefix `_INBOX.<key id>` |
| Hosting | the completion notices of its own jobs' runs (`abi.jobdone.<project>.<module hash>.<job hash>`) | `abi.agent.<project>.<sa>.>`, `abi.mod.<project>.<sa>.>`; its jobs' consumers |
| `discovery:GetJobRun` on `job_run/<project>/<module>/...` | none | that module's (or job's) completion notices: a notice only wakes a waiter, which reads the run record again |
| Each action with an Allow (any resource) and no Deny on every resource | that action's catalog `subjects` (a stream action adds the service's transfer subjects); a service without a registered catalog grants its whole `abi.svc.<service>.v1.>` | none |
| `discovery:InvokeAgent`, `GetAgentRun`, `CancelAgentRun`, `ChatModel`, `OpenApp`, `TriggerJob`, `ScheduleJob`, `CancelJobRun` | the hosting subjects of the modules the resources name | none |
| `bus:Publish` / `bus:Consume`, `event:*` | the topic and its claim checks / `evt.>` by action (`event:Append` publishes, `Query`, `QueryStream`, `QueryForConsumer` subscribe) | the topic, its queue consumers |
| Everything else | denied, `$SYS.>` and other `$JS.API.>` included | denied |

`<sa>` is the ULID part of the account's id: hosting subjects carry it as a whole token,
because NATS wildcards cannot match part of a token. A permission ending in `*` also
matches a client's literal `>` or `*`, so every grant keeps the account's own tokens before
its first wildcard. There are no response permissions: a module answers on `_INBOX.>`.
`_derive` keeps `roles.DELEGATION_SIDS` out of the derivation: the module's side of a
delegation opens no broker subject. Broker permissions lag policy by at most the callout
user's life (five minutes, ten at most); services enforce every change at once, so the
broker only narrows further. `broker_permissions` reads policies from the store, never the
cache.

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
- `create(action, type, parts)`: the create rule of "Placements". A name an existing placement
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

## Invitations and IdP group bindings

```python
grant = iam.create_pending_grant(
    "builtin", "bob@example.com", "builtin.member", "abi:acme:ws1"
)
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
  a scope, a scoped policy stays within it) hold. The inviting person holds what the policy
  grants there (see "Grant only what you hold"), as for a binding. Listing is filtered by
  `iam:ListAttachments` on the same names. `iam:ClaimPendingGrants` (admin on a
  principal) is the identity service's, as the engine.
- **A binding** gives the members of an IdP group a role at a scope: IAM finds or
  creates the ABI group `idp:<provider>:<claim value>` owned by the org of the scope
  (`abi:<org>:-`; the platform for a platform or unscoped binding), maps the claim to
  it and attaches the policy to it. Binding the same claim in another org makes
  that org its own group, so a group never holds another org's attachments. The caller is authorized for the
  attachment alone (`attachment/<policy>/idp:<provider>:<claim value>`): creating
  the group and its mapping is part of that one operation, so a workspace admin never
  needs `iam:CreateGroup` or `iam:MapIdpGroup`. One group per org serves every binding of a
  claim value there; unbinding detaches at that scope only, and only from the groups bindings
  made (named `idp:<provider>:<claim value>`): a hand-made group that maps the same claim is
  never touched, nor listed. IAM's companions of the roles
  (`builtin.platform.*` on the group) are not listed as bindings.
- `claim_pending_grants` runs at every sign-in and refresh, so its common answer (no
  invitation for this person) costs one read of the store revision: the index of who has pending
  grants is rebuilt only when the revision changed. `get_pending_grant` finds one grant by id.
  `list_idp_bindings` still reads the mappings of each `idp:` group; a store query for them is a
  follow-up.
- A policy a pending grant names cannot be deleted. NATS: `create_pending_grant`,
  `list_pending_grants`, `revoke_pending_grant`, `claim_pending_grants`,
  `bind_idp_group`, `unbind_idp_group`, `list_idp_bindings`; the broker offers each
  with the action it needs (`AttachPolicy`, `ListAttachments`, ...).

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
  container_exists=...)` applies the create rule of "Placements" and returns `commit()`,
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
  boot. The Docker templates reuse the deployment's `POSTGRES_*` secrets
  (schema `abi_iam`); `services.iam.store.dsn` points elsewhere.
- Memory: tests.
- `allow_all` is selected only by writing it; `AllowAllAuthorizer` warns when built.
  Fresh installs enforce policies.

The engine loads IAM before every other service and bootstraps it
(`IAMService.bootstrap`: catalog, managed policies, the `engine`, `api` and `idp`
service accounts and their policies), then registers every kernel catalog
(`kernel_catalogs.register_kernel_catalogs`). A serving engine gives its modules the IAM
owner itself, never a NATS facade: a check reads the caller's `CallContext` in
this process. A client-role engine gets `IAMSecondaryAdapterNATSClient`.

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
only; the other IAM operations (every mutation, every list) need
the matching `iam:` action. Bus and event grants follow the action
(`bus:Publish` vs `bus:Consume`; `event:Append` publishes, the read actions
subscribe) and a Deny of an action on a topic is honoured. The secrets IAM keeps
(`iam/...`) are readable only by `engine` over the secret service's NATS
endpoint. Wire codes: `PERMISSION_DENIED`, `GRANT_NOT_HELD` (a
change would give more than the caller holds), `NOT_FOUND`,
`CONFLICT`, `REVISION_CONFLICT`, `INVALID_ARGUMENT`, `UNAUTHENTICATED` (a
refused key). The SDK facade is
`engine.services.iam` (`naas_abi_sdk/services/iam.py`), reachable without a
dependency declaration; records are dictionaries.

## Migrating an existing install

Fresh installs enforce from the start; `authorizer: allow_all` is the only opt-out and must be written down.
For an install that predates IAM, Nexus moves what it kept itself once, at start
(`libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam/bootstrap.py`, `migrate_role_data`; see the
AGENTS.md there), and IAM is the only record afterwards:

| Before | In IAM |
|---|---|
| `workspace_members.role`, the `workspaces.owner_id` fallback | `builtin.<role>` attachments at `abi:<org>:<ws>` (the fallback becomes an explicit owner attachment) |
| `organization_members.role`, `organizations.owner_id` | `builtin.<role>` at `abi:<org>:-` |
| `users.is_superadmin`, `users[].is_superadmin` | `builtin.platform_admin` |
| `organization_role_features` | `builtin.features.<org>.<role>` |
| Workspace graph policies and per-workspace prefixes and namespaces (object storage, documents, vectors, datasets) | placements (`iam:PutPlacement`), plus Allow statements in a workspace policy for shared graphs |
| Every other existing container (module and engine namespaces, collections, repos, graphs) | platform placements, so no workspace can claim a name inside them |
| Remote modules sharing `NATS_JWT_SECRET` | service accounts, keys and approved manifests (`abi dev up` regenerates them; deployed systems run `abi iam module approve`) |
| Nexus users of the old login | users of issuer `urn:abi:nexus`, linked to the built-in IdP at first sign-in (`link_user`) |
| IAM store schema 1 (no owner scopes) | schema 2, at the store's first open: every policy and group platform-owned, except the groups IdP bindings made (named `idp:<provider>:<claim>` and mapped from that claim, with an org) whose attachments are all under `abi:<org>:`, which belong to that org (`abi:<org>:-`). A binding group schema 1 shared with other orgs, the platform or an unscoped binding stays the platform's: owned by one org, its admins could add their users to what it holds elsewhere. Two processes may open the store at once (PostgreSQL adds the columns `IF NOT EXISTS`; SQLite serializes writes). The upgrade logs a warning for each stored customer policy whose patterns reached the platform's policies or groups as `abi:-:-:iam:…` (or `${scope}:iam:…` at `abi:-:-`) and no longer match them: rewrite them `abi:*:*:iam:policy/…`, `…:iam:group/…` |
| Sessions, refresh tokens, app grants and preview tokens signed with `secret_key` | invalidated: users sign in again; workspace secrets get their own key (`secrets_encryption_key`) |

## Decisions

**Authorization is identity-based policies, denied by default.**
*Decision.* AWS-style policy documents (`Allow`/`Deny`, actions, resource patterns)
attached to users, groups and service accounts at an optional scope; no resource-based
policies; an explicit Deny wins; on behalf of a user both sides must allow; narrowed
tokens only narrow; actions are `<service>:<Action>` with an access level; resource names
are `abi:<org>:<ws>:<service>:<type>/<id>` with percent-encoded ids and `*`/`?` patterns,
never regular expressions; the org and workspace of a kernel resource come from placements,
never from a request field; every service registers a catalog and policies are validated
against them; roles are cumulative managed policies generated from the catalogs; a few
resources are sealed in code; the authorizer port is shaped like OpenFGA.
*Consequences.* The check runs in the domain service, so Nexus REST, SDK modules over NATS
and in-process callers are authorized identically (the event, vector_store and cache NATS
adapters go through their services). Every operation needs a catalog entry before it ships.
Graph access needs the query dataset restricted by the triple-store adapters. Encoded ids are
hard to read by hand: use `names.py` (never string formatting) and the admin UI, which decodes them.
Per-object sharing beyond personal resources is only expressible by naming the object in a
statement.

**IAM is a kernel service with its own SQL store.**
*Decision.* `services/iam` in core, reachable in process, over NATS (`abi.iam.v1.*`), through
the SDK and through the auth-callout responder. The store is SQL behind `IAMStore` (SQLite
default, PostgreSQL, memory), not the Document Service: IAM authorizes the Document Service
(reading a policy would need a policy), needs unique constraints, joins and atomic approval
of a manifest with its policy, and sits on the hot path of every call. Private signing keys
stay in the secret service.
*Consequences.* Every kernel service depends on IAM at boot (IAM loads first, services register
catalogs before serving). The engine stores one more database (backups and Docker templates
include it). Suspensions and grants apply at once in process and within the change event over
NATS, bounded by the 60-second cache. An OpenFGA adapter can be added behind `IAuthorizer`.

**Engine-signed tokens, service accounts and broker confinement.**
*Decision.* ES256 tokens with a JWKS, one audience each, ten minutes at most; every module,
script and CI job is a service account with a hashed, revocable, rotatable key exchanged for
tokens; a module declares a permission manifest that an admin approves; the broker confines each
connection through the NATS auth callout; `CallContext` is filled only from verified credentials.
*Consequences.* No module can impersonate `api`, `engine` or another module; a leaked module key
exposes only its approved permissions, and revoking it ends access within the callout user's life
(suspension is immediate). Each deployment creates one account and key per module (`abi dev up`
does it) and approves manifests with `abi iam module approve` or the IAM UI. Hosting subjects carry
the account token. Remote modules must run the SDK of the engine's version: an older one reads
stream info, creates streams and publishes into the jobs stream (all refused), and sends its own token
to hosts, which discovery refuses.

**Delegated tokens replace the on-behalf-of header.**
*Decision.* One mechanism, RFC 8693 exchange in IAM, for every narrow credential (sessions of Nexus,
agent delegations, app and preview links, coding and API keys). A caller acting for a user sends an
`abi:delegated:agent` token; the `Abi-On-Behalf-Of` header is refused. The actor of a call to a
module is the module. A run outlives its token by renewing it through the module's key, up to eight
hours. Links are revocable IAM grants.
*Consequences.* Nothing that is not a session can be a session. A key's scope narrows every
IAM decision made for its owner, in process and over NATS. `api` and `engine` must keep
`iam:ExchangeToken`. The deployment's `ABI_API_KEY` stays the one credential of the engine's
invocation routes until they enforce IAM. A delegation cache holds a token per user, scope and recipient for half its
life (2048 at most); a delegation that cannot be renewed fails the call rather than calling as the
account alone.

**First-party grants are enumerated; no transitional grant exists.**
*Decision.* `builtin.engine`, `builtin.api` and `builtin.job` are statement lists with a `sid` each.
The transitional policies of earlier stages are retired (`RETIRED_POLICIES`). A remote module holds
`builtin.module_bootstrap` then its approved manifest; a Nexus user holds the roles of its
memberships only. The one legacy kept is the issuer `urn:abi:nexus` for accounts of the old login
while they link to an identity provider.
*Consequences.* Zero trust is visible: a known principal with no policy is denied, and a remote
module is refused every IAM administration endpoint.

**Module scopes are a catalog of their own; viewers and members hold none.**
*Decision.* What modules expose is the `module` catalog, `module:<type>/<module>/<name>`
with `module_scope` types, placed in the workspace of the call; the module is named by
its stable identifier (an engine module's configured key, a remote module's id). The
built-in viewer and member roles leave every module scope type out, admin and owner
hold them all, with no migration grant. Nexus decides a module's agents and apps with
it (`nexus:UseAgent` stays for agents a workspace builds itself, `nexus:UseApp` for
links that are no module's app): one source of truth. Discovery keeps its platform
grants as the broker-side check. Members hold `TriggerJob` on module workflows only
(`workflow/<project>/<module>/<name>`, a second name discovery checks for a job of
kind `workflow`), as they hold `InvokeAgent` on agents: a workflow started from a
workspace runs for the user, so the host's check needs the user to hold it; a plain
job (maintenance, batch) is never a role's.
*Consequences.* After the upgrade, members and viewers use no module's agent, app,
workflow or pipeline (Abi included) until a policy grants it in their workspace. A
grant names one item or a module's (`.../acme.people/*`). The broker alone does not
tell items apart for a user: a client that reaches discovery directly with a member's
token reaches every module's agents, as before, and (new) every module's workflows,
never a plain job; Nexus and in-process agents check the scope. Bounding the broker
too would need the workspace in the trigger, which a stored trigger does not carry. A module identifier change (a renamed config key) is a new scope.

**A module declares its actions in a catalog of its own.**
*Decision.* An engine module ships `iam_catalog.yaml` beside its class, registered at
load; a remote module sends it in its manifest (`catalog`), registered at approval.
Its service is derived from the module's identifier and owned by it; reserved names
and another module's are refused. IAM names the resource of a declared action
(`authorize_declared`) in the workspace of the call, so a module never builds names.
*Consequences.* An admin approving a remote module approves its catalog with its
permissions, and a changed catalog waits for approval. A declared type is always a
module scope placed in a workspace: viewers and members need a grant, and the module's
own approved policy holds `<service>:*` so that the user's grant decides.

## Known limits and open questions

- **JetStream answers with fixed content where a module asks.** The server answers a module's
  JetStream requests on the reply subject the module chose, with no permission check, and a stream
  captures what lands on its subjects. With direct gets taken away, what a module can still aim that
  way has content it does not choose (a pub ack, an empty acknowledgement, a fetch from its own
  consumer): another topic's queue can still store a pub ack or an empty message, and bus messages
  are not authenticated. The JetStream API ignores such deliveries; a job host drops a trigger or
  cancel that is not sealed (`engine/AGENTS.md`). Proposed, not built: NATS accounts for modules.
- **Quotas.** `ABI_CLAIM_CHECKS` has no size limit beyond its seven-day age, and the overflow host's
  64 sessions and 1 GiB have no per-caller share: one module can fill either for everyone.
- **The `engine` broker login** may use every subject but `$SYS.>`: the API, Nexus and jobs run on it.
  It is not narrowed to the kernel subjects.
- **Per-object sharing** of single conversations or files beyond personal resources is the
  relationship-based (OpenFGA) question: placement and identity policies cover workspace-level
  access; sharing one object means a statement naming it.
- **Policy conditions** (`conditions`, reserved): IP ranges, time windows, MFA claims. Not needed yet.
- **Federation.** Every ABI server trusting the same IdP issuer is enough for login; cross-server
  service accounts are not designed.
- **No SCIM, no token introspection**: access tokens live ten minutes at most and suspension is
  immediate.
- Alternatives rejected: roles only (cannot say "an IdP group reads one graph and writes another",
  nor confine a module); OpenFGA now (heavier to run without Docker, a new model per service);
  resource-based policies (two evaluation paths, "what can X do" becomes expensive); the workspace
  from `CallContext.workspace_id` (any member could address another workspace); encoding the
  workspace in every data id (migrates all data); raw ids in names; regular expressions in patterns;
  HS256 with per-module secrets (each verifier would need every secret); IAM on the Document Service
  (circular).

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
