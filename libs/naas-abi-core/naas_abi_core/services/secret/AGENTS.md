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
| `DotenvSecretSecondaryAdaptor(path=".env", read_only=False, environment_first=False)` | Reads / writes `.env` files with thread-safe locking; reads fall back to the process environment. `read_only=True` serves a file another process owns (e.g. a volume mounted `:ro`): `set` / `remove` skip it, so the fan-out still writes to the other adapters, and a `remove` leaves the key served from the file. `environment_first=True` reads the environment before the file, matching how `{{ secret.X }}` is rendered |
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

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/Secret_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/adaptors/secondary/Base64Secret_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/adaptors/secondary/NaasSecret_test.py
uv run pytest libs/naas-abi-core/naas_abi_core/services/secret/adaptors/secondary/dotenv_secret_secondaryadaptor_test.py
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

### Per-caller rights

The primary authorizes by the verified service identity of the token, never the request
(docs/adr/20261024_secret-service-closed-to-sdk-modules.md). `api`, `engine` and `dagster`
(`FIRST_PARTY_IDENTITIES`) keep full access. An SDK module is denied by default and uses only
the exact names granted under `nats.secret.modules.<module id>`:

```yaml
nats:
  secret:
    modules:
      my_company_module: {read: [MY_COMPANY_API_KEY], write: [MY_COMPANY_STATE]}
```

Values a module writes are opaque and never interpolated: a `set` from a non-first-party identity
whose value has `$`, a quote, a backslash or a line break is `INVALID_ARGUMENT`, because the
backends parse stored text back (the dotenv reader expands `${NAME}`; a base64 bundle could gain
a key). `Base64Secret` also escapes what it writes and reads its bundle with `interpolate=False`,
and refuses keys that could not stay one key (a bundle that relied on `${NAME}` expanding on
read comes back literal: store the final value). `dotenv` keeps interpolating what it reads (operators'
files use it); the primary is the boundary.

`read` allows `get` and shows the name in `list`; `write` allows `set` and `remove`; neither
implies the other. An ungranted `get` is "not found" and `list` leaves the name out, so nothing
says which secrets exist; an ungranted `set` / `remove` is `PERMISSION_DENIED`, the same for
every name. A first-party identity is not a valid key (`SecretPrimaryAdapterNATS` and the config
refuse it). A `nats_rpc` secret adapter must keep a first-party `service_identity` (default `api`).
Tests: `secret__primary_adapter__NATS_test.py` (unit),
`engine/Engine_secret_nats_integration_test.py` (real broker, `ABI_REQUIRE_NATS_SERVER=1`),
`engine/engine_configuration/EngineConfiguration_NATSSecret_test.py`.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
