# Secret Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/secret/`. Canonical reference for agents.

## Purpose

Unified interface for reading / writing secrets across multiple backends. The service composes a **list** of adapters: `get` consults them in order (first hit wins), `set` / `remove` propagate to all, `list` merges (earlier adapters override later ones).

Emits `SecretSet` / `SecretRemoved` / `SecretError` events.

## Files

```
secret/
├── SecretPorts.py     # ISecretService, ISecretAdapter, SecretAuthenticationError
├── Secret.py          # public service
├── Secret_test.py
├── iam_catalog.py     # IAM action catalog and seals (idp/, iam/ keys)
├── Secret_authorization_test.py  # authorization contract
├── adaptors/secondary/
│   ├── Base64Secret.py
│   ├── NaasSecret.py
│   └── DotenvSecretSecondaryAdaptor.py
└── ontologies/        # SecretSet, SecretRemoved, SecretError
```

## Port (`SecretPorts.py`)

```python
class ISecretAdapter:
    def get(key: str, default=None) -> str | Any | None
    def set(key: str, value: str) -> None
    def remove(key: str) -> None                    # no-op on missing keys
    def list() -> Dict[str, str | None]

class ISecretService:                              # same surface
    ...

class SecretAuthenticationError(Exception): ...
```

## Service API (`Secret.py`)

```python
Secret(adapters: List[ISecretAdapter])

get(key, default=None) -> str                       # first adapter that returns non-default wins
set(key, value)                                     # writes to all adapters; → SecretSet
remove(key)                                         # removes from all adapters; → SecretRemoved
list() -> Dict[str, str | None]                     # merged view (earlier overrides later)
```

## Available Adapters

| Adapter | Backend / Notes |
|---|---|
| `DotenvSecretSecondaryAdaptor(path=".env")` | Reads / writes `.env` files with thread-safe locking |
| `NaasSecret(naas_api_key, naas_api_url=None)` | Naas API over HTTPS (Bearer token) |
| `Base64Secret(secret_adapter, base64_secret_key)` | **Decorator** — wraps another adapter; encodes / decodes a base64 dotenv blob under a single key |

## Instantiation

No factory file. Wire directly:

```python
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.adaptors.secondary.DotenvSecretSecondaryAdaptor import (
    DotenvSecretSecondaryAdaptor,
)
from naas_abi_core.services.secret.adaptors.secondary.NaasSecret import NaasSecret

secret = Secret(adapters=[
    DotenvSecretSecondaryAdaptor(".env"),       # local override wins
    NaasSecret(naas_api_key=os.environ["NAAS_API_KEY"]),
])
```

## Authorization

Every operation is checked in the domain service against IAM (RFC
[§5, §6.4](../../../../../docs/specs/rfcs/20261013_identity-and-authorization.md)),
for the caller of the current `CallContext`, so in process and over NATS answer
the same. The catalog is `iam_catalog.py`, registered by the serving engine at
boot. A caller who cannot see a resource gets the default, as for a missing key; one who can see it but not
act gets `PermissionDeniedError` (`PERMISSION_DENIED`). A service not wired into
an engine with IAM (a library use, a NATS facade whose server checks) does not
check. The contract test is `Secret_authorization_test.py`: no policy, granted and denied
principals, in process and over NATS.

* Each key is `secret/<key>` (opaque, so `/` is `%2F`), placed by key prefix.
* `get` of a key the caller may not see returns `default`; `set` and `remove`
  raise `ResourceNotFoundError` (`NOT_FOUND`).
* `list` returns the keys the caller may `List`, with a value only where it may
  also `Get`.
* Seals (`SEALS`): `idp/` keys belong to the built-in IdP and `iam/` keys to
  the engine, wherever a placement puts them; no policy opens them to anyone
  else, `api` and `engine` included.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/Secret_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/adaptors/secondary/Base64Secret_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/adaptors/secondary/NaasSecret_test.py
```

## Adding a new adapter

1. Implement `ISecretAdapter` in `adaptors/secondary/<Name>.py`. All four methods.
2. `remove` **must be idempotent** — never raise on missing keys.
3. Raise `SecretAuthenticationError` for auth-related failures so callers can differentiate.
4. Add `<Name>_test.py` and verify `list()` round-trips against `set()` / `remove()`.

## NATS RPC adapters

`adaptors/primary/secret__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adaptors/secondary/SecretSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/secret/v1/`.

Every primary runs its domain call as the verified caller: it authenticates the
request with `nats_rpc.authenticate_request` (built on `engine/nats_identity.py`,
it answers a refusal itself) and hands that `CallContext`
(`engine/call_context.py`) to its dispatcher. The actor is the
token's identity; the user it acts for is named by the token itself: a
delegated token (`abi:delegated:agent`, `act` the acting service, `sub` the user)
made by IAM's token exchange, never a header (the old `Abi-On-Behalf-Of` header is
refused); trace and target workspace come from the request's `context`. Never read identity from request fields
(`principal_id` and `tenant_id` are reserved). Clients of `api` and `engine` send a
delegation for the current call's user, and the call's trace and workspace. Nothing authorizes per secret yet, so the
endpoint is an allowlist (`secret_nats_contract.may_use`, answered
`PERMISSION_DENIED`): `engine` reaches every name but `idp/...`, `idp` its own,
any other service account only the names under its own prefix (`<module id>/...`
for a module), a user nothing; in `get`, `set`, `remove` and `list`. IAM's
signing keys, the broker's passwords and the callout seed live in this store, so
a module granted `secret:*` must never reach them.

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB (docs/adr/20261003_nats-rpc-overflow.md); above
that, at the overflow host's capacity, or with an older peer, the call fails
with non-retryable `PAYLOAD_TOO_LARGE`. Micro-service error headers raise
instead of becoming an empty success. Overflowed values are held whole in
memory; results that should not be require streaming or a storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

In NATS mode a fanout may mix local adapters and `nats_rpc` ones
(`[dotenv, nats_rpc]`): the engine serves only the local adapters, and its
modules read them through the engine's endpoint before the `nats_rpc` upstream,
in the configured order (`engine/engine_loaders/AGENTS.md`).

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
