# Feature access (Workspace settings > General › Features) - AGENTS.md

## Purpose

Who may use each feature of a workspace, set from General: **Everyone**, **Only…** (members
and groups chosen) or **Nobody**. It decides nothing itself: each choice is written as IAM
policies, made as the caller, and IAM decides every call (`services/iam/AGENTS.md`, "Features:
zero trust").

## Files

| File | Role |
|---|---|
| `port.py` | `FeatureChange`, `CHOICES`, `FeaturePolicyStore` (which policy was written for each feature of a workspace) |
| `service.py` | `FeatureAccessService.read / save / managed_among`; the pure checks `offered`, `holds`, `as_written`, `names_feature`, `check_changes` |
| `adapters/secondary/postgres.py` | `SqlFeaturePolicyStore`, table `workspace_feature_policies` (migration `0074_workspace_feature_policies.sql`) |
| `adapters/primary/feature_access__primary_adapter__FastAPI.py` | `GET` / `PUT /api/workspaces/{workspace_id}/feature-access` |
| `runtime.py` | The service on the engine's IAM (`iam_admin`'s `EngineIamGateway`), `AUTHZ.container_of`, `CONTAINER_DEFAULTS.record_of`, the audit log; `configure` for tests |

## Rules

- **One policy per feature**: "Feature · <name>", owned by the workspace, a sub-policy of
  "<W> access", one Allow of `nexus:UseFeature` on `${scope}/nexus:feature/<key>`. Made on the
  first save that is not Nobody, recorded in `workspace_feature_policies`, never found by name.
- **The choice is where it is attached**, at the workspace: "<W> members" (Everyone: a newcomer
  joins the group, so holds it), the chosen users and groups (Only…), nothing (Nobody). A save
  attaches what is missing and detaches the rest; the policy stays.
- **Every write is IAM's, as the caller, audited first** (`run_audited`, the IAM admin pages' log,
  operations `feature-access.create|everyone|only|nobody`): grant only what you hold, derive only
  from a policy you hold, within the chain, all apply. On top of them a row changes only for a
  caller who holds the feature there (IAM's `grantable` at the workspace, what `/publishers`
  answers) and whom IAM lets create, attach and detach policies there. No role is checked.
- **The ceiling is "<W> access"**: a feature its chain does not allow (`offered`) is "not offered
  in this workspace" and only Nobody is saved for it. The chain is read as Nexus (`gateway.policy`).
- **Coexistence**: other policies naming the feature at the workspace (as the caller lists them,
  managed ones aside) are listed with it, Allow or Deny, attached or not. A Deny wins as anywhere.
- **Changed by hand** (`as_written` false: another document, owner or parent), the row is read-only
  and links to its policy; General never rewrites it.
- A save is a batch: a malformed one (unknown feature, a feature twice, Only… with nobody) is
  refused whole (422); otherwise each feature is applied alone and a refused one is named in
  `errors`, the others saved.

## Tests

`service_test.py` (real IAM, SQLite, the real organization and workspace creation): the three
choices, a caller who does not hold the feature (and IAM refusing her the attachment itself), the
ceiling, a Deny elsewhere winning and listed, a policy changed by hand, a newcomer joining the
members, the mark on Access › Policies. The routes: `adapters/primary/*_test.py`; the store and
its migration: `adapters/secondary/postgres_test.py`; the routes' declarations:
`services/iam/route_matrix_test.py` (`FEATURE_ACCESS_ROUTES`).
