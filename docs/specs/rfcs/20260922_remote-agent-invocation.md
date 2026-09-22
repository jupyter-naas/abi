# Remote agents and module dependencies

Status: Proposed (not implemented by the document-checkpoint change)

## Problem

Service RPCs do not expose agents hosted in independent modules. A shared
checkpointer provides persistence but neither discovers agents nor invokes them.
A Python Agent or LangGraph object must stay inside its owning module process.

## Proposed contract

- A module declares required module identities and compatible agent contract
  versions. A discovery service records module instances, readiness, agent
  descriptors, contract versions, invocation subjects, and expiring leases.
- Startup waits for required capabilities within a bounded deadline before
  advertising ready. Heartbeats renew leases; expired dependencies make the
  consumer degraded. A lookup is not proof a subsequent call will succeed.
- A caller submits a typed invocation containing a stable invocation ID, target
  module/agent, conversation ID, protobuf input, tracing context, and deadline.
  The owning module validates the caller and input and executes its own graph.
  Never transmit Python classes, pickles, graph objects, or model clients.
- The owner persists invocation status and execution ownership through the
  document service. CAS controls transitions; leases require fencing so a stale
  worker cannot finish a run after another replica owns it. Do not infer this
  guarantee merely from checkpoint availability.
- Return an invocation handle. Stream versioned events with sequence numbers
  (tokens, tool events, interrupts, completion, failure); provide status/replay
  and explicit resume/cancel operations. Cancellation is cooperative and cannot
  undo completed tool side effects. Streaming needs backpressure and bounded
  retention independent of one-shot service RPC payload limits.
- Parent agents adapt remote invocations into explicit tools. Each graph retains
  its own checkpoint scope. Parent/child invocation links provide traceability;
  passing conversation context is explicit rather than concurrent writes into
  the same graph state.

## Retry and security decisions to settle before implementation

An invocation ID deduplicates submission, not every tool side effect. After a
lost acknowledgement, query durable status before resubmitting. JetStream
redelivery alone cannot guarantee exactly-once execution. Tools with external
side effects need their own idempotency or reconciliation contracts.

Module identities, allowed agent contracts and document namespace grants must be
verified server-side with broker credentials/ACLs and scoped service identity.
The current deployment-wide JWT model is insufficient for untrusted modules.
Lease/heartbeat intervals, startup timeout, stream retention and run fencing
policy need explicit defaults with tests. Circular required dependencies should
be rejected or modelled as optional capabilities.

## Suggested delivery order

1. Document service RPCs and checkpoint resume (implemented in the accompanying
   ADR; async SDK integration, no automatic migration of PostgreSQL history).
2. Module registration, readiness/lease discovery and dependency resolution.
3. Typed agent invoke/status/events/resume/cancel, with durable invocation state
   and ownership. Prove a parent in one module invokes a child in another process.
4. Failure tests: worker death, lost replies, expired leases, cancellation,
   resubmission, disconnected event consumers, and concurrent conversation runs.
