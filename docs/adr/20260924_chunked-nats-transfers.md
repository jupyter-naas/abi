# Chunked NATS object and model transfers

Status: Accepted

Date: 2026-09-24

## Context

Unary broker payload ceilings and a fixed 120-second generation deadline added
restrictions absent from local object storage and LangChain models. Output token
streaming alone did not solve large input histories or oversized tool chunks.

## Decision

Use the shared protobuf `transfer/v1` framing contract on domain-owned NATS
subjects. Open, write, start, read and close exchanges authenticate the caller;
opaque session handles are caller-bound. Strict upload/read sequences reject
replay. No automatic retry is introduced. Domain adapters retain operation and
error mapping; the shared host owns transport resources only.

Uploads spool to temporary disk before an explicit start can call the domain.
Downloads have two queued packets per session. Defaults are 64 KiB chunks
(reduced to at most half the broker packet ceiling), 32 sessions per domain and
60 seconds idle expiry. A configured total-upload cap is optional, defaulting to
none. Polling refreshes activity while waiting for a model's first or next token.
Short exchange timeouts do not bound total generation. Optional model execution
deadlines are configured separately; remote agents also default to no deadline.

Object byte APIs collect or split chunks internally; stream APIs use bounded
reads. Model messages, histories, tools, outputs and embeddings use fragmented
protobuf frames while preserving normal LangChain APIs. Old unary endpoints
remain compatible with their existing limits. No new base SDK dependency.

## Consequences

Existing configurations remain valid and local mode is unchanged. Updated SDK
facades require updated engine transfer endpoints. Deployments must size temporary
disk and can explicitly cap uploads/concurrency. Model payloads are reassembled
in memory for providers and callers; provider context limits remain authoritative.

Sessions are ephemeral, not durable jobs. Owner restarts interrupt transfers;
callers reconcile uncertain writes/inference rather than retry automatically.
Closing cancels async work; synchronous operations must finish before closing
resources. Provider billing cannot be guaranteed to stop. Slow consumers must
read within the idle period. Polling creates additional small control requests.

Discovery, ordinary unary RPCs, checkpoints and durable agent records retain their
own bounds. This decision does not change their persistence or authorization.
Verification includes a 32 KiB broker handling multi-megabyte object transfers and
large/slow model calls, plus the separate-process wheel-only module demonstration.


## Review follow-up (2026-09-25)

The following updates supersede the initial defaults and upgrade guidance above.

- Model inputs have a finite 16 MiB per-upload budget and 64 MiB aggregate budget
  across retained uploads, configurable through `nats.models.streaming`.
  Limits are checked before writes, including concurrent in-flight writes. This
  replaces small message-count caps with a byte budget; protobuf/provider decoding
  has additional memory overhead. Object streaming remains uncapped by default.
- Cleanup removes session handles immediately and runs independently of expiry.
  Close/shutdown wait at most one second. Files stay open until synchronous work
  finishes; deferred uploads retain their budget. Deferred cleanup count is bounded
  by `max_sessions` before admitting more work. A Python thread cannot be forcibly
  killed; backend socket deadlines and process isolation remain operational needs.
  This bounds TransferHost shutdown, not Python's executor shutdown at process exit.
- Upload files are created lazily. Model upload reads use the same safe thread
  wrapper as backend operations. Unexpected transfer/provider errors are logged
  with their exception before a sanitized error is returned.
- Small object byte uploads use unary RPC (at most 64 KiB and half the broker
  limit). The configured object upload cap also applies to unary writes. Larger
  and streaming writes remain chunked. Old owners support bounded unary fallback
  only on transfer-open NoRespondersError, never on a timeout or post-open failure.
  Large payloads require upgraded owners; uncertain mutations are never replayed.
- GET context entry prefetches one bounded fragment so missing-object errors occur
  before the caller begins a response. New owners always use the streaming port.
- Agent hosts enforce a configurable 300-second output inactivity timeout, reset
  after each persisted event. There is no default total duration limit on healthy
  streams. Non-streaming calls must finish within this inactivity budget. Explicit
  caller deadlines still apply. Cancellation-resistant synchronous work retains its
  conversation claim until it stops; this change does not pretend to fence or kill it.
- SDK model-stream cancellation waits for the pending iterator step to finish its
  cleanup before closing the generator, preserving CancelledError across loops.

Colocated transfer tests and SDK regressions cover capacity, byte budgets,
sequencing, cleanup with a blocked backend, cancellation, active/idle agents,
legacy fallback and early object errors. CI runs these plus native-broker tests.
