# IAM Service - AGENTS.md

## Purpose

Who may do what, for every kernel service: principals (users, groups, service
accounts), AWS-style policies, attachments, built-in roles, containers, placements,
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
  [Action catalogs](#action-catalogs), [Publishers and listing](#publishers-and-listing),
  [Sealed resources](#sealed-resources),
  [Built-in policies](#built-in-policies), [Module scopes](#module-scopes),
  [Sub-policies](#sub-policies),
  [Grant only what you hold](#grant-only-what-you-hold)
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
| `names.py` | Canonical names, paths of containers `abi:<service>:<type>/<id>/…/<service>:<type>/<id>`, id encoding, scopes and owners, `*`/`?` matching, variables |
| `catalog.py` | `ActionCatalog` (with its `publisher`), `ResourceType`, `ActionSpec`, `CatalogRegistry` (catalog format) |
| `listing.py` | The lister port (`ResourceLister`, `ListingQuery`, `ListedPage`, `ListerDirectory`) and the listing as the caller (`run_listing`, `ResourcePage`) |
| `publishers.py` | Catalogs and what the caller may grant, grouped by publisher (`by_publisher`) |
| `policy.py` | Policy documents: schema, validation (every error listed), `Statement` |
| `evaluator.py` | The evaluation algorithm: `check`, `filter`, `explain` over a `PolicySource` |
| `grants.py` | Grant only what you hold: glob containment of resource patterns, within a sub-policy's chain too, `Holdings` (what a caller holds, side by side), `grantable`, `within_chain` |
| `roles.py` | Built-in managed policies generated from the catalogs, and the enumerated ones of `engine`, `api` and engine jobs |
| `iam_catalog.py` | IAM's own `iam:*` catalog and the code-declared seals |
| `guard.py` | `ServiceGuard`: how a runtime service checks (names, require, filter, create rule, placements) and the shared wire codes |
| `enforcement.py` | `ResourceGuard`, what a data service enforces with; `scan_allowed`, `own_storage`, `internal_call`, wire codes |
| `kernel_catalogs.py` | The kernel services' catalogs (`services/<name>/iam_catalog.py`), registered at boot, and `register_listers` (what the loaded services and engine modules list) |
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
| `adapters/secondary/listers__nats.py` | `NATSModuleListers`: the listers remote modules serve, found through discovery |
| `adapters/primary/iam__primary_adapter__NATS.py` | `abi.iam.v1.*` endpoints and `abi.iam.v1.changed` |
| `adapters/iam_nats_codec.py` | Records and errors on the wire, shared by both NATS sides |
| `tests/iam__secondary_adapter__generic_test.py` | The `IAMStore` contract every adapter passes |
| `tests/iam_harness.py`, `conftest.py` | A bootstrapped service on the memory store, and helpers |
| `tests/authorization_contract.py` | The contract every runtime service passes per operation: no policy, granted, denied, in process and over NATS |
| `tests/data_service_contract.py` | The data services' contract: a table of cases for no policy, granted and denied principals, list filtering, in process and over NATS |
| `tests/grant_contract.py` | Grant only what you hold: the refusals and what keeps working, in process and over NATS |
| `tests/sub_policy_contract.py` | Sub-policies: what they grant, live narrowing, inherited Denies, `explain`, the refusals, deriving, deleting, in process and over NATS |

## Ports

**`IAMStore`** (secondary): principals (unique `(issuer, subject)` for users,
unique service-account names), static group members, IdP group mappings,
policies with optimistic revisions and their parents (`list_sub_policies`; a
parent is not deleted while it has sub-policies), attachments (unique per policy, principal
and scope), containers (unique per type and id, with their parent), placements, catalogs, keys (hashed), manifests (one row
per submitted version) and signing keys (public half and schedule). What an older version
recorded of the sets of orgs and workspaces (`iam_scope_sets`) is read as stored
(`legacy_scope_sets`) and dropped (`drop_legacy_scope_sets`) by whoever moves it into policies,
and by nothing else. Every write bumps `revision()` in
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

**`ResourceLister`** (`listing.py`, secondary): the existing resources of one type,
candidates for a listing as the caller ("Publishers and listing"). In process
(`register_lister`) or a remote module's, found by a **`ListerDirectory`**
(`listers__nats.NATSModuleListers`, discovery and `abi.mod.<project>.<sa>.<instance>.iam.list`).

## Vocabulary

| Term | Meaning |
|---|---|
| **Principal** | Who acts. A user, a group or a service account. |
| **Actor** | The principal that holds the credential on a call. |
| **On behalf of (OBO)** | The user an actor acts for. Optional. |
| **Action** | `<service>:<Action>`, one per operation, for example `triple_store:Query`. |
| **Resource name** | A path of containers: `abi:<service>:<type>/<id>/…/<service>:<type>/<id>`. |
| **Container** | A resource that holds resources: a step of their names. Declared by its catalog, registered with IAM. |
| **Policy** | A versioned document of statements. Attached to principals. |
| **Attachment** | (principal, policy, optional scope: a container, below one, or the platform). |
| **Placement** | The container a kernel resource sits in. Recorded by IAM. |
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

- A group has a `name` and an **owner scope** (`owner_scope`): the platform (`abi:`)
  or a registered container. Its name carries it (`<owner>/iam:group/<id>`, see
  "Resource names"), so the admins of that container manage it. Groups cannot contain
  groups.
- **Static members** are users or service accounts, kept in IAM. A group owned by a
  container holds only **users of its top container** (the first step of its owner's
  path: an organisation for its workspaces' groups): users with an attachment of their
  own at that container or below it. Service accounts never join one: a module's account
  is approved by its manifest. A user whose last attachment within that top container is
  detached (`detach_policy`, or `delete_container` of the container it was at) leaves
  the groups owned within it. Platform groups take any user or service account.
- **Where it is attached.** A group owned by a container receives attachments only at
  its owner or below it (`names.within_owner`: an organisation's at the organisation,
  below it or at any of its workspaces; a workspace's at that workspace or inside it),
  always at a scope.
  IAM's own companions (`builtin.platform.*`) follow its roles as for any principal. Platform groups receive attachments anywhere.
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
is optimistic concurrency), `owner_scope` and `parent_id` (the policy it is a
sub-policy of, or none: "Sub-policies"; never set on a managed policy).

**Owner scopes.** Every policy is owned by the platform (`abi:`, the default and every
managed policy's) or by a registered container; it never changes. Its name carries it,
`<owner>/iam:policy/<id>` (`abi:iam:policy/<id>` for the platform's), so whoever holds
`iam:CreatePolicy` (and the rest) there manages it. A container owns something only once it
is registered ("Containers"). A policy owned by a container:

- is written for its scope: **every** resource pattern, a Deny's included, is `${scope}`
  or starts with `${scope}/` (refused at create and update with `PolicyValidationError`;
  `policy.check_owned_document`, which Nexus's validate route calls too), so attached to
  anyone it neither grants nor refuses anything beyond its scope;
- is attached only at its owner or at a container below it, always at a scope
  (`names.within_owner`): an organisation's at the organisation, below it or at any of its
  workspaces, a workspace's at that workspace or at a container inside it. No unscoped
  attachment of it exists.

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
| `<container>` | The container: what it holds directly and itself | the container's name, `abi:nexus:organization/org-1` |
| `<container>/*` | **Below**: the container and every container under it, at any depth, each as if the policy were attached there | each container from `<container>` down to the resource's own (below) |
| `abi:` | The platform: platform-level resources | `abi:` (`${scope}/` reads `abi:`) |
| none | The policy uses no `${scope}` | none |

A policy attached at a scope must write every Allow resource pattern `${scope}` or
`${scope}/…` (a Deny only narrows, so it may name anything): the scope only fills
`${scope}`, so any other pattern would let whoever may attach at that scope grant beyond
it. **A policy attached at a container reaches only `${scope}/…`**: IAM refuses such an
attachment, refuses to update a policy attached at a scope beyond it, and enforces the rule
when it evaluates: a statement reached through a scoped attachment keeps only its
`${scope}` and `${scope}/` Allow patterns, whatever the policy says (`policy.within_scope`).
A pattern that names a type stays at its level (`${scope}/nexus:member/*` names the members
of the container, never those of a container inside it); `${scope}/*` reaches everything
below.

- **Below** replaces the organisation-wide scope: an organisation's owners and admins hold
  their role `<org>/*` (Nexus mirrors it), so the role's `${scope}/triple_store:graph/*`
  reaches the graphs of the organisation and of each of its workspaces, and its `${scope}`
  each workspace itself. A role attached at `<org>` alone reaches the organisation's own
  level: what sits directly in it, and the organisation itself.
- **The platform's own.** `${scope}` never reaches the platform's own policies, groups
  and unscoped attachments (`abi:iam:policy/…`, `abi:iam:group/…`,
  `abi:iam:attachment/…`): a statement reached through an attachment at the platform
  (`abi:`) does not match them (`evaluator`, and `grants.Holdings` leaves them out of what
  it holds), and a statement attached at a container names only what is in it. Only an
  unscoped statement written for them (`abi:iam:policy/*`, `abi:*`, `*`: the platform
  admin's, `engine`'s, `api`'s) reaches them. A role attached at the platform therefore
  never edits a platform policy, which may be attached unscoped. This rule is what the
  `%2A` names said before.

A Deny is kept whole, so a policy with a Deny outside `${scope}` refuses beyond the
scope it is attached at. Such a policy (`confined_to_scope` but not
`wholly_within_scope`, only ever the platform's) is attached at a scope, invited to
(`create_pending_grant`) or bound (`bind_idp_group`) only by whoever may also attach it
unscoped, `iam:AttachPolicy` on `abi:iam:attachment/<policy>/<principal>`: the platform
admin. A scope's admins and owners are refused with `PermissionDeniedError`, and lists at a
scope (`list_policies(scope=)`, Nexus `/attachable-policies`) do not offer it to them.

An attachment is named at its scope's container, `<container>/iam:attachment/<policy>/<principal>`
(a below one too; the platform's and an unscoped one `abi:iam:attachment/…`, which only
unscoped statements reach). Attaching below a container grants at every container under it,
so "Grant only what you hold" checks it there: an admin of an organisation's own level holds
nothing in its workspaces and attaches nothing below it.

**Variables** are substituted into resource patterns before matching, against
the principal whose policies are being evaluated (`X` in `principal_decision(X)`
below): the actor when computing the actor's decision, the OBO user when
computing the user's.

| Variable | Value |
|---|---|
| `${scope}` | The attachment's container's name (each container from it down, for an attachment below one; `abi:` at the platform, where `${scope}/` reads `abi:` and `${scope}` alone matches nothing). Invalid in a policy attached without one. |
| `${principal.id}` | `X`'s principal id. A policy reached through a group resolves to the member being evaluated, never to the group; percent-encoded as one segment. |
| `${user.id}` | The call's user: the OBO user if the call is on behalf of one, else the actor if it is a user, else unresolved. The same on both sides, so an actor's policy can name the user it serves. |
| `${module.id}`, `${module.project}` | Manifest-only: bound when a module's manifest is approved; they match nothing for any other principal. |

A statement with an unresolved variable matches nothing. Variables are not
allowed in actions. On a Nexus call the actor is `api` and the user is the
signed-in one: `builtin.self` is attached to the user, so in the user's decision
its `${principal.id}` is the user; `api`'s policies never see the user as
`${principal.id}`.

## Resource names

A resource name is a **path of containers**: `abi:`, then the steps of the containers
the resource sits in, from the top, then the resource's own step.

```abnf
resource-name  = "abi:" *( container-step "/" ) step
container-name = "abi:" container-step *( "/" container-step )
platform       = "abi:"                                     ; the path of no container
container-step = service ":" type "/" segment               ; a container's id is one segment
step           = service ":" type "/" id
service        = %x61-7A *( %x61-7A / DIGIT / "_" )         ; catalog name
type           = %x61-7A *( %x61-7A / DIGIT / "_" )         ; declared in the service catalog
id             = "-" / segment *( "/" *pchar )              ; only the last step's id may be a path id
segment        = 1*pchar
pchar          = unreserved / pct-encoded
unreserved     = ALPHA / DIGIT / "-" / "." / "_" / "~"
pct-encoded    = "%" 2HEXDIG                                ; uppercase hex
```

```text
abi:nexus:organization/org-1/nexus:workspace/ws-2/triple_store:graph/<iri>
abi:nexus:organization/org-1/nexus:workspace/ws-2/crm:project/p-9/crm:deal/d-1
abi:nexus:organization/org-1/nexus:member/u-7
abi:model_registry:model/gpt-x                      (the platform: no container)
```

- **Parsing.** Ids are percent-encoded, so a raw `:` appears only between a step's
  service and type: after `abi:`, the `/`-separated tokens holding a raw `:` start the
  steps; every other token is an id segment. A container step has exactly one id segment;
  the last step takes the rest (`names.parse_resource_name`).
- **Containers.** A catalog marks which of its types are containers
  (`ResourceType.container`, "Action catalogs"). A container of any service may sit in a
  container of any other; core knows that a container holds resources, nothing more. A
  container's **name** is its own resource name, `<parent>/<service>:<type>/<id>`: the
  organisation `org-1` is `abi:nexus:organization/org-1`, its workspace `ws-2` is
  `abi:nexus:organization/org-1/nexus:workspace/ws-2`. Actions on a container are decided
  on that name.
- **One container per resource.** Each resource sits in exactly one container, or in
  none (the platform, `abi:`). Something used in several places (an agent, a shared graph)
  is shared through policies.
- **The platform** is the path of no container, written `abi:` where a container is
  expected (an owner, a scope, a placement): `abi:model_registry:model/gpt-x` is
  platform-level.
- `-` as the whole `id` names a singleton (`service/-`).
- **No reserved names.** Nothing is named with `%2A` or any marker: the platform's own
  policies, groups and unscoped attachments are named at the platform
  (`abi:iam:policy/<id>`), and the rule that keeps them from the scopes is explicit
  (see "Attachments and scope": `${scope}` never reaches them).

**Encoding ids.** The id is percent-encoded UTF-8: every octet outside
`unreserved` is encoded, including `:`, `/`, `*`, `?`, `%` and spaces. Each
resource type declares its id kind in its catalog:

- **`opaque`**: one segment, the whole value encoded (a `/` becomes `%2F`): graph
  IRIs, key-value, cache and secret keys, event types, model ids, every container's id.
  `http://ontology.naas.ai/graph/x` becomes `http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fx`.
- **`path`**: a hierarchy; each part is encoded on its own and the parts joined with
  a raw `/`: object paths, document namespace/collection/id, dataset
  namespace/name, vector collection/id. Object storage joins `prefix` and `key`
  with one `/` after stripping leading and trailing `/` from the prefix: prefix
  `workspaces/ws-1/files`, key `q3 report.pdf` is `object/workspaces/ws-1/files/q3%20report.pdf`.
  A container type is never a path type.
- **`singleton`**: `-`, for service-wide resources.

Canonical names are built and parsed only by `names.py` (`resource_name(..., container=)`,
`container_name`, `parse_resource_name`, `parse_container`), never by string formatting in
callers (SDK modules do not build names: the engine's services and IAM do).

**Wildcards** are unchanged. A resource pattern is matched against the whole canonical
name. `*` matches any sequence of characters, including none and including `:` and `/`
(it crosses levels); `?` matches exactly one character of the encoded form (so it can match
one character of `%2F`); everything else is literal. There is no escaping and there are no
regular expressions: canonical names never contain a raw `*` or `?` (they are `%2A`,
`%3F`), so a wildcard is never confused with a literal. `*` alone matches every resource.
**A pattern that names a type stays at its level**: the step `<service>:<type>/` must
follow the container literally, and a raw `:` is only ever a step's, so
`<container>/nexus:member/*` names the members directly in the container, never those of a
container below it. `<container>/*` reaches everything below, at any depth. End an id
before the wildcard: `…/nexus:organization/org-1/*` matches org `org-1` only,
`…/nexus:organization/org-1*` also matches `org-10`.

| Pattern | Matches |
|---|---|
| `abi:nexus:organization/org-1/nexus:workspace/ws-2/*` | everything in ws-2, including what its CRM projects hold |
| `abi:nexus:organization/org-1/*` | everything in org-1 and in all its workspaces |
| `abi:nexus:organization/org-1/nexus:member/*` | org-1's members only |
| `abi:nexus:organization/org-1/*/triple_store:graph/*` | every graph anywhere under org-1 |
| `abi:nexus:organization/org-1` | org-1 itself (its own actions: `nexus:UpdateOrganization`) |
| `abi:triple_store:graph/*`, `abi:*/triple_store:graph/*` | every platform graph; every graph in some container. Together, every graph (`names.anywhere`) |
| `abi:document:namespace/people`, `…:collection/people/*`, `…:document/people/*` | the platform's `people` document namespace, its collections and documents. Not `document:*/people*`: that also matches another namespace's collection named `people`. |

A type stays at its level only when the type is not a container of the same type's
service nested in itself: `<C>/crm:folder/*` also reaches what a folder inside a folder
holds, as it reaches everything inside the folders directly in `C`.

## Containers

IAM keeps the **registry of containers** (`iam_containers`), each with its type, id and
parent: `(service, type, id) -> parent container` (`ContainerRecord`). A container's id is
unique within its type, so its path is read from its type and id alone
(`iam.container(service, type, id)`, None for an unknown one).

- **Registering** (`iam.register_container(service, type, id, parent=)`) is a create on its
  name as placed: the caller needs the type's create action (the action its catalog marks
  `creates: true` on that type) on `<parent>/<service>:<type>/<id>`. The parent must be the
  platform or a registered container, and the type a container type of a registered
  catalog. A type that names its `parents` sits in those only (`ValueError`
  elsewhere). Registering again under the same parent changes nothing; under another parent
  it is refused (`IAMConflictError`): a container never moves.
- **Deleting** (`iam.delete_container(service, type, id)`) needs the type's delete action
  (marked `deletes: true`) on its name. It drops what the container owns and everything
  below it, deepest first: its containers, the policies and groups they own (a policy with
  its attachments and invitations, a group with its attachments, members and mappings,
  sub-policies before their parents), every attachment, pending grant and binding at them
  (deep ones included), and their placements. A user left with no attachment within the
  top container of its path leaves the groups owned there.
- **Who registers.** naas_abi registers its organisations and workspaces as it creates
  them, with its own account (`api`), and deletes them with them: a workspace's parent is
  its organisation, a workspace in no organisation sits at the platform. A remote module's
  SDK registers its own (`engine.services.iam.register_container`), as the user it acts for
  when there is one: both must hold the create action.
- **Over NATS**: `register_container`, `delete_container`, `get_container`. Reading a
  container's path (`get_container`, `IAMService.read_container`) answers only a caller
  allowed some action of the container's type (its catalog's) on it; anyone else gets
  none, as for an unknown container, so an unapproved module learns neither that a
  workspace exists nor which organisation holds it. In process, the services that own a
  resource read the registry unchecked (`container`, `call_container`).

## Placements

A kernel service builds `<service>:<type>/<id>` from the request. It cannot take
the container from the request (anyone could claim a container they belong to while
addressing another container's data), and data ids rarely encode one (Nexus graph IRIs
are `…/graph/<slug>-<uuid>`). So IAM keeps **placements**: `(service, id-key) -> container`.

- The container is a container name, or the platform `abi:`. `id-key` is an exact canonical
  id, or a prefix ending in `*` (plain string prefix matching on the canonical id, covering
  every type of that service whose id starts that way: a document placement on
  `nexus-ws-1` plus `nexus-ws-1/*` covers the namespace, its collections and its
  documents).
- **Resolution** (`IAMService.placement_of`): an exact key beats a prefix, a longer
  prefix beats a shorter one; no match means the resource is platform-level,
  `abi:<service>:<type>/<id>`. A resource type a catalog declares `placement: platform`
  (model_registry models, discovery modules) always resolves to platform. A container type
  is never placed: its name comes from the registry.
- **Id prefixes.** A resource type marked `id_prefix: true` holds children whose ids extend
  its own (`<its id>/<rest>`): document `namespace` and `collection`, vector_store
  `collection`, source_control `repo`, dataset `namespace`. They are not containers (a
  container is a step of the path): a placement on one is written as a pair, the exact id
  and the prefix `<id>/*`, so its children resolve to its placement, platform included.
- **Every existing id prefix has a placement.** Those created through a service record one
  at creation; approving a module's manifest records platform placements for the module's
  own `<module_id>` document and dataset namespaces unless already placed (`modules.py`);
  Nexus places its per-workspace prefixes and namespaces in the workspace when it creates
  one. "No placement covers this name" therefore means a new top-level resource or a new
  id prefix.

**The container of the call.** `CallContext.container` is the container a call is made in,
a container name, or none. It is request data, not identity: a caller may name any
container, and IAM reads it only to name what the call creates and the module scopes and
declared actions it uses (see "Module scopes"). IAM takes it only once it checked that it is
the registered path of its last step (`IAMService.call_container`); a container it does not
know, or named under another path, places nothing and names nothing: the create or the use
is refused as not found. It travels in process (`CallContext.container`), over NATS
(`common.CallContext.container`) and through the SDK (`call_context.container`).

A call from the published SDK 0.2 sets the older `common.CallContext.workspace_id` and no
container. The engine refuses such a call when `workspace_id` is set
(`INVALID_ARGUMENT`, "upgrade the SDK: this engine takes the container of a call, not a
workspace id", `nats_identity`), so it is never placed wider than before; a call of SDK
0.2 that names no workspace runs as before.

**Writing placements**

1. **On creation.** A create operation is marked `creates: true` in the catalog.
   Before it runs, the service resolves the placement of the would-be name
   (`ServiceGuard.create`, `ResourceGuard.create`). The create always needs its
   action allowed on the name *as placed*.
   - A child of an existing id prefix, or any name an existing placement covers,
     takes that placement. The call's container must be empty or equal to it
     (for a platform placement: empty); on a mismatch the call is denied with the
     "not found or permission denied" outcome computed on the name as placed. Nothing
     new is recorded. So a member of ws-A cannot claim a name inside ws-B's namespace or
     a module's platform namespace by making the call in ws-A.
   - The call's container decides only for a name no placement covers. With one set
     the name is placed in it; a container IAM does not know (or names under another
     path) makes the create not found, whoever asks: it is placed nowhere. With none
     the name is platform-level. On success `Creation.record()` writes the
     placement: exact for a top-level resource (none when platform-level), exact plus
     `<id>/*` for an id prefix, platform included.
   - **Implicit id prefixes**: a create whose name sits under an id prefix that does not
     exist yet (the first `dataset:Create` in a new namespace) first places that prefix by
     the rule above, then creates the child inside it.
2. **Explicitly**, with `iam:PutPlacement`, mainly for prefixes.
3. **On delete.** Deleting an id prefix or placed resource drops the placements the
   create recorded (`forget`); deleting a container drops every placement in it or below.

The container of the call never renames an existing resource or overrides a placement:
for an operation on an existing resource it is ignored. Placements are cached like
policies. Placements are written as `engine` (`PLACEMENT_WRITER`), so a caller never needs
`iam:PutPlacement` to create.

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
  S = statements of every policy attached to X and to each of X's effective groups,
      and, for a sub-policy, the Deny statements of each policy of its chain
  if any Deny statement in S matches:   EXPLICIT_DENY
  if any Allow statement in S matches,
     and, for a sub-policy's, an Allow of each policy of its chain matches too:
                                        ALLOW
  otherwise:                            IMPLICIT_DENY
```

- **Sub-policies** ("Sub-policies") narrow: an Allow of a sub-policy counts only where an
  Allow of its parent, and of each policy above it, matches the same action and resource,
  their variables filled from the sub-policy's attachment. Their Denies refuse through it.
  IAM reads the chain when it decides; nothing is copied.

- An explicit Deny wins over any number of Allows, including Allows reached
  through another group.
- **OBO is an intersection**: an agent module that may write graph G, acting for
  a user who may only read G, cannot write G.
- **Token narrowing (`T`) only narrows.** It holds Allow statements only (a
  Deny is rejected when the token is issued; a statement's `actions` and
  `resources` must be lists of strings, anything else matches nothing).
- **Resource names are container paths.**
*Decision.* A name is `abi:`, the steps of its containers from the top, then the resource
(`<service>:<type>/<id>` each, ids percent-encoded, only the last id a path). A catalog marks
its container types; IAM registers containers with their parents and knows nothing more of
them: no organisation, workspace or other module concept. Placements map a resource to a
container, the call carries the container it is made in (`CallContext.container`), and
attachments and owners are any container, below one, or the platform. Wildcards are
unchanged: a type stays at its level, `<container>/*` reaches everything below. What
`%2A` names did is an explicit rule: `${scope}` never reaches the platform's own policies,
groups and unscoped attachments. Roles are attached at any container and stay at its level;
attached below a container (`<container>/*`) they count at every container under it. A
container type's actions are decided at the container itself (`${scope}`), its create action
in its parent.
*Consequences.* Any module declares containers (a project in a workspace) and a policy
attached at one reaches what it holds and nothing else. naas_abi is one such module: its
`organization` and `workspace` are containers it registers through IAM's public API, and its
mirror of an organisation's owners and admins is an attachment below the organisation. A
name is longer and an id at a container's place has no `/`. SDK 0.2 calls naming a workspace
are refused. A rule that read "organisation versus workspace" is restated per container, and
these behaviours change (listed for the owner in the task notes): a group of a workspace in no
organisation takes the users of that workspace only (before: of every workspace in no
organisation); an admin of an organisation's own level may detach an attachment below the
organisation of a role below owner (before: only one held there); a role attached at the
platform no longer manages attachments at the platform (only unscoped grants do); a
container type nested in itself (a folder in a folder) is reached by a grant on the type at
the level of the outer one; registering a container needs its create action, deleting one its
delete action (before: `iam:PutScope`, `iam:DeleteScope`).

**Policies are the one place access is decided.** Nothing bounds an Allow but its own
  chain and the other side of the call: there are no sets of an org or a workspace, and no
  workspace switch (what an older version kept of them became policies: "Migrating an
  existing install").
- Reasons: `allow`, `explicit_deny`, `implicit_deny`, `suspended`, `sealed`.
  `explain` returns the outcome, the reason and the deciding statement (side,
  policy id, statement index or `sid`, attachment, scope, group), and the chain: for an
  Allow of a sub-policy, `bounded_by`, the statement of each parent that allowed it too,
  nearest first; for a parent's Deny refusing through a sub-policy, `through`, the
  sub-policies it was reached by, the attached one first.
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

**Freshness.** Policy (a parent's included), attachment, group, placement and status changes take effect
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
`iam:RegisterCatalog` on `abi:iam:catalog/<service>`.

```yaml
service: triple_store
version: 1                      # bumped on every change; IAM keeps the highest
resource_types:
  - name: graph
    id: opaque                  # opaque | path | singleton
    placement: placed           # placed | platform
    container: false            # true: a container, a step of the names it holds ("Containers")
    id_prefix: false            # true: children's ids extend this id (not a container)
    platform_companions: false  # true (a container type): a role attached at one brings the platform companions
    parents: []                 # a container type: the containers it sits in ("<service>:<type>", "-" the platform); empty: any
    personal: false             # true: the id starts with the owner's principal id
    policy_only: false          # true: no built-in role holds it, a policy grants it
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
    creates: true               # placed in the container of the call; a container type's: registering one
    subjects: ["abi.svc.triple_store.v1.create_graph"]
  - name: DropGraph
    level: admin
    resource_types: [graph]
    owner_only: false           # true: an admin action no role below owner holds
    deletes: false              # true, on a container type: deleting one (iam.delete_container)
platform_access:                # first-party catalogs only: what the roles' platform companions reach
  - resources: ["view/*"]       # <type>/<id>, named abi:<service>:<type>/<id>
    viewer: [QueryView]         # builtin.platform.viewer and .member
    member: []                  # builtin.platform.member
    self: []                    # builtin.self
```

`iam/v1/iam.proto` defines `ActionCatalog`, `ResourceType`, `ActionSpec` and
`PlatformAccess` with the same fields.

**What the built-in roles leave out is the catalog's to say**, so core names no
service's actions or types in its roles (`roles.py`):

- `policy_only` on a resource type: no role holds it at its scope, owners included; only
  a policy grants it (Nexus's `feature`).
- `owner_only` on an `admin` action: no role below owner holds it (Nexus's
  `DeleteWorkspace`, `DeleteOrganization`). Validation refuses it on another level.
- `platform_access`: rows of the platform types table ("Built-in policies") for this
  catalog's platform-level resources: `viewer`, `member` and `self` actions, each a
  registered action of the catalog, on `<type>/<id>` patterns of its types. Only a
  first-party catalog (no `module`) declares them: a module's catalog grants nothing to
  every member, and validation refuses one that tries.
- `container` on a resource type: a container ("Containers"): a step of the names of what
  it holds, registered with IAM, never placed, never a path type; its catalog declares an
  action on it marked `creates: true` (registering one) and may mark one `deletes: true`
  (deleting one). Any catalog, a module's included, declares containers.
  `platform_companions` on a container type: a role attached at one brings the platform
  companions ("Built-in policies"; Nexus's `workspace`). `parents` on a container type:
  the containers it may sit in (`<service>:<type>`, `-` for the platform; empty: any):
  registering one elsewhere is refused, and "Grant only what you hold" counts its names
  there only (`grants.universe`), so a create action granted with `*` (Nexus's
  `CreateOrganization` on `abi:nexus:organization/*`) reaches no organization inside a
  workspace. Nexus's `organization` sits at the platform, its `workspace` in an
  organization or at the platform.
- `id_prefix` on a resource type: its id is the prefix of its children's ids (document
  `namespace` and `collection`, ...): placed as a pair ("Placements"). Formats 1 and 2
  called it `container`; a stored catalog of those formats is read with its `container`
  as `id_prefix`, and so is a catalog over NATS (`ResourceType.id_prefix` keeps the field
  number `container` had, the new `container` has its own). A module's catalog in a
  manifest has no format: there `container` is the new flag.
- `format` (`catalog.CATALOG_FORMAT`, 3): in the stored form (`to_dict(stored=True)`,
  `from_dict(..., stored=True)`) and over NATS, never in what a module manifest hashes, so
  no manifest changes hash on an upgrade. A same version registered again with a lower
  format (an older writer) never replaces the stored one: it is ignored.
  A stored catalog written before the flags has none (format 1) and says nothing of them,
  which must never read as "nothing is policy only": a **first-party catalog whose flags
  are unknown holds nothing for the built-in roles or the platform companions** until it
  is registered again (`ActionCatalog.flags_known`). IAM loads the stored catalogs and
  regenerates the roles at boot, so an engine started on an older store narrows (that
  service's actions are no role's for a moment), never widens, before or after a
  registration that fails. A module's catalog has no flags to read.

Rules: action names are unique within a service; a new version may only
add actions or resource types, and removing one is refused while a policy still names
it explicitly; `subjects` drives broker permissions (stream actions list their
service's transfer subjects, in-process-only actions list none).

**Request-to-resource rules shared by every service**

- **Ids are canonical**; the container comes from placement (or, for a container, the
  registry), never from the request.
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
| `document` | `namespace`, `collection` (id prefixes), `document` (path) |
| `keyvalue`, `secret` | `key` / `secret` (opaque) |
| `cache` | `key` (opaque), `service` (singleton, platform) |
| `vector_store` | `collection` (id prefix), `vector` (path), `service` (singleton, platform) |
| `triple_store` | `graph` (opaque), `view` (opaque, platform), `schema` (path, platform: a schema of the schema graph by its source) |
| `dataset` | `namespace` (id prefix), `dataset` (path), `catalog` (singleton, platform) |
| `event` | `event_type` (opaque), `cursor` (path) |
| `activity_log` | `actor` (opaque, personal, platform), `service` (singleton, platform) |
| `email` | `sender` (opaque, platform), `message` (opaque, placed on send) |
| `model_registry` | `model` (opaque, platform) |
| `discovery` | `module`, `agent`, `model`, `app`, `job`, `job_run` (path, platform), `run` (path, personal, platform) |
| `source_control` | `repo` (id prefix), `branch`, `proposal` (path), `forge_user` (personal, platform) |
| `coding_environment` | `environment` (path, personal, placed), `template` (platform), `coder_user` (personal, platform) |
| `identity` | `provider` (opaque, platform) |
| `iam` | `attachment` (path, at its scope's container), `policy` and `group` (opaque, at their owner); `principal`, `key` (personal for personal keys), `manifest`, `placement`, `container`, `catalog`, `audience` (platform); `scope` (deprecated, authorizes nothing) |
| `module` | `agent`, `app`, `workflow`, `pipeline` (path, module scopes): see "Module scopes" |
| `<module service>` | a module's own catalog (`acme_people` for `acme.people`), every type a module scope: see "Module scopes" |
| `nexus` | registered by Nexus at start, not by core: `organization` and `workspace` are its containers; see `libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam_admin/AGENTS.md` |

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

## Publishers and listing

What the policy builder shows: each publisher, its resource types, their actions, and the
existing resources of each type that the caller may list.

**Publishers.** Every catalog names who publishes it (`ActionCatalog.publisher`):

| Publisher | Catalogs |
|---|---|
| `engine` (the default) | the kernel services' (`kernel_catalogs.py`), `iam`, and the `module` catalog itself |
| `naas_abi` | `nexus`, registered by Nexus |
| a module, by its key | its declared catalog (its publisher is its `module`, whatever it writes), and its agents, apps, workflows and pipelines of the `module` catalog |

A module's key is a remote module's id, an engine module's configured key (`module_key`).
The `module` catalog is the engine's, but each of its resources is one module's:
`<container>/module:<type>/<module>/<name>` belongs to `<module>`, so a view by publisher
shows the `module` types under each module that exposes some (`publishers.by_publisher`).
`publisher` is in the stored form and on the wire (`ActionCatalog.publisher`), written only
when it is neither `engine` nor the catalog's own module, so no module manifest changes hash.

**Listers.** A resource type may have a lister (`listing.ResourceLister`): given a
`ListingQuery` (service, type, container, search text, the name to start after, a page
size) it returns the type's existing resources in that container (in it or below it), by
canonical name, sorted by name, after the name given, at most a page, and whether there are
more (`ListedPage`). It finds candidates and decides nothing: what it returns is filtered as
below before anyone sees it. `listing.page_of` pages an in-memory list for one.

- **In process**, for the engine's services and engine modules:
  `iam.register_lister(service, type, lister)` (`IAMService`, not over NATS; the catalog must
  be registered and declare the type; a later registration replaces an earlier one). The
  engine registers, once its modules are loaded, the listers its loaded kernel services
  offer (each service's `iam_listers()`, `{(service, type): lister}`) and its modules'
  (`BaseModule.iam_listers()`, for its declared catalog), as the engine
  (`kernel_catalogs.register_listers`; one refused is logged, its type offered as wildcards);
  naas_abi registers its own at start.
  A kernel lister reads its adapter unchecked (the graphs, collections, namespaces, objects,
  event types, models, datasets, repositories, providers, templates it holds), its items named
  where IAM places them (`ResourceGuard.name`): `list_resources` is the one check, so a
  listing is filtered once, and "nothing here" (an object prefix that does not exist) is an
  empty page, not a failure. The services' own list calls stay guarded for their callers.
  Reading unchecked keeps the service's own input rules: object storage lists under the
  caller's search text only when it is a plain path (no `.`, `..` or empty segment, no
  leading `/`, the check every guarded object call makes), else nothing, since a name is
  checked as written while the backend lists what the path resolves to.
- **Over NATS**, for a remote module: the SDK serves the listers a module registers
  (`Module.listers`, `@lister`) on `abi.mod.<project>.<sa>.<instance>.iam.list`
  (`ListerRequest` / `ListerResponse`) and names their types in its discovery descriptor
  (`ModuleDescriptor.listers`). The host subscribes before the instance renews as
  initialized, and discovery reports an instance `STARTING` until then, so IAM, which asks
  `READY` instances only, never picks one that does not answer yet. A serving engine on NATS
  gives IAM a directory of them
  (`IAMService.remote_listers`, `adapters/secondary/listers__nats.py`): for a type of a
  module's catalog with no lister in process, IAM asks a ready instance of that module that
  names the type (at most two instances, each within the directory's timeout, all within one
  wait; the directory is closed at the engine's shutdown). `has_lister` asks the same
  directory, so a type of a module's catalog that no ready instance lists is offered as
  wildcards in the publishers' view too. No action names that subject, so the broker lets only
  the engine's own connections publish there; the module answers as itself, and its answer is
  filtered here.
- **Containers**: IAM lists a container type itself, from its registry. A lister registered
  for one only adds labels: an item it returns that the registry does not hold under that
  name is dropped, and the registry alone answers when it has none or it fails.
- **Singletons**: IAM lists the one resource of a singleton type itself:
  `<container>/<service>:<type>/-` for a placed one at a container, `abi:<service>:<type>/-`
  for a platform one at the platform.
- **A type with none of these is offered as wildcards only** (`ResourcePage.listed` false).

**A listing runs as the caller.** `iam.list_resources(service, type, scope=, text=,
cursor=, limit=, module=)` returns a `ResourcePage`:

- **Scoped.** `scope` is a container or the platform (`abi:`); below a container
  (`<container>/*`), that container. Only what sits in it or below it is returned, and the
  container itself when it is of the type asked (what `${scope}` names there: a workspace's
  Workspaces are that workspace): what a policy attached there can name (a platform resource
  is listed at the platform only; `listing.at_container`).
- **Only what the caller may list**: a resource is kept when one of the type's `list`
  actions allows it, or, for a type with no `list` action, any action of the type, as
  `filter` decides for the current caller (`listing.listing_actions`). A stranger gets
  nothing. It needs no `iam:*` action: like `grantable`, it says only what the caller could
  already list.
- **Searched.** `text` keeps the resources whose id or label contains it, case folded.
  `module` keeps the `module` catalog's resources of that module only.
- **Paged by name.** `cursor` is the last name of the previous page; `next_cursor` is None at
  the end. IAM reads the lister page by page until its own page is full, examining at most
  `listing.MAX_EXAMINED` candidates and `listing.MAX_SECONDS` per call (a page may then be
  short, with a `next_cursor`). What a lister returns outside the scope, after-cursor order or type is
  dropped.
- **A lister that fails** (raises, times out, answers what cannot be read): the type is
  offered as wildcards (`listed` false) and the failure is logged at warning level with the
  service and the type. It never fails the call.
- An unknown service or type is `IAMNotFoundError`; a malformed scope `ValueError`.
- Over NATS: `list_resources` (`ListResourcesRequest` / `ListResourcesResponse`), the same
  answer; in the SDK, `engine.services.iam.list_resources`.

What a caller may grant at a container (`grantable`) is per catalog; by publisher and type,
`publishers.by_publisher(catalogs, grantable, modules=, listable=)` groups it: the engine
first, then naas_abi, then the modules by key, each with the types the caller may grant
something of, each type with its actions, what the caller may grant of each, and whether
it is listed. Under a type, an action keeps only its granted patterns that can name one of
that type's resources at the scope (`by_publisher(scope=)`, `grants.overlaps` within the
type's names: `grants.universe(..., nesting=)`, where each container sits only in its
parents, so no organisation is in a workspace); a `module` catalog action goes under a
module when one of them can name that module's items. The nesting is for showing what a
pattern names only: IAM decides within the names without it. A pattern holding a literal
step of a type that is no container and not the type itself (`.../nexus:agent/*` under
graphs) names none of the type's resources, since a name is its containers' steps, then
its own: it is left out before the search, which would leave it out too, slowly (an owner
who is also the platform admin holds every type's pattern). Nothing appears that the
caller may not grant.

## Sealed resources

A sealed resource is a resource pattern bound to one principal. No other principal
is ever allowed on it, whatever its policies say, `engine`, `api` and the platform
admin included, and acting on behalf of a user never opens one. Seals are declared
in code by the service that owns them (`iam_catalog.py`, next to each service's
catalog) and loaded at boot; no API changes them, so editing policies cannot open
them. The seals: the built-in IdP's document namespace `idp` (namespace, collections
and documents) and secrets `idp%2F*`, sealed to `idp` (and to the module id `idp`,
`Seal.module_id`); `secret/iam%2F*`, sealed to `engine`. Seals match at any placement:
each is written for the platform and for any container (`names.anywhere`,
`abi:document:namespace/idp` and `abi:*/document:namespace/idp`). An operator who needs the IdP's data back uses the IdP's own admin API
or the database directly, outside ABI's authorization by design.

## Built-in policies

Built-in policies are managed: IAM generates their documents from the registered
catalogs (so a new service's actions join the roles automatically), stores them with
explicit action lists (so `explain` shows real statements), and regenerates them when
a catalog version changes (`roles.py`). **Roles are attached at any container**:
"viewer on workspace W" is `builtin.viewer` attached with scope
`abi:nexus:organization/O/nexus:workspace/W`, "admin of organisation O and of everything
in it" is `builtin.admin` at `abi:nexus:organization/O/*`.

For each catalog resource type that can be placed in a container, the role's statement
covers `${scope}/<service>:<type>/*`; a personal type covers
`${scope}/<service>:<type>/${principal.id}` and `…/${principal.id}/*` instead
(`${principal.id}` is the member being evaluated, so on a Nexus call it is the user,
not `api`). **A container type** is decided where it is: the actions on it cover
`${scope}`, the container the role is attached at (an admin of W updates W), and its
create action (`creates: true`) covers `${scope}/<service>:<type>/*`, so the role at a
container makes containers of that type in it (an admin of O creates a workspace in O)
and nothing else of them: a role attached at O never reaches a workspace of O, unless it
is attached below O. **The roles are cumulative**: `viewer` ⊆ `member` ⊆ `admin` ⊆
`owner`; each holds every statement of the role below it, so a principal needs one role
attachment per scope.

| Policy | Allows on the scope's types | Excludes |
|---|---|---|
| `builtin.viewer` | every `list` and `read` action | every `policy_only` type; the whole `iam` catalog; every module scope type |
| `builtin.member` | viewer, plus every `write` action | every `policy_only` type; the whole `iam` catalog; every module scope type |
| `builtin.admin` | member, plus every `admin` action, except on the `iam` `attachment` type; the scope's policies and groups (`ListPolicies`, `GetPolicy`, `CreatePolicy`, `UpdatePolicy`, `DeletePolicy`, `ListGroups`, `GetGroup`, `CreateGroup`, `DeleteGroup`, `AddGroupMember`, `RemoveGroupMember` on `${scope}/iam:policy/*` and `${scope}/iam:group/*`); `iam:ListAttachments` on `${scope}/iam:attachment/*`, and `iam:AttachPolicy` and `iam:DetachPolicy` on `${scope}/iam:attachment/builtin.admin/*`, `…/builtin.member/*`, `…/builtin.viewer/*` and `…/pol_*/*` (customer policies: the scope's own and those above it, IAM refusing one owned elsewhere) | every `policy_only` type; every module scope type; anything on `attachment/builtin.owner/*` and the other managed policies; `iam:MapIdpGroup`, `iam:UnmapIdpGroup`; every `owner_only` action |
| `builtin.owner` | admin, plus every action on every `attachment/…` (owner included) and every `owner_only` action | every `policy_only` type; every module scope type; `iam:MapIdpGroup`, `iam:UnmapIdpGroup` |
| `builtin.platform_admin` | `*` on `*` (attached without scope) | sealed resources |
| `builtin.self` | held implicitly by every user (no attachment row, unknown users included; `explain` shows it with no attachment id) | none |

- **IAM administration is the admins' and owners'.** Viewers and members hold nothing
  of the `iam` catalog at their scope (no list, no read): every IAM administration
  call refuses them. Owners and admins at a container manage that container's policies
  and groups and attach them there; attached below a container (an organisation's owners
  and admins, which Nexus mirrors), they manage those of every container under it too.
  They also see, in a list at their scope, what they may attach there from above (see
  "Service API").
- **Owner protection.** An admin cannot attach or detach `builtin.owner`; demoting or
  removing an owner means detaching their owner attachment, so only an owner can, at
  every container alike.
- **A role at a container stays at its level.** A role attached at a container reaches
  what sits directly in it and the container itself; one attached below it reaches every
  container under it as well. Nexus attaches an organisation's roles at the organisation
  and mirrors its owners' and admins' below it: organisation membership alone never grants
  workspace access.
- **Platform types.** A role at a container never reaches a platform-level resource
  (`abi:<service>:…`). Two more managed policies, kept in step with role attachments by IAM,
  carry what members need there (`roles.PLATFORM_TYPES` is the kernel services' table:
  models, discovery modules/agents/apps/runs, views, coding templates, the user's own
  forge/coder/activity/key/principal resources, drives; a first-party catalog adds its rows
  with `platform_access`, as Nexus does for creating an organization, provider models and a
  user's own files and storage): `builtin.platform.member` while the principal has a
  `member`, `admin` or `owner` attachment that brings the companions,
  `builtin.platform.viewer` while it has only `viewer` ones. **An attachment brings them**
  when it is below a container, or at a container whose type its catalog marks
  `platform_companions: true` (Nexus's `workspace`); an attachment at any other container
  (an organisation's own level) brings neither. Because Nexus calls as `api` on behalf of
  the user, the user must hold these, not only `api`. A member holds `discovery:TriggerJob`
  on `workflow/*`, the second name of every job of kind `workflow` (a viewer nothing), as it
  holds `InvokeAgent` on `agent/*`: which workflow it starts is the module scope's. An
  explicit Deny on a workflow's `job/…` name still refuses it (discovery
  `trigger_decision`). Not reached by any role (platform admin, built-in accounts and
  explicit policies only): plain jobs and job runs, email senders and messages,
  `dataset:catalog`, `cache:service`, `vector_store:service`, `activity_log:service`, and
  unplaced data until placed or granted.
- **Zero trust for `policy_only` types.** No role holds one, owners included, and IAM
  generates no policy for one: what reaches it is a policy someone attached, as for any
  grant. Nexus's features are such a type: a member of a workspace uses no feature until
  a policy grants one (a workspace's "Features of <role>", attached directly, through a
  group or with an invitation). Core IAM has no feature logic; that a feature outside
  Nexus's `enabled_features` is usable by nobody, the platform admin included, is Nexus's
  rule, applied before it asks IAM (`services/iam/authz.py` there).
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
  dropped, with what was attached to it, at boot. Those an older version generated by
  prefix (`roles.RETIRED_POLICY_PREFIXES`: the `builtin.features.*` it made from Nexus's
  settings and attached beside each role) are not: they stay in force, unchanged, until
  whoever made them has moved what they grant, then go with `iam.retire_policies(ids)`
  (in process, `iam:DeletePolicy` on each, every id checked before any goes;
  `iam.retired_policies()` lists them). Until then such a policy follows **its own role**,
  the last segment of its key (`builtin.features.org-1.admin` rode with `builtin.admin`,
  `roles.retired_role`): detaching that role at a scope detaches it there, whatever role
  is still held (an admin made viewer loses the admin's), and adding a member to a group
  skips it as one of the group's role companions while that role is held
  (`_retired_companions`, one rule for both). No new one is ever attached.
- **`builtin.idp`**: the built-in IdP's own namespace, secrets and sender, for the
  built-in account `idp`. By default the IdP (`libs/naas-abi-idp`) runs as the
  module account `module/<project>/idp` with its approved manifest instead; the
  seals and the secret endpoint (`secret_nats_contract.is_idp`)
  name both, so the module id `idp` is reserved: an admin creates its account,
  nothing else does.
- **`builtin.platform.viewer` / `.member`**: attached and detached by IAM in step
  with the role attachments that bring them (above).
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

Everything a module exposes is grantable per container (a workspace, a module's project), one item at a time
(`module_scopes.py`). Two kinds, both marked `module_scope: true` on their resource
types (`ResourceType.module_scope`), so the UI finds them and no role holds them:

- **The `module` catalog.** Every agent, app, workflow and pipeline of every module,
  engine or remote, is `<container>/module:<type>/<module>/<name>`, named in the container
  of the call (`scope_resource`). `<module>` is the module's stable identifier: an engine
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
  named in the container of the call, but a container type, which is registered
  ("Containers"). Approval adds `OwnCatalog` (`<service>:*` on `abi:<service>:*` and
  `abi:*/<service>:*`, `names.anywhere`) to the module's managed policy: the module's side of its own
  actions, for the users it acts for (it grants the broker nothing). It is added after
  the approver's grant check ("Grant only what you hold"), which covers the approved
  permissions: it names only the module's own service, which exists with this manifest
  alone, and a user's grant still decides each declared action done for them.

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
IAM names the resource itself (`authorize_declared`): in the container of the call
(`CallContext.container`, or `container=`), once IAM checked it is registered under that
path; platform level without one; refused as not found for a container IAM does not know.
A declared container type's own resource is the container: `authorize_declared(action,
"project", ["p-9"])` names `<container of the call>/crm:project/p-9`.

**The container of the call is safe.** A module scope is a permission to use
something in a container, not data a container owns, so its name is placed in the
container the call is made in, never looked up. The use happens there: Nexus checks
the scope in the workspace the request names after checking the user belongs to it,
and a user who claims another container gets what they hold there, which is what
using it there needs. A user who holds nothing in a container holds no module scope
there. A pattern names a type at its level, so a grant at a workspace does not reach
what is used inside a project of it: the project's own grants do.

**Zero trust.** No built-in role holds a module scope type, `builtin.admin` and
`builtin.owner` included (`roles._role_statements` leaves every `module_scope` type out): a
user uses a module's agent, app, workflow, pipeline or declared action in a container only
with a policy granting it there, an admin or an owner of a workspace with no policy nothing.
For example:

```yaml
statements:
  - effect: Allow
    actions: ["module:UseAgent"]
    resources: ["${scope}/module:agent/acme.people/Recruiter"]
  - effect: Allow
    actions: ["module:RunWorkflow", "module:ReadWorkflowRuns"]
    resources: ["${scope}/module:workflow/acme.people/*"]
```

attached to the member (or a group) at the workspace,
`abi:nexus:organization/<org>/nexus:workspace/<ws>`. Discovery's grants stay
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

## Sub-policies

A policy may have a **parent** (`parent_id`), one at most: it is then a **sub-policy** of it.
A sub-policy never grants more than its parent, and IAM reads the parent when it decides, so
narrowing a parent narrows every sub-policy below it at the next decision.

**What a sub-policy grants.** Its **chain** is its parent, its parent's parent, and so on up
to a policy with none, nearest first.

- An Allow statement of the sub-policy counts for an action on a resource only if the parent
  allows that action on that resource through its own chain: an Allow of every policy of the
  chain matches it (`EffectiveStatement.bounds`, the chain's Allow statements, read through
  the policy cache).
- The Denies of every policy of the chain apply to whoever holds the sub-policy, as if they
  were its own.
- The parent's variables are filled from the sub-policy's attachment: `${scope}` is the
  sub-policy's attachment scope, `${principal.id}` the member being evaluated, `${user.id}`
  the call's user. A parent's Allows are bounds, not grants: `policy.within_scope` applies
  to the sub-policy's own Allows at a scope, never to its parent's (a platform parent
  allowing `abi:*/module:agent/a` bounds a workspace's `${scope}/module:agent/*` to that
  agent).
- Nothing is copied: a change of a parent, or of anything above it, drops the policy cache
  like any change (in process at once, over NATS within `abi.iam.v1.changed`).
- A chain IAM cannot read whole (a cycle or a chain past the depth, which only a write
  that bypasses IAM makes: every store write locks the state row first) grants nothing:
  the sub-policy's Allows count for nothing, its Denies and those of the chain it could
  read still apply. A grant of such a policy (attaching it, inviting to it, a member
  joining a group holding it) is refused with `IAMConflictError` until its parent is
  fixed, so a repaired chain never grants what nobody was checked for.

| Parent P allows | Sub-policy S allows | A holder of S only |
|---|---|---|
| `${scope}/module:agent/m/a`, `…/m/b` | `${scope}/module:agent/*` | uses a and b |
| `${scope}/module:agent/m/a` (b removed) | unchanged | uses a only, at the next decision |
| `${scope}/module:agent/*`, Deny `${scope}/module:agent/m/b` | `${scope}/module:agent/*` | uses every agent but b |

**Refused**, at create and update, with `ValueError` (`INVALID_ARGUMENT`) unless said. A
parent that exists is first checked against "derive only from what you hold", so a caller
who may not derive from it learns nothing more of it (its owner, its chain):

- a **cycle**: a parent that is the policy itself or one of its sub-policies, at any depth;
- a chain **deeper than 8** (`policy.MAX_DEPTH`): the root is at depth 1, and a policy, with
  the sub-policies below it, may sit no deeper than 8;
- a parent that **does not exist**: `IAMNotFoundError`;
- a **managed** child: built-in and module policies may be parents, never sub-policies;
- an **owner** outside the parent's: a sub-policy is owned by its parent's owner or a
  container below it (`names.within_owner(parent owner, child owner)`): a platform
  policy's by the platform or any container; an organisation's by it or a container in it
  (one of its workspaces); a workspace's by it or a container inside it.

**Derive only from what you hold.** A caller makes a policy a sub-policy of P only if P is
attached to them, or to one of their groups (static or carried in the token's `grp`), at the
sub-policy's owner or above (`IAMService._require_derivable`): the attachment's container
(below it or not) is the owner or a container the owner sits in, or the attachment is
unscoped or at the platform. For a sub-policy owned by workspace W of organisation O, an
attachment of P unscoped, at `abi:`, at O, below O, at W or below W; for one owned by O, at
O's or above; for the platform's, unscoped or at `abi:`. Holding P through a sub-policy of P
does not count. The caller is the call's user
when there is one, plus an actor that is not first-party, as in "Grant only what you hold".

- The platform admin (`builtin.platform_admin` attached unscoped or at `abi:`, directly
  or through a group) derives from any policy.
- A first-party account (`engine`, `api`) acting for no user is not checked, as in
  `_require_held`.
- The refusal is `PermissionDeniedError` (`PERMISSION_DENIED`) naming the parent and the
  scope: "You derive only from a policy attached to you or to one of your groups at
  abi:nexus:organization/O/nexus:workspace/W or above: pol_… is not". It comes after `iam:CreatePolicy` (or
  `iam:UpdatePolicy`) on the sub-policy, so only whoever may write policies there learns
  whether a parent exists.

**Grant only what you hold** checks the sub-policy's effective grant: its own Allows
intersected with its chain's, at every scope it is checked at (see there).

**Write-time checks read the store.** A chain is read from the policy cache when IAM
decides, and from the store when it checks a write (attaching, inviting, binding, creating,
updating, the scope rules), so a parent another process just changed is met as it is now.

**Changing the parent** is an update with the optimistic revision (`update_policy(parent=)`:
an id sets it, `""` removes it, None keeps it), checked like a create: the new chain is
refused as above, the caller derives only from what they hold, and the sub-policy's
effective grant under the new chain is checked at each scope it is written for, attached or
invited at. Removing a parent widens the sub-policy to its own document, which is checked
the same way. A change of a policy's parent, or of its document that may let through
something the old one did not (`IAMService._widens`: an Allow reaching beyond the old
Allows, or an old Deny reaching beyond the new Denies, a Deny lifted or narrowed; both
compared as grants are, unproven counting as a widening), also checks, for each policy
below it, its effective grant under the new chain at its own scopes: widening a parent,
its Denies included, widens them. Narrowing a parent (fewer Allows, more Denies) is never
refused for what is below it.
A change that gives the policy, or one below it, a chain that denies beyond `${scope}` it
did not before is that policy attached anew wherever it is attached or invited at a scope:
refused (`PermissionDeniedError`) to whoever may not attach it unscoped there, as attaching
it would be (`IAMService._check_new_denies`).

**Attaching a sub-policy.** The rules of "Policy language" read the chain:

- a sub-policy whose chain names `${scope}` is attached at a scope only;
- at a scope, the sub-policy's own Allows are `${scope}` or `${scope}/…` (its parent's need
  not: they only bound);
- a Deny of the chain outside `${scope}` is a Deny of the sub-policy: attached at a scope
  only by whoever may attach it unscoped (the platform admin), and offered at a scope by
  `list_policies(scope=)` only to them.

**Deleting.** A policy that has sub-policies cannot be deleted: `IAMConflictError`
(`CONFLICT`) naming each the caller may list (`iam:ListPolicies`) and counting the rest
("Policy pol_P has sub-policies: pol_S (W analysts), and 1 you may not list. Delete them or
give them another parent first"). The store refuses it too. `delete_container` deletes of
what a container owns every sub-policy before its parent, from the store's parent links
(`_deletion_order`); a sub-policy is owned at or below its parent's owner, so deleting a
parent's owner deletes its sub-policies with it. A cycle among them is cut first; a
sub-policy owned elsewhere (only a write bypassing IAM makes one) refuses the deletion
before anything changes.

**Reading.** A policy's record carries `parent_id`. `list_sub_policies(policy_id)` lists its
direct sub-policies: `iam:GetPolicy` on the parent (not found otherwise), then each
sub-policy the caller may list (`iam:ListPolicies` at its owner), the others left out.
`explain` names the chain (see "Evaluation").

```python
# workspace: the workspace's container name
iam.create_policy("W analysts", document, scope=workspace, parent="pol_P")
iam.update_policy("pol_S", expected_revision=2, parent="pol_Q")  # "" removes it
iam.list_sub_policies("pol_P")  # [Policy(id="pol_S", parent_id="pol_P", ...)]
```

## Grant only what you hold

No one gives anyone more than they hold. IAM refuses a change whose result would let a
principal do something, at a scope, that the caller cannot do there (`grants.py`,
`IAMService._require_held`). The check runs in `IAMService`, so in process, over NATS,
through the SDK, the CLI and Nexus alike.

**What is checked**, and at which scopes:

| Operation | The grant | Scopes |
|---|---|---|
| `create_policy` | the document, within its chain's for a sub-policy | its owner's (a container's); a platform policy as written unscoped and with `${scope}` as any container or the platform (`abi:*`, below the platform) |
| `update_policy` with a new document or a new parent | the new document within the new chain's; and, when the parent changes or the new document may let through what the old one did not, an Allow added or widened or a Deny lifted or narrowed (`IAMService._widens`), each policy below it within its new chain's | as `create_policy`, plus every scope it is attached or invited at; for each policy below, its own |
| `attach_policy` (user, group, service account) | the policy | the attachment's (below a container: at it and at every container under it) |
| `add_group_member` | every attachment of the group, but IAM's companions of its roles, which follow them: the unscoped `builtin.platform.*` its role sync wants for the group's roles (`IAMService._companions`). A platform policy attached to the group by hand is checked like any other | each attachment's |
| `create_pending_grant` | the policy | the invitation's |
| `bind_idp_group` | the policy, before the group is made, unless the binding is there already | the binding's |
| `approve_manifest`, narrowed or not | the approved document, its module variables bound | unscoped (the module's policy is attached unscoped) |

Attaching what is attached already, inviting again, binding again or adding a member a
group holds grants nothing new and is not checked.

**The rule.** Take each Allow statement of the grant at the scope (`${scope}` filled; at a
scope, `policy.within_scope` applied first). Every action it matches must be allowed to the
caller, on every resource it matches. For a sub-policy, only the resources an Allow of each
policy of its chain also matches for that action count (`first_uncovered(parents=)`, the
chain's patterns in the same product search, their `${scope}` the same scope): the grant is
its effective one, its own within its parent's. An action the chain allows nowhere is not
granted, and needs no cover. An action kept as a pattern (a wildcard of a service with no
catalog) is bounded by every Allow of the chain whose actions may meet it. Its actions (`Holdings._actions`):

- **A wildcard is expanded against the registered catalogs, and the bus.** The bus has no
  catalog, yet the broker turns `bus:*`, `*` or `*:Publish` into publishing and consuming a
  topic: a wildcard matching `bus:Publish` or `bus:Consume` is checked for them, on the
  bus's topics (`abi:bus:topic/<t>`, `grants.UNCATALOGUED`), like the names themselves.
  A topic is never at a scope, so a scoped grant reaches none. Any run after
  `abi:bus:topic/` is a topic, a raw `:` included, so every topic resource needs cover.
  Topics are compared in the spelling the broker grants (`grants.canonical_topic`: each
  literal run decoded, then encoded as a canonical name): `topic/pay:ments` is
  `topic/pay%3Aments`, `topic/pay%6Dents` is `topic/payments`, and in a grant the runs
  around a variable too (`topic/pay%6Dents.${principal.id}` is
  `topic/payments.${principal.id}`). What the caller holds is made canonical when concrete.
  A Deny of the caller is matched in its written and its canonical spellings, and refuses
  the topic's sub-topics with it (`topic/payments` refuses `topic/payments.eu`): the broker
  grants a topic with `<topic>.>`, and its queue stream holds them. A topic pattern (a `*`
  or `?`) is kept as written: the broker grants none, and the evaluator compares it with
  canonical names. The broker substitutes no variable, so a topic naming one is granted no
  subject (`broker.topic_problem`) and a manifest naming one is refused, its module
  variables bound first (`topic/${module.id}.events` is fine). A stored policy names the bus
  only by a wildcard of every service (validation refuses `bus:Publish` and `bus:*` as
  unregistered), so only a caller
  holding one on the topics (the platform admin) gives it.
- **A wildcard of one named service with no catalog** (`acme:*`) is taken as written: only
  a caller whose actions match that pattern itself gives it. A concrete name no catalog
  registers is taken as written too. A wildcard of every service (`*`) reaches the actions
  the catalogs and the bus have; a service that has neither has no actions anyone checks.

On every resource:

- **Resources are languages.** `*` is any run, `:` and `/` included; `?` one character (one
  of the three of `%2F`). Only names of the action's resource types count (`grants.universe`):
  `abi:`, container steps `<service>:<type>/<id>/` of the registered container types, then
  `<service>:<type>/<id>` of the action's type, with no raw `:` or `/` in a step's fields
  (but in a path id), so `${scope}/triple_store:*` is no wider than
  `${scope}/triple_store:graph/*` for an action on graphs while `triple_store` declares no
  container. A container type registered later makes names that a wildcard granted before
  may reach, as an action a catalog adds later does. A grant is covered by the union of what
  the caller holds, not one pattern of it. A resource that names no name of the action's
  types grants nothing for that action, so it needs no cover there
  (`${scope}/triple_store:graph/*` under `triple_store:*` for an action
  on views): refusing it would refuse every statement that lists several types.
- **Variables keep their form.** A `${principal.id}` or `${user.id}` of the grant is covered
  by the caller holding the same variable there (an admin holds `…/${principal.id}/*` of a
  personal type as the member role grants it), or a `*`, never a literal id nor a `?`: a
  variable is a whole id. A module variable is covered only by a `*`, except in an approved
  manifest, where it is bound. With no user (an account acting for nobody), the caller's
  patterns naming `${user.id}` match nothing, as the evaluator reads them, so they hold
  nothing.
- **Below a container, and the platform.** What a statement attached below a container C
  holds is, for `${scope}/R`, `C/R` and `C/*/R` (R starting with a step or a `*`; any other R
  only `C/R`), and for `${scope}` alone C itself and, for an action on a container type,
  `C/*`. The same below the platform (`abi:*`, a platform policy's `${scope}` at create)
  gives `abi:R` and `abi:*/R`. A statement attached at the platform holds nothing of the
  platform's own policies, groups and unscoped attachments ("Attachments and scope").
- **No Deny of the caller may overlap it.** A Deny's variables are also taken bound to the
  caller's ids, so a Deny on `…/${principal.id}/*` refuses a grant of the caller's own literal
  id. A Deny statement of the grant never needs cover: it only narrows.
- **What a sub-policy of the caller holds** is its Allows within its chain's, shown without
  a search (`grants.within_chain`): pairs of action and resource patterns, each a pattern
  of the sub-policy that a pattern of a policy of the chain embeds, or the other way round,
  level after level, compared in held form (`${scope}` filled, variables as marks). The rest
  counts for nothing: it may say less than the caller holds, never more. The chain's Denies
  are the caller's Denies. The broker grants a connection what such an Allow opens the same
  way (`IAMService._derive`).
- **Every side decides.** The caller is the call's user when there is one (`api` or `engine`
  acting for a user: their own statements never stand in for the user's), plus an actor
  that is not first-party (a module acting for a user is bounded by its own policy too),
  plus the credential's narrowing (`abi_scope`): a read-only personal key grants no write.
  Nothing else is a side: a module scope or a feature is granted by whoever holds it, through
  a policy, as any other grant.
- **Unproven is refused.** A grant one held pattern embeds (each `*` of it within a `*`,
  each `?` within a `?` or a `*`, the rest character for character) is covered without a
  search: the built-in roles, at a container or below one, mostly are. The
  rest is decided on the product of the patterns' automata. One search past `grants.STATE_BUDGET` states is not proven, and refused as not held; the
  searches of one change together past `grants.CALL_BUDGET` (every statement, action, scope
  and, for `add_group_member`, every attachment: `grants.budget()`) leave the rest unproven,
  and the change is refused as too costly to prove. Each is about a second of work; a
  built-in role takes a few hundred states at most.

**The refusal** is `GrantNotHeldError` (a `PermissionDeniedError`, wire code
`GRANT_NOT_HELD`, the SDK's `GrantNotHeld`). Its message names the first uncovered statement
(index, `sid`, policy), action, resource and scope, and why: not held there, a Deny of a
named policy, or the credential's scope. Nexus answers it with a 403 carrying the message
(`services/exceptions.py`, and `_call` in `iam_admin`); `abi iam` prints it.

**Built-in roles still work.** The roles are cumulative, so an admin attaches member and
viewer, an owner owner, and an org's owners and admins assign roles in its workspaces through
their role below the organisation (`abi:nexus:organization/<org>/*`), on the workspace routes and on the organization's
`PUT /organizations/<org>/members/<user>/workspaces` alike (as the caller, checked at each
workspace before any change). No role holds a `policy_only` type, so an owner gives a
feature only if a policy gives it to them: a custom policy on `${scope}/nexus:feature/*`
is refused to whoever holds fewer features.

**What may I grant.** `iam.grantable(scope)` (`abi.iam.v1.grantable`, the SDK's
`iam.grantable`, Nexus `GET /api/iam/admin/grantable?scope=`) lists, for the caller at that
scope, per catalog (a kernel service or a module), the actions they hold there and the
resource patterns they hold them on, written `${scope}/…` or `${scope}` (`GrantableCatalog`,
`GrantableAction`), minus their Denies: a pattern a Deny covers whole is left out, one it
covers in part lists the Deny in `excluded`, written as the resources are (`${scope}/…` for
the part of it under the scope, as stored when none can be told). It may say less than the
caller reaches there, never more, and it stops listing past `grants.CALL_BUDGET`. Like `explain` of oneself it is about the caller only, so it needs no `iam:*`
action, and a module's connection may always ask (`broker.IAM_ALWAYS`).

`iam.grantable(scope, parent=<policy>)` (`GrantableRequest.parent`) is what a sub-policy of
`parent` owned at `scope` may grant: the same, within the parent's chain (`Holdings.grantable(
parents=)`): per policy of the chain, its Allows naming the action, restricted to the scope,
met with what the caller holds (`grants._meet`: the patterns of either side the other embeds,
so it may say less than the chain lets through, never more; a pattern naming a variable other
than `${scope}` is left out), each then checked as the caller's own are (a Deny of theirs that
covers it drops it). The parent is checked first. It answers only for a parent the caller may
derive from at `scope` (`_require_derivable`, whose refusal it keeps) or may read
(`iam:GetPolicy`, so whoever edits an existing sub-policy sees what it may hold): what a parent
allows is said to no one else. With `derive=True` (`GrantableRequest.derive`, for a new
sub-policy), reading is not enough: `_new_chain`'s verdict, as `create_policy` gives it (the
derive rule, the owner within the parent's, the depth). A parent that does not exist is not
found, as one the caller may not read; a chain that cannot be read whole is
`IAMConflictError`. It is what the policy builder offers a sub-policy; `create_policy` and
`update_policy` still decide (`_require_held` with the chain).

**Writes made for no user.** A first-party account (`engine`, `api`) writing for no user is
not checked: each such write sits behind a route or a boot step that authorized what it
stands for. They are:

| Path | Why it may |
|---|---|
| Boot: `IAMService.bootstrap`, `register_kernel_catalogs`, Nexus `register_catalog` | The root of trust: the managed policies and the built-in accounts. |
| Companions: `builtin.platform.*` kept in step with roles, `claim_pending_grants` | They follow a role that was held when it was attached or invited. |
| The mirror below an organisation (`Memberships.mirror_org_wide`, `sync_org_wide_roles`) | It mirrors an org role the route just granted, checked as the user at the organisation itself, or the seeding below. |
| Seeding: `Memberships.seed`, `org_seed.sync_platform_admins`, the owner of a new org or workspace (`grant(by=None)`) | The configuration's `users:`, the migration of old memberships, and the creator of what `nexus:CreateOrganization` / `CreateWorkspace` let them create. |
| Placements (`put_placement`, `PLACEMENT_WRITER`) | They place resources; they grant nothing. |
| Shared graph grants (`graph_grants.py`, `workspace.<ws>.graphs.*`) | Behind `nexus:UpdateResourceAccess` on the workspace, which offers only graphs the workspace holds, gives writing only to whoever may drop the graph, and sharing every graph only to platform administrators (`resource_access.py`). |
| `abi iam` | The operator holding the project's IAM store and config. |
| The move of the workspace feature overrides (Nexus `services/iam/feature_overrides.migrate_feature_overrides`, once at start) | Features an override gave every role of a workspace, kept for the people who held a role there then, so nobody's features change (a workspace policy attached at the workspace). |
| The move of the sets and the workspace toggles (Nexus `services/iam/policy_tree.migrate_sets`, once at start) | What the sets and the toggles let each person use becomes access policies and sub-policies of them, attached where the roles and policies that reached it were, so nobody gains or loses access ("Migrating an existing install"). |
| The move of the role features (Nexus `services/iam/role_features.migrate_role_features`, once at start) | The features each role had in each workspace, kept for the people who held that role there then, so nobody's features change ("Features of <role>", a workspace policy attached at the workspace). |
| Workspace snapshot import (Nexus `core/workspaces_import.py`) | An operator command run with the project's engine, never a route: it makes the owner of a workspace it creates, as creating one does. |
| `modules.auto_approve` | The `abi dev` overlay only: a module's manifest approved on submission. |

Invitations and IdP group bindings made from Nexus are written as `api` **on behalf of the
inviting person** (`invites/adapters/secondary/engine.py`), so they are checked like any
grant; their reads and withdrawals stay `api`'s own.

## Service API

```python
iam = engine.services.iam  # IIAMService, no dependency declaration needed

iam.require("triple_store:Query", name, not_found=lambda: GraphNotFound(iri))
allowed = iam.filter("triple_store:ListGraphs", names).allowed
iam.authorize(action, resource)  # Decision
iam.allows_every(action, "triple_store", "graph")  # a safe shortcut: False when unsure
iam.explain(action, resource, principal_id=...)  # needs iam:Explain on the principal
iam.grantable(scope)  # what the caller may grant there (needs no permission)
iam.grantable(scope, parent=policy_id)  # ... in a sub-policy of policy_id
iam.grantable(scope, parent=policy_id, derive=True)  # ... in a new one (refused as create)
iam.list_resources(
    "triple_store", "graph", scope=container, text="sales", cursor=None
)  # ResourcePage: what the caller may list there (needs no permission)
iam.placement_of(
    service, canonical_id
)  # the covering placement, or None (serving engine)
# A module's declared action, named by IAM in the container of the call:
decision, resource = iam.authorize_declared(
    "acme_people:ExportReport", "report", ["q3"]
)
iam.require_declared(
    "acme_people:ExportReport", "report", ["q3"]
)  # PermissionDeniedError
```

`allows_every` is True only when nothing can deny: no seal on the type, no
narrowing token, no Deny naming the action, and on each side an Allow spanning
every container and id of the type (`engine` and `api` today). Services use it
to skip per-item work.

Administration (each needs its `iam:*` action): `ensure_user`, `link_user`
(`iam:LinkUser`, in process only: gives a user of the built-in login (issuer `urn:abi:nexus`) one more
identity, `iam_identity_links`, which `find_user` answers first, so its principal, roles, groups and keys follow it
to an identity provider; the user a first sign-in made for that identity is merged into it, retired, and one
holding keys refuses the link; `identity_at(principal, issuer)` names the subject by which a provider knows a
user, its own or linked), `create_service_account`, `get_principal`, `list_principals`,
`suspend_principal`, `resume_principal`, `delete_principal` (keeps the id, drops
attachments and memberships), groups (`create_group`, `add_group_member`,
`map_idp_group`, ...; groups cannot contain groups; `create_group(name, scope=)`, its
owner a container or the platform), policies (`create_policy(name, document, scope=, parent=)`
validated against the registered catalogs, `update_policy(expected_revision=, parent=)`,
`list_sub_policies`: "Sub-policies"; managed policies are IAM's alone), `attach_policy`/`detach_policy` (idempotent;
a policy naming `${scope}` needs a scoped attachment, and only a policy whose
every Allow resource pattern is `${scope}` or starts with `${scope}/` may be attached at a
scope, so whoever may attach at a scope cannot grant beyond it; `update_policy` refuses
to widen a policy attached at a scope, and evaluation enforces the rule anyway:
a statement reached through a scoped attachment keeps only those Allow patterns,
`policy.within_scope`), placements (`put_placement(service, id_key, container)`,
`placement_of`: exact key, then the longest prefix, else None; `resolve_placement`: its
container, else the platform), containers (`register_container`, `delete_container`,
`container`, `list_containers`, `call_container`: "Containers"),
`register_catalog` (highest
version wins; refuses dropping an action a policy names), listers (`register_lister`, in
process only; `has_lister`; `remote_listers`: "Publishers and listing").

Lists page after filtering. `list_policies(scope=S)` returns the policies `S` owns
(`iam:ListPolicies` on each), plus those of the containers above it (its organisation's,
the platform's) that are confined to a scope and that the caller may attach at `S`
(`iam:AttachPolicy` on `attachment/<policy>/*` there): a workspace admin is offered
the roles below owner and the organisation's policies. `list_groups(scope=S)` returns the
groups `S` owns (`iam:ListGroups`), plus the groups of the containers above it but the
platform's, for whoever may list `S`'s attachments to them (`iam:ListAttachments` on
`attachment/*/<group>`); platform groups are not offered there. Without `scope`, a
list holds every policy or group the caller may list where it is owned. Reading one
(`get_policy`, `get_group`) is decided at its owner only.

**Lifecycle.** `delete_container(service, type, id)` (Nexus, when a workspace or an
organisation goes; a module, when its own container goes) deletes the container and those
below it, and the policies and groups they own: a policy with its attachments and
invitations, a group (marked deleted, its id kept) with its attachments, members and
mappings. Then it detaches every attachment left at them (below them included), whatever
its policy, so nothing grants at a container that is gone or comes back under the same id;
a user left with no attachment within the top container leaves its groups. It needs the
type's `deletes` action on the container.

Names: `principal_resource`, `group_resource(id, owner_scope)`,
`policy_resource(id, owner_scope)`, `attachment_resource` (at its scope's container; at the
platform for a platform or unscoped one), `placement_resource`, `container_resource`,
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

- **Requester.** The caller needs `iam:ExchangeToken` on `abi:iam:audience/<audience>`
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
  `abi:iam:principal/<sa id>`), else the requester; never a request field. App,
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
| Always | IAM's read-only and self-service operations (`broker.IAM_ALWAYS`: `token`, `exchange_token`, `jwks`, `submit_manifest`, `get_manifest`, `find_service_account`, `authorize`, `authorize_declared`, `filter`, `grantable`, and `register_container`, `delete_container`, `get_container`, which IAM decides with the container type's own actions: create, delete, and any action of the type for a read; never `abi.iam.v1.changed`), the engine's broker control `abi.broker.v1.*`, `_INBOX.>`, `abi.rpc.overflow.>` | its own inbox prefix `_INBOX.<key id>` |
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
  covers keeps it, and the container of the call must be empty or match; otherwise the
  container of the call places it (`call_container` checks it is registered under that
  path; an unknown container is "not found"). Call `.record()` once the create succeeded:
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
  attach it once) and keeps the companions of the roles in step (the platform ones), as
  attaching the role does. An invitation carries any policy beside the role, each its own
  pending grant at its scope: an invitee gets Nexus features only from a policy the
  invitation carries ("Features of member", say), claimed at the same first sign-in.
- **Authorized as the attachment it stands for.** Creating one needs
  `iam:AttachPolicy` and revoking one `iam:DetachPolicy` on
  `<scope's container>/iam:attachment/<policy>/pending:<provider>:<email>`, so a
  workspace admin invites to that workspace and no further, nobody makes an owner
  they could not attach, and the rules of `attach_policy` (a `${scope}` policy needs
  a scope, a scoped policy stays within it) hold. The inviting person holds what the policy
  grants there (see "Grant only what you hold"), as for a binding. Listing is filtered by
  `iam:ListAttachments` on the same names. `iam:ClaimPendingGrants` (admin on a
  principal) is the identity service's, as the engine.
- **A binding** gives the members of an IdP group a role at a scope: IAM finds or
  creates the ABI group `idp:<provider>:<claim value>` owned by the top container of the
  scope (its organisation for a workspace; the platform for a platform or unscoped
  binding), maps the claim to it and attaches the policy to it. Binding the same claim in
  another top container makes that one its own group, so a group never holds another
  organisation's attachments. The caller is authorized for the
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
refused key). Sub-policies: `CreatePolicyRequest.parent`, `UpdatePolicyRequest.parent`
(absent keeps it, `""` removes it), `Policy.parent_id` (empty: none), `list_sub_policies`
(`ListSubPoliciesRequest`, needing what the in-process call needs); the same refusals,
with the same codes and messages, in process, over NATS and through the SDK. There is no
set operation (the sets are gone: `get_set`, `effective_set`, `list_sets`, `put_set` and
their messages were removed; IAM's catalog 7 drops `iam:GetSet` and `iam:PutSet`). Containers:
`register_container`, `delete_container`, `get_container` (`ContainerRecord`; a read only for a caller allowed an action of the type on it); `put_scope`,
`delete_scope` and `workspace_org` are gone with the scopes (`iam:PutScope` and
`iam:DeleteScope` stay declared, deprecated: they authorize nothing). `Placement.container`,
`AuthorizeDeclaredRequest.container` and `common.CallContext.container` carry container
names; `common.CallContext.workspace_id` is refused when set (SDK 0.2, "Placements"). Listing:
`list_resources` (`ListResourcesRequest`, `ListResourcesResponse`, `ListedResource`), offered to every
module like `grantable` (`broker.IAM_ALWAYS`: it is filtered as the caller); `ActionCatalog.publisher`
(empty: the engine). A remote module's lister answers `discovery.v1.ListerQuery` with `ListerPage` on its
instance's `iam.list` subject, its types in `ModuleDescriptor.listers`. The SDK
facade is `engine.services.iam` (`naas_abi_sdk/services/iam.py`), reachable without a
dependency declaration; records are dictionaries. A module makes calls inside a container
with `call_context.inside(container)` (the SDK's `with engine.inside(container):`).

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
| The role features (`feature_flags.role_baseline`, `organization_overrides`, `organization_role_features`), and the `builtin.features.*` an older IAM generated from them | moved once by Nexus at start (`services/iam/role_features.migrate_role_features`, recorded in `iam_migrations` as `role_features_v1`), from what IAM has in force, never from the configuration: each role held at a workspace becomes that workspace's "Features of <role>" attached there; one held org-wide the organization's, attached org-wide (it still covers workspaces made later); each pending invitation to a role gets the matching pending grant. Every user's `UseFeature` decisions are the same at every step. Then `organization_role_features` is dropped and the `builtin.features.*` are retired (`retire_policies`); until then they stay in force. |
| Workspace graph policies and per-workspace prefixes and namespaces (object storage, documents, vectors, datasets) | placements (`iam:PutPlacement`), plus Allow statements in a workspace policy for shared graphs |
| Every other existing container (module and engine namespaces, collections, repos, graphs) | platform placements, so no workspace can claim a name inside them |
| Remote modules sharing `NATS_JWT_SECRET` | service accounts, keys and approved manifests (`abi dev up` regenerates them; deployed systems run `abi iam module approve`) |
| Nexus users of the old login | users of issuer `urn:abi:nexus`, linked to the built-in IdP at first sign-in (`link_user`) |
| IAM store schema 1 (no owner scopes) | schema 2, at the store's first open: every policy and group platform-owned, except the groups IdP bindings made (named `idp:<provider>:<claim>` and mapped from that claim, with an org) whose attachments are all under `abi:<org>:`, which belong to that org (`abi:<org>:-`). A binding group schema 1 shared with other orgs, the platform or an unscoped binding stays the platform's: owned by one org, its admins could add their users to what it holds elsewhere. Two processes may open the store at once (PostgreSQL adds the columns `IF NOT EXISTS`; SQLite serializes writes). The upgrade logs a warning for each stored customer policy whose patterns reached the platform's policies or groups as `abi:-:-:iam:…` (or `${scope}:iam:…` at `abi:-:-`) and no longer match them: rewrite them `abi:*:*:iam:policy/…`, `…:iam:group/…` |
| IAM store schema 2 (no sets) | schema 3: the table `iam_scope_sets`, created empty at the store's first open (PostgreSQL behind an advisory lock, so the engine and the API opening it together both start). Every org and workspace starts with everything. |
| IAM store schema 3 (no sub-policies) | schema 4: the nullable column `iam_policies.parent_id` and its index, added at the store's first open (PostgreSQL `IF NOT EXISTS`, behind the schema's advisory lock). Every existing policy has no parent. No foreign key: every write locks the state row (`iam_state`) before it checks anything (`IAMStoreSQL._change`; SQLite's `BEGIN IMMEDIATE` already serializes), so "the parent exists" and "the policy has no sub-policies" still hold when the write commits, and a delete and a re-parent racing on PostgreSQL run one after the other. |
| Per-workspace feature overrides (`workspaces.feature_overrides`, the deprecated `feature_flags.workspace_overrides`) | moved once by Nexus at start (`services/iam/feature_overrides.migrate_feature_overrides`, recorded in `iam_migrations`): a feature turned off leaves the workspace's feature set, kept in the move's report for the move of the sets below; one turned on, for each role whose defaults lack it, becomes a workspace policy for the people holding that role there then. No one's features change. The column is cleared. |
| IAM store schema 4 (sets) | schema 5, at the store's first open: `iam:GetSet` and `iam:PutSet` leave the customer policies that named them (a statement naming nothing else with them), their revision bumped; they authorized nothing but the sets. `iam_scope_sets` is no longer created; an existing one stays, read by nothing, until Nexus moved it (`legacy_scope_sets`, then `drop_legacy_scope_sets`, both in process only, `iam:DeleteScope` on each row's scope). |
| The sets of orgs and workspaces (`iam_scope_sets`), the roles that held every module scope (`builtin.admin`, `builtin.owner`), and what each workspace turned off (Nexus's `app_configs.enabled`, `agent_configs.enabled`, `workflow_visibility`) | moved once by Nexus at start (`services/iam/policy_tree.migrate_sets`, recorded in `iam_migrations` as `policy_tree_v1`, after the overrides' and the role features' moves): each org gets a platform-owned "<org> access" (its set's module items and features; everything without a set), each workspace an org-owned "<workspace> access", a sub-policy of it (its own set's items and features, the apps it had turned on, a Deny of what it had turned off). Who held `builtin.admin` or `builtin.owner` gets, where the role reached, a sub-policy of that place's access granting every module scope (the roles brought no feature, so not the access policy itself); a group like a person, a pending invitation to the role as a pending grant beside its own. A customer policy granting module scopes or features moves under the access policy of its owner (an org's or a workspace's), split from what else it grants; where that would not bound it as before (an org's policy attached in a workspace or org-wide, a platform policy) its attachment becomes, at each place it reached, one of a sub-policy of that place's access with the same statements. A service account, never bounded by a set, gets the same grants cut to each place, within what the workspace had turned off (Nexus refused that to every caller). An agent a workspace built and had turned off is denied, at the workspace, to who held a role there. What moves to the workspaces of today (a grant attached org-wide or unscoped) and wildcards spelled out are named in the report's notes. Every user's decision on every module item, declared action and feature is the same before and after (`policy_tree_test.py`, on the memory, SQLite and PostgreSQL stores), but the platform admin, who now reaches what a workspace had turned off. What cannot be kept exactly stops the move (logged, nothing recorded), and Nexus refuses every module scope and feature until a start moves everything. Then IAM's legacy sets and `workflow_visibility` are dropped. |
| IAM store schema 5 (names `abi:<org>:<ws>:<service>:<type>/<id>`, scopes, placements to an org and a workspace) | schema 6, at the store's first open: the table `iam_containers` and the column `iam_placements.container` (PostgreSQL `IF NOT EXISTS`, behind the schema's advisory lock). A placement of the old form reads as the platform when it was the platform's (`-`, `-`), else as `names.UNRESOLVED`, a container nobody registers, which only `*`-wide grants (the platform admin, `engine`, `api`) reach; an owner or a scope of the old form likewise; an old pattern matches no new name. So until the names are rewritten, an install narrows, never widens. The rewrite is the module's that defined the old fields: Nexus, once at start after the move of the sets (`services/iam/container_names.migrate_names`, recorded in `iam_migrations` as `container_names_v1`), registers its organisations and workspaces as containers and has IAM rewrite every stored name in one transaction (`iam.rewrite_names(rewriter)`, in process only, `iam:RewriteNames`): policy documents and their `${scope}:` patterns, owners, attachments, placements, the scopes (which become containers), keys' narrowing statements, manifests and their policies, pending grants and IdP bindings. It may run again: what is already a path is kept, and a placement the module names no container for (a workspace deleted since) is kept in the old form, read as `names.UNRESOLVED`, never written as a container it is not. Every user's decisions are the same before and after (`container_names_test.py`, on a store the code before the change made: `tests/artifacts/names_v1`). |
| Sessions, refresh tokens, app grants and preview tokens signed with `secret_key` | invalidated: users sign in again; workspace secrets get their own key (`secrets_encryption_key`) |

## Decisions

**Authorization is identity-based policies, denied by default.**
*Decision.* AWS-style policy documents (`Allow`/`Deny`, actions, resource patterns)
attached to users, groups and service accounts at an optional scope; no resource-based
policies; an explicit Deny wins; on behalf of a user both sides must allow; narrowed
tokens only narrow; actions are `<service>:<Action>` with an access level; resource names
are paths of containers, `abi:<service>:<type>/<id>/…`, with percent-encoded ids and `*`/`?` patterns,
never regular expressions; the container of a kernel resource comes from placements,
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

**Policies and groups are owned by the platform or a container.**
*Decision.* Each policy and group has one owner, the platform or a registered container, in
its record and in its name (`<owner>/iam:<type>/<id>`); the built-in roles give owners and
admins at a container that container's policies and groups, and viewers and members nothing
of IAM. An owned policy names only `${scope}` and `${scope}/…` resources, Deny included, and
is attached at its owner or below; an owned group receives attachments there and holds only
users of its top container. The platform's are named at the platform, and no `${scope}`
reaches them (an explicit rule since container paths; `%2A` names before). Deleting a
container deletes what it owns. IdP mappings stay the platform admin's.
*Consequences.* A workspace admin builds its own groups and policies with no platform
right, and nothing it writes reaches or refuses beyond its workspace, whoever it
attaches it to: a Deny outside `${scope}` would otherwise let it lock a user, the
platform admin included, out of everything. For the same reason a platform policy with
a Deny outside `${scope}` is attached at a scope only by the platform admin (see "Policy
language"): a scope's admin or owner could otherwise impose its Deny on anyone, in any
org, and the Deny would keep them from detaching it. Platform-scope roles (`abi:`) never
edit the platform's policies, some of which are attached unscoped. Members
and viewers no longer list their scope's attachments (who holds which role is
Nexus's members list, read as `api`). A user leaving an org leaves its groups, so a
group never keeps granting a former member. An existing store upgrades in place
(schema 2).

**Module scopes are a catalog of their own; viewers and members hold none.**
*Decision.* What modules expose is the `module` catalog, `module:<type>/<module>/<name>`
with `module_scope` types, placed in the container of the call; the module is named by
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
(`authorize_declared`) in the container of the call, so a module never builds names.
*Consequences.* An admin approving a remote module approves its catalog with its
permissions, and a changed catalog waits for approval. A declared type is always a
module scope placed in a workspace: viewers and members need a grant, and the module's
own approved policy holds `<service>:*` so that the user's grant decides.

**Grant only what you hold; existing grants are not checked again.**
*Decision.* IAM refuses creating or editing a policy, attaching one, adding a group member,
an invitation, an IdP binding and a manifest approval when the result would give, at a
scope, more than the caller holds there (see "Grant only what you hold"). The caller is the
call's user, never the first-party account acting for them; a narrowed credential narrows
what it may grant; Denies need no cover; what cannot be proven is refused. A grant already
made is not checked again when its granter later loses a permission: narrowing the parent
of a sub-policy narrows it at the next decision, whoever made it. `engine` and `api` writing for no user are not checked, each behind a route
or boot step that authorized what it stands for (the table there).
*Consequences.* A scope's admin can no longer make itself owner through a policy or a group,
nor an owner give a feature it does not hold. Wildcards are expanded against the catalogs
registered when the grant is made: an action a catalog adds later reaches an existing
wildcard grant (as it reaches the generated roles) without its granter's being checked. A
grant whose containment takes more than `grants.STATE_BUDGET` states, or a change whose
searches take more than `grants.CALL_BUDGET` together, is refused even if it is covered. Revoking a granter's role leaves what they gave: take it back explicitly.
Invitations and bindings from Nexus now need the inviting person to hold the role's grants.
`grantable` may under-report a holding whose pattern straddles the scope's fields.

**The catalogs say what the roles leave out; core's roles name no service.**
*Decision.* What the built-in roles hold is generated from the catalogs by level, and what
they leave out is flagged in the catalog that declares it: `policy_only` on a type no role
holds, `owner_only` on an admin action no role below owner holds, and `platform_access` for
the platform-level rows a first-party catalog's resources add to the platform companions.
`roles.py` names its own kernel services' platform rows and no other service, Nexus
included; `builtin.api`, Nexus's own account, keeps its enumerated statements. IAM generates
no feature policy: `put_feature_policies`, `builtin.features.*` and their companions are
gone. The stored ones stay in force until Nexus has moved them into policies, then go
(`retire_policies`); a stored catalog older than the flags holds nothing for the roles until
it is registered again (`format`).
*Consequences.* Nexus's features are a `policy_only` type: no role brings one, owners and
admins included, and a member of a new workspace uses none until a policy grants it (Nexus
moved what each role had into workspace policies once, so nobody's features changed). A
module's catalog cannot declare `platform_access`: what it publishes reaches its users
through policies only. Removing a flag is a catalog change like any other: the roles are
regenerated at the next registration.

**Policies are the one place access is decided.**
*Decision.* The organisation and workspace sets and their evaluation step (`outside_set`) are
gone, with their store table, their `iam` actions and type, their NATS operations, SDK calls
and proto messages; so is Nexus's workspace on/off switch. No built-in role holds a module
scope type, admins and owners included. What an org or a workspace may use is a policy: an
access policy per org and per workspace (a sub-policy of its org's) that the upgrade made
from the sets, and what is granted below them is their sub-policies, narrowed live.
*Consequences.* Narrowing what an org uses is editing its access policy: every sub-policy
below it narrows at the next decision. An admin or owner of a workspace with no policy uses
no agent, app, workflow, pipeline, declared action or feature there; a new workspace grants
nothing to its creator until a policy attached there, or above, does. Core IAM holds no
feature logic: `nexus:feature` is a `policy_only` type of Nexus's catalog like any other. A
module installed later is in no access policy until someone adds it.

**A sub-policy narrows its parent, read live.**
*Decision.* A policy has at most one parent (`parent_id`). What it grants is its own Allows
intersected with what its parent grants through its own chain, and the chain's Denies apply
to it; IAM reads the chain from the policy cache at each decision, filling the parent's
variables from the sub-policy's attachment, and copies nothing. A cycle, a chain deeper than 8,
a missing parent and a managed child are refused; a sub-policy is owned at or below its
parent's owner; a caller derives only from a policy attached to them or their groups at the
sub-policy's owner or above (the platform admin from any); "Grant only what you hold" checks
the intersection; a parent with sub-policies is not deleted.
*Consequences.* Narrowing a parent narrows every sub-policy below it at the next decision, in
process and over NATS, with nothing to rewrite; widening it widens them, so a change of a
parent is checked for each policy below it. A decision reads up to eight policies per
attachment, all cached. Store writes are serialized on the state row, so IAM's own checks
keep chains whole; one broken by a write that bypasses IAM grants nothing rather than
something, and grants of it are refused until it is repaired. A re-parent that brings a
Deny beyond `${scope}` is checked as attaching would be, so it never imposes that Deny
where its holder could not attach it. What a caller holds through a sub-policy counts in grant checks only where it is
shown without a search, so such a caller may be refused a grant they could prove the hard way.
A parent's Deny beyond `${scope}` makes each sub-policy a policy that only the platform admin
attaches at a scope.

**Every catalog names its publisher; a listing is the caller's.**
*Decision.* A catalog says who publishes it (`ActionCatalog.publisher`: the engine by default,
`naas_abi` for Nexus's, a module's key for its own), and the `module` catalog's resources belong to the
module their id names. A resource type may have a lister, which returns candidates and decides nothing:
in process for the engine's services and modules, over NATS for a remote module (the SDK serves it, its
types in discovery), IAM itself for containers (its registry) and singletons. `list_resources` keeps what
the caller may list (the type's `list` actions, else any of its actions, through `filter`), within the
scope, searched and paged by name, and needs no permission, like `grantable`.
*Consequences.* The policy builder can offer, per publisher and type, only what the caller may grant
(`publishers.by_publisher` over `grantable`) and the existing resources they may list, with nothing
listed beyond it. A lister may read unchecked: what it returns is filtered before anyone sees it, and
what falls outside the query (another type, container, order) is dropped. A lister that fails, times out
or is gone leaves its type offered as wildcards and is logged, never failing the call. A remote lister
answers as its module, reachable by the engine alone (no action names its subject); a remote
module's container type is listed from IAM's registry, never from the module. One call examines at most
`MAX_EXAMINED` candidates and `MAX_SECONDS`, so a caller who may list few of many, or a slow
lister, pages through short pages and never holds a worker for long.

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
