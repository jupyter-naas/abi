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
