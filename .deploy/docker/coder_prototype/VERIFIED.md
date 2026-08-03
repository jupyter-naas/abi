# Verified results

Empirical results captured by running this harness against **Coder OSS v2.34.1**
on Docker Desktop (macOS). These confirm / correct the assessment.

## Environment
- Coder `v2.34.1+2e8d80a`, Postgres 17, Docker Desktop 28.4.0.
- Coder run headless behind its REST API; provisioning driven entirely by abi's
  `coding_environment` core service (`CoderAdapter`).

## Headless control-plane flow — VERIFIED end-to-end

Driven through the real service (`CodingEnvironmentFactory.CodingEnvironmentServiceCoder`):

| Step | Result |
|---|---|
| First-user bootstrap (`POST /api/v2/users/first` + login) | ✅ session token obtained |
| `ensure_user` (GET 404 → `POST /users`, `login_type:"none"`) | ✅ created real user `aca23d59…`, idempotent on re-run |
| `list_templates` | ✅ returns `abi-code-server` after push |
| `provision` (`POST /organizations/{org}/members/{user}/workspaces`) | ✅ workspace created, build started |
| build → agent connect (poll loop) | ✅ reached `phase=running agent_ready=True` |
| `get_access` (mint token + assemble subdomain URL) | ✅ `https://code-server--main--dev2--alice.coder.lvh.me/?coder_session_token=…` |

**Confirms** the §4 REST sequence, the `Coder-Session-Token` auth, org
resolution via `/organizations/default`, build/agent status normalization, and
the §4c subdomain-URL transform — against the real API, not mocks.

## Corrections discovered against the live API (assessment had these UNCERTAIN)

1. **`login_type:"none"` works in OSS v2.34.1** — user creation via the admin
   token succeeded. (Was medium-confidence; now confirmed for this version.)
2. **Scoped-token schema** — the `allow_list: [{type,id}]` shape is **wrong**:
   Coder returned `400 cannot unmarshal object into … allow_list of type string`,
   and the scope field is singular `scope`, not `scopes`. `CoderAdapter._mint_token`
   was fixed to send `{token_name, lifetime, scope:"application_connect"}` and
   fall back to a basic `{token_name, lifetime}` token if the scoped form is
   refused. Minting then succeeded against the live API.

## Embedding framing headers — VERIFIED

- **Coder** sends (captured from `http://localhost:7080/`):
  `Content-Security-Policy: … frame-ancestors 'self'; …` — **not** `X-Frame-Options`.
  So cross-origin framing of Coder surfaces is blocked by default and is opened
  by appending to `frame-ancestors` via `CODER_ADDITIONAL_CSP_POLICY`. ✅ confirms §3a.
- **code-server**: no `X-Frame-Options` / no CSP `frame-ancestors` (source-verified
  in the assessment workflow). A local empirical probe was inconclusive because
  the `codercom/code-server` image would not stay running in this sandbox — not a
  header finding, an image/env quirk.

## Local-Docker config needed for a workspace to boot (now baked into the harness)

1. **Docker socket permission** — terraform's docker provider hit
   `permission denied … /var/run/docker.sock`; fixed by running the `coder`
   service as `user: root` (prototype-only; use a socket-proxy or k8s in prod).
2. **Agent-reachable access URL** — `CODER_ACCESS_URL` must be reachable from the
   workspace container; set to `http://host.docker.internal:7080` so the agent
   connects back. (The host-side provision script still uses `http://localhost:7080`.)

## Still to do (needs a browser + the HTTPS edge)

The cross-browser **cookie/redemption** test (Chrome + Safari, default settings)
is the one bar not yet run here — it needs `make edge` (Caddy + local TLS on
`lvh.me`) and a real browser. The embed URL above is exactly what you paste into
`frontend/index.html` to run it.

## Update — compose code-server path (simpler than Coder/Terraform)

Per the "use docker-compose, not Terraform" direction, code-server now ships as
a plain compose service and is a first-class backend behind the same port
(`CodeServerComposeAdapter`). Empirically verified on the running stack:

- code-server runs (the earlier failures were the disk-full window): `GET /`
  returns `302 → /login → 200` with **no `X-Frame-Options` and no CSP
  `frame-ancestors`** — iframe-embeddable.
- Behind Caddy at `https://code-server.lvh.me/` (HTTP/2 302 → /login), served
  over HTTPS under the same registrable domain as the frontend (`app.lvh.me`).
- **Cookie (the load-bearing bit):** login sets
  `code-server-session=…; Domain=code-server.lvh.me; Path=/; SameSite=Lax`.
  `SameSite=Lax` + same registrable domain ⇒ `app.lvh.me` embedding
  `code-server.lvh.me` is a **same-site** iframe, so the cookie **is** sent
  inside it. No `SameSite=None`, no third-party-cookie problem. (Cross-*domain*
  is where Lax would fail in Safari — hence the same-domain strategy.)
- `coding_environment` service: `code_server` adapter + factory
  (`CodingEnvironmentServiceCodeServer`) + config option; **33 unit tests pass**.
- Shipped into the main stack: `code-server` service in `docker-compose.yml` +
  a `code-server.${PUBLIC_WEB_HOST}` route in `.deploy/docker/Caddyfile`.

Tradeoff: one shared editor (not per-user isolated workspaces) — use the
`CoderAdapter` backend when you need per-user isolation/autostop at scale.

**Remaining human step:** visually confirm the editor renders + authenticates
inside the iframe in Chrome and Safari (open `https://app.lvh.me/`, paste
`https://code-server.lvh.me/`). Needs trusting Caddy's local CA first
(`docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./root.crt`).
