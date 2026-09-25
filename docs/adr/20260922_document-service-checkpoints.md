# LangGraph checkpoints through the document service

Status: Accepted

Date: 2026-09-22

## Context

Agents currently select PostgreSQL or in-memory checkpointing. Remote modules
should persist through an engine service instead of owning database connections.
The document service merged into main provides atomic versioned document writes,
queries, and module namespace binding. It initially had no NATS endpoint.

## Decision

Expose its eight storage primitives with a typed protobuf contract and NATS
primary/secondary adapters. Values preserve signed 64-bit integers, bytes, aware
datetimes, and nested structures; protobuf Struct would lose integer precision.
The existing service validates requests on the server. Bulk operations remain
client compositions, not multi-document transactions. Close only disposes the
client transport; no public RPC shuts down the shared storage adapter.

Engine NATS composition and module proxies use network document clients. The SDK
binds document access to the module's Python identity. Namespace fields remain
explicit in the wire contract and follow the existing trusted-caller model:
namespace binding is an API convention, not authorization against a hostile
caller with a valid deployment token. Per-module JWT scopes remain future work.
No Protovalidate annotations are introduced in this initial contract; portable
value, collection and query validation is authoritative in the document service.

`naas_abi_sdk.langgraph.DocumentCheckpointSaver` is an optional
`naas-abi-sdk[langgraph]` integration with LangGraph checkpoint 3.x. It implements
async checkpoint retrieval, history, puts, pending writes and thread deletion.
Use graph.ainvoke/astream. Existing synchronous core Agent execution and its
PostgreSQL selection are unchanged; this is not an automatic memory migration.
The base SDK still depends only on proto and nats-py. LangGraph runs in the
module, while persistence goes through document RPCs.

Store a complete serialized checkpoint and metadata atomically in one immutable
(create-only) document, and pending writes in separately keyed documents. Ordinary
task writes are create-only/first-write-wins; special error/interrupt writes may
be updated, following the installed LangGraph contract. Identical checkpoint
reconciliation is allowed after an explicit repeated call, but divergent data
for the same checkpoint ID fails. Transport calls themselves are never replayed.
Use LangGraph's typed serializer; do not introduce pickle fallback.

State is partitioned by module namespace, stable agent identity, thread ID,
checkpoint namespace and checkpoint ID. Schema version 1 is separate from the
document CAS version. Queries page through the service; metadata filters run on
deserialized metadata. No extra database or backend adapter is introduced.

## Consequences

A second process running the same graph can resume an interrupted conversation
without sharing in-memory state or database credentials. Sharing a storage
service does not mean sharing graph checkpoints between different agents.
Cross-agent collaboration needs invocation contracts, not direct state mutation.

This is async-only, opt-in and bounded by the existing 8 MiB RPC/broker payload
limit. Full snapshots increase storage and network cost; large checkpoint
externalization and retention policies are future work. Failures propagate, with
no local-memory fallback. Deletion can partially complete and requires quiescent
runs. Pending writes are individually atomic, not a batch transaction.

One active execution per agent/thread is still required. This saver does not
provide a distributed run lease or prevent duplicate external side effects.
Remote invocation needs execution ownership and reconciliation before replay.
Existing PostgreSQL history remains in its original tables until an explicit,
validated migration is implemented.

Validation includes the complete document adapter contract over a real broker,
a separate-process graph interrupt/resume test, and module/agent state isolation.
LangGraph contract reference:
https://reference.langchain.com/python/langgraph/checkpoint
