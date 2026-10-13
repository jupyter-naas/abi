# Nexus Maps groups: a data property of feeds

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

The Maps sidebar reads **group → feed → layer**. Feeds (`maps_layouts`) and
layers (`maps_feed_layers`) are server records
(`20261012_nexus-maps-catalog-and-access.md`), but groups are not handled
consistently:

- A feed's `category` holds a slug (`environment`, `organizations-facility`,
  …). The sidebar shows only the slugs listed in web code
  (`MAPS_CATEGORIES_ALL` in `maps/lib/datasets.ts`) and silently drops every
  other feed. Renaming `public` to `environment` / `sigint` / `situation` in
  code made the "Public" feeds disappear.
- User groups (`user-…`) are kept in browser localStorage
  (`maps/lib/maps-layer-groups.ts`), so other members and browsers never see them.
- `NEXT_PUBLIC_MAPS_VISIBLE_CATEGORIES` filters groups at build time for every
  workspace, and core carries a deployment-specific slug
  (`organizations-facility`) with behavior keyed on it
  (`isMapsOrganizationFacilityOnlyDeployment()`).

A group has no attributes of its own beyond its name. It is a property of a
feed, not an entity.

## Decision

1. **`group` is a data property of a feed.** `MapsLayout.group` is a
   free-text label (1–80 characters, trimmed), for example `"Environment"` or
   `"Organizations Facilities"`. It replaces `category`. `from_dict` reads a
   legacy `category` and maps the known slugs to labels (`environment` →
   Environment, `sigint` → SIGINT, `situation` → Situation,
   `organizations-facility` → Organizations Facilities, `public` → Public,
   `custom` → Custom). Any other slug is used as written. Each record is
   rewritten with `group` on its next save. No table and no service are added.
2. **The sidebar derives groups from feeds.** A group is the set of feeds that
   share a `group` value, matched case-insensitively and displayed with the
   first spelling found. Groups are sorted by label, with `Custom` last. A feed
   with no group shows under `Custom`. No feed is ever dropped because of its
   group value.
3. **Every feed source carries the property.** API and SPARQL feeds store it on
   their record. Built-in web feeds declare it in `datasets.ts`. Module graph
   layers and browser imports carry it too, defaulting to `Custom`. Seeds set
   it on the `MapsLayout` they register. Choosing a group in Settings → Maps
   means picking an existing value or typing a new one.
4. **No group-level visibility or access.** Hiding stays per layer
   (`hidden_layouts`): hiding a group means hiding each of its layers. Access follows the feed (`maps_grants`). A deployment
   hides layers by default with `register_maps_seeds(hidden_layouts=[...])`:
   the ids are added to each workspace's `hidden_layouts` once per seed
   revision (`seed_revisions["hidden:<id>"]`), so an admin may show them again.
5. **Removed:** `MAPS_CATEGORIES_ALL`, the localStorage group store,
   `CATEGORY_PATTERN`, `NEXT_PUBLIC_MAPS_VISIBLE_CATEGORIES` and
   `isMapsOrganizationFacilityOnlyDeployment()`. On first load, a workspace
   admin's browser writes each localStorage group label onto the feeds that used
   it, then clears the key.

## Consequences

- Groups need no CRUD, seeds or migration table. A group appears when a feed
  uses its value and disappears when no feed does.
- Renaming a group means updating the property on each of its feeds; no single
  record holds the name.
- A group has no order, icon or description. If one is ever needed, that is when
  groups become records, through a new ADR.
- Deployments stop filtering at build time. A deployment that shows only its
  own feeds hides the built-in layers through `hidden_layouts` seeds, or narrows
  feeds with grants. Which feeds are on by default is decided separately.
- Typos create separate groups (`Enviroment`). The group picker offers the
  existing values first to limit this.
