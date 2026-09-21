# Maps graph layers

Modules register `GraphMapLayer` descriptors in their FastAPI hook with `register_map_layer`. ABI contains the reusable catalog and viewer; company-specific evidence and projection queries stay in their module.

`service.py` defines the read-only `GraphQueryPort`, descriptor and catalog. The primary adapter exposes `GET /api/maps/layers` and `GET /api/maps/layers/{id}`. Both require workspace membership, resolve existing graph grants and disable caching. Projections receive `WorkspaceGraphStore`, never the unrestricted catalog store. The declared graph must be readable before the feed runs. Snapshot selection belongs to the module; never union historical snapshots automatically.

Each pin can carry `entityUri`, `graphUri`, `country`, `precision`, `observedAt`, `sources`, `relationships`, `address`, `photoUrl`, `streetViewUrl` and `imageSearchUrl` for the inspector. The inspector embeds a cited photo or a same-origin `/api/maps/streetview` preview from lat/lng. Treat pin labels and sources as untrusted content. Only HTTP(S) evidence links are navigable; KG links are constructed within the current workspace.

Optional `coverage: {pins: [...]}` provides city summaries from the same scoped projection. Each city pin has its own graph identity, coordinates and evidence, with `memberIds` linking address pins. The browser renders geographic country fills, never materializes countrywide operations as RDF facts, and validates member IDs against the returned address pins.

Run `pytest service_test.py` and colocated API tests. Frontend contract tests live beside `maps/lib/maps-feed.ts`.
