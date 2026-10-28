# Sign-in and credentials (Nexus as an OIDC relying party) - AGENTS.md

## Purpose

Nexus has **no login of its own**: no password, magic link, one-time code, reset, signup
or refresh token, and no token signed with `secret_key`. People sign in at an OIDC
identity provider the engine trusts (`identity.providers`: the built-in
[`libs/naas-abi-idp`](../../../../../../../../../naas-abi-idp/AGENTS.md) by default, or
Okta, Entra, Zitadel, Keycloak, ...), and Nexus is its relying party: authorization code
with PKCE, a server-held httpOnly session cookie with CSRF protection, nothing in
`localStorage`. The engine's side (verifying ID tokens, the `(issuer, sub)` to IAM user
mapping, the provider side of the PKCE flow) is
[`libs/naas-abi-core/.../services/identity/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/identity/AGENTS.md);
IAM, which authorizes, is [`.../services/iam/AGENTS.md`](../../../../../../../../../naas-abi-core/naas_abi_core/services/iam/AGENTS.md).
This file covers `services/oidc/` (the sign-in and the session) and `services/auth/`
(the account, and the credential every request presents).

## Files

| File | Role |
|---|---|
| `oidc/service.py` | `OidcSignInService`: `route`, `begin`, `complete`, `resolve` (the session a cookie names, refreshed when due), `logout`; the CSRF helpers; `PLACEHOLDER_EMAIL_DOMAIN` |
| `oidc/port.py` | `OidcSessionPersistencePort`, `IdentityGateway`, `PrincipalGateway`, the records (`OidcUser`, `SessionRecord`, `LoginRequest`) |
| `oidc/runtime.py` | `RUNTIME`: builds the service from the engine's identity and IAM; `session_secret`, `is_document_request`, the cookie-auth result; tests `configure` another |
| `oidc/adapters/primary/` | `/api/auth/oidc/{providers,route,login,callback,session,logout}` |
| `oidc/adapters/secondary/engine.py` | The engine's identity and IAM, in process (`EngineIdentityGateway`; `EngineIAMPrincipals` caches "is the principal active" for 5 s) |
| `oidc/adapters/secondary/postgres.py` | `users`, `auth_sessions`, `oidc_login_requests`, `organization_domains` |
| `oidc/migration.py` | `migrate_users`: what `abi user migrate` runs (see "Accounts of the old login") |
| `auth/credentials.py` | Which credential kinds exist and where Nexus honours them (`accepted_kinds`, `bearer_credential`, `revoke_user_credentials`) |
| `auth/` (rest) | The signed-in user's account: `GET\|PATCH /api/auth/me`, the avatar. Nothing else of `/api/auth` |
| `identity_events/middleware.py` | `RequestIdentityMiddleware`: resolves the credential into the request's `CallContext` (`api` acting on behalf of the user) and leaves the session on `request.state.nexus_session` |
| `api_keys/` | Personal API keys (`/api/iam/api-keys`) |
| `apps/links.py`, `coding_environment/agent_credentials.py` | Links and the coding agent's key, as IAM keys |
| `secrets/migration.py`, `core/secret_key.py` | The key of workspace secrets (see "Keys") |

## Sign-in

- `GET /api/auth/oidc/login?provider=&email=&next=` starts it. `route(email)` answers
  the provider of the email's verified organization domain (`organization_domains.provider`),
  else the engine's default provider; with neither `provider` nor `email` the default
  provider is used. The default provider never captures an email by itself (it would shut
  out every account it does not hold): it is a "Continue with ..." button and the target
  of a bare `/login`.
- The engine builds the authorization URL and **redeems the code** with the provider's
  client secret: Nexus never holds one. Nexus keeps the `state`, the `nonce` and the code
  verifier server-side (`oidc_login_requests`, single use, 10 minutes), bound to the
  browser by an httpOnly `nexus_oidc_binding` cookie (path `/api/auth/oidc`, `Lax`)
  that the callback must present (`browser_mismatch` otherwise). `next` is reduced to a
  path of the web app (`safe_next_path`: never another origin).
- Failures redirect to the web app's `/auth/login?sso_error=<code>` (`no_provider`,
  `unknown_provider`, `expired_request`, `browser_mismatch`, `sign_in_failed`,
  `token_rejected`, `suspended`, `email_in_use`, `provider_unavailable`).
- After the session exists, `on_signed_in` runs `invites.runtime.claimer`: the user's
  invitations are claimed (`services/invites/AGENTS.md`). Its failure never fails the
  sign-in.

## Users: one Nexus row per `(issuer, sub)`

- The row's `id` is the IAM principal id (`usr_...`, with `principal_id`, `idp_provider`,
  `idp_issuer`, `idp_subject`), so every place that keys a user by the call's id (the
  knowledge graph's `created_by`, the activity log, the kernel's personal resources) stays
  consistent. IAM resolves the real principal: its attachments, mapped groups and
  suspension apply on every kernel call Nexus makes for the user.
- **Emails are never linked or trusted by default.** Only a *verified* email is stored. A
  verified email another account holds refuses the sign-in (`email_in_use`) until an
  administrator links the accounts (`iam:LinkUser`). An absent or unverified email is
  stored as `<principal id>@unverified.internal` (`.internal` is reserved and never
  delegated), so no lookup, invitation or sign-in link by email finds the account.
  `trust_email` (provider setting) lets a provider whose directory controls the addresses
  count them as verified. A profile edit (`PATCH /me`) never changes the email: invitations
  find an account by email, and an address nobody proved would let a user take an
  invitation meant for another.
- Every sign-in refreshes the name, and a verified email the row did not have yet.

## The session

- The cookie `nexus_session` (`oidc_session_cookie`) holds a random secret; Nexus stores its
  SHA-256 (`auth_sessions.id`), the user, the IdP groups, and the provider's refresh and ID
  tokens **encrypted** under `secrets_encryption_key`. httpOnly, `Secure` (except over plain
  http on this machine, so `abi dev` works), `SameSite=lax` by default
  (`oidc_cookie_samesite`; a web app on another site than the API needs `none` and HTTPS on
  both, and the API's CORS allows `X-CSRF-Token`). It lasts `oidc_session_max_age_hours`
  (7 days) at most.
- **The provider vouches for the user again** at `refresh_at`: at most 10 minutes after each
  verification, earlier when the ID token expires sooner. A refresh the provider refuses ends
  the session; a provider that cannot be reached authenticates nothing until it answers.
  The refresh is **claimed** with a compare-and-set on `refresh_at` (a 30 s lease): of the
  requests and workers that find a session due, one refreshes, the others carry on with the
  session, so a provider that rotates refresh tokens never sees one replayed, and a claim
  whose holder died lapses by itself.
- Each request also checks that the IAM principal is active (cached 5 s): a suspension ends
  the session within 5 s, and the kernel denies the user's calls at once.
- **Logout** (`POST /api/auth/oidc/logout`, CSRF-checked) ends the session, revokes its
  refresh token at the provider, ends the user's remote-app grants, and returns the provider's
  `end_session_url` when it has one.
- The request then runs as `api` acting on behalf of the principal, with the mapped IAM
  group ids (`RequestIdentityMiddleware`). A session whose signature, expiry or principal
  fails names nobody: the request is `ANONYMOUS`, never `api`.

### CSRF and what a cookie never authenticates

- A cookie-authenticated request that changes state carries `X-CSRF-Token`: an HMAC of the
  session secret, never stored, derived again on every request. The web app reads it from
  `GET /api/auth/oidc/session` and keeps it **in memory only**. Without it the request names
  nobody and authenticated routes answer 403 (`request.state.nexus_csrf_failed`).
- **The cookie never authenticates a page or a frame.** A request the browser marks as a
  navigation (`Sec-Fetch-Mode: navigate`) or as a document, iframe, embed or object
  (`Sec-Fetch-Dest`) names nobody, and `/session` gives it no CSRF token: a link to an API
  URL never acts as the signed-in user, whatever it serves. The web app's own requests are
  `fetch` calls and keep working.
- **User bytes never run on the API origin**, which holds the cookie
  (`core/user_content.py`): routes that serve uploads send `user_content_headers` (sandbox
  CSP, `nosniff`, active types such as SVG, HTML, XML and script as `attachment`), and the
  security-headers middleware applies the same to any other `/api` response of an active
  type. Sandboxed apps (`/app-*`) keep their own policy.
- The web app holds the cookie session only and keeps no token (`stores/auth.ts`): use
  `authFetch`, or `withAuth` / `getAuthHeader(method)` + `authCredentials()` for a raw
  `fetch`, and `selectSession` / `hasSession` to know whether someone is signed in. The
  WebSocket handshake carries the cookie too.

## Credentials: which kind goes where

Every credential has a kind, derived from its audience, and Nexus honours it only where it
belongs (`auth/credentials.py`, `accepted_kinds(path)`):

| Kind | Credential | Accepted by |
|---|---|---|
| `session` | the cookie of an identity-provider login, or a session token the engine issued (`abi:session`, ES256) | every route, and the WebSocket |
| `api-key` | a personal API key (`abi_pk_...`), or the `abi:delegated:api-key` token it is exchanged for | `/api/*` except the session-only prefixes `/api/auth/` and `/api/iam/` |
| `coding` | a coding environment's key (`abi_pk_...`, audience `abi:delegated:coding`) | the OpenAI gateway only, `/api/v1/*`, which also takes a session and an API key |

- `RequestIdentityMiddleware` resolves the credential and leaves it on
  `request.state.nexus_credential`. A real credential of a kind the route does not take is
  refused with a 403 that names it (`nexus_credential_refused`), never read as a session.
  Never decode a bearer token by hand: `bearer_credential` verifies it against the engine's
  IAM (keys, and `abi:session` tokens), and a token signed by Nexus does not exist.
- **Everything else is not a session**: an app-html link, a preview link, a remote-app
  grant (they open their own routes) and an agent delegation (it is for the kernel and the
  module hosts) are refused here. A delegation names an actor (`act`) and is never a user's
  own credential.
- A key's own limit (`abi_scope`) travels in the call's `CallContext`, so it bounds every
  Nexus decision as it bounds every kernel one: a key narrowed to reading files reads like its
  user and writes nothing. A credential made here has a reach of its own, so a request that
  carries a limited credential may not make another (`refuse_a_limited_credential`).
- **Links are IAM grants** (`apps/links.py`): `/app-html/` links, `/app-preview/` tokens and
  `/app-remote/` grants are `abi_gk_<id>_<secret>` keys of the user who opened them, audience
  `abi:delegated:app` or `abi:delegated:preview`, bound to what they open (`resource`) and
  narrowed to what opening needs (`scope`: `discovery:OpenApp` on that app, or nothing), stored
  hashed, eight hours at most (`MAX_MINUTES`), revocable, ended with their owner, and **checked
  again at every request**, so revocation is immediate. No secret of Nexus signs one; the
  `*_expire_minutes` settings above eight hours still load and are clamped. A user holds at most
  1000 live links (`LinkLimitReached`, answered 429).
- **A coding environment's agent** holds a personal key of its owner made for it
  (`coding_environment/agent_credentials.py`): audience `abi:delegated:coding`, bound to its
  sidecar (`resource`; the gateway finds the exec sidecar from it and the `coding_environments`
  row, never from a claim a client supplies), narrowed to its workspace, revoked with the
  environment, a year at most.
- **Personal API keys** (`api_keys/`, `GET|POST /api/iam/api-keys`, `DELETE
  /api/iam/api-keys/{id}`, session-only; the page is `app/account/api-keys`). IAM keeps them
  hashed (`abi_pk_<id>_<secret>`, shown once), five active per user, expiry a year at most
  (the default), revocable. A key is *full access*, *read only* (every action IAM classes `read`
  or `list`) or *custom* (statements of the owner's writing), and never exceeds the owner's
  policies. Scripts present it as the bearer, or exchange it at `POST /api/iam/token`
  (`client_credentials`, ten-minute token). A key carries no IdP groups (it is not a session), so
  what a user holds only through a group claim does not reach their keys until it is a stored
  membership. Keys are not accepted on the engine's own HTTP routes (`/agents`, `/pipelines`,
  `/workflows`, `/tools`), which take `ABI_API_KEY`.
- **Revocation.** `revoke_all_user_tokens` calls `revoke_user_credentials` (IAM's
  `revoke_tokens`): every token of the user issued so far is refused, their grants and coding
  keys are revoked, their personal API keys stay (`include_keys` removes them too).
- **Calls Nexus makes over NATS for the signed-in user** carry a delegation
  (`engine_credentials.api_delegate`): IAM signs it in process, naming `api`, or for a module host
  that module (`api_host_token`), and the user. There is no `Abi-On-Behalf-Of` header.
- Settings-cache keys are the verified user (`RequestIdentityMiddleware`'s credential). Only a plain
  session is cached (`kind == session`, no `scope`), apart per set of IdP groups; a key, a coding key or
  a narrowed credential is answered live and never reads or fills a session's entries.

## Accounts of the old login

Before the login moved out, Nexus had its own users (a password hash, `urn:abi:nexus` as
their IAM issuer). They keep their roles, groups, keys and data by being **linked at their
first sign-in**:

1. `abi user migrate` (a dry run until `--apply`; `oidc/migration.py`) makes each account no provider
   signs in yet exist at the **built-in** provider with the same email and a new `sub`
   (`ProvisioningBuiltinIdP`): nobody twice, no password moved (the provider signs in with a mailed
   code). The API logs a reminder at start while accounts are unlinked.
2. At the first sign-in, when the built-in provider verified that address, `_link_legacy_user`
   links the identity to the account's IAM user with `iam.link_user` (`iam:LinkUser`: the user the
   old login made gets the provider's `(issuer, sub)` as one more identity, `find_user` answers the
   link first; the user the sign-in made a moment earlier is merged into it, roles and groups move,
   and one that holds keys refuses the link) and records the identity on the Nexus row, which keeps
   its id, its email and every row that points at it: nothing is re-keyed. A suspended account is
   not opened by linking it.

**Only the built-in provider links**: it proves an address by mailing a code
(`provisioning: builtin`); an external provider's verified email is never enough ("email already
belongs to another account" stays its answer), and accounts are never linked across providers. An
organization whose domain routes to an external provider therefore cannot link its old accounts:
its people sign in as new accounts, or an administrator links them with `iam.link_user`.
`iam.link_user` and `iam.identity_at` run in the engine that holds IAM: Nexus calls them in
process, `api` holds `iam:LinkUser`.

**Seeding goes through the provider.** `users:` in the configuration makes the Nexus account (no
password, the roles configured) and also makes the person exist at the built-in provider
(`org_seed.provision_seed_users`, as `api`, retried while the module comes up); the first sign-in
links it like any other. No admin password is generated by `abi new project`, `abi dev up` or
`abi deploy local`; `abi dev code` prints the code the provider mailed.

The legacy `urn:abi:nexus` naming stays for every account that has not signed in through a
provider yet, and for the linked ones too (their Nexus id is still the id every row and every
call names).

## Keys

`secret_key` signs nothing and encrypts nothing. Workspace secrets and the provider tokens of
sessions are encrypted (Fernet) under `secrets_encryption_key`, generated into the engine's secret
store as `NEXUS_SECRETS_KEY` when unset (`core/secret_key.py`). At start everything still under an
old key (the old `secret_key` as configured or persisted as `SECRET_KEY`, and the published
defaults) is re-encrypted under the current one (`secrets/migration.py`, called from
`main._move_secrets_to_the_secrets_key`): idempotent; a value no known key opens is left as it is,
counted and logged, and setting the old `SECRET_KEY` again moves it at the next start.
`credentials_test.py::test_the_secret_key_signs_and_reads_no_token` scans the application for a JWT
signer or a `secret_key` use.

Consequences for operators: a deployment with several replicas whose secret store is per replica
must set `NEXUS_SECRETS_KEY` (or `secrets_encryption_key`) **before** upgrading, else each replica
generates its own and re-encrypts the shared database under it; `SECRET_KEY` stays set until every
replica has started once; losing `NEXUS_SECRETS_KEY` loses the workspace secrets. The settings of the
removed login (`auth_password_enabled`, `magic_link_*`, `otp_*`, ...) are accepted and ignored with a
warning by `NexusConfig` so an older configuration loads; an old `NEXUS_USER_*_PASSWORD` in `.env`
can be deleted.

## What was removed from the database

Migration `0058_oidc_identity.sql` adds `users.principal_id`, `idp_provider`, `idp_issuer`,
`idp_subject`, `organization_domains.provider`, `auth_sessions` and `oidc_login_requests`.
`0059_iam_role_data.sql` marks the one-time move of memberships into IAM (`iam_migrations`);
`0060`/`0062` create `invitations`; `0061_remove_builtin_login.sql` drops `refresh_tokens`,
`revoked_tokens`, `password_changes`, `password_reset_tokens`, `magic_link_tokens`, the unused
`api_keys` mock and `users.hashed_password`. Sessions and tokens signed before the upgrade end:
people sign in again, links are reopened, coding environments get a new key.

## Limits, and what is not done

- No SCIM and no token introspection: group changes and offboarding reach ABI within ten minutes
  (token expiry and the session's `refresh_at`), or at once through an IAM suspension.
- A provider that cannot be reached authenticates nobody once `refresh_at` passes.
- The invitation of someone with no account needs a provider (400 otherwise); an existing
  account is added directly (`services/invites/AGENTS.md`).

## Tests

```bash
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/oidc --import-mode=importlib --no-cov -q
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/auth --import-mode=importlib --no-cov -q
uv run pytest libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/api_keys --import-mode=importlib --no-cov -q
```

`oidc_sign_in_test.py` runs the whole sign-in against an in-process provider and against the
built-in IdP (`-k BuiltinIdP`); `credential_boundaries_test.py` proves that nothing that is not a
session can be one (a coding key, an app-html link, a preview link, a remote-app grant and an agent
delegation on `/api/*` and on the WebSocket).
