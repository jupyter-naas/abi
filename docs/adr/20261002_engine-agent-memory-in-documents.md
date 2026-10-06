# Engine agent memory in the Document Service, stored as increments

## Status
Accepted. Amends `20260922_document-service-checkpoints.md`, which left the
synchronous core Agent on PostgreSQL or in-memory checkpoints and stored each
checkpoint as one full snapshot.

Amended 2026-10-06: the migration is an engine job an admin runs at release,
with the engines running, and pruning runs daily (Migration, Consequences).

## Date
2026-10-02

## Context
Core agents are built by module factories with `memory=None` and no engine
handle. `create_checkpointer()` then returned one process-wide LangGraph
`PostgresSaver` when `POSTGRES_URL` was set (Docker, and zen production on GCP),
else a new `MemorySaver` per agent (native `abi dev`: lost on restart, visible
nowhere). Remote SDK agents already checkpointed through the document service.
Agent memory lived in three places, and the Nexus System app's Document explorer
showed only the SDK part.

The document saver stored every checkpoint as a full snapshot. A conversation
rewrote its whole history at each step: on a 30-turn chat through a core Agent,
bytes written per turn grew from 20 KB to 268 KB (4.27 MiB in total). One
document or one list page could also exceed the 8 MiB NATS payload limit, so a
long conversation, or one large tool result, broke an SDK agent.

How engine agents share checkpoints today, which this decision must preserve:

- The shared `PostgresSaver` keys a thread by `thread_id` and `checkpoint_ns`
  only, whichever agent writes it.
- Nexus chat (thread = conversation id) and the OpenAI gateway (thread =
  `openai-<chat id>`) run each request on a duplicate of a cached agent with a
  fresh `AgentSharedState`. History and the active agent after a handoff
  (`current_active_agent` channel) come back from the checkpointer only.
- Sub-agents are subgraph nodes of their supervisor's graph. LangGraph then uses
  the parent's checkpointer, in child checkpoint namespaces, whatever the
  sub-agent was built with.
- A sub-agent invoked directly on its supervisor's thread continues that
  conversation: it reads what the supervisor wrote. This needs one scope across
  agents.
- Nexus switches the agent of a conversation (for example to the Documents,
  Slides or Sheets agent when such a file is open). A different top-level agent
  on a thread resumes routing to the previous agent's node, which its graph lacks,
  and the turn ends without calling a model. This defect predates this change
  and is left as is: it is a routing decision, not a storage one.

## Decision
- **Savers.** `naas_abi_core.services.agent.DocumentCheckpointSaver` implements
  LangGraph's synchronous saver API over a namespace-bound core
  `DocumentService`; its async methods run the sync ones in a worker thread.
  `naas_abi_sdk.langgraph.DocumentCheckpointSaver` stays async-only. Both plan
  their writes and decode their reads through `naas_abi_sdk.langgraph_documents`
  and only do I/O, so the documents are identical and a thread moves between an
  engine agent and an SDK agent unchanged. Core imports it from naas-abi-sdk,
  which core installs with its `[nats]` extra; the SDK stays core-free and
  Python 3.10 compatible.
- **Schema 2: increments.** A checkpoint document (`langgraph_checkpoints_v2`)
  keeps scope, ids, parent, metadata and the checkpoint without its values. Each
  channel value is inline when its serialization is at most 1 KiB, else a
  reference to a blob (`langgraph_blobs_v2`). A list value (`messages`) is a blob
  listing chunks of 32 element references; elements and chunks live in
  `langgraph_items_v2`. Blobs, chunks and elements are content-addressed within
  the thread, so an appended message writes the message, the last chunk, a small
  blob and the checkpoint document. A child checkpoint reuses its parent's entry
  for every channel whose version did not change, without serializing it.
  Pending writes go to `langgraph_writes_v2`.
- **Content addressing over version keys.** PostgresSaver keys blobs by channel
  version and relies on random version suffixes; with integer versions, two
  concurrent turns would write different content under the same key.
  Content-addressed values cannot collide, so versions need not be unique
  (`next_version` keeps a thread's type: integers for new threads,
  PostgreSQL-style strings for migrated ones) and identical values, like a
  system prompt re-emitted each turn, are stored once.
- **No document or read above a fixed size.** Any serialized value above 256 KiB
  is split into ordered `langgraph_parts_v2` documents. Reads fetch by reference
  (`ref in [...]`, scoped to the thread) in batches of at most 2 MiB, a quarter
  of the broker limit; checkpoint and write pages are sized to that budget, and
  the latest-checkpoint lookup that starts every turn reads one document.
- **Knowing what is stored.** A saver remembers, per checkpoint it loaded or
  wrote, the documents that checkpoint references (bounded, least recently used
  out). A put recalls them for its parent and for the ancestors LangGraph lists
  in `metadata["parents"]` (subgraph checkpoints reuse their supervisor's
  messages). Write order (parts, elements, chunks, blobs, then the checkpoint)
  makes a stored checkpoint complete; only `delete_thread` removes documents.
  Without a remembered parent, a put writes everything create-only: correct,
  just larger.
- **Schema 1 still reads.** Threads with no schema 2 checkpoint are read from
  `langgraph_checkpoints_v1` / `langgraph_writes_v1` and continue in schema 2;
  `list` returns schema 2 steps, then schema 1 ones. New writes go to schema 2
  only. `delete_thread` removes both.
- **Wiring and precedence.** `Engine.load()` binds
  `DocumentCheckpointSaver.for_engine(services.document)` through
  `engine.context.set_default_agent_checkpointer` before modules load, and
  `shutdown()` unbinds it. `create_checkpointer()` returns, in order: the engine's
  saver, a `PostgresSaver` for `POSTGRES_URL`, a `MemorySaver`. An explicit
  `memory=` always wins. Agents outside an engine keep the old behaviour, and so
  do engines without a document service or without naas-abi-sdk (a warning says
  why). The saver uses the engine's own document root, not the NATS client view.
- **Scope.** Every engine agent shares namespace `naas_abi_core.services.agent`
  and agent_id `engine.v1`, as they shared one `PostgresSaver`. Per-module or
  per-agent scopes would break the sub-agent case above and are not provably
  safe. SDK agents keep their module namespace and `agent_memory_id`.
- **Migration.** `abi agent migrate-memory` copies threads into schema 2 of a
  scope (default: the engine's; `--namespace`, `--agent-id`) from LangGraph's
  PostgreSQL tables (`--from postgres`, `$POSTGRES_URL` or `--source-url`;
  thread IDs from `SELECT DISTINCT thread_id FROM checkpoints`) or from document
  schema 1 (`--from documents-v1`). It reads the source through LangGraph's
  public saver API and writes through `put`/`put_writes`, oldest first and only
  what is missing: a dry run unless `--apply`, idempotent and resumable.
- **Migration and retention as engine jobs.** In NATS mode, when the document
  saver backs agent memory, `Engine.job_owners` hosts `AgentMemoryJobs` (owner
  `naas_abi_core.agent_memory`) over the same code:
  - `agent_memory_migrate` has no trigger; a super admin runs it from the Nexus
    System app (Jobs tab, Run now, audited). Payload
    `{"from": "postgres" | "documents-v1", "threads": [...], "apply": false}`.
    The default is a dry run whose report is the run's result. It reads the
    target too, so it counts the checkpoints present and missing and lists
    `diverged` threads. The PostgreSQL database is the engine's `POSTGRES_URL`
    (its secret service, then the environment), never a payload value: payloads
    are kept on the run record and shown in the UI, and errors are redacted.
  - `agent_memory_prune` runs daily at 03:00 UTC with the CLI's defaults
    (`keep_last` 20, values younger than 60 s kept, applied). A manual run takes
    `keep_last`, `threads`, `min_age_seconds` and `apply`.

  `abi agent migrate-memory` and `abi agent prune-memory` stay as ops tools.
- **Viewer.** The Nexus System app reads both schemas without deserializing:
  `references`, `batches` and `raw_channel_values` give the typed values, which
  its own decoder renders. Listing pages read only each conversation's tail;
  blob, item and part collections list plainly.

## Consequences
- Bytes written per turn no longer grow with history. The same 30-turn chat
  writes 20 to 24 KB per turn, 0.64 MiB in total instead of 4.27 MiB, through
  either saver; reads still return the whole conversation, which the model needs.
  A 20 MB tool result round-trips with no request or reply above the read budget.
- A step writes more, smaller documents (about 23 per turn of a core Agent) and a
  read takes a few batched queries (checkpoint, values level by level, writes)
  instead of one.
- Production rollout: deploy the release with the engines running. Right
  after, a super admin runs `agent_memory_migrate` from the System app, first
  as a dry run (`{}`), then with `{"apply": true}`
  (`docs/migrate-to-nats.md`). Until then, earlier conversations have no
  memory: their threads are not found. This window is accepted and kept short
  by the runbook; it is not closed by copying a thread from PostgreSQL on its
  first read. A thread a user continued during the window is reported as
  `diverged`: its newer head hides the migrated history. Without NATS mode no
  engine hosts jobs: stop the engines and run `abi agent migrate-memory`
  instead.
- Rollback is the previous release: the PostgreSQL tables still hold history up
  to the switch, but not the conversations held after it. A release before
  schema 2 does not read schema 2 documents.
- Concurrency is as with `PostgresSaver`: concurrent turns on one thread fork
  from the same parent and the newest checkpoint becomes the head. Checkpoint
  documents are create-only and values content-addressed, so nothing is
  overwritten or torn. There is still no run lease, and deleting a thread
  requires its runs to be stopped.
- Superseded values (an element a later step removed) stay until the daily
  prune drops the checkpoints that reference them, or the thread is deleted.
  The prune runs while engines serve. The 60-second grace and the kept head
  protect a running turn, except in one rare case: a turn on the thread being
  pruned writes a value identical to one that only pruned checkpoints held.
  The value counts as stored, then the prune deletes it.
- Engine agent memory appears in the Document explorer under
  `naas_abi_core.services.agent`. Native `abi dev` memory now survives restarts.
- Migrated pending writes have an empty `task_path`: LangGraph's `get_tuple`
  does not return it, and LangGraph does not read it back.
- Without the NATS mode, the document service loads only when a module declares
  it. Zen does (Intelwatch); a deployment that does not keeps the fallback.
- Tests: a saver contract held to LangGraph's `InMemorySaver` runs against the
  engine saver (sync and async API) and the SDK saver on one document backend;
  agent scenarios run against the old shared saver and the document saver
  across restarts and must match; a 30-turn chat asserts flat bytes per turn.
  The jobs are tested for their payloads, dry runs, redaction, cancellation and
  pruning, and copy from a real PostgreSQL when `DOCUMENT_TEST_POSTGRES_DSN` is
  set.
