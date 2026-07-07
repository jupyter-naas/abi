# Coder embedding prototype

A self-contained harness to **de-risk the embedding boundary** before folding
Coder into abi's main stack. It runs Coder OSS unmodified behind its REST API,
and drives provisioning through abi's `coding_environment` core service
(`libs/naas-abi-core/.../services/coding_environment`).

> Why this exists: the assessment found that the real embedding risks are
> **third-party cookies** and the **token→cookie redemption handshake**, *not*
> framing headers. This harness proves the headless flow + lets you run the
> cross-browser cookie test on a same-registrable-domain layout.

## Layout

| Path | What |
|---|---|
| `docker-compose.yml` | Postgres + Coder (HTTP); optional Caddy edge (`edge` profile) |
| `Caddyfile` | Same-domain HTTPS edge for the browser test (`app.lvh.me` + `*.coder.lvh.me`) |
| `template/main.tf` | Coder Docker template running code-server as a `subdomain`, `owner`-shared app |
| `scripts/bootstrap.sh` | Headless: create first user, capture a session token |
| `scripts/provision.py` | Headless provision via the abi `coding_environment` service |
| `frontend/index.html` | Minimal custom chrome that embeds the editor in an `<iframe>` |
| `Makefile` | `up / bootstrap / provision / template / headers / edge / down` |

## A. Headless flow (HTTP — no DNS/TLS needed)

```bash
cd coder_prototype
make up                 # postgres + coder on http://localhost:7080
make bootstrap          # create owner user, write .coder-token
make provision          # ensure_user -> list_templates (-> provision if a template exists)
make provision-inmem    # the same flow against the fake adapter (no Docker at all)
```

`make provision` exercises the **real CoderAdapter against the real Coder REST
API**. Without a template it stops after `list_templates`. To go further:

```bash
make template           # push template/main.tf  (pulls the docker provider + base image)
make provision          # now provisions a real workspace and prints the embed URL
```

## B. Embedding test (HTTPS, same registrable domain)

This is the part that actually settles the cookie question. `lvh.me` and all
its subdomains resolve to `127.0.0.1`, giving a production-equivalent
**same-eTLD+1** layout (frontend `app.lvh.me`, editor `*.coder.lvh.me`).

```bash
make edge               # brings up Caddy with local TLS + the CSP frame-ancestors allow
# trust Caddy's local CA so the browser accepts the certs:
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./root.crt
#   then add ./root.crt to your OS/browser trust store, and re-run bootstrap/template/provision
```

Open `https://app.lvh.me/`, paste the embed URL printed by `provision.py`
(it includes `?coder_session_token=...`), and click **Embed**.

### PASS / FAIL bars (run in BOTH Chrome and Safari, default settings)

- **Headers** — the app response has no `X-Frame-Options`, and Coder's CSP
  `frame-ancestors` includes `https://app.lvh.me`. (`make headers` checks the
  raw values.)
- **Token redemption + cookie (the bridge)** — after the iframe loads the
  `?coder_session_token=…` URL, DevTools shows a `Set-Cookie` for
  `coder_…_session_token`, **and that cookie is sent on subsequent requests
  _inside the iframe_**. Must be on an `owner`-shared app (a `public` app
  proves nothing about auth).
- **WebSocket** — the editor WS reaches `101` and stays open (no `1006`).
- **Interactivity** — within 15 s of render: a terminal `echo abi-ok` round-trips
  AND a new file saves to the workspace FS.
- **Cold start** — record click→interactive seconds from a stopped workspace.

If headers/origin block it, the fallback is to proxy the editor under a
**subpath of the parent origin** (`https://app.lvh.me/ide/`) forwarding
`Host`+`Upgrade`/`Connection` — same-origin needs no flags.

## Shipping it inside abi's main stack

This standalone harness mirrors what goes into the real `docker-compose.yml`:

- Add a `coder` service → point `CODER_PG_CONNECTION_URL` at the existing
  Postgres (add `.deploy/docker/postgres/initdb/003-create-coder-db.sql` with
  `CREATE DATABASE coder;`).
- Route `coder.${PUBLIC_WEB_HOST}` + `*.coder.${PUBLIC_WEB_HOST}` through the
  existing **Caddy** (forward `Host` + WebSocket upgrade) under wildcard TLS.
- The Python `coding_environment` service (in the `abi` container) talks to
  `http://coder:7080/api/v2`; admin token via SecretService / `{{ secret.CODER_ADMIN_TOKEN }}`.
- Security: the `docker.sock` mount gives Coder host-Docker control — lock down
  or move to a k8s template for production.

## Verified results

See `VERIFIED.md` (written by the prototype run) for the empirical header
values and the headless-flow output captured against the running Coder.
