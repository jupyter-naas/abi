# Login moves out of Nexus

Status: Accepted

Date: 2026-10-19

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §12.1 and §13.
Builds on: [`20261013_identity-providers-and-builtin-idp.md`](20261013_identity-providers-and-builtin-idp.md), [`20261015_nexus-oidc-sessions.md`](20261015_nexus-oidc-sessions.md), [`20261019_delegated-tokens-and-api-keys.md`](20261019_delegated-tokens-and-api-keys.md), [`20261019_provisioning-and-invitations.md`](20261019_provisioning-and-invitations.md).
Supersedes: [`20260924_auth-signup-and-rate-limits.md`](20260924_auth-signup-and-rate-limits.md) and the Nexus password parts of [`20260924_no-default-credentials.md`](20260924_no-default-credentials.md).

## Context

Subtask 13 of #44 ends Nexus as an identity provider. By now people can sign in through the engine's OIDC
providers (the built-in IdP, subtask 9), sessions are cookies the API holds (subtask 7), every narrow credential
is an IAM grant or key (subtask 8) and invitations make people at the provider (subtask 10). What Nexus still
had of its own:

- a password, magic-link and one-time-code login, password reset and public signup (`services/auth`), refresh
  tokens, and an HS256 session signed with `secret_key`;
- the tables behind them (`refresh_tokens`, `revoked_tokens`, `magic_link_tokens`, `password_reset_tokens`,
  `password_changes`, the unused `api_keys` mock, `users.hashed_password`) and their rate limits;
- a seeder that made `admin@example.com` with a generated password written to `.env`, and the CLI that
  generated, printed and logged in with it;
- one key, `secret_key`, that signed those sessions *and* derived the Fernet key that encrypts workspace
  secrets (and, since #61, the provider tokens of cookie sessions).

## Decision

1. **Sign-in is OIDC only.** The password, magic-link, one-time-code, reset, signup and refresh-token code is
   deleted from Nexus, with its tables (migration `0052_remove_builtin_login.sql`, also dropping
   `users.hashed_password`), its settings (accepted and ignored with a warning by `NexusConfig`, so an older
   configuration still loads), the web pages and the `abi user create` command. What stays of `/api/auth` is
   the account itself: `GET|PATCH /me` and the avatar. The web app holds a cookie session and nothing else;
   scripts hold a personal API key (`abi_pk_`), and a session token only the engine issues
   (`abi:session`, ES256) is the one bearer session. Nexus signs no token.
2. **An email no domain maps goes to the default provider.** There is no built-in login left to fall back
   to, so `route(email)` answers the verified organization domain's provider, else the engine's default.
3. **The old accounts keep everything by being linked, at the first sign-in, by verified email, at the
   built-in provider only.** `abi user migrate` (a dry run until `--apply`) makes each account no provider signs
   in yet exist at the built-in provider with the same email and a new `sub`; it creates nobody twice and moves no
   password (the provider signs in with a mailed code). At the first sign-in, when the provider verifies that
   address, Nexus:
   - links the identity to the account's IAM user with `IAMService.link_user` (`iam:LinkUser`): the user the
     built-in login made (issuer `urn:abi:nexus`) gets the provider's `(issuer, sub)` as one more identity
     (`iam_identity_links`; `find_user` answers the link first), so its roles, groups and keys stay. The
     user the sign-in itself made a moment earlier is merged into it (roles and groups move, it is retired;
     one that holds keys refuses the link);
   - records the identity on the Nexus row, which keeps its id, its email and every row that points at it:
     nothing is re-keyed. A suspended account is not opened by linking it.
   Only the built-in provider links (`provisioning: builtin`, which proves an address by mailing a code);
   an external provider's verified email is never enough, and "email already belongs to another account"
   stays its answer. Accounts are never linked across providers.
4. **Seeding goes through the provider.** `users:` in the configuration still makes the Nexus account (no
   password, the roles configured) and now also makes the person exist at the built-in provider
   (`org_seed.provision_seed_users`, as `api`, retried while the provider module comes up); the first
   sign-in links it like any other. `abi new project`, `abi dev up` and `abi deploy local` generate no admin
   password; `abi dev up` says how to sign in and `abi dev code` prints the code the provider mailed (dev mail
   is a file in `storage/email`). `abi deploy local --regenerate` drops the dead password keys.
5. **`secret_key` signs nothing and encrypts nothing.** Workspace secrets and the provider tokens of sessions
   have a key of their own, `secrets_encryption_key` (generated into the secret store as `NEXUS_SECRETS_KEY`
   when unset). At start, everything still under an old key (the old `secret_key` as configured or persisted,
   and the published defaults) is re-encrypted under it (`services/secrets/migration.py`): idempotent, nothing
   is lost when no known key opens a value (it is counted and logged, and setting the old `SECRET_KEY` again
   moves it at the next start). A test scans the application for a JWT signer or `secret_key` use.
6. **The invitation of someone with no account needs a provider.** The magic-link fallback is gone: with no
   provider configured the invite answers 400. Someone who already has an account is added directly, and told
   so by an email with a sign-in link (no code, no secret).
7. **Settings cache keys are the verified user** (`RequestIdentityMiddleware`'s credential), where they were
   the unverified `sub` of a bearer token: a cookie session is cached like any other. Only a plain session is
   cached (`kind == session`, no `scope`), apart per set of IdP groups; a key, a coding key or a narrowed
   credential is answered live and never reads or fills a session's entries, so a key's narrowing cannot be
   bypassed by the user's own cached list.

## Consequences

- An upgraded project runs `abi user migrate --apply` once (the API logs a reminder at start while accounts are
  unlinked), after which its people sign in with a code and find their roles and data as they were. Sessions
  and tokens signed before the upgrade end: people sign in again.
- A project that configured the removed settings loads and logs which keys were ignored; its `.env` may keep an
  old `NEXUS_USER_*_PASSWORD` that nothing reads: it can be deleted.
- **A deployment with several replicas whose secret store is per replica must set `NEXUS_SECRETS_KEY` before
  upgrading** (or `secrets_encryption_key`): otherwise each replica generates its own key and re-encrypts the shared
  database under it, and the others find the values unreadable. The same goes for `SECRET_KEY`, which must stay set
  (identically) until every replica has started once.
- An organization whose domain routes to an external provider cannot link its old accounts (only the built-in
  provider proves an address by mailing a code): its people sign in as new accounts, or an administrator links them
  with `iam.link_user`.
- `secret_key` can be unset once the start logged that nothing is left under it. Losing
  `NEXUS_SECRETS_KEY` loses the workspace secrets, as losing `secret_key` did.
- `iam.link_user` and `iam.identity_at` run in the engine that holds IAM (not over NATS): Nexus calls them
  in process. `api` holds `iam:LinkUser`, and only the sign-in's built-in-provider rule decides when it is used.
- The legacy `urn:abi:nexus` naming stays for every account that has not signed in through the provider yet, and
  for the linked ones too (their Nexus id is still the id every row and every call names); a later release may
  retire it once nobody is unlinked.
- API keys cannot call `/api/auth/*` (session-only): `abi user me` was removed, and the CLI no longer logs in
  with a password (`NEXUS_ACCESS_TOKEN` or `--token`).
