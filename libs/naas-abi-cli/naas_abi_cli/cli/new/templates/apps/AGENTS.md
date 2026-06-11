# `apps/` — AGENTS.md

> Scope: app definitions for the `{{ module_name_snake }}` module. See the module's [AGENTS.md](../AGENTS.md) for module-wide context.

## What goes here

**Apps** are self-contained UI surfaces this module ships to the Nexus catalog. Each app is a folder holding a `manifest.json` (its catalog entry) and, optionally, the assets it serves — typically a single `index.html`. Apps are *discovered*, not imported: nothing in Python code references them. The Nexus API walks every loaded module's `apps/` directory at startup.

## Folder shape

One folder per app, `snake_case`, never starting with `_` (underscore-prefixed folders are skipped by discovery):

```
apps/
└── <app_name>/
    ├── manifest.json   # catalog entry (required)
    ├── index.html      # the page served to the iframe (optional)
    └── README.md       # per-app notes
```

The app id exposed by the API is `<module.dotted.path>:<app_name>`, so the folder name *is* the app name — keep it stable.

## `manifest.json`

The only required file. Read verbatim into the catalog by the apps adapter. Recognised fields:

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Human-readable title in the catalog. |
| `description` | yes | One-line summary. |
| `category` | yes | Catalog bucket (e.g. `marketplace`, `alpha`). Falls back to `unknown`. |
| `url` | no | Where the app lives — `html:<filename>` for a bundled file, or a full `https://…` URL for an external app. |
| `icon_emoji` / `avatar_url` | no | Catalog icon. |
| `version`, `author`, `license`, `maintainer`, `tier` | no | Metadata. |
| `keywords` | no | List of search terms. |
| `pricing` | no | `{ "type": "free", "price": 0 }`. |
| `demo_login` / `demo_password` | no | Pre-filled demo credentials. |

## How an app gets served

Set `url` to **`html:<filename>`** (e.g. `html:index.html`). The Nexus apps adapter (`apps__primary_adapter__FastAPI.py`) resolves the shorthand:

1. Discovery reads `apps/<app>/manifest.json` for every loaded module.
2. `url: "html:index.html"` is rewritten to `/app-html/<module/path/url>/<app>/index.html`
   (the module's dotted path becomes slash-separated).
3. `GET /api/apps/?workspace_id=…` turns that into a fully-qualified URL the frontend iframe loads.

Point `url` at any file in the app folder (`html:dashboard.html`, `html:build/index.html`, …) — it only has to exist. To embed an externally hosted app instead, set `url` to a full `https://…` URL and skip the bundled HTML.

> **The catalog is process-cached.** Restart the Nexus API to pick up a new or changed manifest.

## Scaffold a new app

```bash
abi new app <name> apps/
```

This drops `apps/<name>/` with a templated `manifest.json` (wired to `html:index.html`), a Hello-world `index.html`, and a `README.md`.

## Enabling

No registration needed. As long as this module is enabled in `config.yaml`, its apps appear in the catalog automatically:

```yaml
modules:
  - path: src/custom/{{ module_name_snake }}
    enabled: true
```

Drop the folder in, restart the API, and it shows up.

## See also

- Apps adapter (discovery + `html:` resolution + serving routes): `.abi/libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/apps/adapters/primary/apps__primary_adapter__FastAPI.py`
- Reference apps: `.abi/libs/naas-abi-marketplace/.../alpha/wsr/apps/dashboard/manifest.json` (external URL), `.abi/libs/naas-abi-marketplace/.../domains/document/apps/sandbox/manifest.json` (`html:` bundled page)
