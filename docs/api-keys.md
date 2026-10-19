# API keys and narrow credentials

Scripts, CI and tools call ABI with a key, never with a password or a copy of
a session. This page covers personal API keys, the service keys of scripts and
CI, and the other narrow credentials ABI hands out (links to apps, a coding
environment's key), and what each can reach.

Design: RFC [`20261013_identity-and-authorization`](specs/rfcs/20261013_identity-and-authorization.md) §8.1, §9.3 and §9.4,
ADR [`20261019_delegated-tokens-and-api-keys`](adr/20261019_delegated-tokens-and-api-keys.md).

## Personal API keys

A personal API key (`abi_pk_<id>_<secret>`) is a credential of the person who made it. It can never do
more than they can: their policies decide, and the key's own limit narrows further.

**Make one** in the web app under Account, API keys: a name, how long it lasts (30 days, 90 days or a year; a year
is the most), and its access:

| Access | What the key may do |
|---|---|
| Full access | Everything its owner may |
| Read only | Only what reads and lists (every action ABI classes as `read` or `list`) |
| Custom | The statements you write: `[{"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]}]` |

The key is shown **once**. ABI stores only a hash of it: if it is lost, revoke it and make another. You may hold
five active keys. Revoking a key stops it at its next request.

**Use it** as a bearer token on any `/api/*` route of Nexus:

```bash
curl -H "Authorization: Bearer abi_pk_..." https://abi.example.com/api/workspaces
```

or exchange it for a short-lived token (ten minutes at most), the OAuth2 `client_credentials` form:

```bash
curl -X POST https://abi.example.com/api/iam/token \
  -d grant_type=client_credentials -d client_secret=abi_pk_...
# {"access_token": "...", "token_type": "Bearer", "expires_in": 600}
```

A key does **not** reach the account (`/api/auth/*`) or the key management (`/api/iam/*`): a key can neither make
another key nor widen itself, and it is not accepted on the WebSocket. It does not carry the groups your identity
provider gave you at sign-in: what you hold only through an IdP group claim does not reach your keys.

The same key works on the engine's own API (`/agents/...`). Revocation, expiry and suspension of its owner take effect at
the next request.

## Service keys, for scripts and CI

A service account (`ci/<name>`, made with `abi iam`) has keys of its own, `abi_sk_<id>_<secret>`: at most five, expiring in
90 days unless told otherwise. A request made with one runs *as that account*, so what it may do is what policies
attached to that account allow, nothing implicit. Use it as the bearer token of the engine's API, or let a module's SDK
exchange it (`ABI_SERVICE_KEY`).

`ABI_API_KEY`, the one shared key of a deployment, still works on the engine's API as the `api` account. Move scripts to
service keys; it goes when `api` is enumerated.

## Links and coding environments

These are made by ABI itself, for one purpose, and none of them is a session:

| Credential | Made for | Reaches | Lasts |
|---|---|---|---|
| App link (`/app-html/…?token=`), preview link (`/app-preview/<token>/`), remote app grant (`/app-remote/<grant>/…`) | Opening one app or preview, for the user who asked | Its own route only | 8 hours at most, revocable, checked again at every request |
| A coding environment's key | The agent inside a workspace, as its owner | The OpenAI gateway (`/api/v1/*`) only, bound to that workspace's sidecar | The configured lifetime (30 days by default, a year at most); revoked with the environment |

When a user's tokens are revoked (a password change), their sessions, links and coding keys go with them; their API keys
stay.

## For module authors

A module that serves an agent or an app does not receive the caller's credential. It receives a *delegation*: a token
that names the module and the user it acts for, good for ten minutes, renewable by the module itself for up to eight
hours (the SDK does it), and refused anywhere the module is not the one acting. The module learns who is calling from it,
and its kernel calls for that user carry it: what happens is decided for the module *and* the user, so a call can never
do more than the user may. The old `Abi-On-Behalf-Of` header is refused.
