# Remote agent proxies and conservative invocation ownership

## Status
Accepted for the first invocation implementation.

## Date
2026-09-23

## Context
Discovery exposes module and agent descriptors but cannot execute an agent.
Agent and IntentAgent share invoke/stream_invoke; their graphs and model clients
must remain in the owning process. Timeout/reconnect must not silently repeat
side effects. SDK consumers must not import ABI core or receive JWT signing keys.

## Decision
Add an async AgentProxy resolved through declared module dependencies. Keep
invoke(prompt), stream_invoke(prompt), duplicate and optional as_tools surfaces.
A provider binds an async handler before READY and publishes instance-addressed
NATS endpoints. RemoteAgentAdapter lives in core and adapts both synchronous
Agent and IntentAgent without introducing a core dependency in SDK consumers.

The provider verifies callers via an authenticated discovery authorization RPC,
which checks the provider's lease/identity and validates the incoming service JWT.
The trusted provider receives the caller's bearer token, not the signing key.
This preserves Stage 1 trust; it does not implement per-module/end-user grants.

Store invocation IDs, results, sequenced events and conversation claims through
the document service. Create-only and CAS prevent competing owners from starting
the same invocation. Do not implement automatic takeover: claims have no lease
expiry. After death/uncertainty, another provider may return durable status but
cannot execute the same record or unlock the conversation. Operator reconciliation
must prove the old worker is stopped before removing an orphaned claim.

Cancellation/deadline are cooperative. Synchronous worker cancellation waits for
actual thread completion. There is no claim that discovery expiry fences tool
side effects. Raw graphs, graph interrupt/resume and parent-graph handoffs are
outside this first contract. LangChain tools preserve a parent's thread ID and
can dispatch from synchronous worker threads into the SDK loop.

## Consequences
SDK-only modules can invoke each other with no protobuf in business code. Existing
core Agent/IntentAgent providers need core, but their callers do not. A real
LangGraph parent-tool integration and a wheel-only multi-process demonstration
validate both routes without external model credentials.

Polling durable event pages provides replay after reconnect, with bounded storage
per run: 1024 events, 64 KiB per text value, 384 KiB per record, 32 active runs.
Default execution deadline is 120 seconds. Records do not auto-expire; retention
and orphan reconciliation remain explicit operational responsibilities. This costs
more document/RPC traffic than a transient stream and can block a conversation
until reconciliation, but avoids unsafe automatic re-execution.

Existing proto tooling still lacks Protovalidate annotations; server-side guards
and behavior tests enforce the new limits. Framework dependencies remain optional
through SDK [agents]. Existing local modules and NATS settings are unchanged.

## Capacity and claims (2026-10-05)

This supersedes the "32 active runs", "claims have no lease expiry", and
"Default execution deadline is 120 seconds" sentences above, and the line in
`docs/adr/20260924_chunked-nats-transfers.md` that remote agents default to no
deadline.

- One provider process accepts 200 live runs, shared by every agent it hosts.
  The 201st submit is `AGENT_BUSY`. Distinct `thread_id`s run together. One
  `thread_id` still has a single claim.
- A claim is released when a successful discovery lookup no longer lists its
  owner. The orphaned invocation is marked `OWNER_GONE` and is not replayed. A
  new invocation on that thread may start. This process never treats its own
  instance as gone. If the lookup fails, the claim stays.
- `invoke` and `stream_invoke` send a 300 second deadline when the caller omits
  `timeout`. An explicit `timeout` in the 1 to 3600 second range replaces it.
  `submit(deadline_seconds=0)` still means no deadline; the 300 second idle
  watchdog then applies.
- The idle watchdog covers streamed runs and runs without a deadline. An
  unstreamed run (invoke mode, or a handler without `stream_invoke`) records
  no progress until its handler returns, so a deadline, when there is one,
  bounds it alone: `invoke(prompt, timeout=1800)` may run for 30 minutes.
- A draining provider refuses new submits and lets an accepted run finish.
  That run releases its conversation claim when it completes. The draining
  instance stays listed, so another replica does not treat the claim as
  abandoned while the run is still going. The next submit resolves a `READY`
  instance.
- A provider that loses its discovery lease registers again under the same
  instance id (see the discovery ADR, "Lease loss keeps the instance id"), so
  its in-flight runs keep their owner: status, events and cancel still reach
  them, and their conversation claims stay held.

## Authorization without a registry read per poll (2026-10-06)

Every agent RPC asked discovery to authorize the caller, and discovery read and
decoded the whole registry snapshot (up to 512 KiB) for each one. A handle
without pushed updates polls every 0.1 s, so 50 of them made about 500 full
reads per second.

- The provider reuses discovery's answer for a caller token and agent for
  5 seconds on status, event and cancel, never past the token's `exp` (read
  from the token discovery already verified). Refusals are not reused. Every
  submit still asks discovery, which checks the provider is `READY`.
- Discovery answers those polls from the registry as that replica last read or
  wrote it, when under a second old and when it allows the call. Leases are
  checked against the clock. A submit or a refusal reads the registry, so the
  snapshot only ever lets a poll through for up to a second after another
  replica evicted or unregistered the provider.
- A KV watch keeping every replica's copy current was considered. It adds a
  long-lived consumer per replica and reconnect handling for a gain the
  provider-side cache already delivers; the snapshot is refreshed by every
  renewal this replica handles anyway.
