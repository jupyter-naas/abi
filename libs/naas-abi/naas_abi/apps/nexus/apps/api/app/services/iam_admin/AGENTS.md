# IAM admin pages - AGENTS.md

## Purpose

The Nexus side of the IAM admin UI: policies, attachments, groups, service accounts and keys, module permission
approvals, the access simulator and the audit of every change.
Every call is IAM's, made **as the signed-in user**: IAM's `iam:*` actions decide what each page may read and change
([`libs/naas-abi-core/.../services/iam/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/iam/AGENTS.md)).
Nexus adds no role check of its own.

## Files

| File | Role |
|---|---|
| `port.py` | `IamGateway`: IAM bound to a user (`bind`), the catalogs, and the engine's own name lookups; `ScopeDirectory`: the organizations and workspaces the sets page names |
| `service.py` | `IamAdminService`: the use cases, audit (`run_audited`), the `access` view, the empty-list-is-a-refusal rule |
| `narrowing.py` | What narrowing a manifest means: Allow patterns may be removed, never added; Deny stays |
| `views.py` | IAM records as the JSON the pages read; a key's value only in `created_key` |
| `runtime.py` | Builds the service (engine IAM + `SqlAdminAuditLog(prefix="iam.")`); tests `configure` another |
| `adapters/secondary/engine.py` | `EngineIamGateway`: the engine's IAM in process, acting as the user from the verified session |
| `adapters/secondary/sql_directory.py` | `SqlScopeDirectory`: organizations and their workspaces, by name, from Nexus's database |
| `adapters/primary/iam_admin__primary_adapter__FastAPI.py` | `/api/iam/admin/*`; each route `declares` the `iam:*` action it performs |
| `testing.py` | `MemoryAudit` (remembers records; `broken` makes every write fail), `MemoryDirectory` |

## Routes

`/api/iam/admin` (session only, like the rest of `/api/iam/`):

- `GET /access?scope=` the actions the caller may do (platform, or attachments and that level's policies and groups
  at `scope`; at a scope, what the platform alone administers is false; no role feature defaults exist to
  report: no role brings a feature, a policy does);
  `GET /catalogs?scope=`
- `GET /grantable?scope=` what the caller may grant at `scope` (IAM's `grantable`: per catalog, the actions and
  `${scope}:…` resource patterns they hold there, minus their Denies), for the policy builder; any caller, about
  themselves, like `/access`
- `GET|POST /policies` (`?scope=`; the body's `scope` is the owner, its `parent` the policy it is a sub-policy
  of), `GET|PUT|DELETE /policies/{id}`, `POST /policies/validate?scope=` (`document` or YAML/JSON `text`).
  A policy carries `parent_id`; `GET /policies/{id}` adds `parent` (`{id, name, owner_scope, managed}`, the
  name read as `api` for the id the caller sees, null fields when it cannot be) and `sub_policies` (those below
  it the caller may list, IAM's `list_sub_policies`). `PUT` takes `parent`: absent keeps it, `null` or `""`
  removes it, an id sets it. Deleting a parent that has sub-policies is a 409 naming them
- `GET|POST|DELETE /attachments` (`?scope=`, `?principal_id=`, `?policy_id=`), `GET /attachable-policies?scope=`
- `GET /principals`, `GET /principals/{id}`, `POST /principals/{id}/suspend|resume`
- `GET|POST /groups` (`?scope=`; the body's `scope`, or `org` alone, is the owner), `GET|DELETE /groups/{id}`, `PUT|DELETE /groups/{id}/members/{member}`,
  `PUT|DELETE /groups/{id}/idp-mappings`
- `GET|POST /service-accounts`, `DELETE /service-accounts/{id}`, `GET|POST /service-accounts/{id}/keys`,
  `DELETE …/keys/{key}`, `POST …/keys/{key}/rotate`
- `GET /manifests?status=`, `POST /manifests/{principal}/{sha256}/approve` (optional narrowed `document`) and `/reject`
- `POST /simulate` (`principal_id`, `action`, `resource`); `GET /audit` (`require_superadmin`)
- `GET /sets?organization_id=` the modules × workspaces page: every module's scopes (`modules/scopes.gather`), the
  deployment's features, and each organization (all, or the one named) with its workspaces whose set the caller
  may read (`iam:GetSet`), each `{id, name, set, effective, editable}` (`set` and `effective`:
  `{modules, features}`, a part `null` for everything; `editable`: `iam:PutSet`); 403 when there is none. An org
  whose own set the caller may not read but some workspace's they may is listed with `set: null`.
  `PUT /sets/{org}` and `PUT /sets/{org}/workspaces/{ws}` (`{modules, features}`) record a set: 403 when not the
  caller's, 422 with IAM's message naming what a workspace's set has beyond its org's, 404 for an unknown
  organization or workspace

## Rules

- **Act as the user.** `bind(user)` takes the identity from the request's verified context (`AUTHZ.context`), never a
  request field. `api` is not widened for this: it stays out of IAM's administration.
- **Name the action with `declares`.** The route matrix needs it; the check is IAM's, inside the call. A read that
  travels as POST or a caller-only route goes in the matrix's allowlists with its reason.
- **A list that comes back empty for a caller who may list nothing is a 403** (`_listing`), not an empty page.
- **Audit before the change** (`_change`): no record, no change; the record names the actor, the operation, the
  resource and a short detail, never a key's value or a policy's text. A new change operation goes through `_change`.
- **Keys:** the value is in `created_key`'s answer only (`Cache-Control: no-store`); never log or audit it.
- **Narrowing** is checked here (`narrowing.py`): IAM's `approve_manifest` checks that the approver holds what the
  approved document grants, not that it is no wider than what the module submitted.
- **A grant beyond what the caller holds** (IAM's `GrantNotHeldError`, "Grant only what you hold" in core's
  `services/iam/AGENTS.md`) is a 403 whose detail is IAM's message: the statement, action and resource the caller
  does not hold. Creating or editing a policy, attaching one, adding a group member and approving a manifest all
  answer it.
- Names of principals and policies in a list are read as `api` (`gateway.principal`, `gateway.policy`) for ids the
  caller already sees through a list IAM let them read.

## Decisions

- **The pages are IAM calls made as the signed-in user.** `services/iam_admin` binds the engine's IAM to the
  user's own `CallContext` (their IdP groups included) and calls it in process. IAM's `iam:*` actions decide each
  page and button; Nexus adds no role check and no list of "who is an admin". `GET /access` asks IAM which actions
  the caller holds, so the pages show only what will answer. `api` keeps its enumerated statements: acting as the
  user is what keeps `api` out of IAM's administration.
- **One UI, one API, the scope a parameter.** Decision: attachments, policies and groups are the IAM types
  placed in an org and workspace (attachments at their scope, policies and groups at the scope that owns them:
  core `services/iam/AGENTS.md`, "Owner scopes"), and every route takes the scope as a parameter: `POST
  /policies` and `POST /groups` create at the body's `scope`, `GET /policies?scope=` and `GET /groups?scope=`
  list that level's own plus what the caller may attach there from above (IAM's `list_policies` /
  `list_groups`), `GET /attachable-policies?scope=` the policies the caller may attach there (leaving out a
  policy owned by another org or workspace and, at a scope, a platform policy with a Deny outside `${scope}:`
  for anyone but the platform admin, as IAM refuses it), and `GET /access?scope=`, `/catalogs?scope=`,
  `/grantable?scope=` and `/policies/validate?scope=` answer for that level (an org-wide scope, in these and in
  the lists, answers for its org). One web module serves every level (Nexus `AGENTS.md`, "Roles & permissions
  UI module"): Platform settings, Organization settings and Workspace settings › Roles & permissions mount it
  with their scope, and `GET /access?scope=` alone decides its sections and buttons. Consequences: an org or
  workspace admin holds, at their scope, the attachment actions and that level's policies and groups, and
  nothing else of IAM; members and viewers hold none of it. Service accounts and keys, module approvals, the
  simulator, IdP mappings and the audit are the platform's: `access` answers their actions (`_PLATFORM_ONLY`,
  `nexus:ReadSystem`) false at any scope, the platform admin's included, so only the platform's page shows them.
  The Platform Settings sidebar shows Roles & permissions for any
  platform-level `iam:` action `GET /access` grants, and the tables and System only with `nexus:ReadSystem`:
  a delegated IAM admin without it sees Roles & permissions alone, a stranger a 403; Organization and Workspace
  settings show it for any `iam:` action at their scope.
- **Every change is audited, fail-closed.** The System app's `run_audited` and `audit_logs` table are reused: a
  `requested` record is written first and nothing changes if it cannot be (503); `succeeded` or `failed` (the
  exception type only) follows. IAM's records are the rows `iam.<operation>` (`SqlAdminAuditLog` takes the action
  prefix), with the actor, the operation, the resource and a short detail (a name, a scope), never a key's value
  or a policy's text. A refused attempt is a record too. Membership changes made from the Users page
  (`MEMBERSHIPS`) and invitations are audited by their own routes, not by this log.
- **Policies are edited visually or as text, and IAM validates both.** The editor autocompletes actions from the
  registered catalogs and resources from the name grammar; the text view takes YAML or JSON. `POST
  /policies/validate` returns every error IAM lists (and the normalized document), so the editor shows them as the
  user types and a save refused for them says the same. With `?scope=` at an org or a workspace it also applies the
  rule of a policy that level owns (core's `check_owned_document`: every pattern under `${scope}:`), so a document
  it calls valid there is one `POST /policies` with that `scope` takes.
- **Keys are shown once.** Creating or rotating a service account's key returns its value in that one answer
  (`Cache-Control: no-store`); IAM keeps a hash, the audit and every list never carry it, and the page holds it in
  component state until dismissed.
- **A manifest is approved as submitted, narrowed or rejected, never widened.** IAM's `approve_manifest` takes any
  valid document the approver holds, so the API checks the narrowing itself (`narrowing.py`): an Allow statement may
  lose actions and resources, none may gain or appear, and Deny statements stay exactly as submitted (dropping one
  widens). A delegated approver approves no more than they hold: narrow what they do not.
- **The policy builder offers what the caller may grant.** `GET /grantable?scope=` is IAM's `grantable`, so the
  builder and IAM's refusal agree: what it lists is what the caller holds at that scope (it may list less, never
  more). It needs no permission: it says only what the caller holds.
- **The modules × workspaces page edits the sets as the user.** Decision: `GET/PUT /sets` call IAM's
  `get_set`, `effective_set` and `put_set` bound to the user, every change through `_change` (`iam.put_set`,
  resource `<org>` or `<org>/<ws>`, the parts' sizes as detail), and `editable` is IAM's `iam:PutSet` decision.
  Consequences: the platform admin edits organizations' sets, an org's owners and admins its workspaces' (their
  org-wide role), a workspace admin reads their workspace's; nobody else sees the page. Names come from Nexus's
  database (`ScopeDirectory`), which of them the caller sees from IAM. The rows take three IAM calls whatever
  the number of columns (`filter` for `GetSet`, `filter` for `PutSet`, one `list_sets`) and are intersected
  here (`sets.intersect`); only a workspace whose org's set the caller may not read asks IAM its effective set.
- **The simulator is `explain`.** "Can X do Y on Z" is IAM's `explain` on the principal (`iam:Explain`): the answer
  names the deciding side, policy, statement, attachment, scope and group, and shows the statement when the
  caller may read its policy; for a sub-policy, `bounded_by` (each parent's statement that allowed it too) and
  `through` (the sub-policies a parent's Deny was reached by).
- **Sub-policies are IAM's, passed through.** Decision: `POST` and `PUT /policies` hand `parent` to IAM's
  `create_policy` / `update_policy` as the user, through `_change` (the audit detail says `sub-policy of <id>`,
  `parent <id>` or `no parent`); every rule (one parent, a cycle, a chain deeper than 8, a missing parent, an owner
  outside the parent's, derive only from what you hold, grant only what you hold within the chain, no deleting a
  parent) is IAM's, so its refusals come back as they do over NATS and through the SDK: 403 (`PERMISSION_DENIED`,
  `GRANT_NOT_HELD`), 404, 409, 422 with IAM's message. Consequences: the editor shows a policy's parent and keeps it
  on save (it leaves `parent` out of the `PUT`); choosing a parent and the tree of policies are the builder's
  (a later change).
- **The routes take a session only** (the `/api/iam/` prefix): an API key cannot administer permissions.
- A user holding a custom role with only `iam:ListPolicies` gets exactly that page; a stranger gets 403 on all of
  them. Group and service-account deletion keep the id (IAM's rule); the lists hide deleted ones.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam_admin --import-mode=importlib --no-cov -q
```

The route tests run a real IAM on the memory store (`team` fixture: `owner`, `admin`, `member`, `viewer`,
`stranger`; plus `root`, a platform admin, and `lister`, who holds only `iam:ListPolicies` on
`abi:*:*:iam:policy/*`, every policy wherever it is owned). The `ws2` fixture adds `ws-2` of `org-1` with
`ws2admin` and `colleague`, and `outsider` in another org: a workspace admin's and an org admin's policies
and groups.
