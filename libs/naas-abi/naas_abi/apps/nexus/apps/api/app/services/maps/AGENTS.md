# Maps graph layers

Modules register `GraphMapLayer` descriptors in their FastAPI hook with `register_map_layer`. ABI contains the reusable catalog and viewer; company-specific evidence and projection queries stay in their module.

`service.py` defines the read-only `GraphQueryPort`, descriptor and catalog. The primary adapter exposes `GET /api/maps/layers` and `GET /api/maps/layers/{id}`. Both require workspace membership, resolve existing graph grants and disable caching. Projections receive `WorkspaceGraphStore`, never the unrestricted catalog store. The declared graph must be readable before the feed runs. Snapshot selection belongs to the module; never union historical snapshots automatically.

Each pin can carry `entityUri`, `graphUri`, `country`, `precision`, `observedAt`, `sources`, `relationships`, `address`, `photoUrl`, `streetViewUrl` and `imageSearchUrl` for the inspector. The inspector embeds a cited photo or a same-origin `/api/maps/streetview` preview from lat/lng. Treat pin labels and sources as untrusted content. Only HTTP(S) evidence links are navigable; KG links are constructed within the current workspace.

Optional `coverage: {pins: [...]}` provides city summaries from the same scoped projection. Each city pin has its own graph identity, coordinates and evidence, with `memberIds` linking address pins. The browser renders geographic country fills, never materializes countrywide operations as RDF facts, and validates member IDs against the returned address pins.

# Maps catalog (layers, basemaps, access)

ADRs: `docs/adr/20261012_nexus-maps-catalog-and-access.md`, `docs/adr/20261013_nexus-maps-groups.md`.

- `layouts/` — **feeds** (data sources): `group` (sidebar group label: feeds sharing it form one group; no group records) and `feed_type` `sparql` (query on the workspace graphs) or `geojson_url` (a `/api/...` path the web proxy `/api/maps/custom/{feed}` calls with the member's token). `/api/maps/feeds` (= `/api/maps/layouts`: CRUD, `/visibility`, `/color`, `GET /{id}`). Deleting a feed goes through `feed_layers` (cascade).
- `feed_layers/` — **layers**: views on one feed (title, color, icon, order, `class_labels` = feature types kept, empty = all). `/api/maps/feed-layers`. A feed always keeps one layer; new feeds get a default layer with the feed id. Hidden flags share `hidden_layouts`.
- `basemaps/` — basemap records with a renderer config (`tile`, `countries` + palette, `geojson`) and preview bytes. `/api/maps/basemaps` (CRUD, `/visibility`, `GET|PUT /{id}/preview`). Core seeds and their previews: `basemaps/builtin.py`, `basemaps/assets/`.
- `settings/` — per-workspace JSON in `maps_settings`: hidden layers/basemaps, colors of record-less layers, applied seeds. Always read-modify-write the whole document through the port.
- `seeds.py` — `register_maps_seeds(app, layouts=..., feed_layers=..., basemaps=...)` from a module's API hook. Seeds are copied once per workspace and become `system` (edit/hide, never delete). Bump `revision=` to migrate seeded copies in every workspace (`settings.seed_revisions`). `hidden_layouts=[...]` hides any layer id by default, once per revision (admins can show it again).
- `permissions/` — `maps_grants`: deployment items everywhere unless narrowed; custom items at home unless shared (read-only, `shared_from`). Deployment items and "all workspaces" need a superadmin. Services enforce it on list/get/preview; `/api/maps/permissions` manages it.
- `catalog/` — `GET /api/maps/catalog`, the single read the web store loads.

Run `pytest` on this directory (service and colocated API tests). Frontend contract tests live beside `maps/lib/maps-feed.ts`, `maps-basemaps.ts`, `maps-country-cluster.ts` and `permissions-api.ts`.
