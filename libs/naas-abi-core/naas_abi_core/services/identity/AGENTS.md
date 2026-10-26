# Identity Service - AGENTS.md

## Purpose

The OIDC identity providers the engine trusts, configured engine-wide under
`identity.providers`. The engine is not an identity provider: it verifies providers' ID tokens and
resolves them to IAM users. Authorization stays with IAM (`services/iam`).

- **A user is `(issuer, sub)`**, never an email. The IAM user is created on
  first sign-in (`iam.ensure_user`) and holds no password. The same person
  through two providers is two principals: nothing links them automatically.
- **Verification** reads each issuer's discovery document and JWKS, follows key
  rotation, and checks `iss`, the signature, `aud`/`azp`, `exp`, `nbf`/`iat`
  (30 s of skew) and the nonce.
- **Groups**: the provider's `groups_claim` values map to IAM groups through
  `iam.map_idp_group`; the mapped ids come back with the user (the engine
  token's `grp`).
- **Suspension**: a token naming a suspended or deleted IAM user is refused.
- **Relying parties** (Nexus) run authorization code + PKCE through this
  service: it builds the authorization URL, redeems the code, refreshes and
  revokes at the provider. **Client secrets never leave the engine**, so a
  relying party works the same in process and over NATS.

## Files

| File | Role |
|---|---|
| `IdentityPorts.py` | Records (`IdentityProvider`, `ProviderInfo`, `ProviderMetadata`, `VerifiedToken`, `AuthenticatedUser`, `TokenSet`, `SignIn`), errors, `OIDCHttpPort`, `IIdentityService`, `claim_values` |
| `provider_keys.py` | `ProviderKeys`: one provider's discovery document and JWKS, cached; `parse_metadata`, `check_endpoint_url` |
| `token_verifier.py` | `TokenVerifier`: the ID token checks, for every configured provider |
| `IdentityService.py` | The domain service: providers, `verify_token`, `authenticate`, the relying-party sign-in |
| `token_authenticator.py` | `IdentityTokenAuthenticator`: what IAM calls to exchange an IdP token for an `abi:session` token; the engine wires it in `EngineServiceLoader` |
| `iam_catalog.py` | The `identity:*` catalog, registered with the kernel catalogs |
| `adapters/secondary/OIDCHttpHttpx.py` | `OIDCHttpPort` over httpx |
| `adapters/secondary/OIDCHttpBuiltinIdP.py` | `OIDCHttpPort` for the built-in IdP (`provisioning: builtin`): its issuer is read over NATS, everything else over the fallback |
| `adapters/secondary/IdPAppNATS.py` | An app of the IdP module (`idp`, `admin`) called over NATS as the engine, bound to the instance running as `module/<project>/idp` |
| `adapters/secondary/AdminHttp.py` | A provider's admin API over httpx (fixed base URL, no redirects, bounded answers) and `ClientCredentialsToken` |
| `adapters/secondary/ProvisioningBuiltinIdP.py`, `ProvisioningZitadel.py`, `ProvisioningKeycloak.py` | `ProvisioningPort` for each `provisioning` setting; `none` is `ProvisioningNone` in `IdentityPorts.py`, the default of a provider with no adapter |
| `adapters/secondary/IdentitySecondaryAdapterNATSClient.py` | `IIdentityService` over NATS, for client-role engines |
| `adapters/primary/identity__primary_adapter__NATS.py` | `abi.identity.v1.*` |
| `adapters/identity_nats_codec.py` | Records and errors on the wire |
| `tests/identity_contract.py` | **The generic identity suite** every provider passes, and its `IdentityProviderHarness` |
| `tests/fake_idp.py` | An OIDC provider over real HTTP in this process (RS256/ES256, rotation, PKCE, refresh, revocation) |
| `tests/zitadel_server.py` | Zitadel and PostgreSQL from pinned native binaries, and the Zitadel harness |
| `tests/builtin_idp_server.py` | The built-in IdP (`naas-abi-idp`) over real HTTP in this process, its harness, and `AdminApp` (its admin app called in process) |
| `tests/zitadel_provisioning_test.py` | The Zitadel adapter against the pinned Zitadel binary |

Engine configuration: `engine/engine_configuration/EngineConfiguration_Identity.py`.

## Port

**`OIDCHttpPort`** (secondary): `get_json(url) -> HttpJSON(body, max_age)` and
`post_form(url, data, basic_auth=) -> (status, body)`; both raise
`ProviderUnavailableError` when the provider cannot be reached.

**`ProvisioningPort`** (secondary): `ensure_user(email, name=)` makes the person exist at
the provider (creating them when it has none) and `find_user(email)` looks. One adapter
per provider's `provisioning` setting: `builtin` calls the IdP's admin app
over NATS, `zitadel` and `keycloak` their admin APIs, `none` raises `NotImplementedError`
(that provider's users are managed in the provider). A `ProvisionedUser` names the
provider's id for the person (the `sub` of their tokens), whether this call created them
and whether the provider has them disabled. Errors: `ProviderUnavailableError`,
`ProvisioningError`, `ValueError` for an address the provider refuses.

**`IIdentityService`**: what callers use, implemented in process by
`IdentityService` and over NATS by `IdentitySecondaryAdapterNATSClient`.

Errors: `TokenRejectedError(reason)` with `reason` one of `malformed`,
`unknown_issuer`, `unknown_key`, `invalid_signature`, `wrong_audience`,
`expired`, `not_yet_valid`, `nonce_mismatch`, `missing_claim`, `algorithm`;
`PrincipalSuspendedError`; `SignInError(error, description)` (the provider's
OAuth error); `UnknownProviderError`; `ProviderUnavailableError`.

## Service API

```python
identity = engine.services.identity  # IIdentityService

identity.list_providers()  # ProviderInfo, never the client secret
identity.default_provider  # the provider a login page offers as a button
user = identity.authenticate(id_token, nonce=nonce)  # AuthenticatedUser
user.principal_id, user.issuer, user.subject, user.group_ids

# A relying party's sign-in (Nexus): it keeps state, nonce and verifier.
url = identity.authorization_url(
    "acme",
    redirect_uri=...,
    state=...,
    nonce=...,
    code_challenge=s256(verifier),
    login_hint=email,
)
sign_in = identity.exchange_code(
    "acme", code=..., code_verifier=verifier, redirect_uri=..., nonce=nonce
)
sign_in.user, sign_in.tokens.refresh_token, sign_in.refresh_at
identity.refresh("acme", refresh_token=..., principal_id=sign_in.user.principal_id)
identity.revoke("acme", refresh_token=...)
identity.provision_user("acme", "bob@example.com", name="Bob")  # ProvisionedUser
identity.find_provisioned_user("acme", "bob@example.com")  # or None
identity.end_session_url("acme", id_token_hint=..., post_logout_redirect_uri=...)
```

- **Authorization.** Every call is checked with the `identity` catalog on
  `abi:-:-:identity:provider/<name>` for the current `CallContext`:
  `ListProviders`, `GetProvider`, `VerifyToken` (no side effect),
  `Authenticate` (creates or refreshes the IAM user, as `engine`) and `SignIn`
  (the relying-party operations). `exchange_code` and `refresh` resolve the
  user too, so they need `SignIn` **and** `Authenticate`; the authorization URL,
  revocation and end-session need `SignIn` only. A caller with none gets "not found". `api` and
  `engine` hold them through their enumerated policies; a module needs a grant.
  `ProvisionUser` (admin) and `FindProvisionedUser` (read) are an administrator's: the
  inviting person's own rights (`iam:AttachPolicy` at the scope) are checked where the
  invitation is made (Nexus, `abi iam invite`), and the provisioning call is made as `api`
  or `engine` for nobody.
- **Pending grants.** `authenticate` (so a code exchange and a refresh too) calls
  `iam.claim_pending_grants` for the user it resolved, as the engine: what an invitation
  granted that email on that provider attaches at the first sign-in with it verified
  (`services/iam/AGENTS.md`).
- **`refresh_at`** is the ID token's expiry, at most ten minutes after the
  sign-in: a relying party re-verifies at the provider by then.
- **A refresh** that returns an ID token must name the same user
  (`subject_changed` otherwise). One that returns none (OIDC Core §12.2) is
  accepted: the provider took the refresh token and the subject cannot change,
  so the service only checks that the session's principal is an active user of
  this provider's issuer: its own identity there, or one linked to it
  (`iam.identity_at`; a user of Nexus's old login linked at its first sign-in). `tokens.id_token` is then `None` and no groups are
  re-read: the relying party keeps the ones it holds.
- **Key cache.** The JWKS is cached for its `Cache-Control: max-age` (300 s
  when none, an hour at most; `no-store`, `no-cache` and `max-age=0` mean no
  caching, so every verification reads it again). An unknown `kid` refetches it at most once every
  `jwks_refetch_seconds` (30). Known keys keep verifying for 15 minutes past
  their cache while the provider is unreachable.

## Adapters and configuration

```yaml
identity:
  default_provider: acme
  providers:
    - name: acme                      # ^[a-z0-9-]{1,32}$, unique
      issuer: https://acme.okta.com   # https; http on localhost only; unique
      client_id: abi
      client_secret: "{{ secret.ACME_OIDC_SECRET }}"   # omit for a public client
      groups_claim: groups            # a claim name, or a dotted path
      scopes: [openid, email, profile, offline_access]
      provisioning: none              # builtin | zitadel | keycloak | none
      # admin:                        # zitadel: token (+ url, org_id); keycloak: client_id,
      #   token: "{{ secret.ZITADEL_PAT }}"  # client_secret (+ url, realm, send_actions)
  verifier:
    clock_skew_seconds: 30
    jwks_cache_seconds: 300
    jwks_refetch_seconds: 30
    http_timeout_seconds: 10
```

Validated when the configuration loads. The service is always loaded, right
after IAM; with providers, each one's discovery document and JWKS are read in a
background thread at boot and failures are logged (a provider that is down
does not stop the engine). The serving engine exposes it over NATS
(`EngineNATSLoader`); a client-role engine gets the NATS client; modules in a
serving engine get the owner itself (`EngineNATSDependencies`), like IAM.

**The built-in IdP** (`provisioning: builtin`, `libs/naas-abi-idp`): at most one
provider, its issuer path is `/idp` (Nexus serves it there). The service's HTTP
port becomes `OIDCHttpBuiltinIdP`: a URL below the issuer goes through the
module's `idp` app over NATS (the serving engine attaches `IdPAppNATS` in
`Engine.__serve`, after its NATS runtime is up; before that the provider is
"down" and read again on first use), any other URL over httpx. A built-in
provider's discovery document may only name endpoints below its issuer
(`parse_metadata`), so it cannot send the engine, or the client secret,
elsewhere. Only the discovery instance whose service account is
`module/<project>/idp` is called.

**Provisioning** (`provisioning:`): `builtin` needs nothing more (the serving engine
attaches the IdP's `admin` app next to its `idp` app, `Engine.__attach_builtin_idp`; the IdP
admits only the engine's own accounts, `naas_abi_idp.admin`); `zitadel` needs
`admin.token` (a machine user's personal access token, `ORG_USER_MANAGER`), `keycloak`
`admin.client_id` and `admin.client_secret` (a service-account client with
`manage-users` and `view-users`); `none` takes no `admin`. Validated at load. Zitadel makes
the user with an unverified email and `sendCode`, Keycloak with `emailVerified: false` and
its verify/update-password mail, so only the mailbox's owner verifies it; the built-in IdP
verifies by mailing a code at every sign-in. Over NATS a refusal of a provider that
cannot be provisioned is the wire code `UNIMPLEMENTED` (`NotImplementedError`).

Step-by-step guides for Okta, Entra ID, Zitadel and Keycloak are user documentation:
https://docs.naas.ai. What a provider must offer is in "What ABI expects of a provider".

## What ABI expects of a provider

| | |
|---|---|
| Discovery | `<issuer>/.well-known/openid-configuration`, naming exactly the configured `issuer` |
| Client | A confidential web client (client ID and secret), authorization code grant, PKCE with S256 (a public client has no secret) |
| Redirect URI | `<Nexus API URL>/api/auth/oidc/callback` (`oidc_redirect_uri` in the Nexus configuration overrides it); post-logout redirect URI `<Nexus web URL>/auth/login` |
| Refresh tokens | Required: a relying party re-verifies each user at the provider at least every 10 minutes. Ask for `offline_access` where the provider needs it. A refresh may leave the ID token out (OIDC Core §12.2). |
| ID token | Signed with an asymmetric key (RS256, ES256, PS256 or EdDSA) published in the JWKS. `aud` holds the client ID; `azp`, when present, is the client ID. |
| Email | `email` with `email_verified: true` (see "Users, groups and emails") |
| Groups (optional) | A claim listing the user's groups, named by `groups_claim` (a claim name or a dotted path such as `realm_access.roles`) |
| Token lifetime | Ten minutes or less is recommended: a relying party refreshes at most ten minutes after each verification whatever the provider's lifetime |

Provider-specific traps worth knowing when debugging: Entra ID needs the tenant-specific
issuer (`https://login.microsoftonline.com/<tenant>/v2.0`; the multi-tenant `common` and
`organizations` endpoints publish a templated issuer no token matches, so they are refused),
sends no `email_verified` (set `trust_email: true`) and gives group object IDs, with an
overage claim instead of `groups` above 200 groups; Okta's org authorization server cannot
carry a custom groups claim (use a custom one); Zitadel puts project roles in
`urn:zitadel:iam:org:project:roles` (the role keys are the groups); Keycloak's groups mapper
should have "Full group path" off, and realm roles are `realm_access.roles`.

## Users, groups and emails

- **A user is `(issuer, sub)`**, never an email. The first sign-in creates the IAM user
  (`usr_...`) and a Nexus account with the same id (`users.id = principal_id`, with
  `idp_issuer` and `idp_subject`), so every place that keys a user by the call's id stays
  consistent and IAM resolves the real principal: its attachments, mapped groups and
  suspension apply on every kernel call Nexus makes for the user.
- **Groups.** Map a value of the provider's groups claim to an IAM group
  (`iam.map_idp_group("acme", "data-engineers", group_id)`, needs `iam:MapIdpGroup`), or bind it
  to a role at a scope (`iam.bind_idp_group`, "Invitations and IdP group bindings" in
  `services/iam/AGENTS.md`). The mapped groups apply for as long as the session's last
  verification, ten minutes at most; a personal API key is not a session and carries none.
- **Offboarding.** Disabling a user at the provider ends their Nexus session at the next refresh
  (within ten minutes). Suspending the IAM user ends it within five seconds, and every kernel call for
  the user is denied at once.
- **Emails are never linked or trusted by default.** Only an email the provider verified is stored by a
  relying party: a verified email another account holds refuses the sign-in (`email_in_use`) until an
  administrator links the accounts; an absent or unverified one becomes
  `<principal id>@unverified.internal` (`.internal` is reserved and never delegated, so no lookup by email
  finds the account), and so does an address Nexus cannot represent (`.test`, `.local`).
  `trust_email: true` counts a provider's `email` as verified, for a directory that controls its
  addresses (Entra ID); do not set it where users choose their own address. The one exception to "never
  linked" is the old Nexus login's accounts: the built-in provider's verified email links such an
  account to its IAM user (`iam.link_user`, "Built-in policies" in `services/iam/AGENTS.md`;
  `abi user migrate` makes the people at the built-in provider first).
- Nexus has no login of its own: no password, code, magic link or reset reaches a provider's account.

## Relying parties (Nexus)

The engine does the provider side of the sign-in; a relying party (Nexus) keeps the rest. What it must do
for the contract to hold:

- Keep the state, the nonce and the code verifier server-side, single use, bound to the browser by an
  httpOnly cookie the callback must present (Nexus: `oidc_login_requests`, 10 minutes).
- Hold the session server-side (Nexus: `auth_sessions`): the cookie carries a random secret, only its
  SHA-256 is stored, and the provider's refresh and ID tokens are encrypted at rest. Vouch for the user
  again at `refresh_at` (at most ten minutes after each verification; a refused refresh ends the session,
  an unreachable provider authenticates nothing); claim a refresh with a compare-and-set (a 30 s lease) so
  one of many workers refreshes and providers that rotate refresh tokens never see one replayed; check that
  the IAM principal is active on each request (cached five seconds), so a suspension ends the session within
  five seconds.
- Run the request as `api` on behalf of the principal with its mapped group ids; protect state-changing
  cookie requests with a CSRF token derived from the session (an HMAC, never stored) and never let the
  cookie authenticate a navigation or a frame; never serve user bytes on the API origin that holds the cookie.
- A web app on another site than the API needs `oidc_cookie_samesite: none` and HTTPS on both. Nexus
  settings: `oidc_session_cookie` (`nexus_session`), `oidc_cookie_samesite` (`lax`),
  `oidc_session_max_age_hours` (168), `oidc_redirect_uri`.

**Login routing.** The login page asks for an email first: a verified organization domain whose `provider`
is set (`organization_domains.provider`, `PUT /api/organizations/{org_id}/domains/{domain_id}/provider`)
sends the login to that provider; otherwise the email goes to `default_provider`. With neither, the page
says no provider is configured. The default provider is also a "Continue with ..." button and where a bare
`/login` goes, but it never captures an email's route on its own (it would shut out every account the provider
does not hold). Organizations stay an ABI concept: a provider is not per organization.

## Invitations and provisioning

An administrator invites someone who has no account yet (Nexus People, Invite, or `abi user invite`; the
lower level `abi iam invite`). Three things happen:

1. **IAM keeps the roles** as pending grants (`builtin.<role>` at the organization's or workspace's scope, for
   that email on that provider), claimed by whoever first signs in through that provider with the address verified.
2. **The person is created at the provider** through `ProvisioningPort`, per `provisioning`:
   `builtin` creates the user through the built-in IdP's admin app over NATS; `zitadel` through Zitadel's user
   API (Zitadel mails the verification code); `keycloak` through the realm's admin REST API, asking Keycloak to
   mail its "verify email, update password" link (if that mail fails the invitation still stands and the admin
   is warned: until the person verifies the address the invitation claims nothing); `none` does nothing (an
   invitation is a pending grant only: the person must exist at the provider before they can sign in).
3. **Nexus records the invitation** (who, where, as what), mails a sign-in link and lists it as pending until
   the person signs in; it can be resent or revoked (which withdraws the pending grants). Which provider: the
   one asked for, else the one the email's verified organization domain routes to, else `default_provider`, else the
   only provider; without any, inviting someone with no account answers 400. A person who already has a Nexus
   account is added directly and mailed a notice.

`zitadel` needs `admin.token` (a machine user with `ORG_USER_MANAGER` or `IAM_USER_MANAGER`), `keycloak`
`admin.client_id` and `admin.client_secret` (a confidential client with its service account on and the
`realm-management` roles `manage-users` and `view-users`); both secrets belong in the secret service. The
built-in IdP's admin app accepts only the engine's own accounts (`api`, `engine`), whatever discovery allowed: a
module holding a workspace role cannot administer the IdP. `abi iam invite`, `abi iam invitation list|revoke`
and `abi iam group bind|unbind|list` call the running engine like `abi chat` does (against `abi dev up`, export
`ABI_CONFIG_OVERLAY=.abi/dev/dev.overlay.yaml` and the dev stack's `OXIGRAPH_URL` first, so the command joins the
dev engine instead of starting its own).

## The built-in provider

For installs with no provider (`abi dev up`, small installs) the engine trusts the built-in IdP, the
`naas-abi-idp` module (guide: `libs/naas-abi-idp/AGENTS.md`), configured like any provider:

```yaml
identity:
  default_provider: builtin
  providers:
    - name: builtin
      display_name: Email code
      issuer: https://abi.example.com/idp      # https://<API host>/idp, always (http on localhost only)
      client_id: abi
      client_secret: "{{ secret.ABI_IDP_CLIENT_SECRET }}"
      groups_claim: groups
      scopes: [openid, email, profile, groups, offline_access]
      provisioning: builtin
```

`abi dev up` runs the module and, when the project names no provider, adds this block through the dev overlay
and generates the client secret into `.env`; `abi new project` generates the secret and depends on
`naas-abi-idp`; the Docker stack runs it in its own SDK-only container and the account
`module/<project>/idp` and its key are created once the stack is up (`abi iam service-account create
module/<project>/idp --key`, then `abi iam module approve module/<project>/idp`). Elsewhere run
`python -m naas_abi_idp` with its `ABI_IDP_*` settings: it needs a broker, the engine's email service for the
codes and a public `https://<API host>/idp`. To let another application sign in at it, register it through its
admin API and list its origin in Nexus's `idp_client_origins`. Out of scope: SAML, brokering other providers, MFA
policies: plug in a provider for those.

## Decisions

**The engine verifies; it is not an identity provider.**
*Decision.* Identity is a kernel service next to IAM: it authenticates, IAM authorizes. It verifies ID tokens
against each configured issuer's discovery document and JWKS: exact `iss`; an asymmetric algorithm the key allows;
`aud` holding the client ID and `azp` equal to it when present or when there are several audiences; `exp`, `nbf` and
`iat` with 30 s of skew; the nonce. The JWKS is cached for its `max-age` and an unknown `kid` refetches it, at
most every 30 s. It resolves `(issuer, sub)` to the IAM user, maps the groups claim and refuses suspended principals.
It also runs the provider side of a relying party's sign-in, so client secrets never leave the engine. It is
exposed over NATS as `abi.identity.v1.*` and to SDK modules as `engine.services.identity`, and authorized by its own
`identity:*` catalog on `abi:-:-:identity:provider/<name>`; the IAM user is written as `engine` once the caller holds
`identity:Authenticate`, as placements are.
*Consequences.* Nexus has no login code (no passwords, magic links, codes, reset, signup or refresh tokens of its
own) and `secret_key` signs and encrypts nothing. Group changes and offboarding reach ABI within ten minutes through
token expiry, or at once through IAM suspension; there is no SCIM and no introspection. Accounts are never linked
across providers automatically. A provider that is down does not stop the engine, but authenticates nobody until it
answers.

**Providers are engine-wide, organizations are not tenants.**
*Decision.* `identity.providers` is configured once for the engine; an organization may route its verified email
domain to a provider, and the default provider is a button.
*Consequences.* Federation across ABI servers needs every server to trust the same issuer; cross-server service
accounts are not designed.

**No external identity provider is bundled.**
*Decision.* Okta, Entra ID, Zitadel and Keycloak are documented (https://docs.naas.ai); Zitadel, a single native
binary pinned and downloaded by a test helper like `nats-server`, is the external reference of the generic identity
suite in CI. The built-in IdP is an SDK module because neither Keycloak nor Zitadel offers email-code as the only
sign-in factor, nor runs in-process for `abi dev up` without Docker.
*Consequences.* CI downloads Zitadel and PostgreSQL native binaries (~70 MB, cached); the same suite runs against the
in-process provider and the built-in IdP on every run.

## NATS and SDK

Proto `naas-abi-proto/naas_abi_proto/identity/v1/identity.proto`, subjects
`abi.identity.v1.<operation>`. Wire codes: `NOT_FOUND`, `PERMISSION_DENIED`,
`TOKEN_<REASON>`, `SUSPENDED`, `SIGN_IN_FAILED` (message `"<oauth error>: <description>"`),
`UNAVAILABLE`, `INVALID_ARGUMENT`. The SDK facade is `engine.services.identity`
(`naas_abi_sdk/services/identity.py`) for modules that declare `identity`.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/identity --import-mode=importlib -q
uv run pytest libs/naas-abi-core/naas_abi_core/engine/engine_configuration/EngineConfiguration_Identity_test.py -q
# The generic suite, and the provisioning adapter, against Zitadel (downloads pinned binaries, ~70 MB, once):
ABI_REQUIRE_ZITADEL=1 uv run pytest libs/naas-abi-core/naas_abi_core/services/identity/tests/zitadel_contract_test.py libs/naas-abi-core/naas_abi_core/services/identity/tests/zitadel_provisioning_test.py -q
uv run pytest libs/naas-abi-core/naas_abi_core/services/identity/IdentityService_provisioning_test.py --import-mode=importlib -q
```

- The generic suite (`tests/identity_contract.py`) runs against `FakeIdP` on
  every run, and against Zitadel when its binaries can be fetched (skipped
  otherwise; `ABI_REQUIRE_ZITADEL=1` turns the skip into a failure, as CI sets).
- The built-in IdP runs the same suite (`tests/builtin_idp_contract_test.py`).
- **Another provider**: implement
  `IdentityProviderHarness` (`create_user`, `sign_in`, `rotate_signing_key`,
  `other_client`) and subclass `IdentityProviderContract` with a `harness`
  fixture.
- The NATS tests need `nats-server` on `PATH` and skip otherwise.
- The Nexus side of a provider sign-in is covered by
  `libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/oidc/oidc_sign_in_test.py`, which also runs against Zitadel:
  `ABI_REQUIRE_ZITADEL=1 uv run pytest --import-mode=importlib libs/naas-abi-core/naas_abi_core/services/identity/tests/zitadel_contract_test.py libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/oidc/oidc_sign_in_test.py`.
  The suite pins SHA-256s of Zitadel 4.19.4 and PostgreSQL 17.6 (Zonky's native builds) and caches both under
  `~/.cache/naas-abi/test-binaries`.

## Adding a new adapter

An HTTP adapter: implement `get_json` and `post_form` of `OIDCHttpPort`, keep
redirects off and answers bounded, report `max-age`, and raise
`ProviderUnavailableError` for transport failures. A new provider needs no
adapter: it is configuration.
