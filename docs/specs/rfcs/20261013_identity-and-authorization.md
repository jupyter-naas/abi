# RFC: Identity and authorization on the NATS engine

- **Date:** 2026-10-13
- **Author:** Maxime Jublou
- **Status:** Accepted
- **Discussion:** [#1314](https://github.com/jupyter-naas/abi/issues/1314)
- **Builds on:** [`20260910_distributed-modules-nats-jetstream.md`](20260910_distributed-modules-nats-jetstream.md) ("Decisions locked in": checks in the domain service, identity in a `contextvars.ContextVar`, ARN-style names)
- **Decisions:** [`20261013_authorization-policy-model.md`](../../adr/20261013_authorization-policy-model.md), [`20261013_identity-providers-and-builtin-idp.md`](../../adr/20261013_identity-providers-and-builtin-idp.md), [`20261013_engine-tokens-service-accounts-broker.md`](../../adr/20261013_engine-tokens-service-accounts-broker.md), [`20261013_iam-kernel-service.md`](../../adr/20261013_iam-kernel-service.md)

This RFC is the specification for every subtask of the permission-system job (#44). Subtasks implement it.
They do not invent grammar, action names or evaluation rules. If one of those has to change, this document
changes first, in the same pull request.

## Problem

#1314 sets the direction:

- authentication moves to OIDC identity providers;
- a built-in IdP serves installs that have none;
- ABI keeps authorization only, with fine-grained, AWS-style policies, zero trust by default;
- one check runs in the engine's domain services for every caller.

On `feat/standalone-nats-sdk`, nothing of this exists yet:

- **Nobody knows the caller.**
  - `CallContext` (`naas_abi_proto/common/v1/common.proto`) has `principal_id`, `workspace_id` and
    `tenant_id`. Nothing sets them or reads them.
  - Identity travels only in the `Nats-Auth-Token` header: an HS256 JWT with claims `{sub, iat, exp}`
    (`engine/nats_auth.py`), signed with the shared `NATS_JWT_SECRET`.
  - The only identities are `api`, `engine` and module names. Most NATS primary adapters verify the token
    and throw `sub` away.
  - The event, vector_store and cache NATS adapters skip their domain service.
- **Every credential is trusted.**
  - The broker has two users, `abi` and `module`, and both have every right.
  - Modules receive `NATS_JWT_SECRET`, so any module can sign tokens as `api` or `engine`.
  - Admin rights are hard-coded to the identities `api` and `engine`: `document_admin` and discovery
    eviction.
- **The end user never reaches the engine.**
  - Nexus calls remote agents and apps as `api`. The user travels as prompt text or as an unauthenticated
    `HttpRequest.user_id`.
  - `PlatformServicesAgent`'s tools reach the whole triple store, object storage, cache and key-value store
    with no user check.
- **Nexus authorization is mostly a placeholder.**
  - `services/iam` matches scopes, and every caller passes `scopes={"*"}`. It fails open when unbound.
  - About 45 inline `role in ("owner", "admin")` checks.
  - Viewers are read-only only in graph, sheets and ontology icons.
  - Feature flags are enforced only for office-agent listing.
- **Known bugs:**
  - (a) The coding-agent JWT is a 30-day full session.
  - (b) Coding-environment and code-review routes trust a client-supplied `repo_id` and grant `write` on it.
  - (c) Admins can grant, demote or remove owners.
  - (d) `POST /api/workspaces` accepts any `organization_id`.

## Proposal

### 1. Vocabulary

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

Authorization is identity-based only. There are no resource-based policies: a resource never carries a
policy of its own.

### 2. Principals

Three kinds of principal. Ids are a kind prefix plus a lowercase ULID, for example
`usr_01jabcdefghjkmnpqrstvwxyz0`. Pattern: `^(usr|grp|sa)_[0-9a-z]{26}$`. Ids never change and are never
reused.

**Users**

- A user is the pair `(issuer, sub)` from a verified IdP token. It is never identified by email.
- IAM creates the user principal on first login. It holds no password.
- It stores `issuer`, `sub`, the provider `name`, and the last seen `email`, `email_verified` and display
  name. Those fields are informational.
- `(issuer, sub)` is unique.
- Accounts are never linked automatically across providers. The same person signing in through two IdPs is
  two principals unless an admin links them explicitly (`iam:LinkUser`, an admin action).

**Groups**

- A group has a `name` and an optional `org` (null for a platform group).
- **Static members** are users or service accounts, kept in IAM.
- **Mapped members** come from IdP group claims. A mapping `(provider name, claim value) → group id`
  is set with `iam:MapIdpGroup`.
  - When a user's IdP token is exchanged (§9), IAM reads the provider's `groups_claim`, maps each value
    and writes the group ids into the engine token's `grp` claim.
  - Mapped membership therefore lasts as long as the token, at most 10 minutes.
- A user's effective groups are their static groups plus the token's `grp`. A service account has static
  groups only.
- Groups cannot contain groups.

**Service accounts**

- A service account has a unique `name` and an optional owner (the user who created it, for scripts and CI).
- Name forms:

  | Form | Example | Used by |
  |---|---|---|
  | `engine` | | Built-in, the engine process |
  | `api` | | Built-in, Nexus |
  | `idp` | | Built-in IdP |
  | `module/<project>/<module_id>` | `module/acme/people` | One per remote module |
  | `ci/<name>` | `ci/nightly-export` | Scripts and CI |

- Keys and manifests: §8.

**Status**

Every principal has a `status`: `active`, `suspended` or `deleted`.

- Suspending takes effect immediately (§5.6, §11.4):
  - every check for that principal, as actor or as OBO user, is denied;
  - token exchange refuses it;
  - the NATS auth callout refuses its connections.
- `deleted` keeps the id, so audit records stay readable. Nothing can be attached to a deleted principal.

**On behalf of**

- A call carries an actor and, optionally, a user it acts for. Examples:
  - Nexus (`api`) serving a signed-in user;
  - an agent module serving the user who chats.
- Both must be allowed (§5.3). OBO never unlocks a sealed resource.

### 3. Policies

#### 3.1 Document schema

The same schema in YAML and JSON.

```yaml
version: "2026-10-13"
statements:
  - sid: ReadSalesGraph            # optional
    effect: Allow                  # Allow | Deny
    actions:
      - triple_store:Query
      - triple_store:QueryStream
      - triple_store:ListGraphs
    resources:
      - "abi:org-1a2b3c4d5e6f:ws-0f1e2d3c4b5a:triple_store:graph/http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fsales-*"
  - effect: Deny
    actions: ["triple_store:DropGraph", "triple_store:ClearGraph"]
    resources: ["*"]
```

```json
{
  "version": "2026-10-13",
  "statements": [
    {"sid": "ReadSalesGraph", "effect": "Allow",
     "actions": ["triple_store:Query"],
     "resources": ["abi:org-1a2b3c4d5e6f:ws-0f1e2d3c4b5a:triple_store:graph/*"]}
  ]
}
```

Validation (IAM rejects the whole document on any failure, with every error listed):

| Field | Rule |
|---|---|
| `version` | Required. `"2026-10-13"` is the only version. |
| `statements` | Required, 1 to 100 items. |
| `sid` | Optional. `^[A-Za-z0-9]{1,64}$`, unique within the document. |
| `effect` | Required. Exactly `Allow` or `Deny`. |
| `actions` | Required, 1 to 100 action patterns (§3.3). A pattern without a wildcard must name a registered action. A pattern with a wildcard must match at least one registered action. |
| `resources` | Required, 1 to 100 resource patterns (§4.5). Each is `*` or starts with `abi:`. |
| `conditions` | Reserved. Rejected in version `2026-10-13`. A later version defines it. |
| anything else | Rejected. |

The serialized document is at most 32 KiB.

#### 3.2 Stored policies

| Field | Meaning |
|---|---|
| `id` | `pol_<ulid>`, or `builtin.<name>` for managed policies (§7). |
| `name`, `description` | Shown in the admin UI. |
| `document` | The schema above. |
| `managed` | True for built-in policies. Only IAM rewrites them. |
| `revision` | Increments on every change. Updates use it for optimistic concurrency. |

#### 3.3 Action patterns

- An action is `<service>:<Action>`:
  - `service` is the catalog name, `^[a-z][a-z0-9_]*$`;
  - `Action` is PascalCase, `^[A-Z][A-Za-z0-9]*$`.
- Patterns use `*` (any characters, including none) and `?` (exactly one character). Examples:
  `triple_store:*`, `triple_store:List*`, `*`.
- Matching is case-sensitive.

#### 3.4 Attachments and variables

An attachment binds a policy to a principal (user, group or service account), with an optional `scope`.

| `scope` | Meaning | `${scope}` expands to |
|---|---|---|
| `abi:<org>:<workspace>` | One workspace | `abi:<org>:<workspace>` |
| `abi:<org>:-` | The org's own resources only (members, domains, billing) | `abi:<org>:-` |
| `abi:<org>:*` | The org and every workspace in it | `abi:<org>:*` |
| `abi:-:-` | Platform resources | `abi:-:-` |
| none | The policy uses no `${scope}` | — |

Variables are substituted into resource patterns before matching. They resolve against the principal
whose policies are being evaluated, `X` in `principal_decision(X)` (§5.3): the actor `P` when computing
`d_P`, the OBO user `U` when computing `d_U`.

| Variable | Value |
|---|---|
| `${scope}` | The attachment's scope. Invalid in a policy attached without one. |
| `${principal.id}` | `X`'s principal id. A policy reached through a group resolves to the member being evaluated, never to the group. |
| `${user.id}` | The call's user (§10.1): `U` if the call is on behalf of a user, else `P` if `P` is a user. Otherwise unresolved. It is the same in `d_P` and `d_U`, so an actor's policy can name the user it serves. |

- A statement with an unresolved variable matches nothing.
- Variables are not allowed in actions.
- Example: on a Nexus call, `P` is `api` and `U` is the signed-in user. `builtin.self` is attached to `U`, so
  in `d_U` its `${principal.id}` is `U`. `api`'s policies, evaluated in `d_P`, never see `U` as
  `${principal.id}`.

### 4. Resource names

#### 4.1 Grammar

```abnf
resource-name = "abi:" org ":" workspace ":" service ":" type "/" id
org           = scope-id / "-"
workspace     = scope-id / "-"
scope-id      = 1*64( %x61-7A / DIGIT / "-" / "_" )   ; lowercase id, never exactly "-"
service       = %x61-7A *( %x61-7A / DIGIT / "_" )     ; catalog name
type          = %x61-7A *( %x61-7A / DIGIT / "_" )     ; declared in the service catalog
id            = "-" / segment *( "/" segment )
segment       = *( unreserved / pct-encoded )            ; RFC 3986; empty only inside path ids
unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
pct-encoded   = "%" 2HEXDIG                              ; uppercase hex
```

- `org` and `workspace` are the stable Nexus ids (`org-<12 hex>`, `ws-<12 hex>`), never slugs. Renames
  change no names.
- `-` in `org` or `workspace` means "none".
- `-` as the whole `id` names a singleton (§4.3).

#### 4.2 Levels

| Level | Form | Example |
|---|---|---|
| Workspace | `abi:<org>:<ws>:…` | `abi:org-1a2b3c4d5e6f:ws-0f1e2d3c4b5a:dataset:dataset/sales/orders` |
| Org | `abi:<org>:-:…` | `abi:org-1a2b3c4d5e6f:-:nexus:organization/-` |
| Platform | `abi:-:-:…` | `abi:-:-:model_registry:model/qwen-2.5-3b` |
| Workspace in no org | `abi:-:<ws>:…` | legacy workspaces with a null `organization_id` |

#### 4.3 Encoding ids

The id is percent-encoded UTF-8. Every octet outside `unreserved` is encoded, including `:`, `/`, `*`,
`?`, `%` and spaces. Each resource type declares its id kind in its catalog:

- **`opaque`:** one segment. The whole value is encoded, so a `/` inside it becomes `%2F`.
  - Graph IRIs, key-value, cache and secret keys, event types, model ids.
  - `http://ontology.naas.ai/graph/x` → `http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fx`
  - `nexus:session:42` → `nexus%3Asession%3A42`
- **`path`:** a hierarchy. Each part is encoded on its own and the parts are joined with a raw `/`.
  - Object paths, document namespace/collection/id, dataset namespace/name, vector collection/id.
  - Object storage joins `prefix` and `key` with one `/`, after stripping leading and trailing `/` from
    the prefix: prefix `workspaces/ws-1/files`, key `q3 report.pdf` →
    `object/workspaces/ws-1/files/q3%20report.pdf`.
- **`-`:** the singleton id, for service-wide resources such as `service/-`.

Canonical names are built and parsed only by IAM's helpers, never by string formatting in callers:
`naas_abi_core.services.iam.names.resource_name(...)` and `parse_resource_name(...)`, mirrored in the SDK.
`abi iam name <service> <type> <id...>` prints one.

#### 4.4 Placement: where the org and workspace come from

A kernel service builds `<service>:<type>/<id>` from the request. It cannot take the org and workspace from
the request: anyone could claim a workspace they belong to while addressing another workspace's data. Data
ids rarely encode a workspace either: Nexus graph IRIs are `…/graph/<slug>-<uuid>`. So IAM keeps
**placements**.

- **A placement is `(service, id-key) → (org, workspace)`.**
  - Both may be `-`. A platform placement (`-`, `-`) is recorded like any other. It is how a platform
    container keeps workspaces from claiming names inside it.
  - `id-key` is an exact canonical id, or a prefix ending in `*`.
  - The prefix is plain string prefix matching on the canonical id.
  - It covers every type of that service whose id starts that way. A document placement on `nexus-ws-1`
    plus `nexus-ws-1/*` covers the namespace, its collections and its documents.
- **Resolution.**
  - An exact key beats a prefix, and a longer prefix beats a shorter one.
  - With no match, the resource is platform-level, `abi:-:-:…`.
  - For a resource type a catalog declares `placement: platform` (model_registry models, discovery
    modules), resolution always gives platform.
- **Containers.** A resource type marked `container: true` in its catalog holds children whose ids extend its
  own: `<container id>/<rest>`. Containers:
  - document `namespace` and `collection`;
  - vector_store `collection`;
  - source_control `repo` (children `branch/<repo>/…` and `proposal/<repo>/…`);
  - dataset `namespace`.

  A placement on a container is always written as a pair: the exact id and the prefix `<id>/*`. Its
  children therefore resolve to the container's placement, platform included.
- **Every existing container has a placement.**
  - A container created through a service records one when it is created (below).
  - The migration (§13) places every container that exists before IAM: Nexus workspace data in its
    workspace, everything else on the platform.
  - Approving a module's manifest (§8.3) records platform placements for the module's own namespaces, the
    `<module_id>` namespace of document and dataset, unless they are already placed.

  So "no placement covers this name" means the name is a new top-level resource or a new container.
- **Writing placements.**
  1. **On creation.** A create operation is marked `creates: true` in the catalog. Before it runs, the
     service resolves the placement of the would-be name. The create always needs its action allowed on
     the name *as placed*.
     - **A child of an existing container takes the container's placement**, platform included.
       - Any name covered by an existing placement, exact or prefix, is treated this way.
       - `CallContext.workspace_id` must be empty or equal to that placement's workspace. For a platform
         container it must be empty.
       - On a mismatch the call is denied with the §5.4 outcome computed on the name as placed:
         `PERMISSION_DENIED` if the caller can see it, not found otherwise.
       - Nothing new is recorded: the container's prefix already covers the new resource.
       - So a member of ws-A can claim a name neither inside ws-B's namespace nor inside a module's
         platform namespace by passing `workspace_id=ws-A`.
     - **`workspace_id` decides only for a name no placement covers**: a new top-level resource or a new
       container.
       - With `workspace_id` set, the name is placed in that workspace. A caller cannot create in a
         workspace they hold no create right in.
       - With it empty, the name is platform-level.
       - On success the service records the placement: exact for a top-level resource (none when
         platform-level, since nothing can be created inside it), exact plus `<id>/*` for a container,
         platform included.
     - **Implicit containers.** A create whose name sits in a container that does not exist yet (the first
       `dataset:Create` in a new namespace, the first `document:EnsureCollection` in a new namespace) first
       places that container by the rule above. It then creates the child inside it.
     - IAM maps the workspace to its org with its scope registry. Nexus registers each org and workspace with
       `iam:PutScope`.
  2. **Explicitly**, with `iam:PutPlacement`, mainly for prefixes. Nexus places its per-workspace prefixes
     when it creates a workspace, and the migration places existing data (§13).
  3. **On delete.** Deleting a container or a placed resource (`Drop*`, `Delete*`) deletes the placements
     that the create recorded: the exact id and, for a container, its prefix.
- **What `workspace_id` does not do.** It never renames an existing resource and never overrides an existing
  placement. For an operation on an existing resource it is ignored.
- **Caching.** Placements are cached like policies (§11.4).

#### 4.5 Wildcards

- A resource pattern is matched against the whole canonical name.
- `*` matches any sequence of characters, including none and including `:` and `/`. It matches across
  segments. `?` matches exactly one character. Every other character is literal.
- There is no escaping and there are no regular expressions. Canonical names never contain a raw `*` or `?`
  (they are `%2A`, `%3F`), so a wildcard can never be confused with a literal.
- `?` counts characters of the canonical encoded form, so `?` can match one character of `%2F`.
- A pattern of just `*` matches every resource.
- Prefer patterns that end a field before the wildcard: `abi:org-1:*` matches org `org-1` only, while
  `abi:org-1*` also matches `org-10`.
- Examples:

  | Pattern | Matches |
  |---|---|
  | `abi:org-1:ws-2:*` | everything in workspace `ws-2` |
  | `abi:org-1:*` | the org's own resources and all its workspaces |
  | `abi:*:*:triple_store:graph/*` | every graph |
  | `abi:-:-:document:namespace/people`, `abi:-:-:document:collection/people/*` and `abi:-:-:document:document/people/*` | the `people` document namespace, its collections and documents. Not `abi:-:-:document:*/people*`: that also matches another namespace's collection named `people`. |

### 5. Evaluation

#### 5.1 Inputs

- `ctx`:
  - the actor `P`;
  - the optional OBO user `U`;
  - the effective groups of each;
  - the token's narrowing statements `T` (§9.3, optional).
- `action`, for example `triple_store:Query`.
- `resource`, a canonical resource name.

#### 5.2 Statement match

A statement matches when at least one action pattern matches `action` and at least one resource pattern
(after substitution, §3.4) matches `resource`.

#### 5.3 Algorithm

```text
decide(ctx, action, resource):
  1. if P.status != active, or U set and U.status != active:  DENY (suspended)
  2. if resource is sealed and its owner != P:                DENY (implicit)
  3. d_P = principal_decision(P)
     d_U = principal_decision(U) if U set else ALLOW
  4. if d_P == EXPLICIT_DENY or d_U == EXPLICIT_DENY:         DENY (explicit)
  5. if d_P != ALLOW or d_U != ALLOW:                         DENY (implicit)
  6. if T set and no statement of T matches:                  DENY (implicit)
  7. ALLOW

principal_decision(X):
  S = statements of every policy attached to X and to each of X's effective groups
  if any Deny statement in S matches:   EXPLICIT_DENY
  if any Allow statement in S matches:  ALLOW
  otherwise:                            IMPLICIT_DENY
```

- **Deny by default.**
  - Nothing is allowed without a matching Allow.
  - There is no superuser bypass in code. `engine`, `api` and the platform admin hold attached policies
    like anyone else.
- **An explicit Deny wins** over any number of Allows, including Allows reached through another group.
- **OBO is an intersection.** The actor and the user must both be allowed. An agent module that may write
  graph G, acting for a user who may only read G, cannot write G.
- **Token narrowing (`T`) only narrows.**
  - It holds Allow statements only.
  - A Deny in `T` is rejected when the token is issued.
- **The decision records why.** `explain` returns the outcome, the reason (`suspended`, `sealed`,
  `explicit_deny`, `implicit_deny`, `allow`) and the deciding statement: policy id, attachment and
  statement index or `sid`.

#### 5.4 "Not found" or "permission denied"

When `decide` denies:

- the service computes `visible(ctx, resource)`, true when `decide(ctx, a, resource) = ALLOW` for at least
  one action `a` of the same service whose catalog lists the resource's type;
- if `visible`, the call fails with **permission denied**: wire code `PERMISSION_DENIED`, Python
  `naas_abi_core.services.iam.PermissionDeniedError`;
- otherwise it fails with **not found**, exactly as if the resource did not exist. That is the service's own
  not-found error and wire code (`GRAPH_NOT_FOUND`, `DatasetNotFoundError`, `KV_NOT_FOUND`, …), with the
  same message shape.

Further rules:

- **Order.** The check runs before the backend is touched. A denied call never reveals existence through
  timing, side effects or error text.
- **Create.** A create on a name that does not exist yet uses the same rule, on the name as placed by §4.4.
  A caller who can see that name (any allowed action of the service on it) gets `PERMISSION_DENIED`.
  Anyone else gets the service's not-found error for the type being created (`GRAPH_NOT_FOUND` for
  `CreateGraph`, `COLLECTION_NOT_FOUND` for `CreateCollection`, …), or the generic `NOT_FOUND` when the
  service has none. The error never says whether the name, its container or its workspace is the part
  that is missing.
- **Credentials.** Missing, invalid or expired credentials are `UNAUTHENTICATED`. That is authentication,
  not authorization.

#### 5.5 Lists

- **A list action is checked against each item.** Each item's canonical name is checked with the list
  action itself (`triple_store:ListGraphs` on each `graph/…`).
- **What a list returns.** Items an Allow covers and no Deny excludes. Nothing else, including counts
  derived from hidden items.
- **Paging.** `limit` and cursors apply after filtering. Adapters over-fetch or push filters down.
- **Container-scoped lists** (`ListObjects(prefix)`, `ListVectors(collection)`, `ListKeys(prefix)`,
  `document:Collections(namespace)`):
  - When the container is itself a resource (a vector collection, a document collection), it first gets
    the visibility rule of §5.4: not found if invisible.
  - Then its items are filtered.
- **Engine-wide lists** (`ListGraphs`, `ListCollections`, secret `List`) never fail for authorization.
  They return the allowed subset, possibly empty.
- **Container-level reads.** `document:Find`, `document:Count`, `vector_store:Search`,
  `vector_store:CountVectors` and `dataset:InlinedRowCount` are checked once, on their container. Their
  results are not item-filtered, so grant them only where the whole container may be read. `document:Find`
  is a query, not a list action.
- **Push-down.** `filter` (§11.2) also returns prefix hints, the literal prefixes of the matching Allow
  patterns, so storage can push them down:
  - a SPARQL `VALUES` list;
  - a key-prefix scan;
  - a SQL `LIKE` on ids.

  Denies are applied after the push-down.

#### 5.6 Freshness

- Policy, attachment, group, placement and status changes take effect at the next check after IAM's change
  event reaches the checking process.
- That is immediate in-process, and within the event's delivery time over NATS (§11.4).
- Cached state also expires after 60 seconds, so a missed event cannot keep stale grants for long.
- Group membership carried in a token's `grp` claim lasts until the token expires (≤ 10 minutes).

### 6. Action catalogs

#### 6.1 Access levels

| Level | Meaning |
|---|---|
| `list` | Enumerate resources or their names. |
| `read` | Read content or metadata, run read-only queries, invoke a model. |
| `write` | Create resources, change or delete data inside a container, invoke an agent or job. |
| `admin` | Drop or clear containers, maintenance, service lifecycle, permission changes, cross-user views. |

Built-in roles are defined by level (§7), so the level is part of the contract.

#### 6.2 Catalog format

Each service declares its catalog next to its domain code (`services/<name>/iam_catalog.py` in core,
`iam_catalog.yaml` in a module package) and registers it when it loads:

- in process: `iam.register_catalog(catalog)` during engine boot, before the service serves;
- over NATS: `abi.iam.v1.register_catalog`, from a module whose approved policy allows `iam:RegisterCatalog`
  on `abi:-:-:iam:catalog/<service>`.

```yaml
service: triple_store
version: 1                      # bumped on every change; IAM keeps the highest
resource_types:
  - name: graph
    id: opaque                  # opaque | path | singleton
    placement: placed           # placed | platform
    container: false            # true: children's ids extend this id (§4.4)
    personal: false             # true: the id starts with the owner's principal id (§6.3)
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
    creates: true               # records a placement from CallContext.workspace_id (§4.4)
    subjects: ["abi.svc.triple_store.v1.create_graph"]
```

The proto mirrors this. `iam/v1/iam.proto` defines `ActionCatalog`, `ResourceType` and `ActionSpec` with
the same fields.

Rules:

- Action names are unique within a service.
- A catalog may only add actions or resource types in a new version. Removing one requires that no policy
  still names it explicitly; IAM refuses the registration otherwise.
- `subjects` drives broker permissions (§8.4):
  - stream actions list their service's transfer subjects;
  - in-process-only actions list none.

#### 6.3 Request-to-resource rules shared by every service

- **Ids are canonical** (§4.3). The org and workspace come from placement (§4.4), never from the request.
- **"All" calls.** An operation that takes an optional container and means "all" when it is empty
  (`event:Query` with no type, `triple_store:Get`) is filtered per item.
- **Several resources.** An operation that names several resources (`vector_store:DeleteVectors`, SQL
  touching several tables) requires the action on each of them. One denial fails the whole call, with the
  §5.4 outcome of the first denied resource.
- **Personal resources.** A personal resource type (`personal: true` in the catalog) has an id whose first
  segment is its owner's principal id: either the owner id alone (`actor/<owner>`, `forge_user/<owner>`,
  `coder_user/<owner>`) or `<owner>/<rest>` (`conversation/<owner>/<id>`,
  `environment/<owner>/<id>`, `run/<owner>/<project>/<invocation>`, `key/<owner>/<key id>`).
  - Services read the owner from their own records, never from the request.
  - A role reaches a personal type only through its owner, with both forms:
    `<type>/${principal.id}` and `<type>/${principal.id}/*` (§7).

#### 6.4 Kernel service catalogs

In the tables below:

- **Resource** is the part after `abi:<org>:<ws>:`. Placeholders are canonical (encoded) values.
- **Subject** is the operation under `abi.svc.<service>.v1.`.
- **"stream"** is the service's transfer subjects: `transfer.open` and `transfer.<owner>.{write,start,read,close}`.
- **Level** is the access level (§6.1).

##### object_storage

Resource types:

- `object/<path>` (`path`, placed). The path is `prefix` and `key` joined (§4.3).

Nexus places `workspaces/<ws>/*` and `users/<user>/*` prefixes.

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListObjects` | list | each listed `object/<prefix>/<key>` | `list_objects` |
| `ListObjectsRecursive` | list | each listed object | `list_objects_recursive` |
| `GetObject` | read | `object/<prefix>/<key>` | `get_object` |
| `GetObjectMetadata` | read | `object/<prefix>/<key>` | `get_object_metadata` |
| `GetObjectStream` | read | `object/<prefix>/<key>` | stream, operation `get` |
| `PutObject` | write | `object/<prefix>/<key>` | `put_object` |
| `PutObjectStream` | write | `object/<prefix>/<key>` | stream, operation `put` |
| `DeleteObject` | write | `object/<prefix>/<key>` | `delete_object` |

##### document

Resource types (`path`, placed):

- `namespace/<ns>` (container)
- `collection/<ns>/<collection>` (container)
- `document/<ns>/<collection>/<id>`

Placement and binding:

- A module's own namespace is platform-level unless placed.
- In process, the SDK and `ServicesProxy` bind a module to its namespace. Over NATS the namespace now comes
  from the request and is authorized like any other id. The old "bound namespace" becomes a policy that
  names each type, so it cannot match another namespace's collection of the same name:

  ```yaml
  resources:
    - "abi:-:-:document:namespace/<module_id>"
    - "abi:-:-:document:collection/<module_id>/*"
    - "abi:-:-:document:document/<module_id>/*"
  ```

| Action | Level | Resource | Subject |
|---|---|---|---|
| `Namespaces` | list | each `namespace/<ns>` | `namespaces` |
| `Collections` | list | each `collection/<ns>/<c>` | `collections` |
| `CollectionSpec` | read | `collection/<ns>/<c>` | `collection_spec` |
| `EnsureCollection` | admin | `collection/<ns>/<c>` (creates) | `ensure_collection` |
| `DropCollection` | admin | `collection/<ns>/<c>` | `drop_collection` |
| `Get` | read | `document/<ns>/<c>/<id>` | `get` |
| `Find` | read | `collection/<ns>/<c>`, checked once; results are not item-filtered (§5.5) | `find` |
| `Count` | read | `collection/<ns>/<c>` | `count` |
| `Put` | write | `document/<ns>/<c>/<id>` | `put` |
| `Delete` | write | `document/<ns>/<c>/<id>` | `delete` |

`document_admin` and `ADMIN_IDENTITIES = {"api", "engine"}` are removed. Namespace administration is
`Namespaces`, `EnsureCollection` and `DropCollection` on the namespace, granted by policy.

##### keyvalue

Resource types:

- `key/<key>` (`opaque`, placed by key prefix)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListKeys` | list | each listed `key/<key>` | `list_keys` |
| `Get` | read | `key/<key>` | `get` |
| `Exists` | read | `key/<key>` | `exists` |
| `GetTtl` | read | `key/<key>` | `get_ttl` |
| `Set` | write | `key/<key>` | `set` |
| `SetIfNotExists` | write | `key/<key>` | `set_if_not_exists` |
| `Delete` | write | `key/<key>` | `delete` |
| `DeleteIfValueMatches` | write | `key/<key>` | `delete_if_value_matches` |

##### secret

Resource types:

- `secret/<key>` (`opaque`, placed by key prefix)

Sealed prefixes (§11.3, §12.3):

- `secret/idp%2F*` belongs to `idp`.
- `secret/iam%2F*` belongs to `engine`.

| Action | Level | Resource | Subject |
|---|---|---|---|
| `List` | list | each `secret/<key>` | `list` |
| `Get` | read | `secret/<key>` | `get` |
| `Set` | write | `secret/<key>` | `set` |
| `Remove` | write | `secret/<key>` | `remove` |

##### cache

Resource types:

- `key/<key>` (`opaque`, placed by prefix)
- `service/-` (singleton, platform)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListKeys` | list | each `key/<key>` | `list_keys` |
| `Get` | read | `key/<key>` | `get`, `tier.<i>.get` |
| `Exists` | read | `key/<key>` | `exists`, `tier.<i>.exists` |
| `Set` | write | `key/<key>` | `set`, `tier.<i>.set` |
| `SetIfAbsent` | write | `key/<key>` | `set_if_absent`, `tier.<i>.set_if_absent` |
| `Delete` | write | `key/<key>` | `delete`, `tier.<i>.delete` |
| `Describe` | admin | `service/-` | `describe` |

The per-tier subjects are the engine's own; the broker grants them to `engine` only.

##### vector_store

Resource types:

- `collection/<name>` (`path`, placed, container)
- `vector/<collection>/<id>` (`path`)
- `service/-` (singleton, platform)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListCollections` | list | each `collection/<name>` | `list_collections` |
| `GetCollectionInfo` | read | `collection/<name>` | `get_collection_info` |
| `CreateCollection` | write | `collection/<name>` (creates) | `create_collection` |
| `DeleteCollection` | admin | `collection/<name>` | `delete_collection` |
| `ListVectors` | list | each `vector/<c>/<id>`; the collection is checked first (§5.5) | `list_vectors` |
| `ListVectorsStream` | list | as `ListVectors` | stream, operation `list_vectors` |
| `Search` | read | `collection/<name>` (hits are not item-filtered) | `search` |
| `CountVectors` | read | `collection/<name>` | `count_vectors` |
| `GetVector` | read | `vector/<c>/<id>` | `get_vector` |
| `StoreVectors` | write | `vector/<c>/<id>` for each document | `store_vectors` |
| `UpdateVector` | write | `vector/<c>/<id>` | `update_vector` |
| `DeleteVectors` | write | `vector/<c>/<id>` for each id | `delete_vectors` |
| `Initialize` | admin | `service/-` | `initialize` |
| `Close` | admin | `service/-` | `close` |

##### triple_store

Resource types:

- `graph/<iri>` (`opaque`, placed). `graph/default` is the default graph; an encoded IRI always contains
  `%3A`, so the two cannot collide.
- `view/<name>` (`opaque`, platform)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListGraphs` | list | each `graph/<iri>` | `list_graphs` |
| `Get` | read | each graph in the dump; the result holds only allowed graphs | `get` |
| `GetSubjectGraph` | read | `graph/<iri>` when `graph_name` is set, else filtered over all graphs | `get_subject_graph` |
| `Query` | read | the query's dataset, see below | `query` |
| `QueryStream` | read | as `Query` | stream, operation `query` |
| `QueryView` | read | `view/<name>`, and `Query` rules on the graphs it reads | `query_view` |
| `Export` | read | `graph/<iri>`, or filtered over all graphs when none is given | stream, operation `export` |
| `Insert` | write | `graph/<iri>` (`default` when no graph) | `insert` |
| `Remove` | write | `graph/<iri>` | `remove` |
| `CreateGraph` | write | `graph/<iri>` (creates) | `create_graph` |
| `ClearGraph` | admin | `graph/<iri>` | `clear_graph` |
| `DropGraph` | admin | `graph/<iri>` | `drop_graph` |
| `HandleViewEvent` | admin | `view/<name>` | `handle_view_event` |

**SPARQL queries (`Query`, `QueryStream`, `QueryView`).** The service parses the query (rdflib) and runs it
over a dataset restricted to the graphs the caller may `Query`.

- **Explicit graphs.**
  - A graph named explicitly, in `FROM`, `FROM NAMED` or `GRAPH <iri>`, must be allowed.
  - Otherwise the call fails by §5.4: an invisible graph is `GRAPH_NOT_FOUND`.
- **`GRAPH ?g`** ranges over allowed named graphs only.
- **The default graph** is `graph/default`. Whatever union-default-graph setting the backend has, it is
  limited to the allowed graphs.
- **How adapters restrict the dataset.**
  - HTTP adapters (Oxigraph, Fuseki) pass the dataset as SPARQL Protocol `default-graph-uri` and
    `named-graph-uri` parameters, which take precedence over the query's own dataset clauses.
  - Embedded Oxigraph passes `default_graph` and `named_graphs`.
  - When every graph is allowed (`graph/*`), adapters may skip the restriction.

**SPARQL Update through `query`.** Each update operation needs the matching action on each graph it
targets:

| Operation | Action needed |
|---|---|
| `INSERT DATA` | `Insert` |
| `DELETE DATA` | `Remove` |
| `DELETE/INSERT … WHERE` | `Insert` and/or `Remove` on the target graphs, plus `Query` on the graphs `WHERE` reads |
| `LOAD` | `Insert` |
| `CLEAR` | `ClearGraph` |
| `DROP` | `DropGraph` |
| `CREATE` | `CreateGraph` |
| `ADD`, `MOVE`, `COPY` | `Query` on the source, `Insert` on the target, plus `DropGraph` on the source for `MOVE` |

- `DEFAULT`, `NAMED` and `ALL` targets need the action on every graph they cover. In practice that means
  `graph/*`.
- A request the parser cannot classify is refused (`INVALID_ARGUMENT`).

Nexus `GraphAccessScope` (`services/graph/access.py`) moves into this check (subtask 4), and the Nexus
graph routes call the kernel as the user.

##### dataset

Resource types:

- `namespace/<ns>` (`path`, placed, container)
- `dataset/<ns>/<name>` (`path`)
- `catalog/-` (singleton, platform)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `List` | list | each `dataset/<ns>/<name>` | `list` |
| `ListSnapshots` | list | `catalog/-` | `list_snapshots` |
| `Describe` | read | `dataset/<ns>/<name>` | `describe` |
| `NamespaceVersion` | read | `namespace/<ns>` | `namespace_version` |
| `Query` | read | every `dataset/<ns>/<name>` the SQL references | `query` |
| `QueryStream` | read | as `Query` | stream, operation `query` |
| `Create` | write | `dataset/<ns>/<name>` (creates) | `create` |
| `Write` | write | `dataset/<ns>/<name>` | `write` |
| `WriteStream` | write | `dataset/<ns>/<name>` | stream, operation `write` |
| `InlinedRowCount` | admin | `dataset/<ns>/<name>` | `inlined_row_count` |
| `Flush` | admin | `dataset/<ns>/<name>` | `flush` |
| `Compact` | admin | `dataset/<ns>/<name>` | `compact` |
| `Drop` | admin | `dataset/<ns>/<name>` | `drop` |

`Query` takes its references from DuckDB's parser. These are refused with `INVALID_ARGUMENT`:

- a query whose tables it cannot resolve;
- file-reading table functions;
- `ATTACH`.

##### event

Resource types:

- `event_type/<type>` (`opaque`, placed by prefix)
- `cursor/<consumer>/<type>` (`path`)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListEventTypes` | list | each `event_type/<type>` | `list_event_types` |
| `Query` | read | `event_type/<type>`, or filtered per event type when none is given | `query` |
| `QueryStream` | read | as `Query` | stream, operation `query` |
| `MaxSeq` | read | `event_type/<type>` | `max_seq` |
| `QueryForConsumer` | read | `event_type/<type>` and `cursor/<consumer>/<type>` | `query_for_consumer` |
| `GetCursor` | read | `cursor/<consumer>/<type>` | `get_cursor` |
| `Append` | write | `event_type/<type>` | `append` |
| `SetCursor` | write | `cursor/<consumer>/<type>` | `set_cursor` |

##### activity_log

Resource types:

- `actor/<principal id>` (`opaque`, platform, `personal: true`)
- `service/-` (singleton, platform)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListActors` | list | each `actor/<id>` | `list_actors` |
| `Query` | read | `actor/<actor_id>` | `query` |
| `QueryStream` | read | `actor/<actor_id>` | stream, operation `query` |
| `Record` | write | `actor/<event's actor>`; the actor is the call's user (§10.1), never a request field | `record` |
| `Shutdown` | admin | `service/-` | `shutdown` |

Every user reads their own activity through `builtin.self` (§7).

##### email

Resource types:

- `sender/<from address or default>` (`opaque`, platform)
- `message/<message id>` (`opaque`, placed from `CallContext.workspace_id` on send)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListSent` | list | each `message/<id>` | `list_sent` |
| `GetSent` | read | `message/<id>` | `get_sent` |
| `Send` | write | `sender/<from_email>`, `sender/default` when empty; creates `message/<id>` | `send` |
| `DeleteSent` | write | `message/<id>` | `delete_sent` |

##### model_registry

Resource types:

- `model/<canonical model id>` (`opaque`, platform)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListModels` | list | each `model/<id>` | `list_models` |
| `Resolve` | read | `model/<id>` | `resolve` |
| `Chat` | read | `model/<id>` | `chat` |
| `ChatStream` | read | `model/<id>`; one action for the open, next and close subjects | `stream_open`, `<owner>.stream_next`, `<owner>.stream_close` |
| `Embed` | read | `model/<id>` | `embed` |

##### discovery (modules, agents, models, apps, jobs)

Resource types (all platform):

- `module/<project>/<module_id>`
- `agent/<project>/<module_id>/<agent>`
- `model/<project>/<module_id>/<model>`
- `app/<project>/<module_id>/<app>`
- `job/<project>/<module_id>/<job>`
- `run/<owner>/<project>/<invocation_id>` (`personal: true`; the owner is the call's user, or the actor
  when the call is on behalf of no one)
- `job_run/<project>/<module_id>/<job>/<run_id>`

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListModules` | list | each `module/…` | `abi.discovery.<project>.v1.list_modules` |
| `GetModule` | read | `module/…` | `….get_module` |
| `Register` | write | `module/<project>/<module_id>`; only that module's own service account can hold it (§8.3) | `….register` |
| `Renew` | write | `module/…` | `….renew` |
| `Unregister` | write | `module/…` | `….unregister` |
| `Evict` | admin | `module/…` | `….evict` |
| `ListAgents` | list | each `agent/…` | read from `list_modules` |
| `InvokeAgent` | write | `agent/…`; creates `run/…` | `abi.agent.<project>.<sa>.<instance>.<hash>.v1.submit` |
| `GetAgentRun` | read | `run/…` | `….status`, `….event` |
| `CancelAgentRun` | write | `run/…` | `….cancel` |
| `ChatModel` | read | `model/<project>/<module_id>/<model>` | `abi.mod.<project>.<sa>.<instance>.model.<name>.chat` |
| `ListApps` | list | each `app/…` | read from `list_modules` |
| `OpenApp` | read | `app/…`; every HTTP request to the app | `abi.mod.<project>.<sa>.<instance>.app.<name>.http` |
| `ListJobs` | list | each `job/…` | read from `list_modules` |
| `TriggerJob` | write | `job/…` | `abi.jobs.<project>.trigger.…` |
| `ScheduleJob` | write | `job/…` | `abi.jobs.<project>.schedule.…` |
| `ListJobRuns` | list | each `job_run/…` | run records in the provider's namespace |
| `GetJobRun` | read | `job_run/…` | as above |
| `CancelJobRun` | write | `job_run/…` | `abi.jobs.<project>.cancel.…` |

- `AuthorizeAgent`, `AuthorizeModel` and `AuthorizeApp` stop being authorization: the hosting module asks
  IAM `check` with the caller's context. They remain only as lease checks.
- Job trigger and cancel messages gain the `Nats-Auth-Token` header (subtask 5).
- Hosting subjects gain the service-account token `<sa>` (§8.4). Callers never build these subjects: they
  read them from the discovery record.

##### source_control

Resource types:

- `repo/<repo_id>` (`opaque`, placed, container). The id is the service's id, never a Nexus value.
- `branch/<repo_id>/<name>` (`path`)
- `proposal/<repo_id>/<number>` (`path`)
- `forge_user/<principal id>` (`opaque`, platform, `personal: true`)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListRepos` | list | each `repo/…` | `list_repos` |
| `EnsureRepo` | write | `repo/<owner>%2F<name>` (creates) | `ensure_repo` |
| `DeleteRepo` | admin | `repo/…` | `delete_repo` |
| `AddCollaborator` | admin | `repo/…` | `add_collaborator` |
| `SetBranchProtection` | admin | `branch/<repo>/<name>` | `set_branch_protection` |
| `ListContents` | list | `repo/…` | `list_contents` |
| `GetFile` | read | `repo/…` | `get_file` |
| `UpsertFile` | write | `branch/<repo>/<branch>` | `upsert_file` |
| `UpsertFiles` | write | `branch/<repo>/<branch>` | `upsert_files` |
| `ListCommits` | list | `repo/…` | `list_commits` |
| `ListBranches` | list | each `branch/…` | `list_branches` |
| `CreateBranch` | write | `branch/<repo>/<name>` | `create_branch` |
| `DeleteBranch` | write | `branch/<repo>/<name>` | `delete_branch` |
| `GetDiff` | read | `repo/…` | `get_diff` |
| `ListProposals` | list | each `proposal/…` | `list_proposals` |
| `GetProposal` | read | `proposal/…` | `get_proposal` |
| `GetProposalDiff` | read | `proposal/…` | `get_proposal_diff` |
| `ListProposalCommits` | list | `proposal/…` | `list_proposal_commits` |
| `ListComments` | list | `proposal/…` | `list_comments` |
| `ListReviews` | list | `proposal/…` | `list_reviews` |
| `ListChecks` | list | `proposal/…` | `list_checks` |
| `CreateProposal` | write | `proposal/<repo>/-` (creates) | `create_proposal` |
| `AddComment` | write | `proposal/…` | `add_comment` |
| `SubmitReview` | write | `proposal/…` | `submit_review` |
| `Merge` | write | `proposal/…` | `merge` |
| `ListWorkflowRuns` | list | `repo/…` | `list_workflow_runs` |
| `EnsureUser` | admin | `forge_user/<principal id>` | `ensure_user` |
| `MintGitToken` | write | `forge_user/<principal id>`; the user is the call's user (§10.1), never `request.user_id` | `mint_git_token` |

Bug (b) is closed in two places:

- A `repo_id` from another workspace has another placement, so the caller gets `REPO_NOT_FOUND`.
- `AddCollaborator` is an admin action. Nexus grants a member write on a workspace repo by checking
  `source_control:UpsertFile` on that repo for the user, then calling `AddCollaborator` as `api` (§10.2).

##### coding_environment

Resource types:

- `environment/<owner principal id>/<environment id>` (`path`, placed, `personal: true`). The proto's
  `workspace_id` field is the environment id.
- `template/<id>` (`opaque`, platform)
- `coder_user/<principal id>` (`opaque`, platform, `personal: true`)

| Action | Level | Resource | Subject |
|---|---|---|---|
| `ListTemplates` | list | each `template/…` | `list_templates` |
| `ListEnvironments` | list | each `environment/…` of the user | `list_environments` |
| `ListAllEnvironments` | admin | each `environment/…` | `list_all_environments` |
| `GetStatus` | read | `environment/…` | `get_status` |
| `GetLogs` | read | `environment/…` | `get_logs` |
| `GetAccess` | write | `environment/…` (returns a credential) | `get_access` |
| `Provision` | write | `environment/<the call's user>/-` (creates) | `provision` |
| `Start` | write | `environment/…` | `start` |
| `Stop` | write | `environment/…` | `stop` |
| `Delete` | write | `environment/…` | `delete` |
| `EnsureUser` | admin | `coder_user/<principal id>` | `ensure_user` |

The service reads the owner and the user from `CallContext` and from its own records. It never uses
`request.user_id`.

##### iam (its own catalog)

Resource types:

- `principal/<id>`
- `group/<id>`
- `policy/<id>`
- `attachment/<policy id>/<principal id>`, at the attachment's scope (§3.4); an org-wide attachment is
  named at `abi:<org>:-`
- `key/<principal id>/<key id>`, `personal: true` for personal keys
- `manifest/<service account id>`
- `placement/<service>/<id-key>`
- `scope/<org>` and `scope/<org>/<ws>`
- `catalog/<service>`
- `audience/<name>`

All resource types are platform-level unless their scope says otherwise.

| Action | Level | Resource |
|---|---|---|
| `ListPrincipals`, `ListGroups`, `ListPolicies`, `ListAttachments`, `ListKeys`, `ListManifests`, `ListPlacements` | list | each item |
| `GetPrincipal`, `GetGroup`, `GetPolicy`, `GetManifest`, `Explain`, `Simulate` | read | the item (`Explain`/`Simulate`: the principal asked about) |
| `ExchangeToken` | write | `audience/<session, nats, agent, app, preview, coding, api-key>` (§9.4) |
| `CreateServiceAccount`, `DeletePrincipal`, `SuspendPrincipal`, `ResumePrincipal`, `LinkUser` | admin | `principal/…` |
| `CreateGroup`, `DeleteGroup`, `AddGroupMember`, `RemoveGroupMember`, `MapIdpGroup`, `UnmapIdpGroup` | admin | `group/…` |
| `CreatePolicy`, `UpdatePolicy`, `DeletePolicy` | admin | `policy/…` |
| `AttachPolicy`, `DetachPolicy` | admin | `attachment/<policy>/<principal>` |
| `CreateKey`, `RevokeKey` | admin | `key/<principal>/<key>` |
| `ApproveManifest`, `RejectManifest` | admin | `manifest/…` |
| `PutPlacement`, `DeletePlacement` | admin | `placement/…` |
| `PutScope`, `DeleteScope` | admin | `scope/…` |
| `RegisterCatalog` | admin | `catalog/<service>` |

The JWKS (§9.1) is public and needs no action.

#### 6.5 Nexus catalog (`nexus`)

Nexus registers the catalog below. Resources are under `abi:<org>:<ws>:nexus:` unless marked org
(`abi:<org>:-:nexus:`) or platform (`abi:-:-:nexus:`).

- Every router authorizes through IAM as `api` on behalf of the signed-in user (§10.2).
- Kernel calls that Nexus makes for a user are authorized again by the kernel, on behalf of that user.

| Router | Resource types | Actions (level) |
|---|---|---|
| organizations | `organization/-` (org), `member/<user>` (org), `domain/<domain>` (org), `billing/-` (org), `role_features/-` (org) | `ListOrganizations` (list, items `organization/-`), `GetOrganization` (read), `CreateOrganization` (write, platform `organization/-`), `UpdateOrganization` (admin), `DeleteOrganization` (admin), `ListOrganizationMembers` (list), `InviteOrganizationMember` (admin), `UpdateOrganizationMember` (admin), `RemoveOrganizationMember` (admin), `ListOrganizationDomains` (list), `AddOrganizationDomain` (admin), `VerifyOrganizationDomain` (admin), `RemoveOrganizationDomain` (admin), `GetBilling` (admin), `UpdateBilling` (admin), `GetRoleFeatures` (read), `UpdateRoleFeatures` (admin), `CreateWorkspace` (write, org `organization/-`, creates `workspace/-` in the new workspace) |
| workspaces | `workspace/-`, `member/<user>`, `server/<id>`, `resource_access/<kind>` | `ListWorkspaces` (list, items `workspace/-`), `GetWorkspace` (read), `GetWorkspaceStats` (read), `UpdateWorkspace` (admin), `DeleteWorkspace` (admin), `ListWorkspaceMembers` (list), `InviteWorkspaceMember` (admin), `UpdateWorkspaceMember` (admin), `RemoveWorkspaceMember` (admin), `ListServers` (list), `CreateServer` (admin), `UpdateServer` (admin), `DeleteServer` (admin), `UpdateWorkspaceTheme` (admin), `GetResourceAccess` (read), `UpdateResourceAccess` (admin) |
| features | `feature/<FeatureKey>`, one of Nexus's `FeatureKey` values (`core/config.py`): `maps`, `chat`, `files`, `agents`, `skills`, `apps`, `marketplace`, `search`, `ontology`, `graph`, `datasets`, `settings`, `code`, `slides`, `documents`, `sheets` | `UseFeature` (read). Every router of a flagged section requires it, in addition to its own action. |
| chat | `conversation/<owner>/<id>` (personal) | `ListConversations` (list), `GetConversation` (read), `CreateConversation` (write), `SendMessage` (write: complete, stream), `UpdateConversation` (write), `DeleteConversation` (write), `ExportConversation` (read), `GetIngestionJob` (read) |
| agents, skills | `agent/<id>`, `skill/<id>` | `ListAgents`, `GetAgent`, `CreateAgent`, `UpdateAgent`, `DeleteAgent`, `SyncAgents` (admin), `UseAgent` (read; invoking it in chat or `/v1`), and the same set for skills with `UseSkill` |
| openai gateway | `agent/<id>` | `UseAgent`, plus `UseFeature` on `feature/chat` |
| files | `file/<drive>/<path>` (`path`) | `ListFiles` (list), `GetFile` (read: raw, preview, archive), `PutFile` (write: create, upload, rename, extract), `DeleteFile` (write); the platform and system drives also need their workspace setting (`platform_drive_enabled`, `system_drive_enabled`), and the system drive admin actions |
| office (slides, documents, sheets) | `project/<kind>/<slug>` | `ListProjects` (list), `GetProject` (read: content, history, diff, export), `CreateProject` (write), `UpdateProject` (write: every PUT, PATCH and edit command), `DeleteProject` (write), `RunProject` (write: runtime, evaluate) |
| graph and views | `view/<id>` (graph data itself is `triple_store` resources) | `ListViews` (list), `GetView` (read), `CreateView`, `UpdateView`, `DeleteView` (write) |
| ontology | `ontology/<id>`, `icon/<class>` | `ListOntologies`, `GetOntology`, `ExportOntology` (read), `ImportOntology`, `CreateOntologyEntity`, `DeleteOntologyEntity` (write), `UpdateIcons` (write), `RefreshOntologyCache` (admin) |
| search | `topic/<id>` | `Search` (read), `ListTopics` (list), `GetTopic` (read), `UpdateTopic`, `DeleteTopic`, `PreviewTopic` (write), `RefreshTopics` (admin) |
| maps | `layout/<id>`, `layer/<id>` | `ListLayouts`, `GetLayout` (read), `UpdateLayout`, `DeleteLayout` (write), `ListLayers`, `GetLayer` (read) |
| apps | `app/<id>`, `app_project/<slug>` | `ListApps` (list), `GetApp` (read), `UseApp` (read: open, link, grant), `InstallApp`, `UpdateApp`, `UninstallApp` (admin), `ListAppProjects`, `GetAppProject` (read), `CreateAppProject`, `UpdateAppProject`, `DeleteAppProject`, `PreviewAppProject`, `SubmitAppProject` (write) |
| secrets | `secret/<id>` | `ListSecrets` (list: masked), `CreateSecret`, `UpdateSecret`, `DeleteSecret`, `ImportSecrets` (admin) |
| coding and code review | (kernel `coding_environment` and `source_control` resources) | `UseFeature` on `feature/code`; then kernel actions; `SetDefaultRepo` (admin, `workspace/-`) |
| providers | `provider_model/<id>` (platform) | `ListProviderModels` (list), `GetProviderModel` (read), `UpdateProviderModel` (admin) |
| abi servers | `abi_server/<id>` | `ListAbiServers`, `GetAbiServer` (read), `CreateAbiServer`, `UpdateAbiServer`, `DeleteAbiServer` (admin) |
| realtime | `presence/-` | `GetPresence` (read), `Broadcast` (write) |
| speech | `speech/-` | `Transcribe`, `Speak` (read) |
| platform storage | (kernel `object_storage` under `users/<the call's user>/`) | kernel actions; `root=true` needs `object_storage:*` on `object/*` |
| datasets | (kernel `dataset` resources) | kernel actions |
| analytics | `analytics/-` (platform) | `ReadAnalytics` (read), `WriteAnalytics` (admin) |
| system | `system/-` (platform) | `ReadSystem` (read: overview, services, modules, telemetry, NATS, traffic, traces, jobs, runs), `ManageSystem` (admin: reveal, edit or delete entries, trigger or cancel jobs and runs, Ollama pull) |

- **Members and roles.** `InviteWorkspaceMember`, `UpdateWorkspaceMember` and `RemoveWorkspaceMember`
  translate to IAM `AttachPolicy` and `DetachPolicy` on `builtin.<role>`. IAM checks those too, so the owner
  protections of §7 hold whichever API is used.
- **Bug (d).** `CreateWorkspace` is checked on the target organization, not on a request field.
- **Features.** `UseFeature` is granted only by feature policies (§7): `builtin.features.<role>` from the
  deployment's `role_baseline`, or `builtin.features.<org>.<role>` where `organization_role_features`
  overlays it for an org. Either way they are restricted to `enabled_features`.

### 7. Built-in roles as policies

Built-in policies are managed:

- IAM generates their documents from the registered catalogs, so a new service's actions join the roles
  automatically;
- it stores them with explicit action lists, so `explain` shows real statements;
- it regenerates them when a catalog version changes.

They are attached at a scope (§3.4). "Viewer on workspace W" is `builtin.viewer` attached with scope
`abi:<org>:W`. That gives the read-only policy on `abi:<org>:W:*`.

For each catalog resource type `(service, type)` that can be placed in a workspace, the role's statement
covers `${scope}:<service>:<type>/*`. A personal type covers `${scope}:<service>:<type>/${principal.id}`
and `${scope}:<service>:<type>/${principal.id}/*` instead. `${principal.id}` is the member being evaluated
(§3.4), so on a Nexus call it is the user, not `api`.

**The roles are cumulative:** `viewer` ⊆ `member` ⊆ `admin` ⊆ `owner`.

- Each role holds every statement of the role below it, generated into its own document. A principal
  therefore needs only one role attachment per scope, which is what the migration creates (§13).
- Each role's scope-type statements leave out the `nexus` `feature` type, so no role reaches `UseFeature`
  through its scope pattern. Features come only from the feature policies below.

| Policy | Allows on the scope's types | Excludes |
|---|---|---|
| `builtin.viewer` | every `list` and `read` action | the `feature` type |
| `builtin.member` | viewer, plus every `write` action | the `feature` type |
| `builtin.admin` | member, plus every `admin` action, except on the `iam` `attachment` type; plus `iam:ListAttachments` on `${scope}:iam:attachment/*`, and `iam:AttachPolicy` and `iam:DetachPolicy` on `${scope}:iam:attachment/builtin.admin/*`, `…/builtin.member/*`, `…/builtin.viewer/*` | the `feature` type; anything on `attachment/builtin.owner/*`; `nexus:DeleteWorkspace`; `nexus:DeleteOrganization` |
| `builtin.owner` | admin, plus every action on every `attachment/…` (owner included), `nexus:DeleteWorkspace` and `nexus:DeleteOrganization`: every action of every catalog on the scope's types | the `feature` type |
| `builtin.platform_admin` | `*` on `*` (attached without scope) | sealed resources (§11.3), which no policy can unlock |
| `builtin.self` | auto-attached to every user, no scope: the "self" column of "Platform types" | — |

**Features.** `UseFeature` comes only from feature policies. IAM attaches the matching feature policy at
the same scope whenever it attaches a role, and detaches it with the role.

- `builtin.features.<role>` is generated from Nexus's `feature_flags.role_baseline` (`core/config.py`).
  `builtin.features.<org>.<role>` is used where `organization_role_features` overlays it for an org.
- Both allow `nexus:UseFeature` on `${scope}:nexus:feature/<key>` for the role's features that are also
  in `feature_flags.enabled_features`. A feature outside `enabled_features` is reachable by no role, owner
  and admin included. Only the platform admin's `*` can reach it.
- Defaults: `owner` and `admin` get every enabled feature. `member` and `viewer` get `maps`, `chat`,
  `files`, `datasets`, `skills`, `slides`, `documents` and `sheets`.
- Changing `role_baseline`, `enabled_features` or an org overlay regenerates the feature policies.

**Platform types.** A workspace-scoped role never reaches a platform-level resource (`abi:-:-:…`). Every
platform-level type of every catalog is listed below with who reaches it, through two more managed
policies that IAM keeps in step with role attachments.

- **`builtin.platform.viewer`** holds the "Viewer" column. **`builtin.platform.member`** holds the "Viewer"
  and "Member adds" columns.
- Both are attached without scope, by IAM:
  - a principal holds `builtin.platform.member` while it has a `member`, `admin` or `owner` attachment at a
    workspace scope (`abi:<org>:<ws>`) or an org-wide scope (`abi:<org>:*`);
  - it holds `builtin.platform.viewer` while it has only `viewer` attachments there.
- Org-level attachments (`abi:<org>:-`) bring neither. An org member who belongs to no workspace cannot
  chat with models, invoke agents or open apps. That matches today: those surfaces live in workspaces.
- **Self** is `builtin.self`, held by every user.
- **None** means only the platform admin, the built-in service accounts and explicit policies.

Because Nexus calls as `api` on behalf of the user, the user must hold these, not only `api`.

| Service:type | Viewer | Member adds | Self | Notes |
|---|---|---|---|---|
| `model_registry:model/*` | `ListModels`, `Resolve` | `Chat`, `ChatStream`, `Embed` | — | |
| `discovery:module/*`, `agent/*`, `app/*` | `ListModules`, `GetModule`, `ListAgents`, `ListApps`, `OpenApp` | `InvokeAgent` | — | Nexus also checks `nexus:UseAgent` / `UseApp` |
| `discovery:model/*` | — | `ChatModel` | — | |
| `discovery:run/${principal.id}/*` | `GetAgentRun` | `CancelAgentRun` | — | personal |
| `discovery:job/*`, `job_run/*` | — | — | — | none: jobs are platform admin |
| `triple_store:view/*` | `QueryView` | — | — | `Query` rules still apply to the graphs the view reads |
| `coding_environment:template/*` | `ListTemplates` | — | — | |
| `coding_environment:coder_user/${principal.id}` | — | — | `EnsureUser` | personal |
| `source_control:forge_user/${principal.id}` | — | — | `EnsureUser`, `MintGitToken` | personal |
| `activity_log:actor/${principal.id}` | — | — | `Query`, `QueryStream` | personal |
| `iam:principal/${principal.id}` | — | — | `GetPrincipal` | |
| `iam:key/${principal.id}/*` | — | — | `ListKeys`, `CreateKey`, `RevokeKey` | personal API keys |
| `nexus:organization/-` (platform) | — | — | `CreateOrganization` | removed from `self` when `nexus.organizations.self_service: false` |
| `nexus:provider_model/*` | `ListProviderModels`, `GetProviderModel` | — | — | |
| `email:sender/*`, `email:message/*` (unplaced) | — | — | — | none: mail is sent by `api`, `engine` and `idp` |
| `dataset:catalog/-`, `cache:service/-`, `vector_store:service/-`, `activity_log:service/-` | — | — | — | none: maintenance and lifecycle |
| unplaced data (`object`, `document`, `key`, `secret`, `graph`, `event_type`, …) | — | — | — | none until placed (§4.4) or granted explicitly |

Which agents and apps a workspace may use stays a Nexus decision: `nexus:UseAgent`, `nexus:UseApp` and
`UseFeature`, checked before the kernel call.

**Owner protection (bug c).**

- An admin cannot attach or detach `builtin.owner`.
- Demoting or removing an owner means detaching their `builtin.owner` attachment, so only an owner can do
  it, at org and workspace scope alike.

**Org roles.**

- Today's org roles (owner, admin, member) are attached with scope `abi:<org>:-`, the org's own resources.
  That matches today: org membership never grants workspace access.
- Org-wide roles (`abi:<org>:*`) are available but never created by the migration.

**Built-in service accounts.**

- `builtin.engine`, `builtin.api` and `builtin.idp` are attached to `engine`, `api` and `idp`.
- They start as one broad transitional statement each (subtask 3). Subtask 11 replaces them with
  enumerated statements, each with a `sid` that says what needs it.
  - `api` keeps what Nexus does for users. Because of the OBO intersection, the user still bounds every
    call.
  - `engine` keeps boot, jobs and schedulers.
- `builtin.idp` covers only its own namespace, secrets and sender (§12.3).

### 8. Service accounts

#### 8.1 Keys

- **Format.** `abi_sk_<key id>_<secret>` for service accounts and `abi_pk_<key id>_<secret>` for personal
  API keys (§9.4).
  - `key id`: 16 lowercase base32 characters.
  - `secret`: 32 random bytes, base64url without padding.
- **Storage.**
  - IAM stores `key id`, principal, `sha256(secret)`, `created_at`, `expires_at` (optional), `last_used_at`,
    `revoked_at` and a description.
  - A fast hash is enough because the secret has 256 bits of entropy. Comparison is constant-time.
  - The key is shown once, at creation.
- **Rotation.** Create a new key, deploy it, revoke the old one. At most five active keys per principal.
- **Effect.** Revoking or expiring a key takes effect at the next exchange and the next broker connection.
  Tokens already issued expire within 10 minutes. Suspension cuts everything off at once (§2).
- **Default expiry.**
  - Module keys: none.
  - `ci/*` keys: 90 days.
  - Personal API keys: required, 1 year at most.

#### 8.2 Exchange

- **Over NATS.** A service account exchanges its key at `abi.iam.v1.token`: request `{key}`, response an
  engine access token, audience `abi:nats`, at most 10 minutes (§9).
- **Over HTTP.** Scripts use Nexus `POST /api/iam/token` (`grant_type=client_credentials`, the key as
  `client_secret`).
- **Renewal.** SDK and core clients renew the token at half its life.
- **Environment.** The key reaches a module as `ABI_SERVICE_KEY`. `ABI_SERVICE_TOKEN` and
  `NATS_JWT_SECRET` are removed.

#### 8.3 Module permission manifest and approval

A module declares the permissions it needs:

- either in `permissions.yaml` beside its `BaseModule`, a policy document (§3.1);
- or by defaulting them from `ModuleDependencies`: each declared service maps to its catalog's actions on
  the module's own namespaces.

Two manifest-only variables are substituted when it is approved:

- `${module.id}`
- `${module.project}`

```yaml
version: "2026-10-13"
statements:
  - sid: OwnDocuments
    effect: Allow
    actions: ["document:*"]
    resources:
      - "abi:-:-:document:namespace/${module.id}"
      - "abi:-:-:document:collection/${module.id}/*"
      - "abi:-:-:document:document/${module.id}/*"
  - sid: ReadOntologyGraphs
    effect: Allow
    actions: ["triple_store:Query", "triple_store:ListGraphs"]
    resources: ["abi:-:-:triple_store:graph/http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fschema*"]
```

The flow:

1. **Deploy tooling creates the account.** `abi dev up`, `abi deploy`, or an admin through
   `abi iam service-account create` creates service account `module/<project>/<module_id>` and a key.
2. **Bootstrap.** Until approval, the account holds only `builtin.module_bootstrap`:
   - `discovery:Register`, `Renew`, `Unregister`, `GetModule` on its own `module/<project>/<module_id>`;
   - `iam:RegisterCatalog` refused;
   - the token and JWKS subjects.

   The manifest becomes a policy only once approved, never before.
3. **Registration.**
   - `discovery:Register` carries the manifest and its SHA-256 in `ModuleDescriptor`.
   - Discovery refuses a registration whose `module_id` and project differ from the caller's service-account
     name. That binds the logical module name to its principal.
4. **Review.**
   - IAM records the manifest as `pending` unless it equals the approved one.
   - An admin approves it as is, narrows it (edits it), or rejects it: `iam:ApproveManifest` or
     `RejectManifest` on `manifest/<sa>`, from the CLI (`abi iam module approve|reject`) or the IAM UI.
   - The approved document becomes the managed policy `module.<project>.<module_id>`, attached to the
     account.
   - On approval IAM also records platform placements for the module's own `<module_id>` namespaces in
     document and dataset (§4.4), unless they are already placed. No workspace can then claim a name inside
     them.
5. **Before approval** the module registers and serves health, but every other call fails with
   `PERMISSION_DENIED`. Discovery shows the module as awaiting approval.
6. **A changed manifest** is a new pending version. The previous approved policy stays in force until the
   new one is approved.
7. **`abi dev up` approves automatically.** It sets `iam.modules.auto_approve: true` in the dev overlay
   only. Fresh `config.yaml` and the Docker templates keep `false`.

#### 8.4 Broker permissions through NATS auth callout

- **Connections.**
  - Every module connection authenticates through **auth callout** in the engine.
  - The engine's own connection is a static user, `engine`, listed in `auth_users`. Its permissions cover
    the kernel subjects, discovery queues, JetStream and the system subjects the engine needs, not `>`.
  - The callout responder connects as static user `auth`.
- **What the callout does.**
  1. Reads the service key from `CONNECT` (password, with user `sa`).
  2. Checks that the key is valid and the principal active.
  3. Returns a user JWT signed with the callout account's nkey, valid at most 1 hour.
- **Expiry.** On expiry the client reconnects and permissions are recomputed. Services enforce changes
  immediately (§5.6); the broker catches up within the hour.
- **Subjects.** From the approved policy plus the bootstrap:

| Source | Publish allow | Subscribe allow |
|---|---|---|
| Always | `abi.iam.v1.token`, `abi.iam.v1.jwks`, `abi.iam.v1.exchange_token` | `_INBOX_<sa>.>`. Clients set inbox prefix `_INBOX_<sa>`, so no one reads another's replies. |
| Bootstrap | `abi.discovery.<project>.v1.{register,renew,unregister,get_module,list_modules}` | — |
| Hosting its components | replies (`allow_responses`) | `abi.agent.<project>.<sa>.>`, `abi.mod.<project>.<sa>.>`, its job consumers' `$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>` |
| Each action with an Allow (any resource) and no Deny on `*` | that action's catalog `subjects`; a stream action adds `abi.svc.<svc>.v1.transfer.open` and `abi.svc.<svc>.v1.transfer.*.{write,start,read,close}` | — |
| `discovery:InvokeAgent`, `GetAgentRun`, `CancelAgentRun` | `abi.agent.<project>.*.*.*.v1.{submit,status,event,cancel}` | — |
| `discovery:ChatModel`, `OpenApp` | `abi.mod.<project>.*.*.model.*.chat`, `…app.*.http` | — |
| `discovery:TriggerJob`, `ScheduleJob`, `CancelJobRun` | `abi.jobs.<project>.{trigger,schedule,cancel}.>` | — |
| Everything else | denied | denied (including `$SYS.>`, other `$JS.API.>`, `abi.svc.*.v1.*.owners`) |

- `<sa>` is the service account's ULID part. Hosting subjects gain it as a whole token (subtask 6), because
  NATS wildcards cannot match part of a token.
- The broker grants at the operation level. Resource-level decisions stay in the domain services.
- The old `abi` and `module` users are removed. `nats.conf`, written by `abi dev`, the CLI deploy template
  and `.deploy/docker/nats/nats.conf`, declares `authorization { users, auth_callout { issuer, auth_users } }`.

### 9. Tokens

#### 9.1 Engine-issued tokens and JWKS

- **Signing.**
  - The engine (IAM) signs every engine token with **ES256** (P-256).
  - Keys have a `kid` of the form `<yyyymmdd>-<8 hex>`. Private keys live in the secret service at
    `iam/signing-keys/<kid>`, sealed to `engine`.
  - Modules never hold a signing key. HS256 and `NATS_JWT_SECRET` are retired with no dual mode: this is a
    major release, and every first-party module moves in the same subtask.
- **Rotation.**
  - Every 30 days (`iam.tokens.key_rotation_days`).
  - A new key is published at least 15 minutes before it signs.
  - A retired key stays published for 20 minutes after its last use.
- **JWKS.**
  - `abi.iam.v1.jwks`, request and reply, returns an RFC 7517 key set. It needs no token.
  - Nexus also serves it at `/.well-known/abi-jwks.json`.
  - Verifiers cache it for 5 minutes and refetch on an unknown `kid`, at most once every 30 seconds.
- **Issuer.** `urn:abi:engine:<install id>`. The install id is generated at first boot and stored in IAM.

#### 9.2 Claims

| Claim | Meaning |
|---|---|
| `iss` | The engine issuer (§9.1). |
| `sub` | Principal id. For a delegated token, the user. |
| `act` | RFC 8693 actor: `{"sub": "<sa id>"}`. Present when someone acts for `sub`. |
| `aud` | Exactly one audience (§9.3). |
| `kind` | `user` or `service_account`: the kind of `sub`. |
| `grp` | Mapped IdP group ids (users only, §2). |
| `abi_scope` | Optional narrowing: a list of Allow statements (§5.3). |
| `idp` | `{"iss": …, "sub": …}` of the source IdP identity (users only), for audit. |
| `sid` | The Nexus session id, so a logout ends its exchanged tokens. |
| `iat`, `nbf`, `exp`, `jti` | `exp - iat ≤ 600`. Verifiers refuse anything longer and allow 30 seconds of clock skew. |

**No access token lives longer than 10 minutes.** The engine issues no refresh tokens:

- service accounts exchange their key again;
- Nexus sessions refresh at the IdP with the refresh token Nexus holds server-side, then exchange again.

#### 9.3 Audiences

| Audience | Issued for | Accepted by |
|---|---|---|
| `abi:session` | A Nexus session: a user, after the IdP login | Every Nexus REST route and the WebSocket. Nothing else. |
| `abi:nats` | Service accounts (key exchange); `api` and `engine` | Every kernel NATS endpoint, discovery, agent, model and app hosts |
| `abi:delegated:agent` | A module acting for a user (`act` = the module's service account) | Kernel NATS endpoints and module hosts, as actor plus OBO user |
| `abi:delegated:app` | Opening a remote app or app-html link | Only the app routes, `discovery:OpenApp` on the app named in `abi_scope` |
| `abi:delegated:preview` | App-project preview links | Only `/app-preview/…` for that project |
| `abi:delegated:coding` | A coding environment's agent, for the user who owns the environment | Nexus coding and office routes only, narrowed by `abi_scope` to the environment's workspace and repo |
| `abi:delegated:api-key` | A personal API key | Nexus REST routes not marked session-only |

- **Delegated tokens are never a session.** Session-only routes (account, IAM administration, API-key
  management, logout) require `abi:session` exactly.
- **Links stay revocable.**
  - A link (app, preview) carries a grant id that IAM stores, at most 8 hours, revocable.
  - Each open exchanges the grant for a 10-minute token.
- **Bug (a).**
  - The coding environment holds a personal key of its owner (`abi_pk_…`), created for that environment,
    narrowed to its workspace and repo, and revoked when the environment is deleted.
  - Nexus exchanges that key for `abi:delegated:coding` tokens (`sub` = the owner, no `act`). The 30-day JWT
    disappears.

#### 9.4 Token exchange (RFC 8693)

- **Where.** `abi.iam.v1.exchange_token` over NATS. Nexus calls it server-side.
- **Request.**

  | Parameter | Value |
  |---|---|
  | `grant_type` | `urn:ietf:params:oauth:grant-type:token-exchange` |
  | `subject_token` | the token being exchanged |
  | `subject_token_type` | `urn:ietf:params:oauth:token-type:id_token`, `…:access_token` (IdP tokens), `…:jwt` (engine tokens) or `urn:abi:params:oauth:token-type:api_key` (an `abi_pk_…` key) |
  | `audience` | the wanted audience |
  | `resource` | optional, the canonical name of the target agent, app, project or environment |
  | `scope` | optional, a JSON `abi_scope` list |
  | `requested_token_type` | `urn:ietf:params:oauth:token-type:jwt` |

- **Response.** `access_token`, `issued_token_type`, `token_type: Bearer`, `expires_in ≤ 600`.
- **The requester** is the NATS caller (`Nats-Auth-Token`). It needs `iam:ExchangeToken` on
  `audience/<name>`. Only `api` holds it for any audience. Scripts exchange a personal API key through Nexus
  `POST /api/iam/token`, which calls the exchange as `api`.
- **IdP tokens**, for `abi:session` only, are verified against the configured provider (§10.1):
  - `iss` matches a provider;
  - the signature checks against that provider's JWKS;
  - `aud` is its `client_id`;
  - `exp` and `nbf` hold.

  Then IAM resolves or creates the principal, maps groups and refuses a suspended principal.
- **ABI keys** (`urn:abi:params:oauth:token-type:api_key`): IAM checks the hash, the expiry, the revocation
  and the owner's status.
  - A personal API key reaches `abi:delegated:api-key` only.
  - A coding-environment key, a personal key created for one environment (§9.3), reaches
    `abi:delegated:coding` only.
  - Either way, `sub` is the key's owner and `abi_scope` is the key's own narrowing.
  - Service-account keys (`abi_sk_…`) are not exchanged here: they use `abi.iam.v1.token` (§8.2).
- **Engine tokens** can be exchanged only toward a narrower audience:
  - `session` → `agent`, `app`, `preview`, `coding`;
  - never back to `session`;
  - never from one delegated audience to another.
- **The actor of a delegated token** is the service account that owns `resource`: the module behind an agent
  or app, read from discovery. App, preview, coding and API-key tokens have no actor. The actor never comes
  from a request field.
- **`abi_scope`** is intersected with what the subject already holds (§5.3). An exchange can never add a
  permission.

### 10. How `CallContext` is filled

#### 10.1 The type

`naas_abi_sdk.call_context` (subtask 2), re-exported by `naas_abi_core.engine.call_context`: one context
variable, so the engine and the SDK clients it runs read the same value. A core installed without the SDK (no
`nats` extra) runs a verbatim copy, `naas_abi_core/engine/call_context_types.py`.

```python
@dataclass(frozen=True)
class Principal:
    id: str                         # usr_/grp_/sa_ id; "anonymous" for none
    kind: Literal["user", "service_account", "anonymous"]
    name: str | None = None         # service-account name, e.g. "api"
    issuer: str | None = None       # users: IdP issuer
    subject: str | None = None      # users: IdP sub
    groups: frozenset[str] = frozenset()

@dataclass(frozen=True)
class CallContext:
    principal: Principal                     # the actor
    on_behalf_of: Principal | None = None    # the user, when acting for one
    audience: str | None = None
    token_id: str | None = None              # jti, for audit
    scope: tuple[Statement, ...] | None = None   # abi_scope narrowing
    workspace_id: str | None = None          # target workspace: a request input, not identity
    trace_id: str | None = None
    triggered_via: str | None = None         # "api", "cli", "configuration"…, stamped on events

    @property
    def user(self) -> Principal | None: ...  # the call's user, below

_call_context: ContextVar[CallContext]   # default: ANONYMOUS, which every check denies
```

Until IAM assigns `sa_` ids (subtask 6), a service account's id is its name (`api`, `engine`, a module), and
an OBO user's id is the one its trusted caller names (a Nexus user id).

**The call's user** is `on_behalf_of` when it is set, else `principal` when it is a user, else none. Services
use it wherever an operation concerns "the user": the activity actor, the forge or Coder user, the owner of
a new personal resource. It never comes from a request field.

Helpers:

- `use_call_context(ctx)`: a context manager that sets the variable and resets it on exit.
- `current_call_context()`.
- `as_service_account(name)` (core only): in-process only, logged. It is how boot, schedulers, jobs and
  Nexus housekeeping run. Remote code has no equivalent: it holds only its token.
- `on_behalf_of_header(ctx)`: the `Abi-On-Behalf-Of` header naming the call's user, or none.

The event actor fields (`actor_user_id`, `actor_workspace_id`, `triggered_via`) come from the call's user,
`workspace_id` and `triggered_via`. The older names `event_actor_user_id`, `event_actor_workspace_id`,
`event_triggered_via` (and `agent_user_id`, `agent_workspace_id`) are views of this context with a
ContextVar-like `get`/`set`/`reset`, so there is one source of identity.

#### 10.2 Who sets it

Every primary adapter sets it **only from verified credentials**:

| Caller | Source | Result |
|---|---|---|
| NATS (kernel services, discovery, module hosts, the SDK) | The `Nats-Auth-Token` header, verified against the JWKS (§9.1), audience accepted by the endpoint (§9.3) | No `act`: principal = `sub`. With `act`: principal = `act.sub`, OBO = `sub`. Groups from IAM plus `grp`. Scope from `abi_scope`. Set by one shared helper in the NATS dispatch path, not per adapter. |
| Nexus REST | The session cookie's `abi:session` token, or an `abi:delegated:*` token on routes that accept it | principal = `api`, OBO = the user (subtask 2). Every kernel call Nexus makes for the request then runs as `api` on behalf of the user, so the intersection rule (§5.3) applies. Until subtask 7, the user is named only for an unrevoked Nexus session token; a request without one (a link token included) is `ANONYMOUS`, never `api`. |
| Nexus calling remote agents and apps | An `abi:delegated:agent` or `abi:delegated:app` token exchanged for the target (§9.4) | Sent in the `Nats-Auth-Token` header of the call, and handed to the agent host in `SubmitRequest.delegated_token` for the run's downstream calls |
| In-process code | Inherits the caller's context. `asyncio.to_thread` copies it; executor submissions use `contextvars.copy_context().run` (already done by `DomainRPCDispatcher`). Background tasks capture it at creation or use `as_service_account`. | unchanged |
| The SDK module host | Sets the SDK context from the verified incoming invocation. Downstream SDK calls send the delegated token from that context. | principal = the module's service account, OBO = the user |

**Never from request-body fields.** These are request data, not identity:

- `CallContext.principal_id` and `CallContext.tenant_id` in the proto become reserved and deprecated.
  Servers ignore them and clients leave them empty.
- `CallContext.workspace_id` stays, documented as the target workspace for create operations (§4.4). It is
  an input like any other and is authorized.
- `HttpRequest.user_id` (app proto), `request.user_id` in `source_control` and `coding_environment`, the
  prompt preamble Nexus prepends for agents, and any `X-User-*` header are not identity.

**Credentials never reach module code.** When Nexus forwards a request to a module (remote apps, the
built-in IdP route), it forwards an allow-list of headers, never a deny-list. Every credential is dropped:

- `Authorization` and `Cookie` (except the IdP route's own `Path=/idp` cookies, §12.3);
- `X-Api-Key`;
- auth-proxy identity headers such as `X-Amzn-Oidc-*`, `X-Auth-Request-*` and `X-Goog-Iap-Jwt-Assertion`.

The module learns who is calling only from the delegated token's verified claims.

**Transition.** Until subtask 8 issues delegated tokens, an `Abi-On-Behalf-Of: <principal id>` header is
honoured only when the verified caller is `api` or `engine`. Subtask 8 removes it.

- From any other caller the call is refused as unauthenticated, before the domain service, with its own
  message (`on-behalf-of refused: …`) and a log line: a header naming a user can only narrow a call (§5.3),
  so dropping it silently would widen it.
- The core RPC client sends the current call's user only when its own identity is `api` or `engine`; another
  identity calls as itself, as before. The SDK transport sends it only when built with `forward_user=True`,
  which the engine's kernel-calling transports (model registry, jobs) set. Nexus's transports to agent and
  app hosts do not: module hosts get the user from delegated tokens (subtask 8).
- Stage 1 tokens (HS256, `{sub, iat, exp}`) carry no audience, `jti`, groups or `abi_scope`: those fields stay
  empty until subtask 6.

**As built in subtask 2.** `naas_abi_core.engine.nats_identity` is the shared helper: `caller_context` verifies
the token and the header, `nats_rpc.authenticate_request` wraps it for `nats.micro` requests (and answers a
refusal), and `for_request` adds the trace and target workspace of the request's `context` envelope.
`DomainRPCDispatcher.call(fn, request, caller)` runs the worker in a copy of the context holding that caller;
discovery, the model registry and transfer sessions use it the same way. A transfer session runs as the caller
who opened it and belongs to that actor acting for that user: the same actor for another user is refused.
Overflow chunks carry their call's token, user, trace and workspace; a client stream captures its user once,
when it opens. Model registry chat streams are owned the same way as transfer sessions. So far `as_service_account` wraps
engine-hosted jobs (`engine`) and Nexus's configuration seeding (`api`); engine boot still runs anonymous. The event, vector_store and cache
endpoints call their domain services (`EventService`'s stored-level operations, `VectorStoreService`,
`CacheService`'s tier views), so a check in the domain service covers them.

### 11. IAM, the kernel service

#### 11.1 Placement in core

`libs/naas-abi-core/naas_abi_core/services/iam/` follows the service layout:

- port, service, factory, adapters, tests;
- its own `AGENTS.md` and a row in the root Service Map.

Pieces:

- **Secondary `IAMStore` port.**
  - SQLite (default, `storage/iam/iam.sqlite`), PostgreSQL and in-memory adapters.
  - SQLAlchemy, with one generic contract test.
  - It does not use the Document Service: IAM authorizes the Document Service, and needs transactions,
    unique constraints and joins (ADR `20261013_iam-kernel-service.md`).
- **Tables:** `principals`, `users` (`issuer`, `sub` unique), `groups`, `group_members`, `group_mappings`,
  `policies`, `attachments`, `keys`, `manifests`, `placements`, `scopes`, `catalogs`, `sealed`, `grants`
  (link grants), `signing_keys` (metadata only; private keys live in the secret service), `install`.
- **Primary adapters:**
  - in-process (`engine.services.iam`);
  - NATS `abi.iam.v1.*` (proto `iam/v1/iam.proto`);
  - the auth-callout responder;
  - the SDK facade `engine.services.iam`.

Configuration:

```yaml
services:
  iam:
    store:
      adapter: sqlite              # sqlite | postgres | memory
      path: storage/iam/iam.sqlite
      # dsn: "{{ secret.IAM_POSTGRES_DSN }}"
    authorizer: policy             # policy (default) | allow_all (explicit opt-out; warns at boot)
    modules:
      auto_approve: false          # true only in the abi dev overlay
    tokens:
      access_ttl_seconds: 600      # capped at 600
      key_rotation_days: 30
```

`users[].is_superadmin` in the config becomes a `builtin.platform_admin` attachment at boot (subtask 3).

#### 11.2 Authorizer port

The port is shaped like OpenFGA's API, so a relationship-based adapter can be added later without touching
callers:

```python
class IAuthorizer(ABC):
    def check(self, ctx: CallContext, action: str, resource: str) -> Decision: ...
    def filter(self, ctx: CallContext, action: str, resources: Iterable[str]) -> FilterResult: ...
    def explain(self, ctx: CallContext, action: str, resource: str) -> Explanation: ...
```

- `Decision` carries `allowed`, `visible` (§5.4) and `reason`.
- `FilterResult` carries the allowed subset and the prefix hints (§5.5).
- Adapters:
  - `policy`: this RFC, the default;
  - `allow_all`: an explicit opt-out that logs a warning at boot.

Domain services use:

- `iam.require(action, resource)`, which raises the §5.4 error;
- `iam.filter(action, resources)`.

Both read `current_call_context`.

#### 11.3 Sealed resources

A sealed resource is a resource pattern bound to one principal.

- No other principal is ever allowed on it, whatever its policies say. That includes `engine`, `api` and
  the platform admin.
- Seals are declared in code by the service that owns them and loaded at boot. No API changes them, so
  editing policies cannot open them.
- The seals:
  - `abi:-:-:document:namespace/idp`, `abi:-:-:document:collection/idp/*` and
    `abi:-:-:document:document/idp/*`, sealed to `idp`;
  - `abi:-:-:secret:secret/idp%2F*`, sealed to `idp`;
  - `abi:-:-:secret:secret/iam%2F*`, sealed to `engine`.
- An operator who needs the IdP's data back uses the IdP's own admin API or the database directly. That
  is outside ABI's authorization by design.

#### 11.4 Caches and change events

- Every process that checks caches effective statements per principal, plus placements, statuses and
  catalogs.
- IAM publishes `abi.iam.v1.changed` (core NATS fan-out, with a monotonically increasing revision) on every
  change. In process it calls the same invalidation directly.
- Caches drop affected entries on receipt, and everything after 60 seconds.
- A process that sees a revision gap drops its whole cache.

### 12. Identity providers and the built-in IdP

#### 12.1 Providers

Providers are configured engine-wide:

```yaml
identity:
  default_provider: builtin
  providers:
    - name: builtin
      issuer: "https://abi.example.com/idp"
      client_id: nexus
      client_secret: "{{ secret.IDP_NEXUS_CLIENT_SECRET }}"
      provisioning: builtin          # builtin | zitadel | keycloak | none
    - name: acme
      issuer: https://acme.okta.com
      client_id: abi
      client_secret: "{{ secret.ACME_OIDC_SECRET }}"
      groups_claim: groups
      scopes: [openid, email, profile, groups]
      provisioning: none
```

- **Validation at boot.**
  - `name` matches `^[a-z0-9-]{1,32}$` and is unique.
  - `issuer` is `https`, or `http` on localhost only.
  - Discovery is read from `<issuer>/.well-known/openid-configuration`.
- **Login routing.** `organization_domains` gains a `provider` column: an email domain routes to a provider.
  With no match, `default_provider` is used.
- **Organizations stay an ABI concept.** A provider is not per organization, and an org is not an IdP
  tenant.
- **Nexus is an OIDC client.**
  - Authorization code with PKCE (S256).
  - The session is an httpOnly, Secure, SameSite cookie held by the API, with CSRF protection.
  - The IdP refresh token stays server-side. Nothing goes in `localStorage`.
- **No external IdP is bundled.**
  - The docs show Okta, Entra, Zitadel and Keycloak.
  - Zitadel, a single native binary downloaded and pinned by a test helper like `nats-server`, is the
    external reference for the generic identity test suite in CI.
- **Revocation.**
  - Access tokens live 10 minutes at most.
  - IAM suspension takes effect immediately.
  - There is no SCIM and no token introspection.

#### 12.2 Provisioning

The `provisioning` port has one adapter per provider setting (subtask 10):

- `builtin` calls the IdP's admin RPCs;
- `zitadel` and `keycloak` call those providers' admin APIs;
- `none` raises `NotImplementedError`.

**Pending grants.** An attachment can target `(provider, email)` before the user exists. It is claimed on
first login by a matching *verified* email, on that provider only.

#### 12.3 The built-in IdP

- **Package.** A core-free SDK module, the package `libs/naas-abi-idp`. It depends on `naas-abi-sdk`,
  `naas-abi-proto` and `authlib` only, and runs over NATS under service account `idp` with an approved
  manifest.
- **Scope.**
  - Email-code sign-in: 6-digit codes, valid 10 minutes, rate limited per account and per IP. Every wrong
    guess counts against every active code of the account, atomically.
  - Optional password sign-in, off by default.
  - Authorization code + PKCE, refresh tokens, discovery, JWKS (ES256), userinfo and end-session.
  - Client credentials for OIDC clients that need IdP tokens. Engine service accounts use IAM keys (§8),
    not the IdP.
  - Admin RPCs over NATS, its own catalog `idp:` on `abi:-:-:idp:user/<sub>` and `abi:-:-:idp:group/<id>`:
    `ListUsers`, `GetUser`, `CreateUser`, `DisableUser`, `DeleteUser`, `ListGroups`, `CreateGroup`,
    `SetUserGroups`.
  - Org branding on the login page.
  - Mail through `email:Send` on its own sender.
  - Out of scope: SAML, brokering other IdPs, MFA policies.
- **Data and keys.**
  - Users, codes, clients, sessions and refresh tokens live in its Document Service namespace `idp`.
  - Its signing keys live in the secret service under `idp/`.
  - Both are sealed to `idp` (§11.3): neither `api` nor `engine` can read them.
  - It never uses Nexus `secret_key`, and Nexus never reads its data.
- **The trusted route.**
  - The sandboxed `/app-remote/<grant>/` path forbids what a login page needs: access before sign-in,
    cookies and form posts. So the IdP gets a dedicated trusted route instead.
  - Nexus mounts `identity.builtin.route` (default `/idp`) at the issuer URL `https://<host>/idp` and
    forwards it over `abi.app.v1` to the IdP module's app.
  - Differences from remote apps (ADR `20261012_remote-module-apps.md`):
    - no grant;
    - anonymous access;
    - cookies pass through with `Path=/idp`, not renamed;
    - form posts are allowed;
    - CSP `default-src 'self'; frame-ancestors 'none'`;
    - the same request and response header allow-lists.
  - Nexus answers on the route only when the app's owner in discovery is service account `idp`.
- **Defaults.**
  - `abi new project` and `abi dev up` run it as a dev module and configure `identity.providers` with
    `builtin`.
  - The Docker templates run it as its own container.

### 13. Migration

- **The upgrade.**
  - It is the next major.
  - A job, `iam_migrate`, runs a dry run first (`{}`) and then applies (`{"apply": true}`), like
    `agent_memory_migrate`.
  - Fresh installs enforce from the start. Existing installs enforce once `iam_migrate` has run.
  - `authorizer: allow_all` is the only way to opt out, and it must be set explicitly.

| Today | After |
|---|---|
| Nexus `users` (email, password hash) | Built-in IdP users with the same email and a new `sub`, the password hash moved to the IdP, and an IAM principal for `(builtin issuer, sub)`. Nexus `users` points to the principal id. They are linked on first login by verified email, inside the built-in provider only. |
| `workspace_members.role`, the `workspaces.owner_id` fallback | `builtin.<role>` attachments at scope `abi:<org>:<ws>`; the fallback becomes an explicit owner attachment |
| `organization_members.role`, `organizations.owner_id` | `builtin.<role>` at scope `abi:<org>:-` |
| `users.is_superadmin` and `users[].is_superadmin` | `builtin.platform_admin` |
| `organization_role_features` | `builtin.features.<org>.<role>` (§6.5) |
| `workspace_resource_policies`, the `graphWorkspaceId` triples, `WorkspaceGraphPolicyConfig` | graph placements, plus Allow statements in a workspace policy for shared graphs |
| Nexus per-workspace prefixes and namespaces (object storage, documents, vectors, datasets) | workspace placements (`iam:PutPlacement`) |
| Every other existing container (module and engine namespaces, collections, repos, graphs) | platform placements, so no workspace can claim a name inside them (§4.4) |
| Remote modules with `NATS_JWT_SECRET` | service accounts, keys and approved manifests. `abi dev up` regenerates them; deployed systems run `abi iam module approve`. |
| Sessions, refresh tokens, app grants and preview tokens signed with `secret_key` | invalidated: users sign in again. `secret_key` keeps only the workspace-secret encryption until subtask 13 gives that its own key. |

- **Removal.** Nexus's login code, `refresh_tokens`, `magic_link_tokens`, `password_reset_tokens` and the
  `api_keys` mock are removed in subtask 13.
- **Each subtask leaves the branch green.** Each keeps existing remote modules and `make demo-sdk` working.
  It relies on the transitional broad policies of `api` and `engine` until subtask 11 replaces them.

### 14. Subtask plan

| # | Shepherd | Subtask | Delivers | Sections |
|---|---|---|---|---|
| 1 | #55 | Bring the branch up to date, then write the RFC and ADRs | this RFC, the four ADRs | all |
| 2 | #56 | Caller identity on every call | `Principal`, `CallContext`, the context variable and helpers; one NATS helper filling it; Nexus middleware (`api` on behalf of the user); the transitional OBO header; event, vector_store and cache NATS endpoints through their services | §10 |
| 3 | #57 | IAM kernel service: the policy engine | `services/iam`: store, principals, groups, policies, attachments, placements, scopes, catalogs, seals, evaluator, `check`, `filter`, `explain`, built-in roles, `iam/v1` proto, NATS and SDK; transitional broad policies for `api` and `engine` | §2–§7, §11 |
| 4 | #58 | Enforce IAM in the data services | catalogs and checks for object_storage, document, keyvalue, secret, cache, vector_store, triple_store and dataset; SPARQL dataset restriction; `document_admin` removed; seals enforced | §5, §6.4 |
| 5 | #59 | Enforce IAM in the runtime services | event, activity_log, email, model_registry, discovery, source_control and coding_environment; agent, model, app and job checks; module-name binding; bug (b) in the kernel; platform tools on behalf of the user | §6.4 |
| 6 | #60 | Service accounts, module keys and broker permissions | ES256 issuer and JWKS; keys and exchange; manifests and approval; auth callout; `<sa>` in hosting subjects; `NATS_JWT_SECRET` removed; CLI | §8, §9.1–§9.2 |
| 7 | #61 | OIDC identity providers | `identity.providers`, the verifier, Nexus PKCE client and cookie session, `(issuer, sub)` users, group mapping, the generic identity suite on Zitadel | §12.1 |
| 8 | #62 | Delegated tokens and API keys | token exchange, delegated audiences, `SubmitRequest.delegated_token`, link grants, coding tokens (bug a), personal API keys; the OBO header removed | §9.3–§9.4 |
| 9 | #63 | Built-in IdP module | `libs/naas-abi-idp`, the trusted `/idp` route, defaults | §12.3 |
| 10 | #64 | Provisioning and invitations | the provisioning port, pending grants, People → Invite, group binding UI, the end-to-end demo | §12.2 |
| 11 | #65 | Nexus authorization on IAM | the Nexus catalog, routers on `require` and `filter`, viewers read-only, features at the API, bugs (c) and (d), role data migrated, enumerated `api` and `engine` policies | §6.5, §7, §13 |
| 12 | #66 | IAM admin UI in Nexus | policies, attachments, groups, service accounts and keys, approvals, simulator, audit | §3, §8 |
| 13 | #67 | Move login out of Nexus | user migration to the built-in IdP, login code removed, `secret_key` signs no token | §13 |

## Alternatives considered

- **Roles only, with no policies.** A fixed role matrix answers "viewer on W" but cannot answer the
  required "an IdP group reads one graph and writes another". It also cannot confine a module.
- **Relationship-based authorization (OpenFGA) now.** It is strong for per-object sharing, which #1314
  leaves open. It is heavier to run without Docker, and a new model for every service. The authorizer port
  keeps it possible later (§11.2).
- **Resource-based policies** (a policy stored on a graph or a bucket). They duplicate the evaluation path
  and make "what can X do" expensive to answer. Sharing is expressed as a statement attached to the
  receiving principal.
- **Taking the workspace from `CallContext.workspace_id`.** Any member of one workspace could address
  another workspace's data by naming their own. Placement ties the name to the data.
- **Encoding the workspace in every data id** (graph IRIs, document namespaces). It would migrate all
  existing data and break modules that address shared graphs. Placement needs no data move.
- **Raw ids in names** (no percent-encoding). Ids containing `:` or `/` would make names ambiguous and
  wildcards would cross into the wrong field.
- **Regular expressions in patterns.** Harder to read and audit, and slow. `*` and `?` cover the needs.
- **Keeping HS256 with per-module secrets.** Each verifier would need every secret. A JWKS lets anyone
  verify and only the engine sign.
- **IAM on the Document Service.** That is circular (IAM authorizes it), and it lacks the unique constraints
  and transactions IAM needs.
- **Bundling Keycloak or Zitadel as the built-in IdP.** Neither offers email-code as the only sign-in
  factor, and neither runs in-process for `abi dev up` without Docker.

## Open questions

- **Per-object sharing** of single conversations or files beyond personal resources. That is the OpenFGA
  question of #1314. Placement and identity policies cover workspace-level access. Sharing one object today
  means an explicit statement naming it.
- **Policy conditions** (`conditions`, reserved in §3.1): IP ranges, time windows, MFA claims. Not needed
  by any subtask.
- **Federation (#1047).** Every ABI server trusting the same IdP issuer is enough for login. Cross-server
  service accounts are not designed here.
