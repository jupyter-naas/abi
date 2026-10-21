# The engine's secret service is closed to SDK modules

## Status

Accepted. Closes the gap that `docs/adr/20261023_remote-callers-run-engine-tools.md`
("Consequences", "The secret allow list closes one door") left open, and the "explicit, accepted,
temporary gap" the secret primary carried since its port to NATS
(`docs/adr/20261014_module-identities.md` gives the identities this relies on).

## Date

2026-10-24

## Context

`abi.svc.secret.v1` (`SecretPrimaryAdapterNATS`) verified the caller's service token and then
served `get`, `set`, `remove` and `list` to anyone who held a valid one. Since SDK modules got
their own token (a module key derived for one identity), a module that declared `secret` as a
service dependency, or simply called the subject, could read every secret of the engine:
`NATS_JWT_SECRET`, provider keys, the GitHub token. It could also overwrite or remove them.

The per-module secret list of `nats.tool_registry.invoke.modules.<id>.secrets` only controls
which secrets a *tool* may be run with. It closed one door; this was the other. "Engine
secrets never reach a module" holds only when both are closed.

The constraints are those of the tool catalog and of `invoke_tool`:

- **The rights come from the verified service identity**, never from the request. The broker
  has one `module` user for every module; what tells modules apart is the token, signed with
  a key derived for one module id, which cannot assert a first-party identity.
- **Denied by default.** A module that is not named holds nothing.
- **The engine's own processes keep everything.** `api`, `engine` and `dagster` hold the
  project secret (they can sign any token) and are trusted already.
- Nothing may tell a module which secrets exist.

## Decision

### Rights

The primary decides from `verify_service_token`'s identity:

- A first-party identity (`FIRST_PARTY_IDENTITIES`) may do everything, as before.
- Any other identity may **read** (`get`, and the entries of `list`) only the names granted to
  it under `read`, and **write** (`set`, `remove`) only those under `write`. The two are
  independent: a write grant does not allow reading the value back, nor the reverse.

Granted names are exact. There are no patterns: a name that is a prefix of another grants
nothing on the other.

### Configuration

```yaml
nats:
  secret:
    modules:
      my_company_module:
        read: [MY_COMPANY_API_KEY, MY_COMPANY_STATE]
        write: [MY_COMPANY_STATE]
```

`nats.secret.modules` is keyed by module identity (the module id its token asserts). A first-party
identity is refused as a key, and so are an empty one and a misspelt field (`extra="forbid"`: a
typo must not silently grant nothing). Names have the shape of a secret name
(`[A-Za-z_][A-Za-z0-9_]*`, at most 128 characters), the one `invoke.modules.<id>.secrets` already
uses. The primary refuses first-party keys too, for code that builds it directly.

### Answers

- `get` of a name the caller may not read answers like a name that does not exist: found, no
  value. The backend is not even asked.
- `list` returns only the names the caller may read.
- `set` and `remove` of a name the caller may not write answer `PERMISSION_DENIED` with one
  message, whether the name exists or not (a write grant on a name that does not exist yet is
  how a module creates its own). No event is published for a refused write.

A module therefore learns nothing about the engine's secrets beyond its own grants.

### Values a module writes are opaque

A grant on a name is not enough if the *value* can reach other names. The backends store
text and parse it back: the `dotenv` adapter's reader expands `${NAME}` (even inside quotes)
from the file and the process environment, and `Base64Secret` wrote its bundle unescaped and
read it with the same expansion. A module granted `write` and `read` on one name could
`set(NAME, "${NATS_JWT_SECRET}")`, and after the next load of the `.env` read the project secret
back through `get(NAME)` (with `base64`, at once). A value with a quote and a line break could add
a whole `NATS_JWT_SECRET="..."` line to the bundle, poisoning what first-party code reads.

So the boundary and the adapter each close it:

- **The primary refuses**, for a non-first-party identity, a `set` whose value holds `$`, `'`, `"`,
  a backslash, a line break or a carriage return: `INVALID_ARGUMENT`, with one message that names no
  secret and echoes nothing of the value. The grant is checked first, so an ungranted name still
  answers `PERMISSION_DENIED`. First-party callers are unaffected. Any other character is accepted
  (spaces, `=`, `#`, braces, non-ASCII).
- **`Base64Secret` is safe by itself**: it escapes `\`, `"` and line breaks when it writes, reads
  the bundle with `interpolate=False` (nothing in a bundle the code wrote is interpolated), and
  refuses a key that could not stay one key (whitespace, `=`, quotes, `#`, `$`).
- **The `dotenv` adapter keeps interpolating** what it reads. Operators' `.env` files rely on
  `${NAME}`, and a first-party value is trusted. The boundary check above is what keeps a module's
  value out of it; a test pins both sides.

A module that needs such a character in a value (a password with `$`) cannot store it in the
engine: encode it (base64 or hex) or keep it in the module's own environment.

### Not changed

- The wire contract (`secret.proto`): `PERMISSION_DENIED` is already a `CallError` code, and a
  not-found `get` is the existing "unset value".
- `EngineNATSLoader` still serves only the local adapters of the secret fan-out; the grants
  apply to what it serves.
- A client engine that reaches the secret service through the `nats_rpc` adapter keeps its
  `service_identity` (`api` by default). It must be a first-party one to see every secret.

## Consequences

- **A module that keeps its own credentials in the engine's secret service now needs a grant**
  for each name, `read` to use it and `write` to set it. Without one, `get` answers "not found"
  (the SDK returns the default) and `set` fails with `PERMISSION_DENIED`. The standalone demo
  (`examples/standalone_module`) grants its worker `DEMO_VALUE` and checks that another engine
  secret is not found, not listed and not writable. The alternative stays the better default for
  a module's own credentials: keep them in its own environment.
- With both this and `invoke.modules.<id>.secrets`, an operator names what a module may use,
  twice, on purpose: a tool run with a secret and a module reading it are different rights.
- **Do not grant `write` on a name that a tool run by a module takes from `invoke.modules.<id>.secrets`
  or that other components read.** A module can replace the value, so whoever reads it next uses
  what the module wrote. `write` is for the module's own state.
- Values are opaque, never expanded: nothing a module writes can read another secret, and nothing
  it writes can add a key. A module-written value that an operator renders into `config.yaml`
  (`{{ secret.NAME }}`) still lands in the config text: do not grant `write` on such a name.
- A granted `read` hands the module the *value*: the module can keep or leak it. Grant least
  privilege, a dedicated secret per module rather than the engine's provider keys.
- Tokens signed with the project secret (held by first-party processes only) can still assert
  any identity, and keep the grants of that identity if it is a module's. Nobody outside the
  engine holds it; a module cannot derive it from its key.
- An older engine without `nats.secret` is unchanged for first-party callers, and denies modules:
  there is no mode that reopens the service. `Secret` events (`SecretSet`, `SecretRemoved`) are
  published for granted module writes like any other.
- The engine's own non-NATS paths (in-process `Secret`, `{{ secret.X }}` rendering, the tool
  invoker's `SecretServiceResolverAdapter`) are not caller-scoped: they do not go through this
  primary.
