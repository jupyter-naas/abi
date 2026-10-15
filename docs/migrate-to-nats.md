# Migrate a deployment to NATS

**New projects are already on NATS.** `abi new project` creates them in NATS
mode, with discovery on, and `abi new module` creates modules that run in their
own process. This guide is for **existing projects**: ones created before
NATS became the default, or with `abi new project --without-nats`.

A deployment runs in NATS mode when its config has a top-level `nats:` block.
Without that block, the engine keeps its in-process wiring and behaves as
before, even on a version that ships NATS support. `abi deploy local
--regenerate` follows the config: it does not move a project without the block
to NATS, and points here instead.

This guide moves an existing project, such as one created with
`abi deploy local`, from in-process wiring to NATS. It runs in three phases.
Stop after any phase and the deployment still works.

1. Upgrade the code, with NATS off.
2. Turn NATS on for the engines you already run.
3. Optionally, move a service or a module into its own process.

Design background: the [distributed modules RFC](specs/rfcs/20260910_distributed-modules-nats-jetstream.md)
and the ADRs under [`docs/adr/`](adr/) whose names contain `nats`.

## What changes in NATS mode

- Every call between kernel services (object storage, KV, triple store, events,
  and the rest) becomes a request over NATS, even inside one process. There is
  no local fallback: if the broker is down, those calls fail.
- The bus always uses NATS JetStream. RabbitMQ and `python_queue` are not used.
- Each engine that owns a service exposes it on NATS. Several engines can serve
  the same service, and NATS spreads requests between them.
- Agents use the model registry over NATS too, so model lookup and inference
  depend on the broker.
- Calls are authenticated with short-lived tokens signed by one shared secret.
  This proves that a caller is one of your processes, not what it may access.
- When the broker stays unreachable for about two minutes (60 reconnect
  attempts, 2 s apart), the API process stops: SIGTERM, then exit status 1 if
  the shutdown takes more than 20 s. Run it under a supervisor that restarts it
  (Docker `restart: unless-stopped`, Kubernetes). With `api.reload: true` the
  loss is only logged. SDK modules (`run_module`) stop the same way.

## Before you start

- **Install from source.** The `nats` extra of `naas-abi-core` depends on
  `naas-abi-proto` and `naas-abi-sdk`. Until those two packages are published to
  PyPI, install ABI from the repository through the project's `.abi` submodule.
- **Replicas must share their data.** If two engines own the same service, they
  must use the same backend (Postgres, S3 or MinIO, Redis, Fuseki). With `fs` or
  SQLite backends, each engine would answer from its own copy. Nothing detects
  this.
- **Drain the old bus.** Messages still waiting in RabbitMQ or `python_queue`
  are not moved to NATS. Let workers empty the queues before you switch.
- **Take a snapshot.** Run `abi stack snapshot create` if your CLI provides it.
  NATS stores its own data in the `nats_data` volume, which that snapshot does
  not include.

## Phase 1: upgrade with NATS off

This phase changes code only. Behaviour should stay the same.

1. Point the `.abi` submodule at the release or branch that contains NATS
   support, then run `uv sync`.
2. Regenerate the deployment files:

   ```bash
   abi deploy local --regenerate
   ```

   This backs up and re-renders `docker-compose.yml` and `.deploy/`, and keeps
   `.env`. The NATS-related additions are:
   - a `nats` service in `docker-compose.yml`, under the Compose profile `nats`,
     so it does not start by default;
   - `.deploy/docker/nats/nats.conf`, which raises the broker's message size
     limit to 8 MB.
3. Rebuild and restart the stack, then try the usual flows: sign-in, chat with
   agents, knowledge graph ingestion, Dagster jobs, file upload and download.

Two small behaviour changes apply even with NATS off:

- A cache tier with `adapter: object_storage` or `adapter: keyvalue` now loads
  the service it depends on automatically.
- `remove()` on the `dotenv` secret adapter now deletes the key from `.env`.
  Before, it only cleared the process environment, so the key came back on the
  next start.

## Phase 2: turn NATS on

In this phase every engine keeps its services and adds NATS on top.

1. **Add the NATS packages.** In the project's `pyproject.toml`, depend on
   `naas-abi-core[nats]` and add both new packages to `[tool.uv.sources]`, next
   to the existing ABI entries:

   ```toml
   naas-abi-proto = { path = ".abi/libs/naas-abi-proto", editable = true }
   naas-abi-sdk = { path = ".abi/libs/naas-abi-sdk", editable = true }
   ```

   Run `uv sync`, then rebuild the image.

2. **Create the broker's credentials.** There is no shared signing secret: the
   engine signs its tokens with ES256 keys it generates and keeps in the secret
   service (`iam/signing-keys/<kid>`), and publishes their public half (JWKS)
   at `abi.iam.v1.jwks` and `/.well-known/abi-jwks.json` on the API.

   `abi deploy local` writes the broker's credentials to `.env`:
   `NATS_ENGINE_PASSWORD` for the engine's processes, `NATS_AUTH_PASSWORD` for
   its auth callout responder, and `NATS_AUTH_CALLOUT_SEED` /
   `NATS_AUTH_CALLOUT_ISSUER`, the key pair the engine signs the broker's users
   with. The `nats` service refuses to start without them. Run
   `abi deploy local --regenerate` if your `.env` predates them, and remove a
   leftover `NATS_JWT_SECRET`, `NATS_ABI_PASSWORD` or `NATS_MODULE_PASSWORD`.

3. **Add the `nats:` block** at the top level of `config.yaml`, next to `api:`,
   not under `services:`:

   ```yaml
   nats:
     # The Compose service name, logged in as the broker user `engine`.
     nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222"
     # The engine answers the broker's auth callout: every connection but
     # `engine` and `auth` is admitted with its service account's subjects.
     auth_callout:
       nats_url: "nats://auth:{{ secret.NATS_AUTH_PASSWORD }}@nats:4222"
       issuer_seed: "{{ secret.NATS_AUTH_CALLOUT_SEED }}"
   ```

   Use `127.0.0.1:4222` instead of `nats:4222` when the engine runs outside
   Docker on the same machine (the port listens on 127.0.0.1 only). SDK modules
   log in with their own service key (user `sa`, the key as password; the SDK
   does it from `ABI_SERVICE_KEY`) on `ABI_NATS_URL=nats://nats:4222`.
   `abi dev up` runs its own broker on 127.0.0.1 with the same users and callout
   (NATS mode is its default, also for a project without the block;
   `--without-nats` turns it off): its overlay logs the engine in as `engine`,
   and hands each of the `dev.modules` it starts a key of its own.

4. **Remove the `bus:` section** from `services:`. Configs created by
   `abi new project` declare one: `rabbitmq` in `config.local.yaml`,
   `python_queue` in `config.yaml`. In NATS mode the engine refuses to start
   with any bus adapter other than `nats_jetstream`. To keep a `bus:` block, for
   example for `emit_message_events`, it must read:

   ```yaml
     bus:
       emit_message_events: true
       bus_adapter:
         adapter: "nats_jetstream"
         config:
           # must equal nats.nats_url
           nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222"
   ```

5. **Check the cache tiers.** Either all tiers are local or all are `nats_rpc`.
   The engine refuses a mix.

6. **Start the broker and restart:**

   ```bash
   docker compose --profile nats up -d
   ```

   Once `config.local.yaml` has the `nats:` block, `abi deploy local
   --regenerate` renders the NATS stack instead: `nats` starts without a
   profile and the engine waits for it, RabbitMQ moves behind the `rabbitmq`
   profile, and Dagster is left out (move its schedules to module jobs first,
   or restore the previous `docker-compose.yml` from the backup it writes).

7. **Verify:**
   - `curl -s http://localhost:8222/healthz` returns `ok`.
   - `curl -s http://localhost:8222/connz` lists the engine connections. The API
     and Dagster each open several (one per service client), so a count of zero
     means an engine did not connect.
   - With the [NATS CLI](https://github.com/nats-io/natscli), `nats micro list`
     shows the kernel services. The model registry and discovery do not appear
     there.
   - With the log level at `DEBUG`, the engine logs an
     `EngineNATSLoader: exposed <service> over NATS` line for each service it
     serves.
   - Run the same flows as in phase 1.

The API and Dagster both start an engine from the same `config.yaml`, so both
serve every service. That is safe with the shared backends of `abi deploy local`.

### Right after the restart: copy agent memory and activity logs

In NATS mode, engine agents keep their conversation memory in the Document
Service, and the activity log is there by default too. Earlier data stays where
it was until you copy it. Do it right after the restart, as a super admin, in
the Nexus System app: **Jobs** tab, **Run now** with a JSON payload. Each run is
audited, and its report is the run's result.

1. **Agent memory** (`naas_abi_core.agent_memory`, job `agent_memory_migrate`).
   Until it runs, users' earlier conversations have no memory.
   - Run it with `{}`. This is a dry run against the `POSTGRES_URL` database:
     check `threads`, `missing` and `diverged`.
   - Run it with `{"apply": true}`. Running it again copies nothing.
   - A thread listed in `diverged` was continued before the copy, so its newer
     messages hide the copied history. Keeping the window short avoids this.
   - Memory that an older release kept in documents (schema 1) copies with
     `{"from": "documents-v1"}`. `"threads": [...]` limits a run to some
     threads.
   - The engine reads `POSTGRES_URL` from its secrets or environment. Never put
     a connection string in the payload: payloads are shown in the UI.
2. **Activity log** (`naas_abi_core.activity_log`, job `activity_log_migrate`),
   if you need the history recorded before the switch:
   - Run it with `{"data_dir": "storage/activity_log"}`, the old adapter's
     `data_dir`. This dry run counts each actor's events.
   - Run it with `{"data_dir": "storage/activity_log", "apply": true}`. Copied
     events come after the ones recorded since the restart. Running it again
     copies only what is missing.

From then on, `agent_memory_prune` runs daily and keeps each thread's newest
20 checkpoints; the conversation stays whole in them. Without NATS mode no
engine hosts jobs: stop the engines and run `abi agent migrate-memory` (a dry
run, then `--apply`).

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
        nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222"
        # A key of the owning engine's IAM, exchanged for its tokens:
        # abi iam service-account create dagster --key
        service_key: "{{ secret.DAGSTER_SERVICE_KEY }}"
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
engine only through NATS. See `libs/naas-abi-sdk/README.md` and the example in
`examples/standalone_module/`. In short:

1. Create its service account and a key (printed once):

   ```bash
   abi iam service-account create module/default/my_module --key
   ```

2. Run the module with `ABI_NATS_URL` (no login in it) and `ABI_SERVICE_KEY`
   set:

   ```bash
   naas-abi-module my_module --config module.json
   ```

   The SDK logs in with the key and exchanges it for tokens of ten minutes at
   most, renewed at half their life.
3. At start the module submits its permission manifest and waits. Approve it:

   ```bash
   abi iam module list --status pending
   abi iam module approve module/default/my_module
   ```

   Until then the broker lets it reach IAM only. Revoke its key with
   `abi iam key revoke`; the next exchange and the next connection fail.

### Discovery

For modules to find each other and call each other's agents, enable
discovery on exactly one engine per project:

```yaml
nats:
  nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222"
  discovery:
    project: default
    lease_seconds: 20
```

Because the API and Dagster read the same `config.yaml`, adding this block turns
discovery on in both. Discovery is designed for a single owner, so give the
second process a config without the `discovery:` block, or drop Dagster once
module jobs replace its schedules, as projects created with `abi new project`
do. The registry holds at most 256 live module instances per project.

To add a module that runs in its own process, run `abi new module <name>` in
the project: it scaffolds an SDK module under `src/`, adds it to `dev.modules`
and `docker-compose.override.yml`. Use `lease_seconds: 180` so remote modules
outlive an engine restart.

## Roll back

1. Remove the `nats:` block and restore the previous `bus:` section.
2. Restart the engines. They go back to in-process wiring.
3. Stop the broker with `docker compose --profile nats stop nats`.

Messages still in the NATS bus stay in the `nats_data` volume and are not
copied back to the old bus. Undo phase 1 by pointing `.abi` back at the previous
version and running `abi deploy local --regenerate` again.

## Known limits

- The generated stack runs one NATS server, and JetStream streams have one
  replica. If that server stops, every NATS call fails.
- Nothing checks where a service's owners run or whether they share the same
  data.
- Projects are separated by subject prefix, not by NATS accounts. Every
  connection is in the same account.
- Each module is confined by the broker to the subjects of its approved policy
  (docs/adr/20261013_engine-tokens-service-accounts-broker.md). The `engine`
  user reaches every subject but `$SYS`: keep its password to the engine's
  processes.
- A connection keeps the subjects it was admitted with until it reconnects: an
  approval, a narrowed policy or a revoked key reaches the broker at the next
  connection (services ask IAM on every call, so they apply it at once).
- A `nats_rpc` adapter logs in with a broker password (`engine`); it does not
  yet log in through the auth callout with its key.
- The server answers a module's JetStream requests (pub acks, fetches) on the
  reply subject the module chose, and streams capture what lands there: a
  module can still drop a pub ack or an empty message on another topic. Job
  hosts take only the triggers the engine sealed. Separate NATS accounts would
  close this (proposed).
- Remote modules must run the SDK of the same release as the engine: an older
  SDK creates its own streams, consumers and job messages, which the broker now
  refuses.
- Traffic to the broker is not encrypted (no TLS). Keep the broker on a
  private network; a module on another machine should reach it through a
  VPN or an SSH tunnel.
- Remote agent runs stop after 300 seconds without new output, and there is no
  overall time limit. If a Python worker thread hangs, it keeps its run slot
  until it returns.
