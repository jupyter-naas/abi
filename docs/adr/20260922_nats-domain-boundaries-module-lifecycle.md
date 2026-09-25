# Network domain boundaries and independent module lifecycle

Status: Accepted

Date: 2026-09-22

## Context

Remote modules alone do not make an engine decomposable: injected services still
held direct references to other local domains. The owner requested that NATS
configuration enforce network boundaries even in one process, and that remote
modules retain the familiar ABI module construction pattern.

## Decision

A non-null top-level `nats` block now separates local owners from client views.
Only owners are passed to endpoint registration. Owners retain their own backend
adapters; their injected `services` containers and the engine's module-facing
service view contain NATS-backed facades. There is no local fallback when a
network call fails. Non-NATS projects keep the previous local wiring and optional
imports. The bus uses the project NATS broker when this mode is enabled, even
if the legacy service configuration names another bus adapter.

Process-local model registration is retained solely for local module bootstrap;
it is absent from the domain dependency view and from the standalone SDK.
A domain cannot obtain live model objects by falling back to local registry calls.
External NATS adapters keep their explicitly configured routes. Mixed local/remote
secret fanout is rejected because it can route a globally named endpoint into itself.

The cache can use the existing KV service with `adapter: keyvalue` and object
storage with `adapter: object_storage`. Those dependencies are loaded transitively.
Both traverse NATS in network mode. Direct Redis remains an optional cache backend,
not a call to the engine KV domain. Ordered tiers are exposed on additional v1
subjects without changing the existing cold endpoint or protobuf fields.

Facades do not duplicate events emitted by service-level endpoints. Cache and
vector endpoints wrap raw adapters, so their internal facades retain event
publication. Triple-store schema bootstrap runs only on the owner; the remote
facade forwards mutations without repeating triple notifications.

Each primary has a lazy dispatch executor with eight workers. This is an interim
capacity default: parents waiting for downstream domains cannot exhaust those
domains' workers in a shared asyncio executor. Context variables are copied.
Shutdown drains endpoints and closes dispatcher/client resources. Deadlines and
no-replay behavior are unchanged. Cyclic application calls are not made safe by
this wiring and still require domain-level design.

The SDK supplies BaseModule, ModuleConfiguration, ModuleDependencies, EngineProxy,
and run_module/naas-abi-module. A package exports ABIModule with configuration,
service declarations and load/initialize/unload hooks. The runner owns transport
and cleanup. The demo now uses this pattern and reports the lifecycle.

## Consequences

NATS-enabled callers now incur network round trips even in a monolithic process.
Existing local configuration is unchanged. NATS configuration deliberately changes
bus selection and cross-domain failure behavior. This removes local-reference
coupling but does not provide service placement, distributed ownership leases,
module registration/heartbeat, or a scheduler. Separate process placement still
requires explicit owner deployment; multiple engines must not accidentally own
the same subjects with divergent local stores.

The remote module structure matches the existing convention, but migration is not
a drop-in import substitution for arbitrary modules: operations are async and use
protobuf DTOs, configuration is dataclass-based, and framework component discovery
is outside the standalone runtime. Neither library depends on ABI core.

The demo uses real NATS observation to verify cache-to-KV/object-storage/event
requests and runs with the shared asyncio worker pool restricted to one thread.
Local backend data, issued tokens, and all broker processes remain disposable.
Authentication is still the Stage 1 shared-trust model; dependency declarations
are programming boundaries, not security authorization.

## 2026-09-24 follow-up

The model registry now has network lookup/inference proxies; local registration
remains a bootstrap operation. See [Remote model registry](20260924_remote-model-registry.md).
