# Feature access (Workspace settings > General › Features) - AGENTS.md

## Purpose

What a workspace offers, set from General › Features (**Everyone** or **Nobody**) and from the
offer routes (agents, apps, workflows, pipelines). It decides nothing itself: each choice is a
section of the workspace's access policy, "<W> access" (`services/iam/workspace_offer.py`),
written as the caller, and IAM decides every call.

## Files

| File | Role |
|---|---|
| `port.py` | `FeatureChange`, `CHOICES`, `FeaturePolicyStore` (the "Feature · X" policies an older version wrote, for the marks on Access › Policies) |
| `service.py` | `FeatureAccessService.read / save / read_offer / save_offer / managed_among`; the pure checks `offered`, `holds`, `names_feature`, `check_changes`, `check_offer_changes` |
| `adapters/secondary/postgres.py` | `SqlFeaturePolicyStore`, table `workspace_feature_policies` (migration `0074_workspace_feature_policies.sql`): read only now |
| `adapters/primary/feature_access__primary_adapter__FastAPI.py` | `GET` / `PUT /api/workspaces/{workspace_id}/feature-access`, `GET` / `PUT /api/workspaces/{workspace_id}/offer` |
| `runtime.py` | The service on the engine's IAM (`iam_admin`'s `EngineIamGateway`), `AUTHZ.container_of`, `CONTAINER_DEFAULTS.record_of`, the audit log; `configure` for tests |

## Rules

- **One policy, the workspace's access.** Everyone is the feature in the `OfferFeatures` section of
  "<W> access", Nobody out of it. No "Feature · X" policy is made; those an older version made are
  listed with the other policies naming the feature until the access migration retires them.
- **Only… is refused** (named in `errors`): a feature is offered to the workspace or not; a group
  holding a policy for it gives it to some people.
- **Every write is IAM's, as the caller, audited first** (`run_audited`, operations
  `feature-access.everyone|nobody`, `workspace-offer.update`): one `UpdatePolicy` of "<W> access", read
  again first (its revision checked). Grant only what you hold; a row changes only for a caller who
  holds the feature there and whom IAM lets update the policy. No role is checked.
- **The bound is the organization's offer** ("<O> access", the parent): a feature it does not offer is
  refused ("not offered in this workspace's organization"); an item beyond it is refused by IAM (422).
- **Written on the policy's page** (an Allow outside the sections, a ceiling of an older version): the
  row is read-only and says so.
- **Coexistence**: other policies naming the feature at the workspace are listed with it, Allow or
  Deny. A Deny wins as anywhere.

## Tests

`service_test.py` (real IAM, SQLite, the real organization and workspace creation): Everyone and
Nobody as the offer, Only… refused, a caller who does not hold the feature (and IAM refusing her the
widening itself), the organization's bound, a Deny elsewhere winning and listed, a statement written on
the policy's page, a newcomer, the mark of older policies, agents offered and withdrawn. The routes: `adapters/primary/*_test.py`; the store and
its migration: `adapters/secondary/postgres_test.py`; the routes' declarations:
`services/iam/route_matrix_test.py` (`FEATURE_ACCESS_ROUTES`).
