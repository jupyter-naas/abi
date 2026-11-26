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
| `service.py` | `FeatureAccessService.read / save / read_offer / save_offer / save_search_sources / set_files / set_ontologies / save_ontologies / set_graphs / managed_among`; the pure checks `offered`, `holds`, `names_feature`, `check_changes`, `check_offer_changes`; the offer's rows `file_rows`, `ontology_rows` |
| `adapters/secondary/postgres.py` | `SqlFeaturePolicyStore`, table `workspace_feature_policies` (migration `0074_workspace_feature_policies.sql`): read only now |
| `adapters/primary/feature_access__primary_adapter__FastAPI.py` | `GET` / `PUT /api/workspaces/{workspace_id}/feature-access`, `GET` / `PUT /api/workspaces/{workspace_id}/offer`, `PUT .../offer/search-sources`, `PUT .../offer/files`, `PUT .../offer/ontologies` |
| `runtime.py` | The service on the engine's IAM (`iam_admin`'s `EngineIamGateway`), `AUTHZ.container_of`, `CONTAINER_DEFAULTS.record_of`, the audit log, the ontology catalog (`workspaces/.../resource_access.offer_ontology_catalog`, Settings › Ontologies' own); `configure` for tests |

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
- **Ontologies** (`OfferOntologies`, by ref): `read_offer` answers `ontologies` (`offered`: the refs as
  written; `rows`: every file of the deployment, by label, `offered` when a ref names it, `assignable` when
  the caller may assign it there, `AssignOntology` in the workspace's organization, `editable`, `reason`; a ref
  no file answers to is a row with `available` false; `error` when the files could not be listed), or null
  where the deployment has no ontology. `save_ontologies` (`PUT .../offer/ontologies`, `{changes: {id:
  offered}}`) adds a file only for whoever may assign it (`PermissionDeniedError`, 403), refuses an id of no
  file (422), takes a file back by every ref naming it, then writes through `set_ontologies`, as Settings ›
  Ontologies does: an organization's admins add, a workspace admin removes.

## Tests

`service_test.py` (real IAM, SQLite, the real organization and workspace creation): Everyone and
Nobody as the offer, Only… refused, a caller who does not hold the feature (and IAM refusing her the
widening itself), the organization's bound, a Deny elsewhere winning and listed, a statement written on
the policy's page, a newcomer, the mark of older policies, agents offered and withdrawn, the ontologies
(`TestOntologies`: read with what the caller may assign, added by an organization's admin, removed by a
workspace admin, refused outside the catalog). The routes: `adapters/primary/*_test.py`; the store and
its migration: `adapters/secondary/postgres_test.py`; the routes' declarations:
`services/iam/route_matrix_test.py` (`FEATURE_ACCESS_ROUTES`).
