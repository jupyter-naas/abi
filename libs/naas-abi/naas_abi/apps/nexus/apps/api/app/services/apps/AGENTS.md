# Apps domain - AGENTS.md

## Purpose

The apps of the modules (engine modules' `apps/<name>/manifest.json`, remote modules' apps from
discovery) as a workspace lists and opens them. Who may open an app is its module scope (`scopes.py`,
`module:OpenApp`, `../iam/AGENTS.md` "Module scopes"), IAM's decision alone: a workspace keeps no
on/off state of its own for an app.

## Files

| File | Role |
|---|---|
| `port.py` | `AppInfo`, `AppsResponse`: the catalog's HTTP schemas |
| `adapters/primary/apps__primary_adapter__FastAPI.py` | The catalog discovery and the routes (its docstring lists them) |
| `scopes.py` | `app_scope(app_id)`: `<module path>:<app>` or `remote/<module id>:<app>` to `app/<module>/<name>` |
| `links.py`, `app_html_access.py`, `remote/` | Links to `/app-html/`, remote apps' grants and the workspace they open in |

## Rules

- **IAM alone lists and opens.** `GET /api/apps/?workspace_id=` lists exactly the apps of the loaded modules and of
  READY remote modules the caller may open there (`authz.filter_scopes`), the platform admin included; no role holds
  an app by itself. `access-token`, `remote-grant` and the workspace a remote app opens in (`remote/access.py`) ask
  the same scope (`authz.require_scope`). A workspace that should not offer an app denies it in a policy.
- **A remote app is installed while a READY module serves it** (`_remote_app_info`): the Apps pages and the
  workspace settings list only installed apps, as for a loaded module's.
- **No per-workspace switch.** The app-config routes (`GET|POST /api/apps/{ws}`, `GET|PATCH|DELETE
  /api/apps/{ws}/{app_id}`) and `AppsService` are gone; `app_configs` is read by nothing here (the upgrade reads it
  once and drops it). The `nexus` actions they asked (`GetApp`, `InstallApp`, `UpdateApp`, `UninstallApp`) stay
  declared, deprecated (`../iam/catalog/apps.py`).

## Tests

```bash
uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/apps -q --no-cov
```

`adapters/primary/apps__primary_adapter__FastAPI_iam_test.py`: who lists, opens and links apps, the listing exactly
what IAM allows (a Deny removes an app), an admin or owner with no policy listing and opening none.
