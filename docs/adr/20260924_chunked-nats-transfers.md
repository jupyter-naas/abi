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
