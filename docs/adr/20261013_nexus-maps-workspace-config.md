# Nexus Maps: initial workspace setup in config.*.yaml

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

Which Maps feeds a workspace starts with was spread over code and data that
ignore the environment (`ENV` → `config.{ENV}.yaml`):

- module seeds switched feeds off for every workspace
  (`register_maps_seeds(hidden_feeds=...)`);
- a module policy file keyed by workspace slug chose the feeds on when the map
  opens, read through a module endpoint (`workspace-defaults`), with a
  build-time fallback (`NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS`);
- "enabled" (Settings → Maps) and "on by default" were two different lists.

The workspaces themselves already live in `config.*.yaml` per environment
(`organizations[].workspaces[]`, with `apps`, `agents`, `ontologies`, `graphs`).

## Decision

1. **A workspace declares its Maps setup in its config entry:**

   ```yaml
   - slug: "acme"
     maps:
       feeds: [acme-facilities, earthquakes]   # enabled; others start disabled
       basemaps:
         custom: [acme-countries]              # built-in basemaps are always enabled
   ```

   `WorkspaceMapsSeedConfig` (Nexus `core/config.py`) rejects unknown keys.
2. **Initial values only.** Each feed (records, built-in and graph feeds) and
   each custom basemap is decided once per workspace, the first time the
   workspace's catalog meets it: enabled when listed, disabled otherwise
   (`seed_revisions["feed-init:<id>"]`, `["basemap-init:<id>"]`). After that
   only Settings → Maps changes it. A feed the deployment adds later starts
   disabled unless listed. A workspace without `maps` starts with every feed
   disabled. Feeds and custom basemaps an admin creates start enabled.
3. **Enabled means on.** The map opens with every enabled feed on; there is no
   separate default-on list.
4. **Unknown ids are reported, not fatal.** At API startup, once modules have
   registered their seeds, config ids no module provides are logged as errors
   per workspace. One workspace's typo does not stop the API.
5. **Removed:** `register_maps_seeds(hidden_feeds=...)`, module
   `workspace-defaults` endpoints and `NEXT_PUBLIC_MAPS_DEFAULT_ON_FEED_IDS`.

## Consequences

- Each environment's file states its workspaces' Maps setup; dev and prod can
  differ without code changes.
- Changing a workspace's `maps` list later only affects ids not decided yet in
  that workspace; existing workspaces are changed in Settings → Maps.
- The config does not grant access: which workspaces may use a feed stays in
  `maps_grants` (Settings → Maps → Access).
- Ids only an admin created in one workspace (no seed) are reported as unknown
  if listed in the config.
