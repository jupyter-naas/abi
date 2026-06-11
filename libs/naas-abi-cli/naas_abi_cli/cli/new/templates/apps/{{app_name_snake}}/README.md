# `{{ app_name_snake }}` — app

> An **app** is a self-contained UI surface that the `{{ module_name_snake }}` module ships to the Nexus catalog. It is discovered from this folder's `manifest.json` and (optionally) served as a static HTML page.

## Layout

```
apps/
└── {{ app_name_snake }}/
    ├── manifest.json   # catalog entry (required)
    ├── index.html      # the page served to the iframe (optional)
    └── README.md       # this file
```

The app id exposed by the API is `<module.dotted.path>:{{ app_name_snake }}`. The folder name is the app name — keep it `snake_case` and avoid a leading `_` (folders starting with `_` are skipped by discovery).

## `manifest.json`

The manifest is the only required file. It is read verbatim into the catalog. Recognised fields:

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Human-readable title shown in the catalog. |
| `description` | yes | One-line summary. |
| `category` | yes | Catalog bucket (e.g. `marketplace`, `alpha`). Falls back to `unknown`. |
| `url` | no | Where the app lives. Use `html:<filename>` to serve a bundled file (see below), or a full `https://…` URL for an external app. |
| `icon_emoji` / `avatar_url` | no | Catalog icon. |
| `version`, `author`, `license`, `maintainer` | no | Metadata. |
| `keywords` | no | List of search terms. |
| `tier` | no | `community` / `marketplace` / … |
| `pricing` | no | `{ "type": "free", "price": 0 }`. |
| `demo_login` / `demo_password` | no | Pre-filled demo credentials. |

## Serving the HTML page

Set `url` to **`html:index.html`** (or any filename in this folder). The Nexus API resolves that shorthand and serves the file:

1. Discovery walks every loaded module's `apps/<app>/manifest.json`.
2. A `url` of `html:index.html` is rewritten to `/app-html/<module/path/url>/{{ app_name_snake }}/index.html`.
3. The `list_apps` endpoint turns that into a fully-qualified URL the frontend iframe loads.

You can point at any file (`html:dashboard.html`, `html:build/index.html`, …) — it just has to exist in this folder. To embed an externally hosted app instead, set `url` to a full `https://…` URL and drop `index.html`.

> The catalog is process-cached. **Restart the Nexus API** to pick up a new or changed manifest.

## Enabling

Apps are discovered automatically as long as the parent module is enabled in your `config.yaml`:

```yaml
modules:
  - path: src/custom/{{ module_name_snake }}
    enabled: true
```

No extra registration is needed — drop the folder in, restart the API, and the app shows up in the catalog (`GET /api/apps/?workspace_id=…`).

## Scaffold another app

```bash
abi new app <name> apps/
```
