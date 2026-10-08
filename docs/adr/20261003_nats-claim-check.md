# Claim checks for published messages above the broker limit

Status: Accepted

Date: 2026-10-03

## Context

RPC overflow (20261003_nats-rpc-overflow.md) and transfer streams cover every
request/reply call. Published messages were not covered: the bus (core
`NATSJetStreamAdapter`, SDK `BusClient`), the live broadcast of events (agent
tool output, prompts, analytics payloads can be megabytes), job triggers (the
Nexus admin trigger forwards an HTTP body) and the event-to-job bridge, which
wraps an event in a larger trigger. Above `max_payload` they raised
`MaxPayloadError`, were logged and dropped (live subscribers, `OnEvent` jobs),
or failed a write that had already committed (triple store broadcasts). Worse,
the broker counts the header block in the message size and nats-py does not:
a JetStream publish adds `Nats-Expected-Stream`, so a body that just fit made
the server close the connection, failing everything else on it.

An overflow session cannot carry a published message: it is bound to one
caller and read once, while a published message may have many readers.

## Decision

Messages that do not fit travel as claim checks (`naas_abi_sdk/claim_check.py`,
used by core and the SDK alike).

- `prepare(nc, payload, headers, reserve=...)` compares the message as the
  broker counts it (body, header block, and the bytes the client library adds,
  e.g. `stream_header_reserve(stream)` for JetStream) with the connection's
  `max_payload`. A message that fits is sent unchanged. One that does not is
  stored in the JetStream object store `abi_claim_checks` (chunks sized to the
  broker limit) and sent as an empty body with `Abi-Claim-Check: <object>` and
  `Abi-Claim-Check-Size`.
- `resolve(nc, msg)` returns the payload a received message carries, reading
  the object back when it is a claim check.
- Senders: the core bus adapter's `publish` and `enqueue`, the SDK
  `BusClient.publish`/`publish_many`/`enqueue` (so the SDK event broadcast),
  `JobProxy.trigger`, and `JobHost.bridge_event` (which also resolves the
  event it wraps).
- Receivers: the core adapter's subscriber and worker callbacks, the SDK
  `subscribe`/`dequeue` handles (thin wrappers resolving in place), job
  deliveries.
- Limits: 256 MiB per message (`ClaimCheckTooLarge` above it); stored values
  expire after 7 days, so a queued or scheduled message must be read within
  that time.

Replies follow the same accounting: `naas_abi_sdk.messages.reply` answers with
only the reply's own headers (nats-py's `Msg.respond` sends the request's back,
service token included) and refuses a message over the limit instead of sending
it. The broker's `max_payload` is the only limit anywhere (no hard-coded 8 MiB).

## Consequences

- A published message, a queue item or a job trigger above the broker limit
  arrives whole; subscribers, workers and job handlers are unchanged.
- A stored value costs JetStream storage until it expires (7 days), also after
  every reader has seen it; values on fan-out subjects cannot be deleted on
  read. Size the JetStream store accordingly.
- Raw NATS readers outside these helpers (a traffic tap, a bus viewer) see the
  reference, not the payload.
- `naas_abi_core/engine/nats_send_sites_test.py` lists every raw NATS send in
  core, the SDK and Nexus with why it is safe; a new one fails the test until it
  goes through these helpers or is reviewed.
