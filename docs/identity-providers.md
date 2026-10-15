# Signing in with an identity provider

ABI does not keep passwords for the people who sign in through an identity
provider (IdP). The engine trusts the OIDC providers you configure under
`identity.providers`, and Nexus signs people in through them with the
authorization code flow and PKCE. This page shows how to plug in Okta,
Microsoft Entra ID, Zitadel and Keycloak.

Design: RFC [`20261013_identity-and-authorization`](specs/rfcs/20261013_identity-and-authorization.md) §12.1,
ADRs [`20261013_identity-providers-and-builtin-idp`](adr/20261013_identity-providers-and-builtin-idp.md)
and [`20261015_nexus-oidc-sessions`](adr/20261015_nexus-oidc-sessions.md).

## What ABI expects of a provider

| | |
|---|---|
| Discovery | `<issuer>/.well-known/openid-configuration`, naming exactly the configured `issuer` |
| Client | A confidential web client (client ID and secret), authorization code grant, PKCE with S256 |
| Redirect URI | `<Nexus API URL>/api/auth/oidc/callback`, for example `https://abi.example.com/api/auth/oidc/callback` (`oidc_redirect_uri` in the Nexus config overrides it) |
| Post-logout redirect URI | `<Nexus web URL>/auth/login` |
| Refresh tokens | Required: Nexus re-verifies each user at the provider at least every 10 minutes. Ask for `offline_access` where the provider needs it. A refresh must return an ID token. |
| ID token | Signed with an asymmetric key (RS256, ES256, PS256 or EdDSA) published in the JWKS. `aud` holds the client ID; `azp`, when present, is the client ID. |
| Email | `email` with `email_verified: true`. An unverified email is never stored as such (see [Emails](#emails)). |
| Groups (optional) | A claim listing the user's groups, named by `groups_claim` |
| Token lifetime | 10 minutes or less is recommended. Nexus refreshes at most 10 minutes after each verification, whatever the provider's lifetime. |

The client secret stays in the engine: Nexus asks the engine to build the
authorization URL, redeem the code and refresh. It never holds the secret.

## Configure the engine

```yaml
identity:
  default_provider: acme            # where a login goes when no organization domain routes it
  providers:
    - name: acme                    # ^[a-z0-9-]{1,32}$, unique
      display_name: Acme SSO        # the login page's "Continue with ..." button
      issuer: https://acme.okta.com/oauth2/default
      client_id: 0oa1example
      client_secret: "{{ secret.ACME_OIDC_CLIENT_SECRET }}"
      groups_claim: groups          # optional; a claim name or a dotted path
      scopes: [openid, email, profile, offline_access, groups]
      provisioning: none            # builtin | zitadel | keycloak | none
      # trust_email: true           # see Emails
```

- The block is validated when the configuration loads. Issuers must use
  `https`, or `http` on localhost only.
- The engine reads each provider's discovery document and JWKS at boot. It
  logs a provider it cannot reach and tries again on first use: a provider that
  is down does not stop the engine.
- Keep `client_secret` in the secret service (`{{ secret.X }}`), never in the
  file itself.

## Route logins

The login page asks for an email first:

1. A **verified organization domain** whose `provider` is set sends the login
   to that provider. Set it as an organization admin with
   `PUT /api/organizations/{org_id}/domains/{domain_id}/provider` and
   `{"provider": "acme"}` (or `null`).
2. Otherwise the login goes to `default_provider`.
3. Without either, the built-in Nexus login (password or emailed code) is used.

The login page also offers a "Continue with ..." button for each provider.

## Users, groups and accounts

- **A user is `(issuer, sub)`, never an email.** The first sign-in creates the
  IAM user (`usr_...`) and a Nexus account with the same id. No password is
  stored.
- **Accounts are never linked automatically.** The same person signing in
  through two providers gets two accounts. A sign-in whose verified email
  already belongs to another account (a built-in login account, or another
  provider's) is refused with "email already belongs to another account" until
  an administrator links them.
- **Groups.** Map a value of the provider's groups claim to an IAM group:

  ```python
  iam.map_idp_group("acme", "data-engineers", group_id)  # needs iam:MapIdpGroup
  ```

  The mapped groups apply for as long as the session's last verification, at
  most 10 minutes.
- **Offboarding.** Disabling a user at the provider ends their Nexus session at
  the next refresh, within 10 minutes. Suspending the IAM user ends it at once.
- **The built-in login never opens a provider's account:** no password, code,
  magic link or reset reaches it.

### Emails

Nexus uses an account's email for invitations and member lookups, so it stores
only an email the provider verified. An absent or unverified email becomes a
placeholder, `<principal id>@unverified.internal`, which nothing can match.

Some directories issue only addresses they control but send no
`email_verified` claim (Entra ID). Set `trust_email: true` on such a provider
to count its `email` as verified. Do not set it on a provider where users can
choose their own address.

## Okta

1. **Applications → Create App Integration**: OIDC, **Web Application**.
2. Grant types: **Authorization Code** and **Refresh Token**. Client
   authentication: **Client secret**, with **Require PKCE as additional
   verification** enabled.
3. Sign-in redirect URI: `https://abi.example.com/api/auth/oidc/callback`.
   Sign-out redirect URI: `https://abi.example.com/auth/login`.
4. **Security → API → Authorization Servers → default**:
   - **Claims → Add Claim**: name `groups`, include in **ID Token**
     (Always), value type **Groups**, filter `Matches regex .*`.
   - **Access Policies**: set the access token lifetime to 10 minutes; allow
     refresh tokens.

```yaml
- name: okta
  issuer: https://<your-org>.okta.com/oauth2/default
  client_id: <client ID>
  client_secret: "{{ secret.OKTA_OIDC_CLIENT_SECRET }}"
  groups_claim: groups
  scopes: [openid, email, profile, offline_access, groups]
```

Use the org authorization server (`https://<your-org>.okta.com`) only if you
have no custom one. Its tokens cannot carry a custom groups claim.

## Microsoft Entra ID

1. **App registrations → New registration**: single tenant. Redirect URI:
   platform **Web**, `https://abi.example.com/api/auth/oidc/callback`.
2. **Certificates & secrets**: a client secret.
3. **Token configuration**:
   - **Add optional claim**, ID token: `email`.
   - **Add groups claim**: security groups. The `groups` claim lists group
     object IDs: map those IDs with `map_idp_group`.
4. **API permissions**: `openid`, `email`, `profile`, `offline_access`.

```yaml
- name: entra
  issuer: https://login.microsoftonline.com/<tenant ID>/v2.0
  client_id: <application (client) ID>
  client_secret: "{{ secret.ENTRA_OIDC_CLIENT_SECRET }}"
  groups_claim: groups
  scopes: [openid, email, profile, offline_access]
  trust_email: true      # Entra sends no email_verified; its addresses are the directory's
```

- Use the tenant-specific issuer. The multi-tenant `common` and
  `organizations` endpoints publish a templated issuer that no token matches
  exactly, so ABI refuses them.
- A user in more than 200 groups gets an overage claim instead of `groups`.
  Assign groups to the application to keep the list short.

## Zitadel

1. In a project, **New application**: type **Web**, authentication method
   **Code**. Zitadel enforces the PKCE challenge Nexus sends. Use client-secret
   (Basic) authentication.
2. Redirect URI `https://abi.example.com/api/auth/oidc/callback`, post-logout
   URI `https://abi.example.com/auth/login`. In development, **Development
   mode** allows `http` URIs.
3. **Token settings**: **User roles inside ID Token** and **User Info inside ID
   Token**.
4. Project roles are the groups: grant roles to users (or to Zitadel groups)
   and map role keys with `map_idp_group`.
5. Instance **OIDC token lifetimes**: access and ID tokens 10 minutes; refresh
   tokens enabled.

```yaml
- name: zitadel
  issuer: https://<instance>.zitadel.cloud          # or your ExternalDomain
  client_id: <client ID>
  client_secret: "{{ secret.ZITADEL_OIDC_CLIENT_SECRET }}"
  groups_claim: urn:zitadel:iam:org:project:roles
  scopes: [openid, email, profile, offline_access]
```

Zitadel is the reference external provider of ABI's identity tests (below).

## Keycloak

1. In the realm, **Clients → Create client**: OpenID Connect, **Client
   authentication** on, **Standard flow** on.
2. Valid redirect URIs `https://abi.example.com/api/auth/oidc/callback`,
   valid post-logout redirect URIs `https://abi.example.com/auth/login`.
3. **Advanced → Proof Key for Code Exchange Code Challenge Method**: `S256`.
4. Groups: **Client scopes → <client>-dedicated → Add mapper → Group
   Membership**, token claim name `groups`, **Full group path** off, **Add to ID
   token** on. To use realm roles instead, set `groups_claim:
   realm_access.roles`.
5. **Realm settings → Tokens**: access token lifespan 10 minutes.

```yaml
- name: keycloak
  issuer: https://keycloak.example.com/realms/<realm>
  client_id: abi
  client_secret: "{{ secret.KEYCLOAK_OIDC_CLIENT_SECRET }}"
  groups_claim: groups
  scopes: [openid, email, profile]
```

## Nexus session settings

| Setting | Default | |
|---|---|---|
| `oidc_session_cookie` | `nexus_session` | The httpOnly, Secure cookie the API holds the session in |
| `oidc_cookie_samesite` | `lax` | `none` when the web app and the API are on different sites (both must use HTTPS) |
| `oidc_session_max_age_hours` | `168` | The longest a session lasts, refreshes included |
| `oidc_redirect_uri` | `<api_url>/api/auth/oidc/callback` | The redirect URI registered at the providers |

The browser keeps no token: the session cookie is httpOnly, and the CSRF
token the web app sends on every change (`X-CSRF-Token`) lives in memory only.

## Testing a provider

The generic identity suite
(`libs/naas-abi-core/naas_abi_core/services/identity/tests/identity_contract.py`)
checks a provider end to end: discovery, key rotation, token checks, groups,
suspension and a full PKCE sign-in. It runs against an in-process provider on
every test run, and against Zitadel from a pinned native binary, with
PostgreSQL from pinned native binaries too (no Docker):

```bash
ABI_REQUIRE_ZITADEL=1 uv run pytest --import-mode=importlib \
  libs/naas-abi-core/naas_abi_core/services/identity/tests/zitadel_contract_test.py \
  libs/naas-abi/naas_abi/apps/nexus/apps/api/app/services/oidc/oidc_sign_in_test.py
```

To run it against another provider, implement `IdentityProviderHarness` and
subclass `IdentityProviderContract`.
