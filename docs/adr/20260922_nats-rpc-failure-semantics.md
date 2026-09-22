# NATS RPC payload limits and uncertain outcomes

## Status

Accepted for Stage 1.

## Date

2026-09-22

## Context

The Stage 1 service adapters use Core NATS request/reply, independently of the
bus adapter's JetStream work queues. Twelve clients duplicated connection, token,
deadline, and retry logic. Each retried any exception once, even when the remote
operation had already executed. The bus publisher/enqueuer had the same issue.
Micro-service error headers with an empty body were parsed as successful protobuf
defaults. Raising the broker cap alone did not address these failure modes.

## Decision

- Keep the 8 MiB cap already approved for launchers. RPC clients enforce the
  smaller of this cap and the broker's advertised maximum, counting auth headers
  as well as the serialized request. Larger data needs streaming or a storage
  reference; this change does not add either protocol.
- Share transport behavior in `engine/nats_rpc.py`. Domain adapters retain their
  ports, protobuf mapping, and domain exception mapping. No port or proto changes
  are necessary. Dataset's nested error envelope remains supported.
- Primaries return a structured, non-retryable `PAYLOAD_TOO_LARGE` for oversized
  replies. Clients reject micro-service error headers before decoding the body.
  Malformed request protobuf produces `INVALID_ARGUMENT` before domain dispatch.
- Do not automatically replay RPC calls, Core NATS publishes, or JetStream
  enqueues after an exception. Preserve timeout/no-responder/connection exception
  types. A connection error, like a timeout, can follow a completed operation.
- Retain the configurable 10-second RPC default. Include connection setup in that
  deadline; allow one additional second for the synchronous bridge to receive
  the async result, then cancel its local future. Cancellation cannot roll back
  remote effects. Preserve reconnecting clients and disable outgoing reconnect
  buffering so failed calls are not queued to execute after their deadline.
- Do not introduce a deduplication database or change authentication. Future
  automatic retries need an explicit operation ID and an outcome protocol.
  A trace ID alone is not a sufficient idempotency contract.

## Consequences

Transient failures now reach the caller instead of silently triggering a second
side effect. An oversized reply can follow a successful mutation; it does not
mean the mutation was rolled back. Callers must reconcile uncertain outcomes.

JetStream persistence and deduplication apply to stream messages, not arbitrary
Core NATS RPC effects. Durable application deduplication would require stable
operation IDs, payload validation, in-progress/completed outcomes, and atomic
coordination with the domain write. External services such as email providers
need their own idempotency support or reconciliation. Adding Redis, a SQL table,
or a JetStream KV key alone would not make that atomic. Any new persistence
adapter requires a separate design decision and owner confirmation.

Work-queue consumer redelivery remains at least once. This decision removes
automatic producer replay; it does not promise exactly-once business effects.
The remaining Stage 1 exposure/ownership and runtime review findings are separate.

## Validation

Parameterized unit tests cover all twelve RPC adapter pairs, both error envelope
shapes, cancellation, and non-replay. Local broker tests exercise 8 MiB and lower
broker caps, connection reuse after rejection, and a write finishing after its
client deadline. Bus tests cover non-replay for publish and enqueue.
