---
sidebar_position: 2
title: "Breaking changes in 3.0"
slug: /user-guide/upgrade/breaking-changes-3
---

# Breaking changes in 3.0

What changes for a project moving from the released 2.x to 3.0 of
`naas-abi-core`, `naas-abi` and `naas-abi-cli`. `naas-abi-proto` and
`naas-abi-sdk` are new (0.1.0). `naas-abi-marketplace` keeps its own versions.

The steps to upgrade a deployment are in [Migrate from 2.x to 3.0](./migrate-to-3):
phase 1 upgrades the code with NATS off, phase 2 turns NATS on. This list says
what each change means with NATS off (a config without a top-level `nats:`
block, as every 2.x project has) and with NATS on, and what to do about it.

## How this list was checked

- Every file the 3.0 branch modified in the three packages, against the 2.x
  base (`3ac2064b8`), read in full: Python API, config schema, CLI, storage and
  wire formats, Nexus HTTP API, environment and Compose.
- A project made by the released 2.x CLI (`naas-abi-cli` 2.27.1 from PyPI,
  `abi new project`, `abi deploy local`), holding a chat with agent memory, a
  graph, a dataset (string, bigint above 2^53, double, boolean, date,
  timestamp and JSON columns), a file and an activity log, upgraded by
  following the migration guide:
  - phase 1 with Docker Compose and with `abi dev up`, then phase 2 with both,
    including the agent memory and activity log migration jobs;
  - after each phase: sign-in, chat with the earlier conversation, graph,
    datasets, files and jobs (Dagster in phase 1, module jobs in phase 2).
- A new project and module from the 3.0 CLI (`abi new project`, `abi new
  module`), natively and with Compose, answering a chat through the remote
  module.

What broke without a reason was fixed on the branch; it is listed at the end
under [Fixed during the check](#fixed-during-the-check). Every other change
the upgrade test met is in this list.

## What every 2.x project does

| | NATS off (phase 1) | NATS on (phase 2) |
|---|---|---|
| Install | Keep the `.abi` submodule (`naas-abi-proto` and `naas-abi-sdk` are not on PyPI before the release). Add `naas-abi-core[dagster,rabbitmq]` (`abi deploy local` does it). | Same, plus the `[tool.uv.sources]` entries for `naas-abi-proto` and `naas-abi-sdk`. |
| Deploy files | `abi deploy local --regenerate`, then `docker compose up -d --build --force-recreate`. | `nats:` block, no `bus:` section, `abi deploy local --regenerate`, `docker compose up -d --force-recreate --remove-orphans`. |
| Data | Nothing moves. | Run `agent_memory_migrate` and `activity_log_migrate` before users chat. |
| Scheduling | Dagster as before. | Module jobs; Dagster is not in the NATS stack. |

## Dependencies

### Dagster and RabbitMQ are legacy extras
- **What changed:** `naas-abi-core` no longer installs Dagster (it was a base
  dependency), and `naas-abi-core[all]` no longer includes the `dagster` and
  `rabbitmq` extras. `naas-abi` requires `naas-abi-core[nats]` instead of
  `naas-abi-core[dagster]`. The `dagster` extra now carries `dagster-aws` and
  keeps SQLAlchemy below 2.1 (Dagster 1.13's PostgreSQL storage fails on 2.1,
  which is why 2.x's Dagster UI answers 500 on a fresh install).
  Without the extra, `DagsterOrchestration.New`, `DemoOrchestration.New`, the
  RabbitMQ bus adapter and the Dagster app raise `MissingLegacyExtra` (a
  `ModuleNotFoundError` with an install hint), and the module loader leaves
  out orchestrations that import Dagster, with one INFO line per module.
  Commits `d6d5ccdd4`, `f142a6482`, `c7f1f0e4f`, `f3ef4659c`.
- **Who:** every 2.x project: its `pyproject.toml` asks for
  `naas-abi-core[all]`, and its stack runs Dagster and a `rabbitmq` bus
  (`config.local.yaml`, `config.remote.yaml`).
- **NATS off:** affected. After `uv sync`, the Dagster container fails, a
  `rabbitmq` bus fails to load, and `abi dev up` leaves Dagster out.
- **NATS on:** not affected: module jobs and the JetStream bus replace them.
- **Migration:** run `abi deploy local` (it runs
  `uv add 'naas-abi-core[<your extras>,dagster,rabbitmq]'` for a project
  without a `nats:` block), or add the extras yourself. Commit
  `pyproject.toml` and `uv.lock`. A project pinning SQLAlchemy 2.1 or later
  cannot install the `dagster` extra. Both extras are removed in the next
  major.
- **Marketplace:** the orchestrations of the X, PubMed and Document
  (`domains/operations`) modules import Dagster, and no
  `naas-abi-marketplace` extra pulls it. In a classic project that runs them,
  add the `dagster` extra as above; without it, the loader leaves those
  orchestrations out and the modules' other parts load.

### The NATS packages are installed in every mode
- **What changed:** `naas-abi-core[all]` includes the `nats` and `otel`
  extras, and `naas-abi` requires `naas-abi-core[nats]`: `naas-abi-proto`,
  `naas-abi-sdk`, `nats-py`, `pyjwt`, `protobuf` and OpenTelemetry. Nexus
  imports them at startup. Commits `12f22c0a5`, `db6db8cf7`, `81847777e`.
- **Who:** every install. The two new packages are published with 3.0; until
  then they resolve only from path sources (the `.abi` submodule).
- **NATS off / on:** affected at install time only.
- **Migration:** install through the `.abi` submodule, as `abi new project`
  sets up; uv resolves the two packages through `naas-abi-core`'s own sources.
  From PyPI, wait for the 3.0 release. Check for conflicts with your own pins
  of `protobuf`, `opentelemetry-*` or `nats-py`.

### Upgrade the three packages together
- **What changed:** the 3.0 CLI and Nexus import modules that exist only in
  `naas-abi-core` 3.0 (`naas_abi_core.utils.LegacyExtras` at CLI startup,
  `naas_abi_core.engine.nats_transfer` in the graph service).
- **Who:** a project that upgrades `naas-abi-cli` or `naas-abi` while its lock
  keeps `naas-abi-core` 2.x: every `abi` command, or the Nexus API, fails with
  `ModuleNotFoundError`.
- **Migration:** move `naas-abi-core`, `naas-abi` and `naas-abi-cli` to 3.0 in
  one step (the `.abi` submodule does).

## Config schema

### New top-level keys: `nats:`, `telemetry:`, `dev:`
- **What changed:** 2.x ignored unknown top-level keys. `nats:` now switches
  the engine to NATS mode, `telemetry:` configures OpenTelemetry, and `dev:`
  lists the modules `abi dev up` runs (`extra="forbid"`). Commits `f33364df5`,
  `81847777e`, `6eea78b9a`.
- **Who:** a config that already used one of these names for something else.
- **Migration:** rename such a key.

### Event and activity log adapters take typed `config:`
- **What changed:** `services.event.event_adapter.config` and
  `services.activity_log.activity_log_adapter.config` are pydantic models, no
  longer dicts. A `custom` adapter that also sets `config:` is refused.
  Commits `f3d07b514`, `604d4ef78`, `50a4c5fb5`.
- **Who:** code that reads `...config["db_path"]`; configs of custom adapters.
- **Migration:** read attributes (`config.db_path`) or `config.model_dump()`;
  move a custom adapter's settings to `custom_config:`.

### Dataset compaction rewrites files with deletes
- **What changed:** `compaction_delete_threshold` (DuckLake) defaults to 0:
  `compact()` rewrites every data file holding deleted rows, then merges.
  Commit `649082350`.
- **NATS off:** the first Dagster `dataset_compaction_job` after the upgrade
  rewrites more files; the files it replaces stay on disk (the cleanup job is
  NATS only).
- **NATS on:** the engine's `dataset_compaction` and `dataset_cleanup` jobs
  run it.
- **Migration:** set `compaction_delete_threshold` (e.g. `0.5`) to rewrite
  less; with NATS off, delete old files with DuckLake's
  `ducklake_cleanup_old_files`.

### NATS mode validates more
- **What changed:** with a `nats:` block (commits `d6fb02f31`, `088ab3454`,
  `50a4c5fb5`):
  - an explicit `services.bus` must be `nats_jetstream` on the same URL as
    `nats.nats_url`;
  - cache tiers are all local or all `nats_rpc`;
  - every on-demand service loads, whatever the modules declare, so a broken
    `services:` block that never loaded in 2.x fails the start;
  - one engine serves the kernel services per NATS account; a second one with
    `role: serve` fails with `EngineAlreadyServing`;
  - the activity log defaults to the Document Service (below).
- **NATS off:** not affected.
- **Migration:** phase 2 of the guide. A deploy with several API replicas
  sets `ABI_ROLLOUT_ID` and uses shared backends.

## Storage and wire formats

### Agent memory moves to the Document Service on NATS
- **What changed:** engine agents built with `memory=None` checkpoint into
  the Document Service (checkpoint schema 2, namespace
  `naas_abi_core.services.agent`, agent id `engine.v1`). Commit `638abbbdc`.
  - NATS on: always.
  - NATS off: only without `POSTGRES_URL`, and only when the Document Service
    loads (a module declares it); with `POSTGRES_URL` set, agents keep 2.x's
    PostgreSQL checkpointer (`7000398f4`).
  - A daily `agent_memory_prune` (NATS) keeps each thread's newest 20
    checkpoints: LangGraph's state history beyond them is gone; the
    conversation stays whole.
- **Who:** every 2.x Docker deploy (memory in `POSTGRES_URL`) that turns NATS
  on. Natively, 2.x kept memory in the process only.
- **NATS off:** not affected.
- **NATS on:** earlier conversations have no memory until
  `agent_memory_migrate` runs (`{}`, then `{"apply": true}`). A thread
  continued before the copy is reported `diverged`; its newer messages hide
  the copied history for good.
- **Migration:** run the job right after the restart, before users chat.
  Rolling back to 2.x: 2.x does not read schema 2; conversations held on NATS
  are not in `POSTGRES_URL`.

### The activity log moves to the Document Service on NATS
- **What changed:** the default activity log adapter is `document` in NATS
  mode; with NATS off it stays the per-actor SQLite files under
  `storage/activity_log` (`50a4c5fb5`, `7000398f4`).
- **NATS on:** the earlier history is not shown until `activity_log_migrate`
  runs (`{"data_dir": "storage/activity_log"}`, then with `"apply": true`).
  Copied events are numbered after the ones recorded since the switch.
- **Migration:** run the job; or keep SQLite explicitly
  (`activity_log_adapter: {adapter: sqlite, config: {data_dir: storage/activity_log}}`),
  which only suits a single engine.

### Dataset values
- **What changed:** commits `97d4ca0f7`, `094058381`, `649082350`.
  - Query results hold portable values on every path, in process and over
    NATS: `Decimal` becomes `float`, bytes become base64 strings, NaN and
    infinities become `None`, UUIDs and intervals become strings, and dates
    inside structs and lists become ISO strings. Top-level dates and
    timestamps were already ISO strings in 2.x.
  - Writes refuse NaN and infinities (`DatasetSchemaError`).
  - A timestamp with an offset is stored in UTC (2.x dropped the offset and
    kept the wall time), so a table written by both mixes the two.
  - `compact()` returns one row per step, with a `step` column (`rewrite`,
    `merge`).
- **Checked:** a 2.x dataset read after phase 2, over NATS, returns the same
  values as 2.x in process, a bigint above 2^53 included.
- **NATS off / on:** affected the same way.
- **Migration:** cast in SQL (`CAST(x AS DOUBLE)`), decode base64, test for
  `None` where NaN was, replace NaN before writing; rewrite old offset
  timestamps in UTC if they matter; read compaction results by `step`.

### Graph export
- **What changed:** `GET /api/graph/export?format=ttl` returns `@prefix`
  lines then one triple per line (still Turtle; rdflib's pretty form before).
  The body streams: a store error mid-way ends a 200 response early. Counts
  come in `X-Triple-Count` and `X-Named-Individual-Count`. The API needs a
  writable temporary directory. Commits `2f70faac6`, `828886396`.
- **Migration:** parse the file as Turtle rather than diffing it as text;
  check the triple count against `X-Triple-Count`.

### The old bus's messages stay behind
- **What changed:** in NATS mode the bus is JetStream whatever `services.bus`
  says (`70bdf8f2a`).
- **Migration:** drain RabbitMQ or `python_queue` before phase 2.

### Nexus database migration `0057_agent_enabled_override`
- **What changed:** `agent_configs.enabled_override` (nullable), applied at
  startup and idempotent; 2.x ignores it after a rollback.
- **Migration:** none.

## Python API

### Ports gained abstract methods
A custom adapter written for 2.x fails at instantiation
(`TypeError: Can't instantiate abstract class`) until it implements them.
Commits `a36c1f68a`, `c9323acb3`, `1da33738b`.

| Port | New abstract members |
|---|---|
| `IKeyValueAdapter` | `list_keys(prefix, *, limit, after)`, `get_ttl(key)` |
| `IVectorStorePort` | `list_vectors(...)`, `get_collection_info(collection)` |
| `IEventAdapter` | `list_event_types()` |
| `IEventService` (subclasses only) | `query_stream`, `event_types`, `query_stored`, `query_stored_stream`, `get_stored` |
| `ICodingEnvironmentAdapter` | `list_all_environments()` |
| `ISourceControlAdapter` | `delete_repo(*, repo_id)` |
| `ITripleStoreService` (service implementations only) | `query_stream(query)`, `export(graph_name)` |
| `IDocumentAdapter` | `collection_spec(namespace, collection)`, `namespaces()`; `find(..., max_bytes=)` is passed only to a `find` that takes it, in process and over NATS (`ce7a19203`, `e299c28bf`) |

Custom triple store adapters (`ITripleStorePort`) get defaults and keep
working.

### Triple store results and errors
- `query()` on a SELECT returns an `rdflib.query.Result` instead of a
  one-shot iterator, on Oxigraph and Fuseki; Oxigraph answers ASK with an ASK
  result (2.x returned an empty, always truthy iterator). `next(result)`
  fails; use `iter()` or `list()` (`ecffb7536`, `383bf1dd1`).
- Oxigraph `create_graph` on an existing graph raises
  `GraphAlreadyExistsError` (was `requests.HTTPError`); Fuseki transport errors
  raise `Exceptions.RequestError` (were `requests` exceptions)
  (`ca925a8fc`, `eb958ab28`).
- The `kg_sparql_query` agent tool returns at most 200 SELECT rows as
  `{"rows": [...], "total_rows": n, "truncated": true}`; ASK returns
  `{"ask": bool}` and CONSTRUCT a list of N-Triples (2.x failed on both)
  (`3c65e3e6b`).

### Secrets
- The `dotenv` adapter's `remove()` deletes the key from `.env` (2.x only
  cleared the process environment, so it came back), and `get()` after
  `set()` or `remove()` returns the new state (`fe22c0ca7`). Rewriting `.env`
  keeps the file's owner (`efc11d2a0`).

### Modules and the engine
- `BaseModule` mixes in `JobsMixin`: the names `jobs`, `expose_job`,
  `trigger_job`, `atrigger_job`, `missing_job_handlers` and
  `_job_handlers`/`_bind_job_host` are taken. A module class defining one of
  them fails or overrides the engine's hooks (`dd61554a0`). With NATS off,
  declared jobs are logged as needing NATS mode.
- The API app has its own FastAPI lifespan and calls `Engine.shutdown()` at
  exit; code that replaced `app.router.lifespan_context` should wrap it
  instead (`035fdb557`). In NATS mode the API process exits when the broker
  stays unreachable (about two minutes) and relies on its supervisor
  (`41cbfe813`).
- `Engine.load()` calls `shutdown()` when loading fails.
- Agent routing: an agent or supervisor persisted in a thread is adopted only
  if it is in the current agent's tree; nested sub-agents are reached through
  their parent (`7b7082581`).
- `GraphService.export_graph_as_ttl(...)` is replaced by
  `GraphService.export_graph(...)`, which returns counts and an async iterator
  of chunks.

## CLI

### `abi new project` creates NATS projects
- **What changed:** NATS by default (`--without-nats` for the classic
  project). A NATS project: a `nats:` block in its configs and no `bus:`,
  `NATS_JWT_SECRET` and the broker passwords in `.env`, the NATS Compose stack
  (no Dagster), no orchestration in its module, `naas-abi-sdk[agent]` in its
  dependencies. It needs the `.abi` submodule: `--without-abi-submodule` is
  refused with NATS, and a failed submodule add stops the command and removes
  the folder it created. Commits `25f8f1fb3`, `fb9172e8c`.
- **Who:** scripts that run `abi new project` and expect the 2.x layout.
- **Migration:** add `--without-nats`; for `abi dev up` on a NATS project,
  install `nats-server` 2.14 or later.

### `abi new module` creates remote modules in NATS projects
- **What changed:** in a project with a `nats:` block (in `config.yaml` or
  `config.local.yaml`), and outside any project, `abi new module <name>`
  creates a remote SDK module: in the project's `src/<name>/` with a
  `dev.modules` entry, plus a Compose service in `docker-compose.override.yml`
  and its module key in `.env` when the Docker config (`config.local.yaml`)
  is on NATS; outside a project, a repository of its own (`./<kebab-name>/`,
  as `--standalone`). In a project whose configs have no `nats:` block it
  still creates an in-engine module and says so (`e7240c8ae`, `71da49d90`);
  `--remote` forces a remote one, `--in-engine` (alias `--local`) an
  in-engine one. Module names must match
  `^[a-z][a-z0-9-]{0,62}$` once kebab-cased. In a project, the default path
  `.` means `src/<name>` wherever the command runs, and a remote module must
  live under `src/`. Commits `ea721a6f7`, `fb9172e8c`.
- **Who:** scripts that create modules in NATS projects or outside projects.
- **Migration:** pass `--in-engine` for a classic module; pass the target
  folder explicitly to nest a module elsewhere.
- Related: an in-engine module created in a NATS project has no
  `orchestrations/`; inside a remote module, `abi new orchestration` refuses
  (schedule with jobs), and `abi new agent`, `workflow`, `pipeline` and
  `integration` write SDK scaffolds that import `naas_abi_sdk` only.

### `abi deploy local` changes the project's dependencies
- **What changed:** for a project without a `nats:` block, `abi deploy local`
  (with or without `--regenerate`) runs `uv add` to add the `dagster` and
  `rabbitmq` extras, which rewrites `pyproject.toml` and `uv.lock` and needs
  network access; a `uv` failure is printed and the exit code stays 0. It
  stops before writing anything when `.env` is not writable and prints the
  `chown` to run (`3f7552ff0`). Commit `fb9172e8c`.
- **Migration:** commit the dependency change; give `.env` back to your user
  when told (a 2.x container rewrote it as root).

### What `abi deploy local --regenerate` writes
- **NATS off:** the classic stack, unchanged apart from additions: a `nats`
  service behind the Compose profile `nats` and its `nats_data` volume,
  `.deploy/docker/nats/nats.conf`, `NATS_ABI_PASSWORD` and
  `NATS_MODULE_PASSWORD` in `.env`, a Caddy route for `/app-html/remote/*`,
  MinIO from `pgsty/minio` and `pgsty/mc` (the `quay.io/minio` images are no
  longer served, `97bd5bc82`), a working `fuseki-compact`, and an
  `mcp-server` that mounts the project and listens on `0.0.0.0` in its
  container (`7df789955`), published on the host's `127.0.0.1:8000` only: it
  checks no credential and calls the agents with `ABI_API_KEY`, so reach it
  through a tunnel or a proxy that authenticates.
- **NATS on:** the NATS stack: `nats` without a profile (the engine waits for
  it; it refuses to start without both passwords), no `dagster` service,
  RabbitMQ behind the `rabbitmq` profile, `NATS_JWT_SECRET` in `.env`.
- **Migration:** see the guide; after each CLI upgrade, regenerate so that
  `nats.conf` carries the current module permissions.

### `abi deploy local-up`, `local-down` and `local-logs` use the override file
- **What changed:** they pass `docker-compose.override.yml` when it exists;
  2.x's explicit `--file docker-compose.yml` skipped it (`25f8f1fb3`).
- **Who:** projects whose override file was meant for other commands only.

### `abi dev up`
- **What changed:** commits `1ef5ae0b5`, `8ec4a1f83`, `6eea78b9a`,
  `05fb7d56f`, `9b34cc81e`, `58bfb9764`, `ebfeb987b`.
  - The mode follows the config: NATS with a `nats:` block, in-process
    without; `--with-nats` and `--without-nats` choose. NATS mode needs
    `nats-server` 2.14 or later, starts a broker with the two users, writes
    the NATS keys to `.env`, runs the engine through
    `.abi/dev/dev.overlay.yaml` (broker, discovery, JetStream bus), leaves
    Dagster out, and runs the `dev.modules` SDK modules under a supervisor.
  - `dev.modules` entries take `identity:` (the module id) when the name is
    not it; a module whose id cannot be read is refused. Dev modules get their
    module key, never `NATS_JWT_SECRET`.
  - The `dev:` block is read and validated in every mode, so a config that
    does not render fails the start.
  - Without the `dagster` extra, Dagster is left out with a notice.
  - Dagster gets the same public hosts as the API, so its code server loads a
    config that templates `PUBLIC_WEB_HOST` (2.x's did not).
  - `abi dev status` and `abi dev ports` list `nats` and `jaeger`; `abi dev
    down` stops them and the dev modules; a busy port is retried for up to
    5 s before another is taken.
- **Migration:** parse `status`/`ports` output by service name; install
  `nats-server` for NATS projects.

### Smaller CLI changes
- The "ABI project detected. Re-running…" notice goes to stderr (`a0253fd9a`).
- `abi chat`, `abi run` and `abi agent list` load the engine with
  `ABI_ENGINE_ROLE=auto` (serve when no engine does, else client); set the
  variable to change it (`50a4c5fb5`).
- `abi new module --standalone` pins the SDK to `naas-abi-cli-v<version>`
  (`--abi-ref` overrides, `4c333eea3`).
- New commands: `abi module key <module_id>`, `abi agent migrate-memory`,
  `abi agent prune-memory`.

## Nexus HTTP API

No route was removed or renamed.

- **App link tokens are not sessions.** A token from
  `POST /api/apps/access-token` (scope `app-html`) no longer authenticates
  `/api/*` or the WebSocket (401); it still opens `/app-html/`. Use the
  session token or `ABI_API_KEY` (`f9e6b23ac`).
- **A user's agent toggle sticks.** `PATCH /api/agents/{id}` with `enabled`
  stores an override that later syncs keep, instead of realigning the agent
  with the workspace `agents:` roster. Agents toggled under 2.x keep following
  the roster until toggled again. To hand control back to the config:
  `UPDATE agent_configs SET enabled_override = NULL` (`c6cbe455f`).
- **`/app-html/` through the web app** no longer follows redirects, streams
  bodies, and passes on `Content-Security-Policy`, `Referrer-Policy`,
  `Content-Length`, range and cache headers. A Nexus framed by another site
  needs that origin in `frontend_url` or the CORS origins for its apps to
  frame (`0cc5ec60a`).
- **Logout and password changes** write a `revoked_tokens` row every time;
  access tokens carry a float `iat`. A verifier of Nexus tokens outside Nexus
  should allow some clock leeway (`7719c4082`, `e3439fd4a`).
- **Apps of a module whose package is `remote`** are hidden, and
  `/app-html/remote/...` is reserved for remote apps (`7719c4082`,
  `e293b4ef4`).
- **The graph view's filter preview** runs SPARQL aggregates and subqueries on
  the store; a store without them shows an empty preview (`2f70faac6`).
- **Graph export:** see [Graph export](#graph-export).
- **Chat with remote agents** (NATS): the `agent` of `POST /api/chat/stream`
  and `POST /api/chat/complete` must be the agent's id for an agent published
  by a remote module; a name selects in-process agents only. Both endpoints
  answer with remote agents. When the agent is unavailable or its run fails,
  the stream ends with an error message and `/api/chat/complete` answers with
  the provider marked `(error)`, as for an in-process agent; a failure after
  the answer is done is only logged (`2ef173f31`, `72148949b`, `75dd059cc`).
- New super-admin routes under `/api/admin/system/` (System app: data, jobs,
  traces). Jobs run with
  `POST /api/admin/system/jobs/<module>/<job>/trigger` and
  `{"payload": {...}}`.

## Environment variables and Compose services

| Name | Where | Mode | Meaning |
|---|---|---|---|
| `NATS_JWT_SECRET` | `.env` | NATS | Signing secret of every NATS token (32 bytes or more). |
| `NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD` | `.env` | both (written by `abi deploy local`) | Broker passwords of the `abi` (engine) and `module` (SDK modules) users; the `nats` service refuses to start without them. |
| `ABI_MODULE_KEY_<NAME>` | `.env` | NATS | A remote module's key (`abi module key <module_id>`), passed to its container as `ABI_MODULE_KEY`. |
| `ABI_NATS_URL`, `ABI_MODULE_KEY`, `ABI_SERVICE_TOKEN`, `ABI_DISCOVERY_PROJECT` | module process | NATS | SDK module settings; `ABI_MODULE_KEY` wins over `ABI_SERVICE_TOKEN`. |
| `ABI_ENGINE_ROLE`, `ABI_ROLLOUT_ID` | engine process | NATS | Serving role (`serve`, `client`, `auto`) and the rollout a deploy hands over to. |
| `ABI_CONFIG_OVERLAY` | engine process | both | YAML merged over the config (`abi dev up` sets it); a missing file fails the start. |
| `REMOTE_APP_GRANT_EXPIRE_MINUTES` | Nexus | NATS | Lifetime of a remote app grant (default 480). |
| `MCP_HOST` | `mcp-server` | both | Address of the MCP server's HTTP transports (default `127.0.0.1`; `0.0.0.0` in the generated stack). |

Compose (generated stack):

| Service or volume | NATS off | NATS on |
|---|---|---|
| `nats`, `nats_data` | added behind the profile `nats`; not started | started first; the engine waits for it |
| `dagster` | kept (legacy) | removed; `--remove-orphans` removes the container |
| `rabbitmq` | kept (legacy) | behind the profile `rabbitmq`; stop it |
| `minio`, `minio-init` | `pgsty/minio`, `pgsty/mc` | same |
| `mcp-server` | mounts the project and its venv | same |
| remote modules | — | one service each in `docker-compose.override.yml` (`abi new module`); `--regenerate` never touches that file |

`abi stack snapshot create` archives the data volumes and `storage/`, not
`nats_data`.

## For modules and apps built on pre-release builds of 3.0

Remote modules, remote agents and remote apps are new in 3.0, so nothing here
breaks a 2.x project. Projects that ran earlier builds of the branch must:

- with NATS off and `POSTGRES_URL` set, expect agent memory back in
  PostgreSQL: earlier builds kept it in the Document Service whenever that
  service loaded, and 3.0 gives `POSTGRES_URL` precedence without NATS
  (`7000398f4`). Conversations held in documents since are not seen; turn
  NATS on to read them again, or unset `POSTGRES_URL`;

- sign with the module key as the module id (`ABI_MODULE_KEY`, `abi module key
  <module_id>`), never `NATS_JWT_SECRET`; `ABI_MODULE_IDENTITY` and the
  template's `service_token.py` are gone, and discovery registers a module
  only under its own identity;
- not rely on a static `ABI_SERVICE_TOKEN` to call another module: tokens sent
  to a module instance are bound to it (`aud`) for five minutes, and
  `Transport.call` to an `abi.agent`/`abi.mod` subject takes `instance_id=`;
  instance ids are one subject token (`[A-Za-z0-9_-]{1,128}`);
- regenerate `nats.conf`: the `module` user may not subscribe to `abi.svc.>`,
  `abi.discovery.>`, `abi.rpc.>`, `_INBOX.>`, `$JS.>` or `$KV.>`, write
  `$KV.>`, create, update or delete streams, delete consumers, or use the
  direct get; connections other than `run_module`'s pass
  `inbox_prefix="_INBOX_MODULES"`, and a module's bus queue needs a stream the
  engine created (`StreamNotCreated` otherwise);
- send app requests that name a user or a workspace only from Nexus (`api`):
  other callers get `PERMISSION_DENIED`; `scope["abi"]` is
  `{"user_id", "workspace_id", "caller"}`;
- for remote app grants, pass `workspace_id` to
  `POST /api/apps/remote-grant` (older grants are refused; a grant ends at
  logout, password change or `POST /api/apps/remote-grant/revoke`); a module
  enforces its app's `max_upload_bytes` (default 1 GiB), `pull_body(max_bytes=0)`
  means nothing more, and `AppHost(max_uploads=16)` refuses uploads past it.

## Fixed during the check

These broke a 2.x project, or a new 3.0 one, without a reason, and were fixed
on the branch:

| Commit | What broke |
|---|---|
| `7000398f4` | Phase 1 (NATS off) moved agent memory and the activity log to the Document Service: a 2.x Docker deploy's agents forgot every conversation, and no job could copy them without NATS. |
| `efc11d2a0`, `3f7552ff0` | A root container rewrote `.env` as root; `abi deploy local --regenerate` then failed with a traceback. |
| `ce7a19203`, `e299c28bf` | Every query of a 2.x custom document adapter failed on the `max_bytes` keyword, in process and over NATS. |
| `e7240c8ae`, `71da49d90` | `abi new module` created remote modules in classic projects, where nothing runs them (and, once that was fixed, in-engine modules in projects on NATS natively). |
| `97bd5bc82`, `9ac32591e` | The generated stack (and the repository's) pulled MinIO images that no longer exist; `fuseki-compact` restarted forever on a shell syntax error. |
| `e5bd367dd`, `7df789955`, `358379e56` | The generated (and the repository's) `mcp-server` restarted forever (no project mounted) and listened on 127.0.0.1 only. |
| `ebfeb987b` | Under `abi dev up`, Dagster could not load a config that templates `PUBLIC_WEB_HOST`, so no orchestration or job loaded. |
| `43426b522`, `460bf7656` | `abi new project` could not install a NATS project: `naas-abi-sdk[agent]` required langchain-core 1 while `naas-abi-core` needs 0.3. |
| `2ef173f31`, `75dd059cc` | `POST /api/chat/complete` answered "Unknown provider type: remote", then returned a module's failure as a successful answer. |
| `72148949b` | A remote agent's next turn, sent right after the previous one, failed with `CONVERSATION_BUSY`: Nexus stopped reading at `done` and cancelled the finishing run; reading on must not append a late failure to the answer (`75dd059cc`). |
| `a365c76b8` | The migration guide's phase 2 started the classic stack's `nats` profile, where the API and Dagster cannot both serve (`EngineAlreadyServing`), and its restart commands left the API on the old code. |

## Known limits found by the check

Not changed by 3.0, or not fixed here:

- The first start of the classic stack's RabbitMQ can fail on its Erlang
  cookie (the health check creates it as root); it starts on the next try.
  2.x does the same.
- A 2.x project's generated `<Name>Pipeline` subclasses `Pipeline[...]`, which
  fails to import (2.x too). The 3.0 template subclasses `Pipeline`; edit old
  pipelines the same way.
- A thread continued between the switch to NATS and `agent_memory_migrate`
  keeps its newer memory; nothing merges the two.
- `abi deploy local` detects NATS with a text match on the config, while the
  engine parses it: `nats: null` counts as NATS for the former only.
- A failed graph export, and in rare cases an Oxigraph CONSTRUCT that fails
  mid-stream, look like a complete 200 response: compare the triple count.
- A tool's `metadata={"chat_source": False}` keeps its URLs out of Nexus's
  chat sources for core agents, in process or served by a remote module
  through `RemoteAgentAdapter`. Agents built with `naas_abi_sdk.agents` have
  no such opt-out yet: every tool response of theirs can be listed.
