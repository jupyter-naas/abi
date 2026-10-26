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
| `port.py` | `IamGateway`: IAM bound to a user (`bind`), the catalogs, and the engine's own name lookups |
| `service.py` | `IamAdminService`: the use cases, audit (`run_audited`), the `access` view, the empty-list-is-a-refusal rule |
| `narrowing.py` | What narrowing a manifest means: Allow patterns may be removed, never added; Deny stays |
| `views.py` | IAM records as the JSON the pages read; a key's value only in `created_key` |
| `runtime.py` | Builds the service (engine IAM + `SqlAdminAuditLog(prefix="iam.")`); tests `configure` another |
| `adapters/secondary/engine.py` | `EngineIamGateway`: the engine's IAM in process, acting as the user from the verified session |
| `adapters/primary/iam_admin__primary_adapter__FastAPI.py` | `/api/iam/admin/*`; each route `declares` the `iam:*` action it performs |
| `testing.py` | `MemoryAudit` (remembers records; `broken` makes every write fail) |

## Routes

`/api/iam/admin` (session only, like the rest of `/api/iam/`):

- `GET /access?scope=` the actions the caller may do (platform, or attachments at `scope`); `GET /catalogs`
- `GET|POST /policies`, `GET|PUT|DELETE /policies/{id}`, `POST /policies/validate` (`document` or YAML/JSON `text`)
- `GET|POST|DELETE /attachments` (`?scope=`, `?principal_id=`, `?policy_id=`), `GET /attachable-policies?scope=`
- `GET /principals`, `GET /principals/{id}`, `POST /principals/{id}/suspend|resume`
- `GET|POST /groups`, `GET|DELETE /groups/{id}`, `PUT|DELETE /groups/{id}/members/{member}`,
  `PUT|DELETE /groups/{id}/idp-mappings`
- `GET|POST /service-accounts`, `DELETE /service-accounts/{id}`, `GET|POST /service-accounts/{id}/keys`,
  `DELETE …/keys/{key}`, `POST …/keys/{key}/rotate`
- `GET /manifests?status=`, `POST /manifests/{principal}/{sha256}/approve` (optional narrowed `document`) and `/reject`
- `POST /simulate` (`principal_id`, `action`, `resource`); `GET /audit` (`require_superadmin`)

## Rules

- **Act as the user.** `bind(user)` takes the identity from the request's verified context (`AUTHZ.context`), never a
  request field. `api` is not widened for this: it stays out of IAM's administration.
- **Name the action with `declares`.** The route matrix needs it; the check is IAM's, inside the call. A read that
  travels as POST or a caller-only route goes in the matrix's allowlists with its reason.
- **A list that comes back empty for a caller who may list nothing is a 403** (`_listing`), not an empty page.
- **Audit before the change** (`_change`): no record, no change; the record names the actor, the operation, the
  resource and a short detail, never a key's value or a policy's text. A new change operation goes through `_change`.
- **Keys:** the value is in `created_key`'s answer only (`Cache-Control: no-store`); never log or audit it.
- **Narrowing** is checked here (`narrowing.py`), because IAM's `approve_manifest` accepts any valid document.
- Names of principals and policies in a list are read as `api` (`gateway.principal`, `gateway.policy`) for ids the
  caller already sees through a list IAM let them read.

## Decisions

- **The pages are IAM calls made as the signed-in user.** `services/iam_admin` binds the engine's IAM to the
  user's own `CallContext` (their IdP groups included) and calls it in process. IAM's `iam:*` actions decide each
  page and button; Nexus adds no role check and no list of "who is an admin". `GET /access` asks IAM which actions
  the caller holds, so the pages show only what will answer. `api` keeps its enumerated statements: acting as the
  user is what keeps `api` out of IAM's administration.
- **Two places, one API.** Attachments are the one IAM type placed in an org and workspace, so an org admin holds
  `iam:ListAttachments`, `AttachPolicy` and `DetachPolicy` at their scope and nothing else of IAM. Org settings,
  Access, manages attachments at the org and its workspaces (the policies offered are the ones the caller may
  attach there: `GET /attachable-policies`). Everything else (policies, groups, service accounts and keys,
  approvals, simulator, audit) is platform-level and lives in the System app's Access tab, available to whoever
  holds the matching actions. Both use the same routes; the scope is a parameter. The tab is reached through the
  System app, which still requires `nexus:ReadSystem`: a delegated IAM admin without it has the API and the CLI
  but not the tab.
- **Every change is audited, fail-closed.** The System app's `run_audited` and `audit_logs` table are reused: a
  `requested` record is written first and nothing changes if it cannot be (503); `succeeded` or `failed` (the
  exception type only) follows. IAM's records are the rows `iam.<operation>` (`SqlAdminAuditLog` takes the action
  prefix), with the actor, the operation, the resource and a short detail (a name, a scope), never a key's value
  or a policy's text. A refused attempt is a record too. Membership changes made from the Users page
  (`MEMBERSHIPS`) and invitations are audited by their own routes, not by this log.
- **Policies are edited visually or as text, and IAM validates both.** The editor autocompletes actions from the
  registered catalogs and resources from the name grammar; the text view takes YAML or JSON. `POST
  /policies/validate` returns every error IAM lists (and the normalized document), so the editor shows them as the
  user types and a save refused for them says the same.
- **Keys are shown once.** Creating or rotating a service account's key returns its value in that one answer
  (`Cache-Control: no-store`); IAM keeps a hash, the audit and every list never carry it, and the page holds it in
  component state until dismissed.
- **A manifest is approved as submitted, narrowed or rejected, never widened.** IAM's `approve_manifest` accepts
  any valid document, so the API checks the narrowing itself (`narrowing.py`): an Allow statement may lose actions
  and resources, none may gain or appear, and Deny statements stay exactly as submitted (dropping one widens).
- **The simulator is `explain`.** "Can X do Y on Z" is IAM's `explain` on the principal (`iam:Explain`): the answer
  names the deciding side, policy, statement, attachment, scope and group, and shows the statement when the
  caller may read its policy.
- **The routes take a session only** (the `/api/iam/` prefix): an API key cannot administer permissions.
- A user holding a custom role with only `iam:ListPolicies` gets exactly that page; a stranger gets 403 on all of
  them. Group and service-account deletion keep the id (IAM's rule); the lists hide deleted ones.

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/iam_admin --import-mode=importlib --no-cov -q
```

The route tests run a real IAM on the memory store (`team` fixture: `owner`, `admin`, `member`, `viewer`,
`stranger`; plus `root`, a platform admin, and `lister`, who holds only `iam:ListPolicies`).
