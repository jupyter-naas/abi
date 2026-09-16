# Per-workspace ontology enablement

Status: Accepted

Date: 2026-09-16

## Context

Nexus discovers reference ontologies by scanning the TTL files shipped by every
loaded engine module. Until now a workspace could only narrow that catalog
through `WorkspaceSeedConfig.ontologies` in `config.local.yaml`: `None` meant
"show the entire engine catalog", an empty list meant "show nothing", and a
non-empty list acted as an exclusive whitelist. Nothing was stored per
workspace, so changing what a workspace sees required editing YAML and
restarting the API — there was no Settings surface at all.

Marketplace apps had already solved the same problem: an `app_configs` table
holds `(workspace_id, app_id, enabled)`, `resolve_app_enabled` gives DB rows
precedence over the YAML seed, and Settings → Apps renders the full catalog with
a toggle per row.

This is distinct from the `ontology` entry in `feature-access.ts`, which gates
whether the Ontology nav surface is visible at all.

## Decision

Mirror the apps design for ontologies.

Add an `ontology_configs` table and a `services/ontology_configs/` domain (port,
service, Postgres secondary adapter, FastAPI primary adapter at
`/api/ontology-configs/`), wired into `ServiceRegistry` as `ontology_configs`.
`GET /` returns the *unfiltered* catalog with an `enabled` flag per row so
Settings can offer a toggle for disabled files; `PATCH /{ws}/{ontology_id}`
upserts, so the UI toggle never needs a prior POST.

Key `ontology_configs.ontology_id` on `<module>:<filename.ttl>`
(`ontology_catalog_id`) rather than the absolute file path. Paths already flow
through the UI and the `?ontology=` query param, but they differ between a
container (`/app/libs/...`) and a checkout, so a path-keyed row would silently
stop matching after a deploy. The chosen form is also exactly what
`WorkspaceSeedConfig.ontologies` accepts, so a YAML entry and a stored row name
the same file.

Replace the seed-list filter with an enablement scope.
`filter_ontology_catalog` now takes an `OntologyCatalogScope` (stored rows plus
the YAML seed) instead of a list of refs, and `resolve_ontology_enabled` applies
the same precedence as `resolve_app_enabled`: a stored row wins, else the seed
list, else disabled. The ontology adapter's `ontology_catalog_scope` dependency
builds that scope, so every ontology route — listings and the per-path routes
guarded by `_require_catalog_path` — is filtered by one mechanism. A request
carrying no `workspace_id` has no per-workspace state to resolve against and
keeps the full engine catalog.

`_seed_workspace_ontologies` in `org_seed.py` inserts an enabled row per seeded
ref when none exists, mirroring `_seed_workspace_apps`. Because seeding runs
before any TTL is parsed it stores the normalized ref rather than resolving it
against the catalog; `resolve_ontology_enabled` therefore matches stored rows
against every alias form of a file, not just the canonical id.

## Consequences

Ontologies are opt-in. A fresh workspace with no stored rows and no seed list
shows zero ontologies in the sidebar and explorer, and Settings → Ontologies
lists them all as disabled. This is a deliberate behaviour change: previously
`ontologies: None` exposed the whole engine catalog, and any deployment relying
on that default must now name its files in the seed list or enable them from
Settings.

`WorkspaceSeedConfig.ontologies` becomes an *initial* enable set rather than a
permanent whitelist. A stored row always wins, so a file a workspace disables in
Settings stays disabled across restarts, and adding a name to the YAML no longer
removes access to the files it omits.

Disabling an ontology hides it and blocks access: the per-path routes raise
`OntologyPathNotFoundError` (404) for a file the workspace has turned off.

The sidebar no longer falls back to a hardcoded BFO path when nothing is
selected, since that file may itself be disabled; it lands on the consolidated
view instead.

Settings listings and toggle validation rescan the engine catalog, which parses
every module TTL. That cost already existed on the ontology routes and is
acceptable for an infrequently-used settings surface, but it is the obvious
place to add caching if the catalog grows.
