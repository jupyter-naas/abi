# CodingEnvironment Service - AGENTS.md

## Purpose

Provision and manage coding workspaces through interchangeable providers.

## Files

- `CodingEnvironmentPorts.py`: port, value types, and domain errors.
- `CodingEnvironmentService.py`: service orchestration and event publication.
- `CodingEnvironmentFactory.py`: composition helpers.
- `adapters/primary/`: NATS RPC server.
- `adapters/secondary/`: local/provider implementations and NATS RPC client.
- `tests/`: generic adapter contract tests.

## Port

Implement every abstract method of `ICodingEnvironmentAdapter` in `CodingEnvironmentPorts.py`.
Keep provider dependencies in secondary adapters and preserve typed domain errors.

`list_all_environments()` is the platform admin view (the Nexus System app): every
user's workspaces. Coder pages `GET /workspaces` with the admin token; in-memory and
local-directory list every record; compose returns its one shared editor.
`WorkspaceStatus` carries `owner`, `template` and `created_at` when the backend knows
them (`""`/`None` otherwise); keep filling them in new adapters.

## Service API

`CodingEnvironmentService(adapter)` authorizes each operation (below), delegates to the port and publishes domain events.
See its public methods for orchestration beyond the adapter contract.

## Authorization

Every operation is checked inside `CodingEnvironmentService` (`iam_catalog.py`)
once the service is wired with IAM, so in-process and NATS callers are checked
alike. A NATS facade is not wired and checks nothing itself: the owner it calls
does. The guard is described in [`services/iam/AGENTS.md`](../iam/AGENTS.md)
("Enforcing in a domain service"). An environment is a personal resource: a role
reaches it only through its owner, as `environment/${principal.id}/*`.

| Level | Action: resource (NATS subject: the operation under `abi.svc.coding_environment.v1.`) |
|---|---|
| list | `ListTemplates`: each `template`; `ListEnvironments`: each `environment` of the user |
| read | `GetStatus`, `GetLogs`: `environment` |
| write | `GetAccess` (returns a credential), `Start`, `Stop`, `Delete`: `environment`; `Provision`: `environment/<the call's user>/-` (creates) |
| admin | `ListAllEnvironments`: each `environment`; `EnsureUser`: `coder_user/<principal id>` |

- **Resources.** `environment/<owner principal id>/<environment id>` is personal,
  placed in the call's target workspace when provisioned; `template/<id>` and
  `coder_user/<principal id>` are platform-level.
- **The principal is the call's**, never a request field: the call's user, or the
  actor when the call is on behalf of no one. `user_id` and `external_id` in
  requests are ignored: `ensure_user` binds the orchestrator user to the principal
  (`ICodingEnvironmentAdapter.find_user`; local adapters use the principal itself,
  Coder keeps the binding for the process, re-made by every `ensure_user`), and
  `provision`, `list_environments` and `get_access` act for that user. An
  existing orchestrator account is the caller's only when bound to it, or when it
  predates the binding and a first party (`api`, `engine`) vouches for the email
  it carries; an administrator account is never handed over, nor one bound to
  another principal (`AccessDeniedError`).
- The proto's `workspace_id` field is the environment id.
- **The owner of an environment** comes from the orchestrator's records: the
  environments it lists for the owner's orchestrator user (cached per process). An
  environment whose owner the service cannot tell is named with owner `-`, which
  only grants on every environment reach.
- `Provision` is checked on `environment/<principal>/-` as placed (the create rule); the new
  environment is then placed in the target workspace. A target
  workspace IAM has no scope for leaves it on the platform.
- `list_environments` keeps the caller's own; `list_all_environments` needs the
  admin `ListAllEnvironments`. `get_runtime_binding` and `get_harness_binding`
  return a credential, so they need `GetAccess` (None when denied).
- Wire codes `PERMISSION_DENIED` and `NOT_FOUND`; an invisible environment is
  `WORKSPACE_NOT_FOUND`.
- Audit events go through `EventService.emit`.
- Tests: `tests/coding_environment_authorization_test.py` (the
  `AuthorizationContract` for `GetStatus` and `Provision`, ownership, placement).

## Adapters

CoderAdapter, CodeServerComposeAdapter, LocalDirectoryAdapter, InMemoryAdapter, plus `CodingEnvironmentSecondaryAdapterNATSClient`.
Unsupported methods must explicitly raise `NotImplementedError`.

## Factory

Use `CodingEnvironmentFactory` for the existing provider composition helpers.
Engine configuration can also construct adapters, including `nats_rpc`.

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/coding_environment/ --import-mode=importlib
```

## Adding a new adapter

1. Implement the complete port with constructor-injected configuration.
2. Add colocated tests and run the generic adapter contract tests.
3. Add the relevant factory/configuration wiring.

## NATS RPC adapters

A `NotImplementedError` in the wrapped adapter crosses NATS as the non-retryable
code `UNIMPLEMENTED` and is raised again as `NotImplementedError` by the client.
`adapters/secondary/CodingEnvironmentSecondaryAdapterNATSClient_broker_test.py` runs
`list_all_environments` against a local `nats-server` (no Docker).

`adapters/primary/coding_environment__primary_adapter__NATS.py` exposes the service's
protobuf endpoints. `adapters/secondary/CodingEnvironmentSecondaryAdapterNATSClient.py` implements the outbound
port. Wire contracts live under `naas_abi_core/proto/coding_environment/v1/`.

Every primary runs its domain call as the verified caller: it authenticates the
request with `nats_rpc.authenticate_request` (built on `engine/nats_identity.py`,
it answers a refusal itself) and hands that `CallContext`
(`engine/call_context.py`) to its dispatcher. The actor is the
token's identity; the user it acts for is named by the token itself: a
delegated token (`abi:delegated:agent`, `act` the acting service, `sub` the user)
made by IAM's token exchange, never a header (the old `Abi-On-Behalf-Of` header is
refused); trace and target workspace come from the request's `context`. Never read identity from request fields
(`principal_id` and `tenant_id` are reserved). Clients of `api` and `engine` send a
delegation for the current call's user, and the call's trace and workspace. The domain service then authorizes the call (see "Authorization").

Clients inherit connection, JWT renewal, deadlines, and error handling from
`naas_abi_core.engine.nats_rpc.NatsRPCClient`; keep domain conversion and exception
mapping in the adapter. Primaries use `respond_protobuf` for bounded replies.
Requests and replies above the broker limit (8 MiB, or lower) overflow as
transfer frames up to 256 MiB; above
that, at the overflow host's capacity, or with an older peer, the call fails
with non-retryable `PAYLOAD_TOO_LARGE`. Micro-service error headers raise
instead of becoming an empty success. Overflowed values are held whole in
memory; results that should not be require streaming or a storage reference. No RPC is automatically replayed after transport failure:
a timeout can hide a completed operation. Reconcile its outcome before retrying.
`close()` releases only the client's transport, including for vector storage.

Run the colocated NATS tests with `--import-mode=importlib`; shared regressions
are in `engine/nats_rpc_test.py` and `engine/nats_rpc_integration_test.py`.
The latter uses a local `nats-server` executable without Docker.
