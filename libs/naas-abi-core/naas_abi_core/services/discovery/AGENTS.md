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
one configured owner per project is supported. No silent in-memory fallback.

## Tests
Use `uv run pytest .../services/discovery --import-mode=importlib`. Unit tests inject
a clock and a fake port; integration tests use native nats-server. Add port
implementations by implementing both read and compare-and-swap methods.
