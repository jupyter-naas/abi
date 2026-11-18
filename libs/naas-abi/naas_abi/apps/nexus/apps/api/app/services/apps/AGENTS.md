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
- **Portal SSO.** `POST /api/apps/sso-token` with `app_id` asks `module:OpenApp` on that app. The proof's email is
  the signed-in user, and its audience must be that app's host (`pages_sso_audiences`), a hostname without its port.
  On a local Nexus on loopback, the setting `nexus_dev_app_urls` (`NEXUS_DEV_APP_URLS`: `id=url`, comma-separated)
  may add the host of that app's dev origin (`pages_sso.dev_app_url`). The map has no built-in entries. An id that
  is no app's, or an app the catalog of loaded modules lacks, is a 400; a remote app is one (it opens at
  `/app-html/remote/`, with no portal host, and the web app never asks for it). Without `app_id` the route still
  asks `UseApp` and takes any hostname. An empty `pages_sso_secret` is a 503 for those allowed. A view refuses it.
- **A remote app is installed while a READY module serves it** (`_remote_app_info`): the Apps pages and the
  workspace settings list only installed apps, as for a loaded module's.
- **No per-workspace switch.** The app-config routes (`GET|POST /api/apps/{ws}`, `GET|PATCH|DELETE
  /api/apps/{ws}/{app_id}`) and `AppsService` are gone; `app_configs` is read by nothing here (the upgrade reads it
  once and drops it). The `nexus` actions they asked (`GetApp`, `InstallApp`, `UpdateApp`, `UninstallApp`) stay
  declared, deprecated (`../iam/catalog/apps.py`).

## Decisions

- **A dev origin is an audience on a local Nexus on loopback only.** Decision: the SSO route takes the host of an
  app's `nexus_dev_app_urls` entry as an audience while `nexus_env` is `local` and `frontend_url` is on a loopback
  host (`localhost`, `*.localhost`, a loopback address); the map is a `Settings` field, read like every other
  setting. Consequences: `nexus_env` defaults to `local` and no deploy template sets it for the API, so it alone
  would honour the map on a deployed Nexus; `frontend_url` is the web app's public origin there, so a forgotten
  `NEXUS_DEV_APP_URLS` adds nothing. `abi dev up` (`http://localhost:<port>`) and the Docker stack
  (`https://nexus.localhost`) keep it. A deployment that leaves `frontend_url` at its loopback default would count
  as local, but its sign-in already sends people to that origin. The web app gates the iframe separately
  (`next dev` only, `applyDevAppUrl`).

## In a view

`access-token`, `remote-grant` and `app-projects/{slug}/preview-token` are reads sent by POST that a view allows
(`../view_as/reads_by_post.py`); `sso-token` is refused. A link made in a view (`links.mint_link`, which reads the view of
the request) is the person's and: ends no later than the view (`not_after`), is marked in its description
(`OpenedLink.view`), is revoked when the view ends (`links.revoke_view_links`, asked by `ViewAsService`), is audited as
`iam.view_as_open_app` (`view_as.runtime.audited_open`, fail-closed), and is forwarded by the remote proxy
(`remote/http_routes.py`, at `/app-remote/…` and `/app-html/remote/…`) for GET and HEAD only: any other method is
"Read-only: you are viewing as <name>" (403), and the fresh grant the catalog URL makes stays the view's. Consequences: each open in a view mints a grant key for the person, which counts toward their link quota
(`LinkLimitReached`, 429); the links of a view are revoked with it, so the quota comes back. Details:
`../view_as/AGENTS.md`, "Apps opened in a view".

## Tests

```bash
uv run --frozen pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/apps -q --no-cov
```

`adapters/primary/apps__primary_adapter__FastAPI_iam_test.py`: who lists, opens and links apps, the listing exactly
what IAM allows (a Deny removes an app), an admin or owner with no policy listing and opening none.
The portal SSO route there too (`test_*sso*`, `test_a_dev_origin_*`): who mints, for which email and audience,
the dev origin's gate; `pages_sso_test.py`: the token, the audiences, the dev map and the loopback check.
