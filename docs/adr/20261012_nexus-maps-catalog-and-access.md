# Nexus Maps catalog: server-side layers, basemaps and cross-workspace access

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Maps layers came from five places: built-in feeds in web code, deployment layers in
`NEXT_PUBLIC_MAPS_CUSTOM_DATASETS`, workspace SPARQL layouts in Postgres, module
graph layers in memory, and GeoJSON imports in localStorage. Basemaps were
hard-coded in `maps-basemaps.ts` (including deployment-specific styles), their
previews were static files or a one-off deployment route, and
hiding a basemap was localStorage-only. Settings → Maps could not add, update,
delete or hide most of them, and other browsers or members did not see the same
state. Deployments also need to choose *which workspaces* get a layer or
basemap (e.g. one organization's facilities everywhere, another's only on two
workspaces).

## Decision

1. **Feeds and layers.** A *feed* is a data source: a `maps_layouts` record
   (`services/maps/layouts`, also served at `/api/maps/feeds`) with
   `feed_type` `sparql` (unchanged) or `geojson_url`, a Nexus API path the web
   proxy `/api/maps/custom/{feed}` reads from the record and calls with the
   member's token (same-host paths only). Feeds carry the logo, sidebar group,
   default basemap and access. A *layer* (`maps_feed_layers`,
   `services/maps/feed_layers`, `/api/maps/feed-layers`) is a view on one feed:
   title, color, icon, order and `class_labels` — the feature types (pin
   `classLabel`) it keeps, or every feature when empty. A feed always has at
   least one layer: a new feed gets a default "every feature" layer with the
   feed's id (old `?layer=<feed>` links keep working), deleting a feed deletes
   its layers, and its last layer cannot be deleted. Layers are what the
   sidebar lists (a feed with several layers is one expandable row), what
   `?layer=` selects and what is hidden; access follows the feed. The map loads
   each feed once and slices it per layer.
2. **Basemaps** are a new hexagon (`services/maps/basemaps`, table
   `maps_basemaps`): name, picker column, order, renderer config (`tile`,
   `countries` with optional palette, `geojson`) and preview bytes served by an
   authenticated GET with `nosniff` and a sandbox CSP. The web client draws a
   renderer; it holds no basemap ids, labels or previews.
3. **Seeds**: Nexus seeds its generic basemaps; modules call
   `register_maps_seeds(app, layouts=..., feed_layers=..., basemaps=...)` in
   their API hook (e.g. facility feeds, per-technology layers, a group
   basemap). A feed without seeded layers gets its default layer.
   Seeds carry a **revision** (`register_maps_seeds(..., revision=N)`); each
   workspace records the revision applied per seed (`maps_settings.seed_revisions`),
   and a higher revision re-applies the seed to the system copy — the way a
   deployment migrates its seeded feeds and layers (admin edits to those copies
   are overwritten on that bump, never otherwise). Once a feed has seeded layers,
   its automatic "every feature" default is dropped. Features may carry several
   types (`classLabels`, e.g. activity poles); a layer keeps a feature when
   any of its types is listed. A seed is copied into a workspace the
   first time its catalog is listed (`maps_settings.seeded_*` prevents
   re-creation). Seeded items are `system`: editable and hideable, never deleted.
4. **Per-workspace settings** (`maps_settings` JSON, `services/maps/settings`):
   hidden layers, hidden basemaps, colors of layers without a record. Hiding is a
   workspace choice and never deletes anything.
5. **Access** (`services/maps/permissions`, table `maps_grants`), keyed by item:
   deployment items are available to all workspaces unless narrowed to a list;
   custom items belong to their workspace and can be shared (read-only) with a
   list or with all. Deployment items and "all workspaces" need a platform
   superadmin; a workspace admin only adds/removes workspaces they administer.
   Enforcement is in the services (list, get, feed record, preview), not the UI.
   The existing `workspace_resource_policies` table was not reused: it is keyed
   by workspace and constrained to ontologies/graphs, while Maps access is set
   per item.
6. `GET /api/maps/catalog` returns everything the sidebar and Settings need in
   one read; writes stay on `/api/maps/layouts`, `/api/maps/basemaps` and
   `/api/maps/permissions`.

## Consequences

- Deployments stop configuring Maps through `NEXT_PUBLIC_*` JSON; changing a
  seed in code does not overwrite a workspace's edited copy.
- Restricting a deployment item hides it where it was already seeded and keeps
  its id reserved there; re-opening it brings the same record back.
- Built-in feeds and module graph layers still live in code / module hooks;
  they are hideable and recolorable but have no access policy (graph grants
  already scope graph layers).
- Browser-only GeoJSON layer imports remain a local convenience and are not
  part of the shared catalog; browser-only basemap imports were removed.
- Stale workspace ids in `maps_grants.workspace_ids` (deleted workspaces) are
  harmless and dropped on the next edit by a superadmin.
