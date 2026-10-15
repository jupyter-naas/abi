---
sidebar_position: 1
title: "Migrate from 2.x to 3.0"
---

# Migrate from 2.x to 3.0

ABI 3.0 (`naas-abi-core`, `naas-abi` and `naas-abi-cli` 3.0.0, with the new
`naas-abi-proto` and `naas-abi-sdk`) runs on **NATS**. The engine serves its
kernel services over a NATS broker, the bus is JetStream, module jobs replace
Dagster, and modules can run in their own process with the SDK. Dagster and
RabbitMQ are **legacy**: optional extras that still work with NATS off, removed
in the next major.

**New projects are already on NATS.** `abi new project` creates them in NATS
mode, with discovery on, and `abi new module` creates modules that run in their
own process. This guide is for **existing projects**: ones created with 2.x,
or with `abi new project --without-nats`.

A deployment runs in NATS mode when its config has a top-level `nats:` block.
Without that block, the engine keeps its in-process wiring, and agent memory,
the activity log, the bus and Dagster stay as they were. `abi deploy local
--regenerate` follows the config: it does not move a project without the block
to NATS.

The upgrade runs in three phases. Stop after any phase and the deployment still
works.

1. [Upgrade the code, with NATS off](#phase-1-upgrade-with-nats-off).
2. [Turn NATS on](#phase-2-turn-nats-on): one engine serves over NATS, and
   module jobs replace Dagster.
3. [Optionally, move a service or a module into its own process](#phase-3-optional-split-into-separate-processes).

How the pieces fit together is in [NATS and the kernel services](/architecture/nats).
Every change, with what it means for your code, scripts and API clients, is in
[Breaking changes in 3.0](./breaking-changes-3).

## What breaks

| | NATS off (phase 1) | NATS on (phase 2) |
|---|---|---|
| Install | Keep the `.abi` submodule: `naas-abi-proto` and `naas-abi-sdk` are not on PyPI before the 3.0 release. Add `naas-abi-core[dagster,rabbitmq]` (`abi deploy local` does it). | Same, plus the `[tool.uv.sources]` entries for `naas-abi-proto` and `naas-abi-sdk`. |
| Deploy files | `abi deploy local --regenerate`, then `docker compose up -d --build --force-recreate`. | `nats:` block, no `bus:` section, `abi deploy local --regenerate`, `docker compose up -d --force-recreate --remove-orphans`. |
| Data | Nothing moves. | Run `agent_memory_migrate` and `activity_log_migrate` before users chat. |
| Scheduling | Dagster as before. | Module jobs; Dagster is not in the NATS stack. |

What changes even with NATS off, the ones you are most likely to see:

- `naas-abi-core` no longer installs Dagster, and `naas-abi-core[all]` no
  longer includes the `dagster` and `rabbitmq` extras. Without them the
  Dagster container fails, a `rabbitmq` bus fails to load, and `abi dev up`
  leaves Dagster out.
- Upgrade `naas-abi-core`, `naas-abi` and `naas-abi-cli` together: the 3.0 CLI
  and Nexus import modules that exist only in `naas-abi-core` 3.0.
- Custom adapters written for 2.x must implement the ports' new abstract
  methods.
- A cache tier with `adapter: object_storage` or `adapter: keyvalue` loads the
  service it depends on.
- `remove()` on the `dotenv` secret adapter deletes the key from `.env`.
- Dataset writes refuse NaN and infinities, and timestamps that carry an
  offset are stored in UTC.
- A graph export in Turtle is `@prefix` lines followed by one triple per line.
- `abi new project` creates NATS projects, and `abi new module` creates remote
  modules in them.

## What changes in NATS mode

- Every call between kernel services (object storage, KV, triple store, events,
  and the rest) becomes a request over NATS, even inside one process. There is
  no local fallback: if the broker is down, those calls fail.
- The bus always uses NATS JetStream. RabbitMQ and `python_queue` are not used.
- One engine serves the kernel services per NATS account. A second engine that
  tries fails with `EngineAlreadyServing`, unless it is a planned handover
  (see [one serving engine](/architecture/nats#one-serving-engine)).
- Agents use the model registry over NATS too, so model lookup and inference
  depend on the broker.
- Calls are authenticated with short-lived tokens signed by one shared secret
  (`NATS_JWT_SECRET`). Remote modules sign with a key derived from it for their
  own module id. See [Security model](/architecture/security).
- When the broker stays unreachable for about two minutes (60 reconnect
  attempts, 2 s apart), the API process stops: SIGTERM, then exit status 1 if
  the shutdown takes more than 20 s. Run it under a supervisor that restarts it
  (Docker `restart: unless-stopped`, Kubernetes). With `api.reload: true` the
  loss is only logged. SDK modules (`run_module`) stop the same way.

## Before you start

- **Read the breaking changes.** [Breaking changes in 3.0](./breaking-changes-3)
  lists everything that changes between 2.x and 3.0, with NATS off and on.
  This guide covers the steps; that list covers what your own code, scripts
  and API clients may need.
- **Install from source until the release is on PyPI.** `naas-abi-core` and
  `naas-abi` depend on `naas-abi-proto` and `naas-abi-sdk`. Until those two
  packages are published, install ABI from the repository through the
  project's `.abi` submodule, as projects made by `abi new project` do.
- **Replicas must share their data.** In NATS mode one engine serves the
  kernel services at a time, and a deploy hands over to the next one. With
  `fs` or SQLite backends, the next engine would answer from another copy.
  Use PostgreSQL, S3 or MinIO, Redis and Fuseki (what `abi deploy local`
  configures) for anything that must survive a handover.
- **Drain the old bus.** Messages still waiting in RabbitMQ or `python_queue`
  are not moved to NATS. Let workers empty the queues before phase 2.
- **Take a snapshot.** With a Docker stack, run `abi stack snapshot create`.
  It archives the data volumes and the project's `storage/` folder (the SQLite
  activity log, the dataset files of `abi deploy local`), not the `nats_data`
  volume where NATS keeps its own data. Without a Docker stack, copy
  `storage/`.

## Phase 1: upgrade with NATS off

This phase changes code only. Agent memory, the activity log, the bus and
Dagster stay where they are.

1. Point the `.abi` submodule at the 3.0 release, then run `uv sync`.
2. With a Docker stack, regenerate the deployment files:

   ```bash
   abi deploy local --regenerate
   ```

   This backs up and re-renders `docker-compose.yml` and `.deploy/`, and keeps
   `.env`. For a project without a `nats:` block it keeps the classic stack
   (Dagster, RabbitMQ) and adds:
   - a `nats` service in `docker-compose.yml`, under the Compose profile `nats`,
     so it does not start;
   - `.deploy/docker/nats/nats.conf`, and the broker's passwords in `.env`
     (`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`);
   - the legacy extras the classic stack needs: it runs
     `uv add 'naas-abi-core[...,dagster,rabbitmq]'`, which updates
     `pyproject.toml` and `uv.lock`. Commit them.

   If it stops with `.env is not writable by this user`, a 2.x container
   rewrote `.env` as root: run the `sudo chown` it prints, then run it again.

   Without a Docker stack, add the extras yourself, keeping the ones you have:
   `uv add 'naas-abi-core[all,dagster,rabbitmq]'`. `naas-abi-core[all]` no
   longer includes Dagster or RabbitMQ; without them, `abi dev up` leaves
   Dagster out (it says so) and a `rabbitmq` bus fails to load.
3. Restart every process on the new code:
   - Docker: `docker compose up -d --build --force-recreate`. Without
     `--force-recreate`, containers whose definition did not change (the
     `abi` service, whose code comes from the bind mount) keep running 2.x.
   - Natively: `abi dev down`, then `abi dev up`.
4. Try the usual flows: sign-in, chat with agents and their earlier
   conversations, knowledge graph, datasets, file upload and download, Dagster
   jobs.

`abi new module` in this project still creates an in-engine module (it says
so); `--remote` creates one that runs once the project is on NATS.

## Phase 2: turn NATS on

In this phase the engine serves its services over NATS, and Dagster gives way
to module jobs.

1. **Add the NATS packages.** `naas-abi-core[all]` and `naas-abi` already
   depend on `naas-abi-core[nats]`; depend on it yourself if you list narrower
   extras. Add both new packages to `[tool.uv.sources]`, next to the existing
   ABI entries:

   ```toml
   naas-abi-proto = { path = ".abi/libs/naas-abi-proto", editable = true }
   naas-abi-sdk = { path = ".abi/libs/naas-abi-sdk", editable = true }
   ```

   Run `uv sync`.

2. **Create the signing secret.** Add a random value of at least 32 bytes to
   `.env`. Shorter keys trigger a warning.

   ```bash
   echo "NATS_JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env
   ```

   Every engine process that talks to NATS must use this same value. Remote
   modules never get it: they get a module key derived from it. The broker's
   passwords, `NATS_ABI_PASSWORD` for the engine and `NATS_MODULE_PASSWORD`
   for SDK modules, are already in `.env` after phase 1's
   `abi deploy local`; `abi dev up` writes them when they are missing.

3. **Add the `nats:` block** at the top level of the config the engine reads
   (`config.local.yaml` for the Docker stack, `config.yaml` for `abi dev
   up`), next to `api:`, not under `services:`:

   ```yaml
   nats:
     # The Compose service name, logged in as the broker user `abi`.
     nats_url: "nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222"
     jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
   ```

   Use `nats://abi:{{ secret.NATS_ABI_PASSWORD }}@127.0.0.1:4222` in
   `config.yaml`: `abi dev up` runs its own broker and points the engine at it
   through its overlay (`.abi/dev/dev.overlay.yaml`), with discovery on. SDK
   modules log in as `module`:
   `ABI_NATS_URL=nats://module:<NATS_MODULE_PASSWORD>@nats:4222`.

4. **Remove the whole `bus:` section** from `services:`, with every line of
   its `config:`. Configs created by `abi new project` in 2.x declare one:
   `rabbitmq` in `config.local.yaml`, `python_queue` in `config.yaml`. In NATS
   mode the engine refuses any bus adapter other than `nats_jetstream`. To keep
   a `bus:` block, for example for `emit_message_events`, it must read:

   ```yaml
     bus:
       emit_message_events: true
       bus_adapter:
         adapter: "nats_jetstream"
         config:
           # must equal nats.nats_url
           nats_url: "nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222"
   ```

5. **Check the cache tiers.** Either all tiers are local or all are `nats_rpc`.
   The engine refuses a mix.

6. **Restart on NATS.** One engine serves the kernel services per NATS
   account: a second one that tries fails with `EngineAlreadyServing`. The
   classic stack runs two engines (the API and Dagster), so do not start its
   `nats` profile; render the NATS stack instead. Move Dagster orchestrations
   to [module jobs](/architecture/remote-modules#module-jobs) first: the
   engine's own dataset maintenance already runs as jobs in NATS mode.
   - Docker:

     ```bash
     abi deploy local --regenerate
     docker compose up -d --force-recreate --remove-orphans
     docker compose stop rabbitmq
     ```

     With the `nats:` block in `config.local.yaml`, the stack has a `nats`
     service the engine waits for, no `dagster` service (`--remove-orphans`
     removes its container), and RabbitMQ behind the `rabbitmq` profile.
   - Natively: `abi dev down`, then `abi dev up`. It needs `nats-server` 2.14
     or later on `PATH` (module job schedules use JetStream message
     schedules), refuses an older one, and leaves Dagster out.

7. **Verify:**
   - The broker answers: `curl -s http://localhost:8222/healthz` returns
     `{"status":"ok"}` (natively, the monitoring URL `abi dev up` prints:
     `NATS mode (discovery project '...', monitoring http://localhost:<port>)`).
   - `curl -s http://localhost:8222/connz` lists the engine's connections, one
     per service client. A count of zero means the engine did not connect.
   - With the [NATS CLI](https://github.com/nats-io/natscli), `nats micro list`
     shows the kernel services. The model registry and discovery do not appear
     there.
   - With the log level at `DEBUG`, the engine logs an
     `EngineNATSLoader: exposed <service> over NATS` line for each service it
     serves.
   - The Nexus System app's **Jobs** tab lists the engine's jobs, among them
     `agent_memory_migrate` and `activity_log_migrate`.

Then copy agent memory and the activity log (next section) before users
chat, and run the same flows as in phase 1.

### Right after the restart: copy agent memory and activity logs

In NATS mode, engine agents keep their conversation memory in the Document
Service, and the activity log is there by default too. Earlier data stays where
it was until you copy it. Do it right after the restart, before users chat, as
a super admin, in the Nexus System app: **Jobs** tab, **Run now** with a JSON
payload. Each run is audited, and its report is the run's result. A script can
do the same with `POST /api/admin/system/jobs/<module>/<job>/trigger` and the
body `{"payload": {...}}`, signed in as a super admin.

1. **Agent memory** (`naas_abi_core.agent_memory`, job `agent_memory_migrate`).
   Until it runs, users' earlier conversations have no memory.
   - Run it with `{}`. This is a dry run against the `POSTGRES_URL` database:
     check `threads`, `missing` and `diverged`.
   - Run it with `{"apply": true}`. Running it again copies nothing.
   - A thread listed in `diverged` was continued before the copy. The copy
     still runs, but the thread's newer messages hide the copied history, and
     nothing brings it back: keep the window short.
   - Memory that an earlier 3.0 build kept in documents (schema 1) copies with
     `{"from": "documents-v1"}`. `"threads": [...]` limits a run to some
     threads.
   - The engine reads `POSTGRES_URL` from its secrets or environment. Never put
     a connection string in the payload: payloads are shown in the UI.
   - A project that ran natively without `POSTGRES_URL` kept agent memory in
     the process only: there is nothing to copy, and the job says so.
2. **Activity log** (`naas_abi_core.activity_log`, job `activity_log_migrate`),
   if you need the history recorded before the switch:
   - Run it with `{"data_dir": "storage/activity_log"}`, the old adapter's
     `data_dir`. This dry run counts each actor's events.
   - Run it with `{"data_dir": "storage/activity_log", "apply": true}`. Copied
     events come after the ones recorded since the restart. Running it again
     copies only what is missing.

From then on, `agent_memory_prune` runs daily and keeps each thread's newest
20 checkpoints; the conversation stays whole in them. Without NATS mode no
engine hosts jobs, and agent memory stays in `POSTGRES_URL`: to move it to the
Document Service ahead of the switch, stop the engines and run
`abi agent migrate-memory` (a dry run, then `--apply`).

### Tuning

These keys have working defaults; change them only when needed.

| Key | Default | Purpose |
|---|---|---|
| `nats.client_timeout_seconds` | 10 | How long the engine's own service calls wait for a reply. Long dataset operations (`compact`, `flush`, `query`) can pass their own deadline. |
| `nats.max_concurrent_requests` | 64 | Calls each kernel service of the engine, and discovery, handles at once, on as many worker threads. Later calls wait until a call finishes or their deadline passes. Size it to the backend: a PostgreSQL service gains nothing above its connection pool. |
| `nats.object_storage_streaming.chunk_bytes` | 64 KiB | Chunk size for object transfers. |
| `nats.object_storage_streaming.max_upload_bytes` | none | Largest object accepted over NATS. |
| `nats.object_storage_streaming.max_sessions` | 32 | Concurrent transfers per engine. |
| `nats.models.streaming.max_upload_bytes` | 16 MiB | Largest single model request. |
| `nats.models.streaming.max_buffered_upload_bytes` | 64 MiB | Total model request data held at once. |
| `nats.models.generation_timeout_seconds` | none | Hard limit on one model generation. |
| `nats.jobs.enabled` | true | Whether this engine hosts module jobs. |
| `nats.jobs.retention.max_age_days` | 7 | How long finished job runs are kept. |
| `nats.engine.lease_seconds` | 20 | The serving engine's lease; a crashed engine is replaced after it. |
| `nats.engine.drain_seconds` | 60 | How long a stopping engine finishes the transfers and calls it holds. |

Object uploads up to 64 KiB go in a single request. Larger objects and model
requests are sent in chunks, which older engines cannot receive, so upgrade every
engine together.

## Phase 3 (optional): split into separate processes

### Use a service owned by another engine

An engine can use a service that another engine owns. Set the service's adapter
to `nats_rpc` on the engine that does not own it:

```yaml
services:
  object_storage:
    object_storage_adapter:
      adapter: "nats_rpc"
      config:
        nats_url: "nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222"
        jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
        service_identity: "dagster"   # name of the calling process
```

The same adapter exists for the activity log, cache, coding environment,
dataset, document, email, event, KV, secret, source control, triple store and
vector store services. There is no `nats_rpc` adapter for the model registry;
the engine that owns the models serves them.

Before you split, keep in mind:

- Nothing enforces which engine owns a service. Keep one owner per service, or
  several owners on the same backend.
- A secret service can mix local adapters and `nats_rpc` adapters, such as
  `[dotenv, nats_rpc]`. The engine serves only its local secrets; reads that
  miss them go to the `nats_rpc` upstream, in the configured order.

### Run a module outside the engine

A module built with `naas-abi-sdk` runs as its own process and reaches the
engine only through NATS. [Build a remote module](/capabilities/sdk/build-a-remote-module)
walks through one; [Remote modules and jobs](/architecture/remote-modules)
explains the runtime. In short:

1. Give the module its **module key**, never `NATS_JWT_SECRET`. In the
   project, `abi module key <module_id>` prints it: it is derived from the
   secret for that module id, and signs tokens for that id only. The module's
   token must assert its own module id: discovery registers a module only
   under its own identity.
2. Run the module with `ABI_NATS_URL` (logged in as the broker user `module`)
   and `ABI_MODULE_KEY` set:

   ```bash
   naas-abi-module my_module --config module.json
   ```

   In code, `run_module(..., token=ModuleToken(module_id, key))`
   (`naas_abi_sdk.service_token`) signs and refreshes the token.

The tokens a module sends to another module are bound to the instance called
and last five minutes; only a key (or the engine's `ServiceTokenSource`) can
bind them, so a module holding only a static `ABI_SERVICE_TOKEN` cannot call
other modules. Code that calls a module subject through `Transport.call`
passes the instance id it calls (`instance_id=`); discovery refuses an
instance id that is not one subject token (letters, digits, `_`, `-`).

The broker user `module` may not subscribe to the engine's subjects
(`abi.svc.>`, `abi.discovery.>`, `abi.rpc.>`), to `_INBOX.>`, `$JS.>` or
`$KV.>`, nor write `$KV.>`, create or update streams, delete consumers, or use
the JetStream direct get (`naas_abi_core.engine.nats_permissions`). Update the
project's `.deploy/docker/nats/nats.conf` after each CLI upgrade
(`abi deploy local --regenerate` writes it). `run_module` connects with the
inbox prefix `_INBOX_MODULES` however the module logs in, and so does
`Transport` for a URL logged in as `module`; any other connection a module
opens must pass `inbox_prefix="_INBOX_MODULES"`. The engine that hosts
discovery creates the jobs stream and the claim-check store; a bus queue works
in a module only on a topic whose stream the engine created.

### Discovery

For modules to find each other and call each other's agents, enable
discovery on exactly one engine per project:

```yaml
nats:
  nats_url: "nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222"
  jwt_secret: "{{ secret.NATS_JWT_SECRET }}"
  discovery:
    project: default
    lease_seconds: 180
```

Discovery runs in the engine that serves the kernel services, so it has a
single owner even when other engines (the CLI's, a client engine) read the same
config. `abi dev up` turns it on in its overlay. The registry holds at most 256
live module instances per project. `lease_seconds: 180` (what `abi new
project` writes) lets remote modules outlive an engine restart; the default
is 20.

To add a module that runs in its own process, run `abi new module <name>` in
the project: it scaffolds an SDK module under `src/`, adds it to `dev.modules`
and `docker-compose.override.yml`, and writes its module key to `.env`.

## Roll back

1. Remove the `nats:` block and restore the previous `bus:` section.
2. Docker: run `abi deploy local --regenerate` (the classic stack, with
   Dagster and RabbitMQ, and the legacy extras), then
   `docker compose up -d --force-recreate --remove-orphans`. The `nats`
   service is left behind its profile; `docker compose stop nats` stops it.
   Natively: `abi dev down`, then `abi dev up`.
3. The engines go back to in-process wiring, with agent memory in
   `POSTGRES_URL` and the activity log in `storage/activity_log`, as before
   phase 2. What users did on NATS stays in the Document Service: agents do
   not remember conversations continued since, and the activity log does not
   show their events.

Messages still in the NATS bus stay in the `nats_data` volume and are not
copied back to the old bus. Undo phase 1 by pointing `.abi` back at the previous
version, running `uv sync` and `abi deploy local --regenerate` again, and
restarting with `--force-recreate`. To go back to the data of before the
upgrade, restore the snapshot (`abi stack snapshot restore`).

## Known limits

- The generated stack runs one NATS server, and JetStream streams have one
  replica. If that server stops, every NATS call fails.
- Nothing checks where a service's owners run or whether they share the same
  data.
- Projects are separated by subject prefix and the shared signing secret, not by
  NATS accounts. The token proves which of your processes is calling; it does
  not limit what that process can reach.
- All remote modules share one broker user, so they must be trusted code: one
  module can listen on another module's subjects, read or purge any stream,
  and take over another module's jobs. The full list is in
  [Security model](/architecture/security#known-limits).
- Traffic to the broker is not encrypted (no TLS). Keep the broker on a
  private network; a module on another machine should reach it through a
  VPN or an SSH tunnel.
- Remote agent runs stop after 300 seconds without new output, and there is no
  overall time limit. If a Python worker thread hangs, it keeps its run slot
  until it returns.
- A thread continued between the switch to NATS and `agent_memory_migrate`
  keeps its newer memory; nothing merges the two.
- A 2.x project's generated `<Name>Pipeline` subclasses `Pipeline[...]`, which
  fails to import (2.x too). The 3.0 template subclasses `Pipeline`; edit old
  pipelines the same way.
- `abi deploy local` detects NATS with a text match on the config, while the
  engine parses it: `nats: null` counts as NATS for the former only.
