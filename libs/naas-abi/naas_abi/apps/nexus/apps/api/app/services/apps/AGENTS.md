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
- **Portal SSO.** `POST /api/apps/sso-token` mints a short-lived HMAC token (`pages_sso.py`) for the portal of
  one module app. `app_id` is required (without it, 422) and `module:OpenApp` on that app alone decides: the route
  asks nothing else. In order: a request made with a key that has a limit is a 403
  (`refuse_a_limited_credential`, as for a link: the portal's session would be a credential of its own); an id that
  is no app's is a 400; no OpenApp on it is a 403; an app the catalog of loaded modules lacks is a 400, a remote
  app's too (it opens at `/app-html/remote/`, with no portal host, and the web app never asks for it); an audience
  that is not that app's host (`pages_sso_audiences`, a hostname without its port) is a 400; an app with no secret
  is a 404 "This app has no portal sign-in". The secret is looked up after OpenApp, so the 404 tells nothing to
  someone who may not open the app.
  - **One secret per app, opt-in.** `pages_sso_secrets` (`PAGES_SSO_SECRETS` as JSON) maps an app id
    (`<module_path>:<app_dir>`, as `_scan_apps_catalog` sets it) to the secret that app's portal alone shares. An
    app that is not listed, or listed with an empty secret, gets no token. The old single `pages_sso_secret`
    signs nothing: `NexusConfig` still accepts the key (a project that sets it loads) and logs how to move it, and
    the API logs the same at start while `PAGES_SSO_SECRET` is set in its environment.
  - **The token names its app.** Its claims are `app` (the app id), `aud` (the bare hostname), `email` (the
    signed-in user; the body cannot name another), `exp` and `scope`. `verify_pages_sso_token(..., app_id=)`
    checks `app` too; without `app_id` it checks what it always did, so a portal that ignores the claim still
    accepts the token.
  - **The dev origin.** On a local Nexus on loopback, the setting `nexus_dev_app_urls` (`NEXUS_DEV_APP_URLS`:
    `id=url`, comma-separated) may add the host of that app's dev origin (`pages_sso.dev_app_url`). The map has no
    built-in entries.
  - **The web app needs nothing.** The Apps page always sends `app_id` (`portalSsoTokenRequest`), and on any error
    (an app without a secret included) it frames the app without `?sso=`.
  - A view refuses the route.
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
  `NEXUS_DEV_APP_URLS` adds nothing. `abi dev up` (`http://localhost:<port>`) and `abi deploy local`
  (`https://nexus.localhost` by default) keep it. A deployment that leaves `frontend_url` at its loopback default would count
  as local, but its sign-in already sends people to that origin. The web app gates the iframe separately
  (`next dev` only, `applyDevAppUrl`).

- **A portal token is for one app.** Decision: each portal app has its own secret, opt-in (`pages_sso_secrets`,
  app id to secret); a token names its app (`app`) and is signed with that app's secret; there is no form without
  `app_id` (it asked only `nexus:UseApp`, which every member holds, and took any hostname), removed without a
  deprecation period since no known caller used it. `aud` stays the bare hostname, so a portal's existing check
  still passes. Nexus signing with a key the portals can only verify (JWT + JWKS) was left out: with a secret per
  app, a portal's secret mints only its own sign-ins. Consequences: operators move `PAGES_SSO_SECRET` under the
  portal's app id (`pages_sso_secrets: {"<module_path>:<app_dir>": "{{ secret.X }}"}`, or the `PAGES_SSO_SECRETS`
  JSON) and give each portal its own secret; external apps that are not portals get no token and no email in
  their URL; a leaked portal secret mints only that portal's own sign-ins; two apps on one host, or every local
  portal, no longer accept each other's tokens once each has its own secret. `nexus:UseApp` stays declared,
  deprecated (`../iam/catalog/apps.py`), asked by no route.

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
The portal SSO route there too (`test_*sso*`, `test_a_dev_origin_*`, `test_an_app_without_a_secret_*`,
`test_two_apps_on_one_host_*`): who mints, for which email, app and audience, the 422 without `app_id`, the 404
without a secret, the dev origin's gate; `pages_sso_test.py`: the token and its `app` claim, the audiences, the
dev map, the loopback check, the secrets map and the start-up warning. The settings (`pages_sso_secrets`, the old
`pages_sso_secret`): `libs/naas-abi/naas_abi/ABIModule_test.py`.
