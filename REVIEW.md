# Review: PR #1299 (standalone NATS modules, domain boundaries, document checkpoints)

- **Branch:** `feat/standalone-nats-sdk` into `feat/nats-jetstream-stage1`
- **Reviewed at:** `a582a19f6` (PR head on 2026-10-06). Line numbers refer to this commit.
- **Scope:** the 55 commits since the last full review (`567701d3f`), with the job host, NATS engine wiring, RPC/transfers, discovery, agent hosting, the agent checkpointer, cache, document and dataset read in detail. The Nexus System app was only spot-checked (auth wiring).
- **Not covered:** the local commit `d8dbc6de8` and uncommitted work in the working tree.
- **Evidence:** "Reproduced" means shown against a real nats-server 2.14.7. "Read in code" means traced through the source but not executed.

## Fixed since the 10-04 review

- [x] Event-triggered jobs dropped distinct events. `Nats-Msg-Id` is now a hash of the module-scoped trigger subject, the event subject and the event's own ID. Regression tests cover distinct events and two modules sharing a job name.
- [x] Completed jobs could stay RUNNING. The final status is saved before ack/term, and a redelivery that finds a finished record is retired without running again. Progress writes and broker heartbeats are now separate tasks.
- [x] Runs lost with their host on the last attempt stayed RUNNING. `reap_lost_runs` now fails them once heartbeats stop.
- [x] CI runs the broker job tests. Fixed with item 14.

Test run at `a582a19f6`: 101 job tests passed (SDK and engine, real broker included), none skipped.

## Must fix before merge

- [x] **1. Restarting a host resets every `@every` timer.** *Reproduced.*
  - **Done:** `_ensure_schedule` reads the schedule and publishes only when it is missing or its headers differ, expecting the sequence it read (conflicts re-read). Broker tests: restarts every 0.7 s keep an `Every("2s")` firing; replicas and restarts keep the sequence, a new interval replaces it.
  - **Problem:** `JobHost.reconcile_schedules` (`libs/naas-abi-sdk/naas_abi_sdk/job_host.py:295`) republishes each schedule message on every `start()`. NATS replaces the schedule and restarts its interval from the new message. An `Every("1h")` job whose module restarts, redeploys or scales more often than hourly never fires. On the broker, an `@every 3s` schedule fired 3 times in 10 s when left alone and 0 times when republished every 2 s.
  - **Fix:** read the current schedule with `js.get_last_msg(stream, subjects.schedule(index))` and publish only when it is missing or its headers differ (`Nats-Schedule`, `Nats-Schedule-Time-Zone`, `Nats-Schedule-Target`, `Nats-Schedule-TTL`, trigger kind). Publish with `Nats-Expected-Last-Subject-Sequence` set to the sequence just read (0 when missing), so two hosts starting together don't both reset it. Keep the purge of stale indexes as is.
  - **Test:** broker test that starts two hosts with the same descriptor and asserts the schedule's stream sequence is unchanged; then changes the interval and asserts it is republished.

- [x] **2. A trigger that expires before its retry leaves the run RETRYING or RUNNING forever.** *Reproduced.*
  - **Done:** a retry the trigger's `Nats-TTL` would not outlive (`fired_at` + TTL before the backoff ends) records FAILED and terms; RETRYING runs store `retry_at` and runs store `sequence`; `reap_lost_runs` fails RETRYING runs past `retry_at` and stale RUNNING runs with attempts left once `get_msg` no longer finds their trigger. Broker tests cover the review's scenario and the reaper.
  - **Problem:** trigger messages carry a `Nats-TTL` (60 s to 1 h for schedule ticks via `scheduled_tick_ttl`, 24 h for events). A run with attempts left relies on JetStream to redeliver after `nak`, but once the TTL has passed the message is gone and never comes back. On the broker, a 2 s TTL trigger nak'ed after 3.5 s was not redelivered. `reap_lost_runs` skips runs with attempts left, and retention never prunes non-terminal runs. Example: `Every("5m")` with `max_attempts=3` and a run that takes 6 minutes and fails stays RETRYING in the System Jobs tab.
  - **Fix:**
    - Before a `nak`, check whether the trigger's TTL has passed (`fired_at` + the `Nats-TTL` header). If it has, record FAILED with "Trigger expired before it could be retried" instead of RETRYING.
    - In `reap_lost_runs`, also fail RUNNING or RETRYING runs with attempts left once their trigger message no longer exists. Check with `js.get_msg(stream, sequence)`; the sequence is in the run id, or store it as a field. Only do this for runs not in `self._running` and with stale heartbeats (RUNNING) or past their nak delay (RETRYING).
  - **Test:** broker test with a 2 s TTL trigger, a handler that sleeps 3 s and raises, and `max_attempts=2`; the record must end FAILED.

- [x] **3. Local calls in NATS mode time out after 10 s, so nightly dataset compaction fails.** *Read in code.* **Fixed:** dataset maintenance runs on the engine's own dataset service (adapter-offered cross-domain jobs keep the facades); `_call`/`_context` and dataset `query`/`flush`/`compact` take `timeout_seconds` (maintenance passes 6 h); `nats.client_timeout_seconds` sets the facades' default.
  - **Problem:** `EngineNATSDependencies._client` (`libs/naas-abi-core/naas_abi_core/engine/engine_loaders/EngineNATSDependencies.py:100`) builds every in-process facade with the clients' default `timeout_seconds=10.0`. `Engine.job_owners()` gives `DatasetMaintenanceJobs` that facade, so `compact()` and `flush()` go over NATS with a 10 s limit. On real data the client raises, the run is FAILED (single attempt), and the owner keeps compacting in one of its dispatcher threads. Dagster compaction is disabled when the engine hosts jobs, so nothing compacts. Large SPARQL or dataset queries, vector upserts and object writes from local modules hit the same limit.
  - **Fix:**
    - When this engine owns the service, give kernel job owners the local service instead of the NATS facade, so there is no RPC hop.
    - Add a per-call `timeout_seconds` to the RPC client's `_call` and to the long operations (`compact`, `flush`, `query`), and have `DatasetMaintenanceJobs` pass the job's own timeout.
    - Make the facade default configurable (for example `nats.client_timeout_seconds`) instead of hard-coding 10 s.
  - **Test:** a fake dataset backend whose `compact` takes longer than the client timeout, run through the job path, must succeed.

- [ ] **4. A second engine process in NATS mode becomes a second owner of every kernel service.** *Read in code.*
  - **Problem:** with a `nats:` block, `EngineServiceLoader.load_services` (`libs/naas-abi-core/naas_abi_core/engine/engine_loaders/EngineServiceLoader.py:98`) loads every `ON_DEMAND_SERVICES` entry, and `EngineNATSLoader` serves them all on queue-grouped subjects. `abi dev up --with-nats` avoids this by leaving Dagster out (`libs/naas-abi-cli/naas_abi_cli/cli/dev.py:1753`). Nothing stops it elsewhere: `--service dagster`, a deploy that runs api and dagster from one config, or a script calling `Engine().load()`. Requests then split between the two processes. Services whose state lives in the process break: the in-memory coding environment returns NOT_FOUND for sessions created on the other owner, embedded Qdrant or Oxigraph file locks stop the second engine from starting, and DuckLake's `_CatalogLock` only protects within one process.
  - **Decision:** one serving engine per NATS account, held by a lease and handed over during deploys. A second engine fails at start, and Dagster needs no special case. See `docs/adr/20261006_single-serving-engine.md` (Accepted, partly implemented).
  - **Fix:**
    - [x] `engine/ownership/` domain (`libs/naas-abi-core/naas_abi_core/engine/ownership/`, with its `AGENTS.md`): `EngineLeasePort`, the `EngineOwnership` state machine, JetStream KV and in-memory adapters, a factory, and the generic lease adapter contract.
    - [x] Lease in KV bucket `ABI_ENGINE`, key `owner`. Atomic create, compare-and-swap renewal every `lease_seconds/4` (each call bounded), delete on clean shutdown. A contender treats the holder as dead when the revision has not moved for `lease_seconds` on its own clock.
    - [x] Roles under `nats.engine.role` / `ABI_ENGINE_ROLE`: `serve` (default), `client`, and `auto` (serve when nobody does, else client; never a standby). `abi chat`, `abi agent list` and `abi run script` default to `auto`.
    - [x] Starting a serving engine (`EngineOwnershipLoader`, `Engine.load` claims before opening any backend):
      - Lease free: take it.
      - Held by the same rollout or none: wait up to one lease period, take over if the holder is dead, else fail with an error naming it.
      - Held by a different `ABI_ROLLOUT_ID`: load services and modules, return from `load()` (ready), serve and start jobs once the lease is taken. Stop the process after `standby_timeout_seconds`.
    - [x] Handover in `Engine.shutdown`: stop jobs, release the lease, drain the service subscriptions, close.
    - [x] `NatsRPCClient` and the SDK `Transport` retry `NoRespondersError` for up to 5 s within the call deadline, only on engine-served subjects (`abi.svc.*`, `abi.discovery.<project>.v1.*`), never on transfer chunks or instance subjects (`naas_abi_sdk/no_responders.py`).
    - [x] Fencing: after half a lease period without a renewal the engine stops serving, and serves again if a renewal succeeds while the lease is still its own. If another engine holds the lease, the process stops (SIGTERM).
    - [x] CI: the lease, loader and handover tests, and `test_no_responders.py`, run in `.github/workflows/standalone_sdk.yml`.
    - [x] Zero-downtime deploys use shared backends only. Each service's adapter configuration declares where its data lives (`local_storage()`). A serving engine with `ABI_ROLLOUT_ID` refuses to start, before opening a backend or touching the lease, if a service it owns is SQLite, embedded, in-memory or on the local filesystem. The error names each service and path. A custom adapter passes with `shared_storage: true`.
    - [x] Shared storage for events and the activity log (`docs/adr/20261006_shared-event-and-activity-log-storage.md`):
      - The activity log lives in the Document Service (`adapter: document`, now the default).
      - Events have a PostgreSQL adapter: gapless `seq` visible in order across engines, JSONB filters, and raw-payload search. It passes the same storage contract as SQLite.
      - CI runs both on PostgreSQL (`make test-event-core`).
    - [ ] Copy existing per-actor SQLite activity logs into documents, for installations that need their history. Until then such an installation keeps `adapter: sqlite`.
    - [x] The PostgreSQL event log keeps 7 days. An hourly `event_archive` job, beside the adapter, moves older events into the dataset `events_archive` (`docs/adr/20261006_event-log-archive.md`):
      - Exactly once: the archive's highest `seq` is the resume point.
      - It never archives events an active consumer still needs.
      - Numbering comes from a counter row, so numbers are never reused.
    - [ ] Later: query archived events from the UI. The System app's events browser pages by `seq`, newest first, so the event service can read the dataset `events_archive` below the archive's highest `seq`. Older events would then appear in the same view:
      - type, time, search and JSON filters translate to DuckDB SQL (`json_extract`, `ILIKE`);
      - type counts add the archive's to PostgreSQL's.
      - Until then, the Data tab already shows `abi_event/events_archive` (schema, partitions, a 100-row preview, copyable SQL).
    - [ ] One engine instance id, used for the lease and as the owner id in transfer, overflow and stream subjects (today each generates its own).
    - [ ] Keep owner-scoped transfer and stream sessions after the release until they finish or a drain deadline passes. Today they end when their service's subscription is drained.
    - [ ] A `client` engine that loads no local backend at all. Today it builds the configured services as before, but serves none of them.
    - [ ] Remove Dagster from the dev CLI and compose files when it is retired.
  - **Test:** done for the start matrix, standby and takeover, fencing (including fencing before a standby can take over), lost and restored leases, the client and auto roles, the shared-backend check per adapter, and two real-broker runs under continuous traffic: a handover with zero failed calls, and a crash after which every request sent is answered. Requests in flight at the crash are lost. Both real-broker runs fail when the retry is turned off.

- [x] **5. One slow or abandoned dataset stream freezes dataset writes, then reads.** *Read in code. Reproduced over nats-server 2.14.7, then fixed: `query_stream` spools the result (one JSON line per `FETCH_ROWS` batch) to an anonymous temporary file under the lock and streams from it after releasing the lock; contract test `test_an_unread_query_stream_holds_up_neither_writes_nor_reads` runs directly and over NATS.*
  - **Problem:** `query_stream` (`libs/naas-abi-core/naas_abi_core/services/dataset/adapters/secondary/DatasetSecondaryAdapterDuckLake.py:631`) holds the SQLite catalog's shared lock for the whole transfer, and `_CatalogLock` lets waiting writers go first. If a Nexus Data-tab export is abandoned, the producer blocks in `emit()` with the lock held until the 60 s idle expiry. The next write waits for exclusive access, and every new `query`, `describe` and `inlined_row_count` then waits behind it. A slow but live reader holds everything for the length of the export.
  - **Fix:** don't hold the lock while waiting on the consumer. Under the shared lock, run the query and spool results to a temporary file (Arrow IPC or Parquet). Release the lock, then stream from the file.
  - **Test:** open a stream, don't consume it, then issue a write; the write must finish promptly.

- [ ] **6. Agents in an engine ignore `POSTGRES_URL` and silently lose conversation history.** *Read in code.*
  - **Problem:** `create_checkpointer` (`libs/naas-abi-core/naas_abi_core/services/agent/Agent.py:357`) now returns the engine's Document Service checkpointer whenever one is loaded, ahead of `POSTGRES_URL`. A deployment that kept history in Postgres starts with empty threads until someone runs `abi agent migrate-memory --apply`. If the Document Service is on SQLite, each replica also has its own memory. Only `AGENTS.md` mentions this.
  - **Decision:** every deployment moves to NATS, so as soon as this release ships, all engines use the Document Service checkpointer. Until an admin runs the migration job, users' earlier conversations have no memory: their old thread ids are not found. The admin runs the job from the System app at release time.
  - **Fix:** keep the new default and make the migration something an admin runs from the Nexus System app, as a kernel job. Most of the pieces exist:
    - The Jobs tab already has **Run now** with a JSON payload. It posts to `POST …/jobs/{module_id}/{job}/trigger`, which is super-admin only and audited.
    - Kernel job owners already exist: `DatasetMaintenanceJobs` is registered under `DATASET_JOBS_OWNER` through `Engine.job_owners()`, with sync handlers running in a worker thread.
    - The migration logic is already in core (`CheckpointMigration.migrate_checkpoints`). It is idempotent and reports before it writes. `abi agent migrate-memory` is a thin wrapper around it.

    Steps:
    - Add `AgentMemoryJobs` (owner such as `naas_abi_core.agent_memory`). Register it in `Engine.job_owners()` when the Document Service backs the agent checkpointer.
    - `agent_memory_migrate`: no trigger, so it runs only from **Run now**. Payload `{"from": "postgres" | "documents-v1", "threads": [...], "apply": false}`. With the default `apply: false` it is a dry run, and the report becomes the run's result in the Jobs tab. Read `POSTGRES_URL` from the engine's secrets, never from the payload: payloads are stored on the run record and shown in the UI.
    - `prune-memory` fits the same owner as a scheduled job.

    - [ ] Add `AgentMemoryJobs` with `agent_memory_migrate` (and `prune-memory` on a schedule).
    - [ ] **Window between deploy and migration.** A user who continues an old conversation before the job runs starts that thread from empty. The migration then reports the thread as `diverged`: its newer head hides the copied history, and the dry run lists it. Two options:
      - Accept it: put "run `agent_memory_migrate` (dry run, then apply) right after deploy" in the release runbook, and keep the window short.
      - Close it: while `POSTGRES_URL` is set, have the checkpointer copy a thread from Postgres the first time it reads it.
    - [ ] Amend `docs/adr/20261002_engine-agent-memory-in-documents.md`. Its rollout paragraph still says to stop the engines and run the CLI; replace that with the admin job at release. Add a changelog note. `abi agent migrate-memory` stays as an ops tool, and every deployment being on NATS means the job is always available.

- [x] **7. A rolling deploy that adds or changes a job or agent cannot start.** *Read in code. Fixed locally in `d8dbc6de8`, not pushed.*
  - **Fixed:** `d8dbc6de8` alone still compared every live replica of the contract. Now only one generation (same rollout id, or none) must match; a rollout's new or changed jobs, agents and models wait STAGED for its cohort. `run_module` with a rollout id starts the job host only once READY/DEGRADED (schedules and consumers are module-wide), and the System job list skips staged instances (discovery ADR, "Descriptors across generations").
  - **Problem:** `register` (`libs/naas-abi-core/naas_abi_core/services/discovery/discovery_service.py:183`) returns `DESCRIPTOR_CONFLICT` when a new replica's agents, jobs or dependencies differ from a live replica with the same `contract_major`. With `maxUnavailable=0`, the v2 pod crash-loops until v1 is stopped by hand.
  - **Fix:** push `d8dbc6de8` (rollout generations, drain by module id). Confirm it has a test where v2 adds a job while v1 is live and registration succeeds.

## Should fix

- [x] **8. A mixed local and remote secret fanout now fails at startup in NATS mode.** *Read in code.* **Fixed:** the endpoint serves a view of the local adapters only; the facade reads them through this engine's endpoint and keeps `nats_rpc` adapters for upstream reads, in the configured order.
  - **Problem:** `EngineNATSDependencies.build` (`EngineNATSDependencies.py:178`) raises "NATS mode cannot expose a mixed local/remote secret fanout". Stage 1 supported `[dotenv, nats_rpc]`: it exposed the local part and used `nats_rpc` upstream.
  - **Fix:** restore the stage-1 behavior: expose only the local adapters and keep the remote ones for upstream reads. If the rejection is intended, record it as a breaking change in the ADR and put the migration steps in the error message.

- [x] **9. The idle watchdog kills long non-streamed agent runs.** *Read in code.*
  - **Fixed:** an unstreamed run with a deadline gets no idle watchdog; streamed runs and runs without a deadline keep it (`test_a_deadline_governs_a_run_that_reports_no_progress`).
  - **Problem:** `_watch_progress` (`libs/naas-abi-sdk/naas_abi_sdk/agent_host.py:627`) cancels a run with no progress for `idle_timeout_seconds` (300 s). In invoke mode nothing updates `progress_at` until the handler returns, so `AgentProxy.invoke(prompt, timeout=1800)` with a 6-minute tool-heavy run is TIMED_OUT at 300 s.
  - **Fix:** in invoke mode with a caller deadline, let the deadline govern and skip the idle watchdog. Without a deadline, keep the watchdog as the default cap; it is what bounds runs since the "no deadline by default" fix.
  - **Test:** an invoke-mode run longer than `idle_timeout_seconds` with a longer deadline must succeed.

- [x] **10. Recreating the jobs stream makes new triggers look finished, so they are skipped.** *Read in code.*
  - **Done:** a record whose `fired_at` differs from the delivery's stream timestamp is replaced as a new run (missing `fired_at` still matches). Broker test deletes the stream and checks the reused sequence runs.
  - **Problem:** the run id is `<job>:<stream sequence>` (`job_host.py:614`), and a terminal record makes `_handle_delivery` retire the delivery without running it. If `ABI_JOBS_<project>` is lost or recreated while `job_runs` survives, sequences restart at 1 and new triggers match old SUCCEEDED records until retention prunes them (up to 7 days or 1000 runs).
  - **Fix:** `fired_at` (the trigger's stream timestamp) is already stored. Treat a terminal record as this delivery's only when `existing.data.get("fired_at") == _fired_at(msg)`; otherwise overwrite it as a new run. Treat a missing `fired_at` (records from before the field) as a match, to avoid re-running completed work after the upgrade.

- [x] **11. After the agent host re-registers, its in-flight runs can't be cancelled or tracked.** *Read in code.*
  - **Fixed:** a lost lease re-registers the same instance id with a fresh lease token, so run owners, claims, agent and model subjects stay valid (discovery ADR, "Lease loss keeps the instance id"); broker test `test_a_run_stays_reachable_after_its_owner_loses_the_lease` evicts the owner mid-run.
  - **Problem:** runs store `owner=session.instance_id` at submit (`agent_host.py:366`). After `LEASE_EXPIRED` the session gets a new instance id, and `_bind` drains the old subjects. Cancel and status are routed by the stored owner, which no longer exists. `cancel` returns OWNER_UNAVAILABLE and `events()` raises, while the run keeps executing in the same process.
  - **Fix:** on re-registration, rewrite `owner` on in-flight run records to the new instance id (a conditional write on each record's version), and keep the old subjects subscribed until those runs end. Alternatively, re-register under the same instance id when discovery allows it.
  - **Test:** force a lease expiry during a long run; then cancel and events must still work.

- [x] **12. A second cancel during the sync job grace period frees the slot while the thread still runs.** *Read in code.*
  - **Done:** the grace wait is wrapped in `contextlib.suppress(asyncio.CancelledError)`; test cancels twice and checks the interrupt and the wait for the thread's cleanup.
  - **Problem:** in `SyncJobRunner._stop` (`libs/naas-abi-core/naas_abi_core/engine/engine_loaders/SyncJobRunner.py:126`), the grace wait `await asyncio.wait({done}, timeout=self.interrupt_grace_seconds)` is not protected. Example: the job times out and `_handle_delivery` cancels it, then `JobHost.close()` cancels it again during a 30 s grace. `CancelledError` escapes, `state.interrupt()` is never called, and the runner returns while the thread is still running. The next delivery can overlap it even with `max_concurrency=1`.
  - **Fix:**
    ```python
    if self.interrupt_grace_seconds is not None:
        with contextlib.suppress(asyncio.CancelledError):  # a second cancel ends the grace early
            await asyncio.wait({done}, timeout=self.interrupt_grace_seconds)
        if not done.done():
            state.interrupt()
    ```
    The drain loop below already waits for the thread, and the caller re-raises `CancelledError` (`stopped_by_host`).
  - **Test:** cancel twice during the grace wait; assert `interrupt()` was called and the runner returns only after the thread exits.

- [x] **13. Every agent status poll reads the whole discovery registry.** *Read in code.*
  - **Fixed:** the provider reuses an authorization per (caller token, agent) for 5 s, never past the token's `exp`, submits always ask; discovery answers polls from its last read or written snapshot (under 1 s old, refusals re-read). A snapshot refreshed by every read and write was chosen over a KV watch (remote agent ADR).
  - **Problem:** `_handle_operation` calls `_authorize` (`agent_host.py:162`) on every RPC, polls included. Discovery then reads and decodes the full registry snapshot (up to 512 KiB) from JetStream KV. Handles without pushed updates poll every 0.1 s, so 50 watchers make about 500 full registry reads per second.
  - **Fix:** cache the authorization per (caller token, agent name) for a short TTL, bounded by the token's expiry. Keep `submit` (`new_invocation=True`) always going to discovery. On the discovery side, serve `authorize_agent` from an in-memory registry kept current by a KV watch instead of fetching the snapshot per call.

## CI and tests

- [x] **14. Eight broker test suites run in no CI job.**
  - **Problem:** these skip themselves when `nats-server` is missing, and the only job with a broker (`.github/workflows/standalone_sdk.yml`, `nats-integration`) doesn't list them:
    - `naas_abi_core/engine/engine_loaders/EngineJobLoader_integration_test.py` (the engine jobs suite the last review asked for)
    - `naas_abi_core/engine/nats_tracing_integration_test.py`
    - `naas_abi_core/services/bus/adapters/secondary/NATSJetStreamAdapter_claim_check_test.py`
    - `naas_abi_core/services/cache/adapters/secondary/CacheSecondaryAdapterNATSClient_test.py`
    - `naas_abi_core/services/keyvalue/adapters/secondary/KeyValueSecondaryAdapterNATSClient_test.py`
    - `naas_abi_core/services/email/adapters/secondary/EmailSecondaryAdapterNATSClient_test.py`
    - `naas_abi_core/services/source_control/adapters/secondary/SourceControlSecondaryAdapterNATSClient_broker_test.py`
    - `naas_abi_core/services/coding_environment/adapters/secondary/CodingEnvironmentSecondaryAdapterNATSClient_broker_test.py`

    All pass locally at `a582a19f6` on nats-server 2.14.7.
  - **Fix:** add them to the "Kernel services and their NATS clients over a real broker" step. Also have CI set a variable such as `ABI_REQUIRE_NATS_SERVER=1` that turns the "nats-server is not installed" skip into a failure, so a missing binary can't silently skip suites again.
  - **Done:** the eight suites run in the "Kernel services" step; with `ABI_REQUIRE_NATS_SERVER=1` (set on the `nats-integration` job) a skip naming nats-server fails, through conftest hooks in core, the SDK tests and the standalone example (`naas_abi_core/engine/nats_test_server.py`, tested in `nats_test_server_test.py` and `tests/test_require_nats_server.py`).

- [x] **15. New files without colocated tests.**
  - **Problem:**
    - `services/document/adapters/document_nats_codec.py` and `services/vector_store/adapters/vector_store_nats_codec.py` have no tests at all.
    - The SDK modules (`job_host.py`, `jobs.py`, `agent_host.py`, `discovery.py`, `claim_check.py`, `transport.py`, `module.py`, …) are tested only from `libs/naas-abi-sdk/tests/test_*.py`. That breaks the "each file has its `_test` file" rule.
  - **Fix:** add `document_nats_codec_test.py` and `vector_store_nats_codec_test.py` with round-trip cases: large integers stay exact, nested values, `None`, bytes. For the SDK, either move the per-file tests next to their modules or record the `tests/` layout as a deliberate exception in `libs/naas-abi-sdk/AGENTS.md`.
  - **Done:** both codec tests added (sint64 bounds, 2^53+1 and beyond-int64 JSON integers, nested values, `None` versus `{}`, bytes, datetimes, refused values); the SDK `tests/` layout is recorded as an exception in its `AGENTS.md`.

## Cleanup

- [x] **16. The broker message-size rule exists in four copies, and Go-duration parsing in two.**
  - **Problem:** message sizing appears in `naas_abi_core/engine/nats_rpc.py:165` (`message_size`), `naas_abi_sdk/messages.py` (`message_size`), `naas_abi_sdk/transport.py` (`_message_size`) and inline in `NatsRPCClient._do_request_async`. If the header framing changes and one copy is missed, a request passes the client check and the broker closes the connection. Separately, `job_host._seconds` repeats the duration parsing in `jobs.Every`.
  - **Fix:** keep one `message_size` in `naas_abi_sdk.messages` and import it everywhere. Expose one duration parser from `jobs.py` and use it in `scheduled_tick_ttl`.
  - [x] Message size: `naas_abi_sdk.messages.message_size` is the only copy; core's `nats_rpc` (both checks) and the SDK `Transport` import it. It now counts the header block for `{}` too, as nats-py sends one whenever headers are not None.
  - [x] Duration parsing: `jobs.go_duration_seconds` serves `Every`, `scheduled_tick_ttl` and the trigger TTL check; `job_host._seconds` is gone. (Nexus `jobs_schedule.go_duration_seconds` is a third copy, left as is.)

## Notes (smaller, or decisions to record)

- [x] **17. A document-store outage when a trigger arrives can use up its attempts and leave no run record.** *Read in code.*
  - **Done (full fix):** a failed pre-run read, claim-check resolve or RUNNING write logs an error and nak's with backoff; the consumer's `max_deliver` is unlimited and attempts are handler starts on the run, so an outage uses none (a delivery after the last attempt is termed). Unit and broker tests with `max_attempts=1`.
  - **Problem:** in `_handle_delivery`, the first `documents.get` and the RUNNING `_save` happen before the `try`. If either raises, the error escapes `handle`, nothing is acked or nak'ed, and the broker redelivers after `ack_wait` with no backoff. Each redelivery counts toward `max_deliver = max_attempts`, so an outage of roughly `max_attempts × ack_wait` drops the trigger with only a log line.
  - **Fix:** catch failures in that section and `nak(delay=self._backoff(attempt))`. To stop store outages consuming handler attempts, set the consumer's `max_deliver` higher than `max_attempts` (or unlimited) and enforce `max_attempts` in the host from handler starts recorded on the run.

- [x] **18. A run that can't save its completion holds its concurrency slot until the store recovers.**
  - **Done:** recorded in the jobs ADR ("Review hardening (2026-10-06)"); retries name the run and log at ERROR once the outage lasts `completion_error_after_seconds` (60 s).
  - **Problem:** `_save_completion` keeps the broker heartbeat alive and retries indefinitely (until shutdown). With `max_concurrency=1`, that job is blocked for the whole outage. This looks deliberate, since it avoids re-running finished work.
  - **Fix:** record the trade-off in `docs/adr/20261001_nats-jobs.md`. Make it visible too: escalate the retry log to ERROR after a threshold, or expose a metric.
