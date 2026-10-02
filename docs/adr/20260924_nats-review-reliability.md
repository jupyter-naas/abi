# NATS request ownership and remote agent output

Status: Accepted

Date: 2026-09-24

## Context

Review of PR #1299 found serialized domain calls, duplicate multi-engine
subscriptions, unavailable advertised cache tiers, lost bus configuration and
agent output limits that differed from local execution.

## Decision

Protect token/loop lifecycle with a short thread lock and initial connection
creation with an async lock. Request/reply waits run concurrently, without retries.
Queue independent model/discovery calls and transfer opens. Encode an owner in
transfer IDs and address subsequent requests to that owner's subjects. Legacy
model stream endpoints filter by the encoded owner. Owners never adopt or replay
another process's inference. Replicas must share compatible catalogs/backends.

Use event-driven stream waits. Transfer reads wait at most 500 ms, half the RPC
budget and half the idle period, then return pending. This preserves short network
deadlines during slow first-token generation without frequent busy polling.

Reject explicit bus adapter/URL conflicts in NATS mode and preserve the engine
bus's emit_message_events setting. Reject mixed local/remote cache topologies;
local tier indices must all be served by the owner. Cache/vector mutation audits
are emitted once at the primary, not by client facades. Audit remains fail-open.

Agent output format 2 stores events/results as immutable 8 KiB document fragments
with small manifests. Only after all fragments commit does CAS publish the event
sequence in the run record. Status pages carry references; SDK callers reconstruct
exact strings, without truncation, ring-buffer eviction or event-count caps.
Require explicit wire-format support to avoid old clients silently losing output.
Existing inline records remain readable. Prompts retain the existing 64 KiB cap.

Cache agent membership lookups for at most one second and invalidate caller views
on failures; authorization still runs through discovery for each request. Retry
transient heartbeat errors with capped exponential backoff/jitter. Authentication
and configuration errors are fatal. Unexpected failures receive three consecutive
attempts, then fail visibly. Endpoint rebinds roll back partial subscriptions.

## Consequences

No changes for local mode. Explicit conflicting NATS configurations now fail early
and require correction. SDK agent providers/consumers must upgrade together.
Queue groups prevent duplicate execution, but do not provide placement or fencing
for heterogeneous engine owners. Owner loss interrupts streams, with no replay.

Output size moves from a hard per-run cap to persistent storage capacity. Fragment
records have no automatic retention policy; incomplete uploads can leave orphan
fragments. Cleanup must respect invocation deduplication and execution claims.
No new persistence adapter or implicit ownership takeover is introduced. SDK native
bus operations still bypass engine BusService telemetry. Standard backend limits
and provider context windows continue to apply.

Validation includes concurrent calls on one client, shared first connection,
two engine owners on one broker, duplicate-free discovery mutations, large agent
output and more than 1024 events, audit emission and configuration rejection.

## Follow-up: 2026-09-25

Heartbeat delays are capped after jitter to half the remaining confirmed lease,
with a 50 ms minimum retry interval. Once expired, the cap uses half the nominal
lease so recovery attempts do not spin. This reduces avoidable incarnation churn;
it cannot guarantee renewal during an outage or a request exceeding the lease.

Updated generated model clients address legacy stream reads/closes to the owner
encoded in the stream ID. Generic subjects remain as compatibility endpoints for
older clients. The separate CI job runs core regressions and native-broker tests,
including discovery, large transfers, agents, models and checkpoint resumption.
