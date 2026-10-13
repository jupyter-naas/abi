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
