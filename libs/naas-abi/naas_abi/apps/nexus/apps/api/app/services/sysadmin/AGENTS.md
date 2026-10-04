# SysAdmin domain

Views of a running deployment for platform super admins: kernel services (configuration plus NATS micro-service stats), engine modules, remote modules in NATS discovery, the broker (server, connections, JetStream), and live NATS traffic. Super admins can also browse and change the data kernel services hold (Data tab).

## Layout

- `port.py`: domain values and ports (`ServiceConfigurationSource`, `EngineModuleSource`, `MicroServiceMonitor`, `ModuleRegistry`, `NatsServerMonitor`). Adapters raise `SourceUnavailable(source, reason)`; nothing else crosses a port.
- `service.py`: use cases. Views degrade per source and report `sources: {name: {available, reason}}`.
- `adapters/secondary/`: engine configuration (adapter kinds only, never settings), engine modules, `$SRV.STATS` scatter-gather, discovery, the broker HTTP monitor (`nats.monitoring_url`), in-memory fakes.
- `adapters/primary/`: FastAPI router (`/api/admin/system/*`, `require_superadmin` on the router) and the JSON serializer (dataclass fields plus computed properties).
- `traffic.py`: live traffic. `TrafficEvent` (metadata only), subject classification, caller from the token's `sub`, trace id from `traceparent`, and `TrafficHub` (one tap while a viewer watches, bounded per-viewer queues that drop oldest). `adapters/secondary/nats_traffic_tap.py` subscribes to ABI request subjects plus `_INBOX.>` to pair replies; transfer subjects are excluded. Served as SSE at `/api/admin/system/traffic/stream`. Source order (`FallbackTap`): `JaegerSpanTap` (recent spans from the tracing backend, `telemetry.query_url`) first, the NATS tap second; the first frame names the live source and why others were skipped.
- `GET /telemetry`: tracing as configured (`telemetry:` in the engine config); `traces_readable` says the Traces tab can read traces (`query_url`, else `ui_url`), and the web links trace ids to that tab on it. `ui_url` stays a secondary Jaeger link. HTTP spans come from `app/core/tracing.py`.
- `factory.py`: wires adapters from `engine.configuration` (identity `api`, connection name `nexus-api-sysadmin`, bounded connect time).
- `contracts.py`: one contract per port. A new adapter's test subclasses it with a fixture describing `tests/fixtures.py`'s deployment.

## Service data (Data tab)

- `resources.py`: a service's data as a tree of entries (`""` is the root; containers hold entries, items hold a value), the `ServiceResources` port (list, stat, read, download, write, delete), `ResourceCapabilities` (`browse`, `lookup`, `create`, `reveal`, `write_format` shown by the editor) and per-entry `actions`, `ResourcePage.listable` (false: open entries by id), bounded previews (`PREVIEW_BYTES`), errors, and the `AdminAuditLog` port.
- `resources_service.py`: `ResourceAdminService`. Reads are plain. Create, replace, delete and reveal are audited: a `requested` record is written first and nothing changes if it cannot be (`AuditUnavailable`, 503); `succeeded` or `failed` (exception type only) follows. Replace and delete need the id typed back as `confirm` (409 otherwise). Uploads and downloads are size-bounded.
- One adapter per kernel service in `adapters/secondary/<service>_resources.py`, each tested with `ServiceResourcesContract` (writable data; knobs `base`, `child`, `encode`, `assert_shown`, `sized`, `extra_names` for structured values) or `ReadOnlyResourcesContract` (logs, registries) on a real in-process backend:
  - `object_storage` (paths, folders; a page classifies only its own entries), `secret` (masked until reveal, sizes never disclosed, writes reach every secret adapter), `keyvalue` (raw values, TTL kept on replace), `cache` (never unpickled; binary and pickle show sizes only), `document` (namespace / collection / document, tagged JSON, version-checked deletes; LangGraph saver collections decoded by `langgraph_checkpoints.py`, see below), `vector_store` (collections / documents, JSON with vector), `triple_store` (graphs as Turtle; the schema graph is read-only), `dataset` (namespace / table, CSV), `source_control` (owner / repo / path on the default branch; each write is one commit), `coding_environment` (environments and templates), `event` and `activity_log` (read-only, newest first), `model_registry` (read-only), `email` (create = send; kept mail where the adapter keeps it), `bus` (JetStream streams and messages; `KV_` streams are not deletable) and `discovery` (instances; delete = evict).
  - `ResourceCapabilities.expiry`: the service takes `ttl_seconds` on write (`ExpiringResources`); only keyvalue does. The PUT route takes it as a query parameter and refuses it (405) for other services.
  - Core was extended where a service could not enumerate or administer its data (key listing for keyvalue and cache, raw cache entries, document namespaces and the unlocked proxy's `document_admin`, vector paging and collection info, event types, activity paging, kept sent mail, repository deletion, all coding environments, discovery eviction), through every adapter and the NATS contracts. See ADR 20261002_sysadmin-service-data.md.
- Richer browsing for the web explorer:
  - Listing entries may carry `attributes["summary"]` (one line under the name) plus cheap typed attributes for columns.
  - `read()` may return a structured `view` (`json`, `table`, `triples` with N-Triples terms, `vector`, `email`, `message`, `status`; shapes in `ResourceDetail`). Never put a masked value in a view.
  - `capabilities.search` means `list(..., query=)` filters on the server; otherwise the web filters loaded pages.
  - Keep per-row work cheap and documented: one grouped query per page, never a call per row.
- LangGraph checkpoints (`adapters/secondary/langgraph_checkpoints.py`): the document checkpointers' `langgraph_checkpoints_v2` / `langgraph_writes_v2` (and schema 1 `_v1`) collections list newest first, grouped by thread, with step, source, message count and last message as attributes. Schema 2 values live in `langgraph_blobs_v2` / `langgraph_items_v2` / `langgraph_parts_v2` (listed plainly): a listing page reads only each conversation's tail (`tail_references`, three batched queries), a checkpoint view reads its values with the shared pure helpers (`references`, `batches`, `raw_channel_values` in `naas_abi_sdk.langgraph_documents`), at most `VIEW_PARTS` bytes of split values, and a value not read is described. A checkpoint reads as a `checkpoint` view: the conversation (roles, tool calls, results, model, token usage), the other state, its pending writes (one indexed query) and `parent_entry` (the previous step, id derived like the saver's `_key`). The msgpack values are decoded without importing or constructing anything (`{"$type": "module.Class", ...}`), `SecretStr` values are masked in the view, and pickle is never loaded. The raw document (Raw tab, download) is still the stored bytes. Tests write through the real SDK saver, and schema 1 through core's legacy test writer (`tests/langgraph_fixtures.py`).
- `sql_audit_log.py` writes `audit_logs` (`action` = `sysadmin.<operation>`) and raises instead of swallowing. `history()` reads them back newest first with the actor's name; served at `/resources/history` and `/resources/{service}/history?id=`. `in_memory_resources.py` holds the fakes.
- HTTP: `adapters/primary/sysadmin__primary_adapter__resources.py`, mounted at `/api/admin/system/resources`. Values travel as raw bodies; `HttpActivityLogMiddleware` skips bodies under that prefix. Reveals answer `Cache-Control: no-store`; downloads are attachments with `nosniff`.
- `factory.build_resource_admin` wires every kernel service; one the engine cannot give (not configured, failed to load, NATS mode off for bus and discovery) is listed as unavailable with the reason. A new service needs one adapter passing a contract and one line in the factory.

## Rules

- Never read or return adapter settings, tokens or message payloads. Traffic reads headers and sizes only. The Data tab is the one place values are shown, and only through `ResourceAdminService`.
- The tap receives every reply on the bus while it runs: it starts with the first viewer and stops with the last. Never start it in the background.
- NATS calls must stay bounded: a dashboard never waits on nats-py's reconnect loop.
- `adapters/secondary/nats_integration_test.py` runs both NATS adapters against a real `nats-server -js -m`; run it after changing them.

## Jobs (Jobs tab)

- `jobs.py`: values (`JobDefinition` with structured `TriggerSpec`, `JobRun`, views) and ports: `JobCatalog` (engine owners, discovery), `JobRunStore` (run records), `JobControl` (trigger, cancel), `JobQueue` (consumer depth). Errors: `JobNotFound`, `RunNotFound`, `RunNotCancellable`.
- `jobs_service.py`: `JobsAdminService`.
  - Builds the overview: next ticks, recent runs, running counts and queue depth per job.
  - Pages runs across job modules (newest first; `before` is the last `started_at`) and returns one run with its trace link (`telemetry.ui_url`).
  - Triggers and cancels are audited with `run_audited` (service `jobs`, operations `trigger` / `cancel`).
  - The overview degrades per source (`engine`, `discovery`, `runs`, `queue`).
  - SKIPPED runs (a handler's `ctx.skip`, nothing to do) are left out of runs pages without a status filter (unless `include_skipped`), of each job's recent runs and health, and of failures; the overview gives each job's `last_skipped`.
- `jobs_schedule.py`: pure helpers.
  - `next_cron`: 6-field cron with seconds, aliases, names, cron's day OR rule, zoneinfo; UTC when no time zone is set.
  - `next_every`: the last scheduled fire plus the interval, rolled forward past now.
  - `describe`: triggers in plain English.
- Adapters:
  - `job_catalogs.py`: engine owners from `factory.job_owners` (engine modules, `naas_abi`, the kernel dataset jobs) and discovery descriptors.
  - `document_job_runs.py`: run records in each module's document namespace, collection `runs_collection(project)`, through `document_admin`.
  - `nats_job_control.py`: SDK `JobProxy` / `JobRun`.
  - `nats_job_queue.py`: JetStream consumer info.
  - `in_memory_jobs.py`: fakes.
- Contracts: `JobCatalogContract`, `JobRunStoreContract`, seeded from `tests/fixtures.py`.
- `jobs_integration_test.py` runs an SDK job host on a real `nats-server -js`: trigger, record, queue depth, cancel.
- HTTP lives in `adapters/primary/sysadmin__primary_adapter__jobs.py`, mounted at `/api/admin/system/jobs`:
  - `GET ""`
  - `GET /runs`
  - `GET /runs/{module}/{run}`
  - `POST /{module}/{job}/trigger`
  - `POST /runs/{module}/{run}/cancel`
- Job hosts record `fired_at` (when JetStream stored the trigger) and `trace_id` (the run's CONSUMER span) on every run.
- `GET /failures?since=` lists runs FAILED or TIMED_OUT since a time (default: the last day; at most `MAX_FAILURES` read, `more` when capped): the web polls it every minute for a badge on the Jobs tab and a banner in it, counted since the admin last marked them seen (kept per browser).

## Agent runs (Agents tab)

- `agents.py`: values (`AgentRun`, `AgentEvent`, `AgentRunsPage`) and ports: `AgentRunStore` (records, events) and `AgentControl` (cancel). Errors: `AgentRunNotFound`, `AgentRunNotCancellable`.
- `agents_service.py`: `AgentsAdminService` pages runs across the modules discovery lists with agents (or one module named by the caller, no discovery needed), returns one run with its first `MAX_EVENTS` events (`EVENT_PREVIEW` characters each) and trace link, and cancels ACCEPTED/RUNNING runs through `run_audited` (service `agents`, operation `cancel`).
- Adapters: `document_agent_runs.py` reads what SDK agent hosts write in each module's namespace (`agent_runs_collection(project)` / `agent_events_collection(project)`, `naas_abi_sdk.agent_host`), newest first by `submitted_at`; `nats_agent_control.py` sends the cancel to the owner instance's agent subject with the API's token (the host lets discovery's admin identities cancel any caller's run, never read its output); `in_memory_agents.py` holds the fakes. `AgentRunStoreContract` in `contracts.py`, seeded from `tests/fixtures.py`.
- HTTP: `adapters/primary/sysadmin__primary_adapter__agents.py`, mounted at `/api/admin/system/agents`: `GET /runs`, `GET /runs/{module}/{run}`, `POST /runs/{module}/{run}/cancel`.

## Traces (Traces tab)

- `traces.py`: values (`Span`, `SpanEvent`, `SpanLink`, `Trace`, `TraceSummary`), `TraceQuery` and its checks (`LOOKBACKS`, limit 1–100, min ≤ max), trace id normalization, and the `TraceStore` port. Times are millisecond offsets from the trace start; a trace above `MAX_SPANS` (5000) comes back `truncated`.
- `traces_service.py`: `TraceService`. Tracing that is not configured makes every call raise `SourceUnavailable("tracing", ...)` (503), checked before the arguments.
- Adapters:
  - `jaeger_trace_store.py`: Jaeger's query API v3 (`/api/v3/services`, `/operations`, `/traces`, `/traces/{id}`) at `telemetry.query_url`, else `telemetry.ui_url`. Jaeger filters by service, operation and time only; errors and duration filter in the API over a deeper search (5 × limit, at most 500), since Jaeger's duration filter is per span. No service searches the first `MAX_SEARCH_SERVICES` alphabetically; the `jaeger` service is hidden.
  - `otlp_json.py`: OTLP JSON helpers shared with `jaeger_traffic_tap.py` (attribute values, ids, times) and the conversion to a `Trace`. Arrays and maps become JSON strings.
  - `in_memory_traces.py`: the fake.
- Contracts: `TraceStoreContract`, `UnavailableTraceStoreContract`, seeded from `tests/fixtures.py`. `jaeger_trace_store_integration_test.py` runs it on a real Jaeger (`run_jaeger` from the traffic tap's integration test).
- HTTP lives in `adapters/primary/sysadmin__primary_adapter__traces.py`, mounted at `/api/admin/system/traces`:
  - `GET /services` → `{services, ui_url}`
  - `GET /operations?service=` → `{operations: [{name, kind}]}` (a name can repeat with another kind)
  - `GET ""` with `service`, `operation`, `lookback`, `min_duration_ms`, `max_duration_ms`, `errors`, `limit` → `{traces}`
  - `GET /{trace_id}` → the trace (404 when Jaeger does not have it, 400 for a malformed id)
- `factory.get_trace_store` returns the store or the reason tracing is unavailable; `get_trace_ui_url` gives the Jaeger link.
