# Kernel services handle their calls side by side

Status: Accepted

Date: 2026-10-08

## Context

In NATS mode every module call to a kernel service goes through the service's
NATS endpoints, even inside one process (`Engine.services` returns the NATS
facades). nats-py hands a subscription its next message only once the callback
for the previous one has returned, and `TracedService` awaited the whole
handler there. Each endpoint therefore answered one call at a time per engine:
one slow SPARQL query made every call queued behind it miss the 10 s client
timeout. The handlers' synchronous service code ran on 8 threads per service
(`DomainRPCDispatcher`), which one endpoint never used in parallel.

Throughput is the number of calls in flight divided by their duration: 1,000
calls a second at 10 ms needs 10 in flight, at 200 ms it needs 200.

## Decision

- Each endpoint call runs in its own task (`nats_tracing.ConcurrentRequests`),
  so the subscription takes its next message at once.
- A service admits at most `nats.max_concurrent_requests` calls at once (64 by
  default), across its endpoints, and its dispatcher has as many threads, so an
  admitted call never waits for a thread. With every slot taken, the
  subscription's callback waits for one, and later calls stay in nats-py's
  buffer (512k messages or 128 MiB per subscription) until their deadline.
- The tasks run `nats.micro`'s own request handler, which keeps the endpoint
  statistics (`$SRV.STATS`, shown in the System app) and answers a handler's
  exception with a 500 reply.
- The limit is per process and set once, by `EngineNATSLoader.expose_services`,
  before the primaries are built.

## Consequences

- Calls to one endpoint run concurrently, as they did in-process before NATS
  mode (FastAPI's threads). Adapters were already called concurrently there.
- A drain still answers every call received: a call is counted from the moment
  it is received, while it waits for a slot too. `stop()` cancels the calls
  still running, as before.
- Threads only help while calls wait on I/O. Python CPU work (protobuf, RDF
  parsing) stays near one core per process; beyond that, services move to
  separate processes (docs/migrate-to-nats.md, phase 3).
- A service whose handler calls back into the same service through NATS holds
  one slot while it waits for another. With every slot held that way, calls
  wait until their deadline. No kernel service does this today.
- Streamed reads, transfers (`TransferHost`) and the RPC overflow host already
  ran each message in its own task, at most `max_sessions` × 4 at once
  (`RESOURCE_EXHAUSTED` beyond), as did the model registry (64). They are
  unchanged.

## Addendum (2026-10-08): discovery and the SDK hosts

Three more handlers awaited each message in their subscription callback. They
now share one implementation, `naas_abi_sdk.concurrency.ConcurrentCalls`, which
`nats_tracing.ConcurrentRequests` extends.

- Discovery (`DiscoveryNATS`) answers its calls side by side, up to
  `nats.max_concurrent_requests`. Reads (`get_module`, `list_modules`,
  `authorize_agent`, `authorize_model`) run side by side. `stop()` answers the
  calls received before it returns.
- Discovery's writes go through group commit (`DiscoveryService._mutate`).
  They all compare-and-swap one registry document: run side by side, 20
  concurrent registrations left 15 failing with `REGISTRY_BUSY`, and one at a
  time each paid a full read and write. A replica now writes once at a time,
  and each write takes every mutation that arrived while the previous one was
  in flight, applied in order, each on its own copy of the registry: one that
  fails is left out without changing what the others see. The result is the
  one of running them one by one. On a real JetStream KV, 200 concurrent
  registrations took 2 writes and 110 ms, against 200 writes and 288 ms one at
  a time. A write that fails, or a writer cancelled mid-write, fails every
  mutation it carried; a caller cancelled before its mutation is taken drops
  it. Another replica's write still makes the batch retry, five times at most.
- The SDK's `ModelHost` (module models) and `AgentHost` (submits, polls,
  cancels) take `max_concurrency` (64 by default). `ModelHost.close()` cancels
  the chats still running, as unsubscribing did before; `AgentHost.close()`
  answers the calls received before it cancels the runs, as draining the
  subscriptions did before.
