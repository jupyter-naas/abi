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

## Compatibility for existing installations

An existing configuration needs no NATS migration. Omitting the top-level `nats`
field (or setting it to null) keeps exposure disabled. Engine construction, load,
and shutdown do not import the optional NATS runtime in that case. Existing local,
RabbitMQ, Redis, and other adapter selections remain unchanged; no new JWT secret
or running NATS broker is required. Installing the `all` extra includes the NATS
client dependencies, but does not enable NATS.

The new settings are independent opt-ins:

- Top-level `nats: {nats_url: ..., jwt_secret: ...}` exposes loaded services.
- A service's `adapter: nats_rpc` selects its remote RPC client, using `nats_url`,
  `jwt_secret`, and `service_identity` (default `api`).
- The bus's `adapter: nats_jetstream` selects the NATS/JetStream bus backend.

The repository and generated local Compose files put the broker behind the `nats`
profile. Plain `docker compose up` / `abi stack start` leave it disabled. Start it
explicitly with `docker compose up -d nats`, or include it in the stack with
`docker compose --profile nats up -d` (equivalently, set `COMPOSE_PROFILES=nats`).
This follows [Docker Compose profile semantics](https://docs.docker.com/compose/how-tos/profiles/).
`abi dev` also keeps NATS outside its default service set; use `--service nats`
when explicitly selecting the services to start. Starting the broker alone does
not change the application's adapter configuration.

Regression tests run an old-style configuration in a fresh Python process where
imports of the NATS package are blocked. They exercise engine load/shutdown and
filesystem storage, Python key-value, and Python queue operations.

## Validation

Parameterized unit tests cover all twelve RPC adapter pairs, both error envelope
shapes, cancellation, and non-replay. Local broker tests exercise 8 MiB and lower
broker caps, connection reuse after rejection, and a write finishing after its
client deadline. Bus tests cover non-replay for publish and enqueue.
