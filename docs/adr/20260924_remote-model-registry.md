# Remote model registry and LangChain proxies

- Status: Accepted
- Date: 2026-09-24

## Context

The model registry resolves canonical IDs to wrappers containing live LangChain
chat/embedding instances. Those objects cannot cross process boundaries. Remote
modules need to reuse configured models without provider credentials, and agents
inside a NATS-enabled engine should use the same inference boundary.

## Decision

Expose seven authenticated protobuf RPCs on `abi.svc.model_registry.v1`:
list_models, resolve, chat, embed, stream_open, stream_next, stream_close.
The owning registry remains responsible for model/provider registration and
resolution, including defaults and off-catalog provider factories. Registration
is a local bootstrap capability; it never transmits Python objects or credentials.
The configured engine is the model owner. This slice does not publish models
from arbitrary SDK module processes or add model placement/failover discovery.

SDK registry lookups return portable wrappers with `.model` set to a LangChain
ChatModelProxy or EmbeddingModelProxy. The optional `[models]` extra supports
langchain-core 0.3.78 through 1.x; the base SDK still requires only proto/nats-py.
Core's optional NATS extra depends on SDK[models], never the reverse. Its registry
client restores core wrapper types for existing Agent and IntentAgent users.
When NATS is enabled, service containers and the default registry accessor
receive that client. Primary endpoints always receive the private owner.

Messages use an explicit protobuf type plus finite JSON message data, decoded
only through an allowlist of LangChain message types. No pickle, constructor
loading, arbitrary Python callbacks or tool functions cross the wire. Tool
schemas, tool-call chunks, multimodal JSON content, response metadata and usage
metadata are preserved. Generic tool-based structured output parses on the
caller. JSON provider options are forwarded, subject to runtime configuration
restrictions; arbitrary provider-specific Python types are rejected. The contract
uses the current server-side validation approach; Protovalidate annotations are
still a documented tooling gap, including validation of JSON extension fields.

Streaming uses pull cursors with one outstanding read per stream, sequence checks,
a 16-chunk buffer, 30-second idle expiry, and a 120-second generation deadline.
Responses/requests are capped at 512 KiB (or the broker's smaller limit). Up to
32 inference operations/retained streams and 64 RPC handlers are admitted per
owner. Chat accepts up to 1024 messages, embedding batches up to 1024 texts, and
tool binding up to 128 definitions. Caller RPC timeouts can be shorter; SDK users
should configure timeout=120 for inference. These are interim defaults, not a
project-wide retry/deadline standard.

Each stream belongs to the verified service identity. There is no automatic
inference retry, stream replay, persistence, ownership takeover, or cancellation
of already completed provider side effects. Closing a stream requests local
cancellation. Synchronous provider code may continue until its underlying call
finishes; cancellation does not guarantee avoided billing. Provider exceptions
are sanitized at the boundary to avoid reflecting credentials or prompt content.
Existing shared-trust service JWT and broker ACL limitations still apply.

## Consequences

- Local projects without NATS keep existing model behavior and dependencies.
- NATS-enabled agents depend on broker availability for model lookup/inference.
- Existing model definitions and registration remain valid; callers receiving
  proxies can use LangChain invoke/ainvoke, stream/astream, bind_tools and embeddings.
- SDK synchronous methods work from worker threads while their owning event loop
  runs; calling them on that loop fails explicitly. Async methods support callers
  on a different loop by scheduling I/O on the owning loop.
- Streams add a request/reply per chunk and are ephemeral. A dropped cursor reply
  is an uncertain delivery, not permission to regenerate the model response.
- Provider-native structured output modes and arbitrary provider extensions are
  not claimed as universally compatible. Python objects and local-file handles
  in message content are unsupported; use portable JSON content/URLs/base64.
- No migration of model credentials, agent graphs, or conversation checkpoints.
- The standalone demo covers all seven RPCs with its four-package raw worker,
  and a separate core-free `[models]` environment exercises LangChain proxies.
