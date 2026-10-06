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
caller identity plus a lease token. Stage 1 does not authorize logical module IDs.
`discovery_factory.py` composes the service. Engine exposure is explicit opt-in;
replicas use a project queue group and share the same JetStream CAS snapshot. No silent in-memory fallback.

## Eviction (platform administration)
`evict` removes a registration whatever its lease. Only `admin_identities`
(default `api` and `engine`, the Nexus System app and the engine) may call it;
any other caller gets PERMISSION_DENIED. Identities are Stage 1 service names,
so this is hygiene between first-party processes, not a security boundary
against holders of the shared secret. A live owner's next renewal fails with
LEASE_EXPIRED and the SDK session registers again under the same instance id
with a fresh lease token, so eviction clears crashed or stuck registrations;
stopping a module means stopping its process. Registering an instance id whose
record expired or was evicted is a new registration (STARTING until its next
initialized renewal).

## Tests
Use `uv run pytest .../services/discovery --import-mode=importlib`. Unit tests inject
a clock and a fake port; integration tests use native nats-server. Add port
implementations by implementing both read and compare-and-swap methods.
