# Apps domain - AGENTS.md

## Purpose

The apps of the modules (engine modules' `apps/<name>/manifest.json`, remote modules' apps from
discovery) as a workspace lists, opens and turns them on or off. Who may open an app is its module
scope (`scopes.py`, `module:OpenApp`, `../iam/AGENTS.md` "Module scopes"); what a workspace has is
its set; on or off for everyone in it is `app_configs.enabled`.

## Files

| File | Role |
|---|---|
| `port.py`, `service.py` | `AppsService`: per-workspace app configs (`enabled`) over `AppPersistencePort` |
| `adapters/primary/apps__primary_adapter__FastAPI.py` | The catalog discovery and the routes (its docstring lists them) |
| `adapters/secondary/postgres.py` | `app_configs` |
| `scopes.py` | `app_scope(app_id)`: `<module path>:<app>` or `remote/<module id>:<app>` to `app/<module>/<name>` |
| `visibility.py` | `AppsVisibility`: the apps a workspace turned off, for `services/visibility` |
| `links.py`, `app_html_access.py`, `remote/` | Links to `/app-html/`, remote apps' grants and the workspace they open in |

## Rules

- **The set limits the catalog.** `GET /api/apps/?workspace_id=` and `GET /api/apps/{ws}` list only the apps of the
  workspace's effective set (`iam/sets.within_set`), for everyone, the platform admin included, then those the caller
  may open. Turning one on outside the set (`POST`, `PATCH` with `enabled: true`, the Apps agent's `set_app_enabled`)
  is 403; turning one off, always allowed.
- **Off is refused.** An app is on by its row, else the workspace's catalog seed, else off
  (`resolve_app_enabled`). One off is refused to everyone (`access-token`, `remote-grant`, the workspace a remote app
  opens in: 403 "This app is turned off in this workspace") and listed only to who holds `UpdateApp`, to turn it back
  on. A link minted before it was turned off works until it expires.

## Tests

```bash
uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/apps -q --no-cov
```

`adapters/primary/apps__primary_adapter__FastAPI_iam_test.py`: who lists, opens and switches apps, the set, an app
turned off refused to every role.
