# SDK service facades and scoped module access

## Status
Accepted for the standalone SDK implementation.

## Date
2026-09-23

## Context
Module business code currently constructs protobuf requests. That exposes delivery
mechanics and makes migration from core service methods unnecessarily difficult.
Core's class-wide module registry also couples component lookup to engine loading.
The requested NATS transport and standalone SDK must remain independent of core.

## Decision
Expose async service facades at `module.engine.services`, preserving existing
argument names and defaults wherever the wire contract supports them. Convert
requests and results internally; return Python values and SDK dataclasses generated
from protobuf descriptors. Generate straightforward methods from core source AST
at development time only. Core is never a runtime dependency. Keep typed protobuf
clients at `engine.rpc` and `ABIClient` as an explicit lower-level API.

Pass modules or services into components at construction. Provide `current_module()`
using a ContextVar bound by `run_module` around lifecycle hooks and execution.
Reset it on failure/cancellation and invalidate inherited contexts after unload.
Do not introduce a class registry. Background task ownership remains the module's
responsibility. This does not implement discovery or remote agent invocation.

Add authenticated cache tier discovery to preserve ordered reads, cold writes,
and all-tier deletes. No transport retries are added; uncertain mutations must
be reconciled by callers. Broker/JWT permissions remain unchanged. Scope and
namespace declarations are not authorization boundaries.

## Consequences
Modules no longer import protobuf for normal service calls. Await is required,
and portable SDK types replace core-specific classes. Optional RDF and LangGraph
extras keep the base installation at four distributions. Native engine modules
and configurations without NATS retain their existing behavior.

The new cache facade requires the accompanying engine describe endpoint. Framework
helpers, pickle, distributed lock contexts, and object streaming are not emulated.
Cache/vector raw adapter operations do not recreate core ontology events. Conversion
and task isolation tests plus wheel-installed separate-process demos validate the
boundary. Generated artifacts remain checked in; `make generate` in proto and SDK
is the interim regeneration workflow pending repository-wide codegen decisions.
