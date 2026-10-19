# Discovery service

## Purpose
Track expiring process registrations and dependency-derived readiness. Membership
leases are not execution locks. Clients remain independent of ABI core.

## Files and port
`discovery_service.py` owns validation and readiness. `discovery_ports.py` defines
an async revisioned snapshot port. Transport DTOs live in the standalone proto
package. The JetStream adapter stores an opaque protobuf snapshot using CAS.

## Adapters and factory
NATS primary authenticates issued service tokens; mutations bind to verified
caller identity plus a lease token. Each handler runs under the caller's
`CallContext` (`engine/nats_identity.py`, `engine/call_context.py`).
`discovery_factory.py` composes the service. Engine exposure is explicit opt-in;
replicas use a project queue group and share the same JetStream CAS snapshot. No silent in-memory fallback.

## Authorization (`iam_catalog.py`, RFC §6.4)
`start_discovery(..., iam=)` wires IAM (the serving engine passes its own); every
operation is then checked in the domain service with the `discovery` catalog.
Without IAM (unit tests of the registry) nothing is authorized. Names are
platform-level: `module/<project>/<module_id>`, `agent|model|app|job/<project>/<module_id>/<name>`,
`run/<owner>/<project>/<invocation>`, `job_run/<project>/<module_id>/<job>/<run id>`.

- **Registration**: `Register`, `Renew`, `Unregister` on the module, in the
  provider's context. A module id is held by one principal at a time: another
  principal cannot register it while live instances of it exist (so nobody can
  join a running module and take its requests). A module account
  (`module/<project>/<module_id>`, from #60) registers only its own module.
- **Listing**: `list_modules` and `get_module` show the modules the caller may
  list (`ListModules`, `GetModule`, not found otherwise), each with only the
  agents, apps and jobs it may list (`ListAgents`, `ListApps`, `ListJobs`).
- **Use**: `authorize_agent`, `authorize_model`, `authorize_app` and
  `authorize_job` are a lease check by the hosting module and the check of its
  **caller**. The host forwards the token it received (`caller_token`; the
  `Abi-On-Behalf-Of` header and `caller_on_behalf_of` are gone); `caller.py`
  verifies it as a kernel endpoint does. It is either a host token
  (`abi:host:<sa>`, the caller acting alone, addressed to that host) or a
  **delegation** (`abi:delegated:agent`: `sub` the user, `act` the module acting
  for them, which is the host itself). Discovery accepts a delegation only from the
  host whose account it names (`DiscoveryNATS._is_for_host`), so a module that read
  one from a request replays it nowhere, not even at another host. The caller of
  the checks below is then the module acting for the user, and both sides must
  allow (RFC §5.3): the module's own side is `builtin.module_bootstrap`'s
  `OwnHosted` and `OwnRuns` statements (what it hosts, and the runs of the user it
  acts for), which open no broker subject. Then: `InvokeAgent` on
  the agent for a submit, `GetAgentRun` / `CancelAgentRun` on the run for a poll
  or a cancel (the host names the run and its recorded owner), `ChatModel`,
  `OpenApp`, `TriggerJob` on the job, `CancelJobRun` on the job run. An invisible
  target gets its own not-found code (`AGENT_NOT_FOUND`, `INVOCATION_NOT_FOUND`,
  `MODEL_NOT_FOUND`, `APP_NOT_FOUND`, `JOB_NOT_FOUND`, `RUN_NOT_FOUND`), a visible
  one `PERMISSION_DENIED`. `caller_identity` is the owner of the runs this caller
  starts: the user it acts for, else itself. `caller_admin` is always false.
- **Jobs**: a trigger is a stored message: its token (`JobProxy.trigger` adds the
  transport's credentials) is checked as of `stored_at`, when JetStream stored
  it. The SDK job host asks before it runs a manual trigger (refused: the run is
  recorded FAILED and the message terminated) or honours a cancel. Engine-hosted
  jobs have no lease: `EngineJobLoader.job_authorizer` runs the same check
  (`require_job`) in process. Scheduled and event triggers are the host's own:
  until broker permissions (#60) restrict who may publish on a trigger subject,
  their kind header is trusted.

## Eviction (platform administration)
`evict` removes a registration whatever its lease: `discovery:Evict` on its
module, a policy, not a hard-coded identity. A caller who can see the module
gets PERMISSION_DENIED, anyone else INSTANCE_NOT_FOUND. A live owner's next renewal fails with
LEASE_EXPIRED and the SDK session registers again under the same instance id
with a fresh lease token, so eviction clears crashed or stuck registrations;
stopping a module means stopping its process. Registering an instance id whose
record expired or was evicted is a new registration (STARTING until its next
initialized renewal).

## Generations
Replicas of one generation (the same rollout id, or none on both) must declare
identical dependencies, agents, jobs and models for a contract major, or the
registration fails with DESCRIPTOR_CONFLICT. A rollout may change them for the
generation it replaces: it stays STAGED, outside READY lookups and READY-gated
authorizations, until its cohort cuts over.

A module always keeps a serving generation while it has an initialized
instance: its latest complete rollout; else the generation that served at the
last write (stored statuses), even if its rollout became incomplete; else the
oldest. A completing rollout drains older rollouts of its modules, complete or
not. The cycle check reads edges per generation (own cohort, then the serving
or one other live generation for the rest) and refuses only cycles through the
registering module. See the ADR, "Serving generation and dependency cycles".

## Agent authorization
`authorize_agent` with `new_invocation` false (status, event and cancel polls)
is answered from the registry as this replica last read or wrote it, when that
is under `snapshot_seconds` (1 s) old and allows the call. Leases are checked
against the clock at use. A submit, and anything the snapshot would refuse,
reads the registry, so a snapshot never refuses what the registry allows. An
eviction or unregister through another replica can still let polls through for
up to that second. Every read and successful write refreshes the snapshot.

## Concurrency
`DiscoveryNATS` answers calls side by side, up to `nats.max_concurrent_requests`
(`naas_abi_sdk.concurrency.ConcurrentCalls`); `stop()` answers the calls received
first. Writes use group commit (`DiscoveryService._mutate`): a replica writes
once at a time, each write taking every mutation waiting, applied in order on
its own copy of the registry, in one compare-and-swap. Run side by side, the
compare-and-swaps on the one registry document would exhaust their five retries
(`REGISTRY_BUSY`). Reads do not wait for writes.

## Tests
Use `uv run pytest .../services/discovery --import-mode=importlib`. Unit tests inject
a clock and a fake port; integration tests use native nats-server.
`discovery_authorization_test.py` pins the caller checks (no policy, granted,
denied) for agents, models, apps and jobs, run ownership per user, module-name
binding and list filtering; `caller_test.py` the forwarded caller. Add port
implementations by implementing both read and compare-and-swap methods.
