# Identity Service - AGENTS.md

## Purpose

The OIDC identity providers the engine trusts, configured engine-wide under
`identity.providers` (RFC
[`docs/specs/rfcs/20261013_identity-and-authorization.md`](../../../../../docs/specs/rfcs/20261013_identity-and-authorization.md)
§12.1, ADR
[`20261013_identity-providers-and-builtin-idp`](../../../../../docs/adr/20261013_identity-providers-and-builtin-idp.md)).
The engine is not an identity provider: it verifies providers' ID tokens and
resolves them to IAM users. Authorization stays with IAM (`services/iam`).

- **A user is `(issuer, sub)`**, never an email. The IAM user is created on
  first sign-in (`iam.ensure_user`) and holds no password. The same person
  through two providers is two principals: nothing links them automatically.
- **Verification** reads each issuer's discovery document and JWKS, follows key
  rotation, and checks `iss`, the signature, `aud`/`azp`, `exp`, `nbf`/`iat`
  (30 s of skew) and the nonce.
- **Groups**: the provider's `groups_claim` values map to IAM groups through
  `iam.map_idp_group`; the mapped ids come back with the user (the engine
  token's `grp`, subtask 8 of #44).
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
| `iam_catalog.py` | The `identity:*` catalog, registered with the kernel catalogs |
| `adapters/secondary/OIDCHttpHttpx.py` | `OIDCHttpPort` over httpx |
| `adapters/secondary/OIDCHttpBuiltinIdP.py` | `OIDCHttpPort` for the built-in IdP (`provisioning: builtin`): its issuer is read over NATS, everything else over the fallback |
| `adapters/secondary/IdPAppNATS.py` | The IdP's `idp` app called over NATS as the engine, bound to the instance running as `module/<project>/idp` |
| `adapters/secondary/IdentitySecondaryAdapterNATSClient.py` | `IIdentityService` over NATS, for client-role engines |
| `adapters/primary/identity__primary_adapter__NATS.py` | `abi.identity.v1.*` |
| `adapters/identity_nats_codec.py` | Records and errors on the wire |
| `tests/identity_contract.py` | **The generic identity suite** every provider passes, and its `IdentityProviderHarness` |
| `tests/fake_idp.py` | An OIDC provider over real HTTP in this process (RS256/ES256, rotation, PKCE, refresh, revocation) |
| `tests/zitadel_server.py` | Zitadel and PostgreSQL from pinned native binaries, and the Zitadel harness |
| `tests/builtin_idp_server.py` | The built-in IdP (`naas-abi-idp`) over real HTTP in this process, and its harness |

Engine configuration: `engine/engine_configuration/EngineConfiguration_Identity.py`.

## Port

**`OIDCHttpPort`** (secondary): `get_json(url) -> HttpJSON(body, max_age)` and
`post_form(url, data, basic_auth=) -> (status, body)`; both raise
`ProviderUnavailableError` when the provider cannot be reached.

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
identity.end_session_url("acme", id_token_hint=..., post_logout_redirect_uri=...)
```

- **Authorization.** Every call is checked with the `identity` catalog on
  `abi:-:-:identity:provider/<name>` for the current `CallContext`:
  `ListProviders`, `GetProvider`, `VerifyToken` (no side effect),
  `Authenticate` (creates or refreshes the IAM user, as `engine`) and `SignIn`
  (the relying-party operations). `exchange_code` and `refresh` resolve the
  user too, so they need `SignIn` **and** `Authenticate`; the authorization URL,
  revocation and end-session need `SignIn` only. A caller with none gets "not found". `api` and
  `engine` hold them through their transitional policies; a module needs a grant.
- **`refresh_at`** is the ID token's expiry, at most ten minutes after the
  sign-in: a relying party re-verifies at the provider by then (RFC §9.2).
- **A refresh** that returns an ID token must name the same user
  (`subject_changed` otherwise). One that returns none (OIDC Core §12.2) is
  accepted: the provider took the refresh token and the subject cannot change,
  so the service only checks that the session's principal is an active user of
  this provider's issuer. `tokens.id_token` is then `None` and no groups are
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
      provisioning: none              # builtin | zitadel | keycloak | none (subtask 10)
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

Plugging in Okta, Entra, Zitadel or Keycloak:
[`docs/identity-providers.md`](../../../../../docs/identity-providers.md).

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
# The generic suite against Zitadel (downloads pinned binaries, ~70 MB, once):
ABI_REQUIRE_ZITADEL=1 uv run pytest libs/naas-abi-core/naas_abi_core/services/identity/tests/zitadel_contract_test.py -q
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

## Adding a new adapter

An HTTP adapter: implement `get_json` and `post_form` of `OIDCHttpPort`, keep
redirects off and answers bounded, report `max-age`, and raise
`ProviderUnavailableError` for transport failures. A new provider needs no
adapter: it is configuration.
