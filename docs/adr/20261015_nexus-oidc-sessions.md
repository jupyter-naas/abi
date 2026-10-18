# Identity providers: the engine verifies, Nexus holds the session

Status: Accepted

Date: 2026-10-15

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §2, §9.2 and §12.1.
Builds on: [`20261013_identity-providers-and-builtin-idp.md`](20261013_identity-providers-and-builtin-idp.md), [`20261015_iam-transitional-bootstrap.md`](20261015_iam-transitional-bootstrap.md).
Guide: [`docs/identity-providers.md`](../identity-providers.md).

## Context

Subtask 7 of #44 lets users sign in through OIDC providers configured engine-wide under
`identity.providers`, next to Nexus's built-in login, which stays until subtask 13. Choices the RFC leaves
open:

- **Where the code is redeemed.** A relying party needs the provider's client secret. Nexus runs either
  inside the serving engine or against it over NATS.
- **Which id Nexus names a user by.** Nexus, the knowledge graph (`created_by`), the activity log and the
  kernel's personal resources all key a user by the id on the call. The built-in login's users keep Nexus
  ids, and IAM resolves them through the transitional `urn:abi:nexus` issuer.
- **Emails.** `users.email` is unique, and Nexus finds accounts by email: invitations, members. A
  provider's email is not always verified.
- **Authorization during the transition.** Until subtask 11, Nexus decides what its users may do, and IAM
  gives Nexus-named users a transitional grant. An IAM user from a provider holds no implicit grant.
- **CSRF**, with a session in a cookie.

## Decision

1. **Identity is a kernel service of its own (`services/identity`), next to IAM.** It authenticates and
   IAM authorizes.
   - It verifies ID tokens against each issuer's discovery document and JWKS: exact `iss`; an asymmetric
     algorithm the key allows; `aud` holding the client ID, and `azp` equal to it when present or when
     there are several audiences; `exp`, `nbf` and `iat` with 30 s of skew; the nonce.
   - The JWKS is cached for its `max-age` (5 minutes by default). An unknown `kid` refetches it, at most
     every 30 s.
   - It resolves `(issuer, sub)` to the IAM user, maps the groups claim and refuses suspended principals.
   - It is exposed over NATS as `abi.identity.v1.*` and to SDK modules as `engine.services.identity`.
   - Every operation is authorized with its own catalog (`identity:*` on
     `abi:-:-:identity:provider/<name>`). The IAM user is written as `engine` once the caller holds
     `identity:Authenticate`, as placements are.
2. **The engine runs the provider side of the relying party's sign-in** (`identity:SignIn`): the
   authorization URL, the code exchange with PKCE, refresh, revocation and end-session.
   - Client secrets never leave the engine.
   - Nexus keeps the state, the nonce and the code verifier server-side (`oidc_login_requests`, single
     use, 10 minutes), bound to the browser by an httpOnly cookie the callback must present.
3. **A Nexus account per `(issuer, sub)`, whose id is its IAM principal id** (`users.id = principal_id =
   usr_…`, with `idp_issuer` and `idp_subject`).
   - Every place that keys a user by the call's id stays consistent.
   - IAM resolves the real principal: its attachments, mapped groups and suspension apply on every kernel
     call Nexus makes for the user.
4. **Emails are never linked or trusted by default.**
   - Only a verified email is stored. A verified email another account holds refuses the sign-in
     (`email_in_use`) until an administrator links the accounts.
   - An absent or unverified email becomes `<principal id>@unverified.internal`. `.internal` is reserved
     and never delegated, so no lookup by email finds the account.
   - `trust_email` lets a provider whose directory controls the addresses (Entra ID) count them as
     verified.
   - The built-in login (password, code, magic link, reset) never opens an account a provider signs in,
     and `PATCH /me` never changes its email.
5. **The session is server-held** (`auth_sessions`).
   - The cookie carries a random secret, and Nexus stores its SHA-256. The provider's refresh token and ID
     token are encrypted at rest with the workspace-secret key (encryption only: no token is signed with
     `secret_key`).
   - The cookie is httpOnly, Secure and SameSite (`lax` by default, configurable).
   - The provider vouches for the user again at `refresh_at`: at most 10 minutes after each verification,
     and earlier when the ID token expires sooner. A refused refresh ends the session; a provider that
     cannot be reached authenticates nothing until it answers.
   - Each request also checks that the IAM principal is active (cached 5 s), so a suspension ends the
     session within 5 s; kernel calls for the user are denied at once.
   - The request runs as `api` on behalf of the principal, with its mapped group ids.
6. **CSRF**: every cookie-authenticated request that changes state carries `X-CSRF-Token`.
   - The token is an HMAC of the session secret: never stored, derived again on every request.
   - The web app reads it from `GET /api/auth/oidc/session` and keeps it in memory only.
   - Without it the request names no user, and authenticated routes answer 403.
7. **TRANSITIONAL (#65).** At each sign-in Nexus attaches `builtin.transitional.nexus_user` to the
   principal. The user side of a Nexus call then allows what it allows a built-in login user, until
   subtask 11 attaches the roles of each membership and detaches it.
8. **Routing.** `organization_domains.provider` sends the logins of a verified domain to a provider.
   Otherwise `identity.default_provider` is used, and without one the built-in login.

## Consequences

- The web app keeps no token on a provider sign-in. It persists only the user and the kind of session.
  Requests include the API's cookie, and the WebSocket handshake carries it too.
- A web app on another site than the API needs `oidc_cookie_samesite: none` and HTTPS on both. The API's
  CORS allows `X-CSRF-Token`.
- Over NATS the transitional `Abi-On-Behalf-Of` header names the user but not its mapped groups, which
  travel only in process until delegated tokens (subtask 8).
- Migration `0049_oidc_identity.sql` also creates `organization_domains`, which only the ORM model declared
  before.
- The generic identity suite (`services/identity/tests/identity_contract.py`) runs against an in-process
  provider on every run and against Zitadel 4.19.4 from its native binary, with PostgreSQL 17.6 from
  Zonky's native builds. The helper pins SHA-256s and caches both under `~/.cache/naas-abi/test-binaries`.
  Subtask 9 runs the same suite against the built-in IdP.
