# NATS RPC overflow for payloads above the broker limit

Status: Accepted

Date: 2026-10-03

## Context

The broker's `max_payload` stays at 8 MiB, the NATS recommendation. Only object
storage and the model registry stream through `transfer/v1`. Every other kernel
service call is one request and one reply, and a payload over the limit fails
with `PAYLOAD_TOO_LARGE` (see the RPC failure semantics ADR). Calls that can
exceed it today: a whole triple store `Get` or a large SPARQL result, dataset
query results, one large document, vector search with payloads, a large cache or
key-value value, source control files and diffs, and log or event pages.

Raising the limit is not an option: nats-server 2.14 warns above 8 MiB, refuses
more than 64 MiB, and one large message blocks a connection for everyone on it.

## Decision

Overflow automatically, without changing any service contract, by reusing the
`transfer/v1` framing on a shared host.

- Each engine process runs one overflow `TransferHost` on `abi.rpc.overflow`
  (`naas_abi_core.engine.nats_overflow`), started with the primaries on the
  shared NATS connection.
- **Large replies.** `respond_protobuf` parks a reply that does not fit in a
  read-only session bound to the caller (the request's service token) and
  answers with an empty body and the headers `Abi-Overflow-Reply: <transfer id>`
  and `Abi-Overflow-Size: <bytes>`. The client reads the frames, closes the
  session, and decodes the normal response type. The engine only does this when
  the request carries `Abi-Overflow: 1`: an older client would decode the empty
  body as an empty success. Without it, or without a host, the reply stays the
  non-retryable `PAYLOAD_TOO_LARGE` error.
- **Large requests.** The client uploads the serialized request as transfer
  frames (operation `request`), then sends the call with an empty body and
  `Abi-Overflow-Request: <transfer id>`. The primary resolves the body with
  `request_payload` before decoding. Requests go to a queue group, so the
  replica that receives the call may not own the upload: it reads the upload
  from its owner over NATS, with the caller's own token, so the session's caller
  binding still holds. If no host answers the upload (an older engine), the
  client keeps raising `PAYLOAD_TOO_LARGE`; nothing was sent to the service.
- **Small calls** are unchanged: one round trip, plus one header.
- **Limits** (`nats.rpc_overflow`): 256 MiB per value, 1 GiB of parked replies in
  memory and 1 GiB of uploads spooled to temporary disk per process, 64 sessions,
  1 MiB chunks (at most half the broker limit), 60 seconds idle expiry. A value
  over a limit, or a host at capacity, gives `PAYLOAD_TOO_LARGE` or
  `RESOURCE_EXHAUSTED` as before. Clients refuse to upload or download more than
  256 MiB.
- **Tracing.** Chunk exchanges add to the call's CLIENT span
  (`abi.overflow.*` attributes) instead of opening spans of their own. Each
  parked reply and upload is one SERVER span (`serve_transfer`) continuing the
  caller's trace.

Both clients implement it: core's `NatsRPCClient` and the SDK `Transport`, with
the shared protocol in `naas_abi_sdk.overflow`.

## Consequences

- `PAYLOAD_TOO_LARGE` only appears above 256 MiB, at capacity, or with an older
  peer. Overflowed values are still held whole in memory on both ends; layer 2
  (streamed results for whole-graph reads, dataset queries and listings) is the
  answer for values that should never be held whole.
- No replay is introduced. An upload whose call failed expires with its session.
  A parked reply that is never read expires after the idle period; the operation
  itself has completed, as with any lost reply.
- A large call costs extra round trips (one per chunk) and the overflow host's
  budgets bound what a process can hold for slow readers.
- Raw-subscription services (discovery, the model registry's transfers) keep
  their own bounds. Agent hosts and job hosts are unchanged.
