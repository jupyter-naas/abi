# Login belongs to OIDC providers; the built-in IdP is an SDK module

Status: Accepted

Date: 2026-10-13

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §2 and §12.

## Context

Nexus is its own identity provider:

- passwords, magic links, one-time codes, password reset, signup and refresh tokens;
- HS256 tokens signed with `secret_key`, which also derives the key that encrypts workspace secrets;
- tokens kept in `localStorage`;
- no SSO, OIDC or SAML.

Most of the authentication bugs we have fixed or still carry live in that code:

- open registration;
- one-time-code brute force;
- default secrets;
- scoped tokens accepted as sessions.

Enterprise users want SSO, MFA and offboarding in the tools they already run.

Small installs and `abi dev up` have no IdP and run without Docker. The flow they rely on is: register
someone with just an email, and they sign in with a code sent to that email.

## Decision

- **The engine and Nexus are not identity providers.**
  - They verify tokens from OIDC providers configured engine-wide under `identity.providers`, using each
    issuer's discovery document and JWKS.
  - Nexus is an OIDC client: authorization code with PKCE, a server-held httpOnly session cookie with CSRF
    protection, and nothing in `localStorage`.
- **Users.**
  - A user is identified by `(issuer, sub)`, never by email.
  - IAM creates the user principal on first login. It holds no password.
  - Accounts are never linked automatically across providers.
- **Organizations stay an ABI concept.**
  - Providers are not configured per organization.
  - `organization_domains` gains a provider column and routes a login by email domain. Otherwise the default
    provider is used.
- **The built-in IdP** is a core-free SDK module, the package `libs/naas-abi-idp`.
  - It depends on the SDK, the proto package and `authlib` only.
  - It runs over NATS under its own service account `idp`.
  - It offers email-code sign-in (password optional, off by default), authorization code with PKCE, refresh
    tokens, discovery, ES256 JWKS, and admin RPCs used by provisioning.
  - SAML, brokering other IdPs and MFA policies are out of scope.
- **Its data and keys are private.**
  - Its data lives in its own Document Service namespace, and its signing keys in the secret service under
    `idp/`.
  - Both are sealed to its principal: not even `api` or `engine` can read them.
  - It never uses Nexus `secret_key`, and Nexus never reads its data.
- **It gets a dedicated trusted route.** Nexus serves it at `/idp` on its own host, forwarded over
  `abi.app.v1`. The sandboxed `/app-remote/<grant>/` path of remote apps forbids what a login page needs:
  - access before sign-in;
  - cookies;
  - form posts.

  Only the module running as service account `idp` may answer there.
- **No external IdP is bundled.**
  - We document Okta, Entra, Zitadel and Keycloak.
  - Zitadel, a single pinned native binary, is the external reference IdP for the generic identity test
    suite in CI. The same suite runs against the built-in IdP.
- **Revocation.** Access tokens live 10 minutes at most, and IAM can suspend a principal immediately. There is
  no SCIM and no token introspection.

## Consequences

- **Nexus's login code goes away** (subtask 13 of #44): passwords, magic links, codes, reset, signup and
  refresh-token tables.
  - Existing users move to the built-in IdP with the same email and a new `sub`, linked on first login by
    verified email within that provider only.
  - `secret_key` stops signing tokens, and workspace-secret encryption gets its own key.
- **Users sign in again** after the upgrade.
- **Group changes and offboarding** reach ABI within 10 minutes through token expiry, or at once through IAM
  suspension.
- **Invitations** go through a provisioning port (`builtin`, `zitadel`, `keycloak`, `none`) with pending
  grants claimed on first login by a verified email.
- **CI downloads a Zitadel binary** for the identity tests, as it does `nats-server`.
- **The trusted route is the one place** Nexus forwards cookies and form posts to a module. It is bound to the
  `idp` service account and configured, never discovered.

## As built (2026-10-19, #63)

Implemented as decided, with these differences and details:

- **It runs as a module account, not as a service account named `idp`.** The module `idp`
  (`libs/naas-abi-idp`, `module_id = "idp"`) runs as `module/<project>/idp`, like every
  remote module: it submits its permission manifest (the default one for `document`,
  `secret` and `email`), an admin approves it (`abi dev up` does), the broker confines it,
  and discovery binds the module id to that account. The built-in account `idp` (policy
  `builtin.idp`) stays for a deployment that prefers it.
  - The seals of its namespace (`document`) and secrets (`secret`, `idp/`) name the account
    `idp` **and** the module id `idp` (`Seal.module_id`), and the secret endpoint's
    allow-list treats a module account of that id as the IdP (`secret_nats_contract.is_idp`).
    Module id `idp` is therefore reserved: an admin creates its account, nothing else does.
    `api` and `engine` read neither, whatever their policies say.
- **The trusted route** is `/idp/...` on the API host (`services/idp`). Allow-lists decide
  which paths, request headers, response headers and cookies pass; the CSP is Nexus's; the
  API's sandboxing of active content and its global CSP skip this path alone. Only the
  instance running as `module/<project>/idp` is served, and only while a provider has
  `provisioning: builtin`. The module's apps leave the apps catalog and no generic remote-app
  route opens them (`INTERNAL_MODULES`).
- **The admin RPCs are a second app of the module** (`admin`, JSON over `abi.app.v1`), never on
  the public route. Discovery's `OpenApp` on that app authorizes the caller; the app also
  refuses a call made on behalf of a user, since any user may open apps. The default manifest
  of a module that depends on `idp` denies it.
- **The engine reads the IdP over NATS.** `OIDCHttpBuiltinIdP` replaces the HTTP port for the
  built-in provider's issuer, through `IdPAppNATS`, attached by the serving engine once its
  NATS runtime is up. A built-in provider's discovery document may only name endpoints below
  its issuer. At most one provider is built-in, and its issuer path is `/idp`.
- **Defaults.** `abi dev up` runs the module and, for a project that names no provider,
  configures it through the dev overlay (the project's config stays untouched);
  `abi new project` generates the client secret and depends on `naas-abi-idp`; the Docker
  stack runs it in its own SDK-only container, and its Docker configs name it.
- **Codes.** Six digits, 15 minutes, stored as an HMAC under a key in the secret service.
  Wrong guesses count against the address, across every active code, before they are judged
  (so parallel guesses spend one budget); the budget spent voids all codes. Registering with
  just an email is `signup_enabled` (on in `abi dev up`, off elsewhere).
- **Tokens.** ID and access tokens are ES256, ten minutes at most; refresh tokens rotate and a
  replay revokes the family; PKCE (S256) is required of every client; no introspection.

Consequences added:

- A person whose email already belongs to a Nexus account cannot sign in through the IdP until
  accounts are linked (subtask 13 of #44).
- A deployment outside Docker or `abi dev` creates the `module/<project>/idp` account and key
  itself (`abi iam service-account create ... --key`, `abi iam module approve`).
