# naas-abi-idp - AGENTS.md

## Purpose

The built-in OIDC identity provider of ABI: the default provider of `abi dev up`
and of small installs, where nobody runs Okta or Zitadel. It keeps the flow
Nexus had: **register with just an email, sign in with a code** emailed to it.
Specification: RFC
[`docs/specs/rfcs/20261013_identity-and-authorization.md`](../../docs/specs/rfcs/20261013_identity-and-authorization.md)
§12; decision: ADR
[`20261013_identity-providers-and-builtin-idp`](../../docs/adr/20261013_identity-providers-and-builtin-idp.md)
and its "As built" section.

It is an **SDK module** (`naas_abi_sdk.BaseModule`), `module_id = "idp"`, and
**core-free**: it depends on `naas-abi-sdk`, `naas-abi-proto`, `authlib`,
`cryptography` and `starlette`, never on `naas_abi_core` or Nexus (its Docker
image fails to build if core sneaks in). Out of scope: SAML, brokering other
IdPs, MFA policies.

**Provably separate from Nexus and the engine:**

- It runs as the service account `module/<project>/idp`, with the default
  permission manifest of `document`, `secret` and `email`: its own Document
  Service namespace (`idp`), its own secrets (`idp/...`) and `email:Send`.
- The engine **seals** that namespace and those secrets to this account (module
  id `idp`): not even `api` or `engine` reads them, whatever their policies say
  (`services/document/iam_catalog.py`, `services/secret/iam_catalog.py`,
  `secret_nats_contract.may_use`). Tests: `DocumentService_authorization_test.py`,
  `secret__primary_adapter__NATS_test.py`.
- It never uses Nexus's `secret_key`; Nexus never reads its data. Its signing
  keys (ES256) are secrets `idp/signing-keys/<kid>`, its HMAC key for sign-in
  codes `idp/code-key`.

## Files

| File | Role |
|---|---|
| `module.py` | `ABIModule`: wiring, the two apps, maintenance |
| `__main__.py` | `python -m naas_abi_idp`: `ABI_NATS_URL`, `ABI_SERVICE_KEY`, `ABI_DISCOVERY_PROJECT`, `ABI_IDP_*` |
| `configuration.py` | `IdPConfiguration` (also `from_environment`), `Branding`, `ClientConfiguration` |
| `ports.py` | `DocumentStore`, `SecretStore`, `Mailer` and the errors |
| `service.py` | `IdPService`: users, groups, clients, sign-in codes, sessions, refresh tokens |
| `limits.py` | `RateLimiter`: counters in documents, one compare-and-set per attempt |
| `keys.py` | `KeyRing`: ES256 keys, rotation, JWKS, the code HMAC key |
| `oidc.py` | The authlib server: grants, token and ID-token generation, revocation |
| `web.py` | The public ASGI app (`idp` app): discovery, JWKS, `/authorize`, login pages, `/token`, `/revoke`, `/userinfo`, `/logout` |
| `admin.py` | The admin ASGI app (`admin` app): JSON API for the provisioning port |
| `pages.py` | The login pages and the sign-in mail, with branding |
| `adapters/sdk.py` | The ports over the SDK's `document`, `secret` and `email` services |
| `adapters/memory.py` | In-memory adapters (tests, the generic identity suite) |
| `models.py` | The records; `secrets_hash.py` scrypt, SHA-256 and HMAC helpers |
| `Dockerfile` | SDK-only image (named contexts `abi_proto`, `abi_sdk`) |

## Design

**Synchronous domain, async edges.** Authlib is synchronous, so the HTTP layer
runs `IdPService` and the OIDC server in worker threads, and the SDK adapters
(`adapters/sdk.py`) schedule the async engine services on the module's loop.
Build the service with `asyncio.to_thread` (`module.py`): an adapter called
on the loop's own thread would wait on itself.

**The document is the unit of atomicity** (Document Service: no transactions).
A sign-in challenge, a refresh token, a counter: one document each, changed with
`replace(doc, ...)` (compare-and-set), so replicas and parallel requests agree.

### Sign-in codes

- 6 digits (`code_length`), emailed, valid 15 minutes, at most 5 active per
  address; stored as an HMAC under `idp/code-key`, so a copy of the documents
  alone yields nothing.
- **Attempts are counted across every active code** (bug (e) of #44): one
  budget per address (`max_attempts`, 5), spent *before* a guess is judged and
  given back on success, so parallel guesses cannot all slip through and
  asking for a fresh code does not renew it. The budget spent voids every code
  and locks the address for `rate_limit_window_seconds` (300). The counter is
  per address whether or not it is registered: the answer never says.
- Limits: sends per address (5 / window); per client IP, failures against a tight
  budget (wrong guesses, requests for unregistered addresses: 20 / window) and
  code requests against a loose one (`rate_limit_ip_sends`, 100 / window), so a
  peer many users share is not locked out by their ordinary sign-ins. The IP
  comes from `x-abi-client-ip`, which the trusted route sets from the connection
  as uvicorn resolved it (`FORWARDED_ALLOW_IPS`).
- The mail leaves in the background (`background_mail`) and an unregistered
  address costs the store what a registered one does, so neither the page nor
  its timing tells them apart.
- A new password or email ends the user's provider sessions and revokes their
  refresh tokens, as disabling does.
- Self-registration with just an email: `signup_enabled` (off; `abi dev up`
  turns it on). Otherwise a user exists because the admin API created them.
- Password sign-in is optional (`password_login_enabled`, off): scrypt hashes,
  the same limits.

### OIDC

- Authorization code + **PKCE S256, required of every client**; `redirect_uri`
  matched exactly; a code is spent when first presented, a second use revokes
  what it issued; ID tokens (ES256) carry `email` / `email_verified: true`
  (the provider mailed the address a code), `groups` (the **group names**) and
  `nonce`; access tokens are ES256 JWTs, **at most 10 minutes**; refresh tokens
  rotate on every use, a replayed one revokes its family; disabling a user ends
  their sessions and refresh tokens.
- Client credentials, for service accounts (confidential clients created by the
  admin API; the secret is shown once, kept hashed).
- Discovery (`/.well-known/openid-configuration`), JWKS (`/jwks.json`, the
  active key and the retired ones kept 24 h). **No introspection.**
- The provider's own session (`abi_idp_session`, 8 h) signs a user in again
  without a code; `prompt=login` and `max_age` force it.

### The two apps

| App | Reached by | Authorized by |
|---|---|---|
| `idp` | browsers and relying parties, through Nexus at `/idp` (a dedicated trusted route) | nobody: a login page has no user yet |
| `admin` | services over NATS (`abi.app.v1` requests to the app, as every module app) | discovery's `discovery:OpenApp` on `abi:-:-:discovery:app/<project>/idp/admin`, **and the app itself**: only the engine's own accounts (`api`, `engine`: `admin.ADMIN_ACCOUNTS`) acting for nobody; a user, a module account or a CI account is refused whatever discovery allowed |

The admin API (JSON): `GET/POST /users`, `GET /users/{id}`, `GET /users/by-email`,
`PATCH /users/{id}`, `POST /users/{id}/disable|enable`, `GET/POST /groups`,
`DELETE /groups/{id}`, `PUT/DELETE /groups/{group}/members/{user_id}`,
`GET/POST /clients`, `POST /clients/{id}/disable|enable`, `POST /keys/rotate`.
Errors are `{"error": <code>, "message": ...}` (400, 404, 409). `OpenApp` is a
read-level action, which a service account holds once it holds a workspace role
(`builtin.platform.viewer`), so discovery's answer is not enough: the app host hands
the app the verified actor (`scope["abi"]["principal"]`: `id`, `kind`, `name`, from
discovery's `AuthorizeApp`), and `admin.py` checks it itself. Test:
`tests/test_admin.py` (a module account that holds `viewer` gets 403). The default
manifest of a module that depends on `idp` also denies the admin app
(`naas_abi_sdk.permissions`). Its caller is the provisioning port of the engine's
identity service (`ProvisioningBuiltinIdP`).

### The trusted route and the engine

- **Nexus** (`apps/nexus/.../services/idp/`): `/idp/...` is the issuer
  (`https://<host>/idp`). Only the instance running as `module/<project>/idp`
  answers (`binding.py`: the account's subject token is compared with the
  instance's), only while a provider has `provisioning: builtin`, only an
  allow-list of paths, only `abi_idp_*` cookies on path `/idp`, no Domain, always
  `HttpOnly` and `SameSite=Lax`, Nexus's own CSP (no script, no framing), no
  Nexus session cookie ever reaches the module, `Secure` wherever the issuer is
  https. It serves Nexus as the relying party (its redirect URI's origin and the
  web app's) and the origins in `idp_client_origins`; `/authorize` refuses any
  other `redirect_uri`, which would end in a blocked redirect (a CSP
  `form-action` applies to the redirect after a post). The module is hidden from the
  apps catalog and no generic route opens it (`INTERNAL_MODULES`).
- **The engine** reads the issuer's discovery document, JWKS and token endpoint
  over NATS, through the `idp` app (`IdPAppNATS`, `OIDCHttpBuiltinIdP` in core's
  identity service), never over HTTP; the discovery document may name only
  endpoints below the issuer.

## Configuration

`IdPConfiguration` (JSON file via `ABI_IDP_CONFIG`, or the environment):

| Environment | Meaning |
|---|---|
| `ABI_IDP_ISSUER` | the public issuer URL, `https://<host>/idp` (required; http on localhost only) |
| `ABI_IDP_CLIENT_ID`, `ABI_IDP_CLIENT_SECRET`, `ABI_IDP_REDIRECT_URIS` | the client ABI signs in as; seeded at start, the secret hashed |
| `ABI_IDP_SIGNUP`, `ABI_IDP_PASSWORD_LOGIN` | `1` to enable |
| `ABI_IDP_FROM_EMAIL`, `ABI_IDP_FROM_NAME`, `ABI_IDP_APP_NAME` | the sender and the name on the page |

Branding (`branding`, and `domain_branding` by email domain) in the JSON file:
colors, radius, logo URL, footer, tab title; the page loads no script and no
font, only the logo.

## Running it

| Where | How |
|---|---|
| `abi dev up` | automatic in NATS mode when the project names no other provider, or names `provisioning: builtin` (`dev_modules.with_builtin_idp`); the overlay configures the provider; mail goes to the local email adapter (`storage/email/`) |
| Docker (`abi deploy local`) | the `idp` service of `docker-compose.yml`, its own SDK-only container; create its key once the stack is up (`abi iam service-account create module/<project>/idp --key` into `.env` `IDP_SERVICE_KEY`, `abi iam module approve ...`) |
| By hand | `ABI_NATS_URL=... ABI_SERVICE_KEY=abi_sk_... ABI_DISCOVERY_PROJECT=... ABI_IDP_ISSUER=... python -m naas_abi_idp` |

Module id `idp` is reserved to this module: the seals and the secret endpoint
treat any account `module/<project>/idp` as the IdP, and only an admin creates
accounts.

Until the Nexus login is moved (subtask 13 of #44) a Nexus user whose email an
IdP user shares gets "email already belongs to another account": accounts are
never linked automatically.

## Tests

```bash
uv run pytest libs/naas-abi-idp/tests -q          # the provider, in memory
# The generic identity suite and Nexus's sign-in, against the built-in IdP:
uv run pytest libs/naas-abi-core/naas_abi_core/services/identity/tests/builtin_idp_contract_test.py --import-mode=importlib -q
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/oidc/oidc_sign_in_test.py -k BuiltinIdP --import-mode=importlib -q
```

`tests/` sits outside the package (as the SDK's). `adapters/memory.py` keeps the
semantics of the document service (create-only puts, versions, unique groups).

## Adding to it

- A new endpoint: a route in `web.py` (public) or `admin.py`, and for `web.py`
  the path in Nexus's allow-list (`services/idp/http_routes.py: ROUTES`): a path
  absent there is not served.
- A new stored record: a collection in `models.COLLECTIONS`, one document per
  atomic unit, `replace` for every change.
- Never import `naas_abi_core` or Nexus here.
