# AGENTS - cockpit

Lightweight example. Prefer editing demo JSON / SPARQL stubs over growing the UI.

## Configuration

`config.yaml` is the source of truth for brand identity, default page, page
URL/order/enabled state/public access, banners, CSS variables, BFO colours, and
graph defaults. Do not duplicate those values in HTML or JavaScript.

Page components remain registered in `web/lib/registry.js`; configuration can
reorder, rename, disable, or change the URL of a registered page, but cannot
create a component. The static app has no authenticated session yet, so only
the `public` permission is granted. Dataset routes enforce that permission.

Configuration ownership:

- `brand` - browser/app identity, rail mark, favicon, and font stylesheet
- `app.default_page` - landing page
- `app.pages` - `page_id`, URL segment, label, order, enabled state,
  permissions, icon, and banner
- `theme.css_variables` - all shared CSS design tokens
- `theme.bfo_buckets` / `theme.process_slide` - graph and process colours
- `graph` - initial focus/distance/view, canvas dimensions, and every control
  shown in the graph parameters panel

`config_loader.py` validates the YAML. The browser receives a safe subset from
`GET /api/personnel-cockpit/config`; `web/lib/config.js` applies it, and
`web/js/shell.js` creates navigation and page sections dynamically.

Entities are generated data, not application configuration. The default entity
comes from `data/globals/entities.json`: an organization with
`"is_default": true`, or otherwise the first organization. Do not add
`app.default_entity` to `config.yaml`. `config_loader.load_default_entity()`
provides the same selection to Python and injects it into the public browser
payload.

Do not add page metadata back to `index.html`, `shell.js`, CSS `:root`, or a
parallel JavaScript pages constant. `web/lib/pages.js` is only a config-backed
compatibility shim for browser tabs that cached the old module graph; it must
not contain page definitions.

### Adding or changing a page

1. Add/edit the page entry in `config.yaml`. `order` values and URL segments
   must be unique.
2. For a new `page_id`, add its component under
   `web/components/pages/<page_id>/` and register the mount function in
   `web/lib/registry.js`.
3. Add its dataset mapping to the exporter's `page_datasets` in
   `domains/personnel/scripts/export_demo_apps_from_graph.py`.
4. Regenerate data so `data/entities/<id>/manifest.json` contains the page.

Configuration controls the UI and access; the entity manifest controls which
datasets a page loads. Keep both aligned. Changing a page URL does not rename
its dataset folder or `page_id`.

### Permissions

Permissions are enforced by `api/routes.py`, not only by hiding navigation.
Without an authentication adapter, `public` is the only granted permission;
pages with any other permission are omitted from public config/manifests and
their datasets return HTTP 403. Do not claim role-based security until an
authenticated session is implemented server-side.

## Naming

- Python package: `cockpit`
- Catalog id / kebab: `personnel-cockpit`
- Object-storage prefix (personnel module datastore): `personnel/apps/cockpit/`
- Entity ids mirror url slugs with hyphens → underscores (``demo`` → ``demo``)

## Data

Committed datasets live under ``data/`` and are served to the UI through
``api/`` (``GET /api/personnel-cockpit/entities/demo/...``).

- ``data/entities/<id>/manifest.json`` - page → dataset paths for that entity
- ``data/entities/<id>/<page>/`` - page-ready aggregates the UI reads
- ``data/globals/entities.json`` - sidebar entity dropdown (organization perimeters)
- Build input graph: ``domains/personnel/data/graph/personnel_demo.ttl``

Regenerate with ``make demo-data`` (from ``domains/personnel``). Dev server:
``make app-personnel-cockpit``. Do not invent manager hierarchies - not in the ontology.

## Web layout

Mirrors Financial Cockpit conventions (Next.js-style folders, vanilla ES modules):

```text
web/
├── app/[entitySlug]/[pageId]/page.js   # route contract
├── components/pages/<pageId>/          # one module per manifest page
├── lib/{api,config,routes,registry}.js
└── js/shell.js                         # bootstrap + nav
```

URLs: ``/{entity_url_slug}/{configured_page_url}`` (e.g.
``/demo/graph``). API reads ``entity_id`` and stable `page_id` paths.

## Pages

| page_id | SPARQL tools / content |
| --- | --- |
| workforce | `find_active_employees`, `find_employees_by_status`, `find_headcount_by_job_family` |
| graph | person search + distance 1–3 hop filter on process graph |
| processes | BFO 7-buckets process docs (`processes/processes.json`) |
| logs | acts of working / studying → `logs/ledger.json` (one row per process) |

## Verification

Run from the ABI repository root:

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/apps/cockpit/config_loader_test.py -q
uv run ruff check libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/apps/cockpit
node --check libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel/apps/cockpit/web/js/shell.js
```

After changing config, restart `make app-personnel-cockpit`: the config API
reloads YAML per request, but the development server reads permitted SPA URL
segments at startup.
