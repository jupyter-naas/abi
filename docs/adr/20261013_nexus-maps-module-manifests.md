# Nexus Maps: module manifests, data in object storage

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

Deployment feeds were declared in module Python code
(`register_maps_seeds(...)` from an API hook), and their GeoJSON lived in the
module's git tree, served by a module router (`feed_type=geojson_url`). Data
updates needed a commit, most files were never committed (servers could not
serve them), and each module re-implemented serving and its access checks.

Apps already solve the declaration half: each loaded module ships
`apps/<name>/manifest.json`, discovered at startup.

## Decision

1. **Manifests.** A module declares Maps the same way:
   `<module_root>/artifacts/maps/layers/**/manifest.json` for a feed and its
   layers (free-form folders, e.g. `layers/facilities/<org>/`; a feed is its
   `slug`, not its folder; a manifest elsewhere is reported, not read), `artifacts/maps/basemaps/<id>/manifest.json` (+ preview file) for a
   basemap. Manifests hold metadata only (`extra="forbid"`).
2. **Preseed.** At API startup every manifest becomes a deployment seed
   (`register_maps_seeds`, `revision = version`): copied once per workspace,
   then Settings → Maps edits live in the database and win. Raising `version`
   (feeds and basemaps) re-applies the manifest to every workspace's seeded
   copy; a custom record that took the same id is never touched. A broken manifest
   or a duplicate slug is logged and skipped, never fatal.
3. **Data in object storage.** New feed type `object_storage`: each layer
   names a GeoJSON object (`storage_path`), the feed its logo (`logo_path`),
   as keys relative to the environment's object storage prefix. Nexus serves
   them (`GET /api/maps/feed-layers/{id}/data`, `GET /api/maps/layouts/{id}/logo`)
   after its own checks (workspace member, layer and feed visible). Keys come
   from records, never from requests. Layers may share an object and filter it
   by `class_labels`.
4. **Publishing** data is a deployment step, not a commit: a module's command
   uploads the referenced objects to the object storage `config.<ENV>.yaml`
   configures (bob: `make maps-publish ENV=…`).
5. **Regions belong to the basemap.** A vector basemap (`countries`,
   `geojson`) may declare `renderer.regions`: each region's id, name, color,
   label anchor (`label_x`/`label_y`, share of the map), map view and member
   `countries`. The map labels and counts pins per region whenever that
   basemap is drawn, whichever layers are on; feed data carries no region
   overlay.
6. Loading the same objects into the knowledge graph is a later, opt-in step.

## Consequences

- The same manifest works in every environment; only the published objects
  differ.
- A layer whose object is not published shows an error state (503); the rest
  of the map loads.
- Seeded data sources (feed type, `logo_path`, `storage_path`) belong to the
  manifest: Settings edits metadata only.
- Modules no longer need routers or seeding code for map data. `geojson_url`
  remains for API feeds admins create in Settings → Maps (the target endpoint
  authenticates the member).
