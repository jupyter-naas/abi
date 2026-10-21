---
sidebar_position: 2
---

# Configuration Reference

ABI is configured through `config.yaml`. This page documents every top-level section of a 3.0 project, which runs on [NATS](/developer-guide/architecture/nats). The classic in-process configuration (no `nats:` block, Dagster, RabbitMQ) is described in [its own section](#classic-configuration-legacy) at the end.

---

## Environment files

A project keeps one config file per environment. The engine reads
`config.<ENV>.yaml` when the `ENV` environment variable names a file that
exists, else `config.yaml`:

| File | Read by |
|---|---|
| `config.yaml` | `abi dev up`, the CLI (`abi chat`, `abi run`), scripts |
| `config.local.yaml` | The Docker Compose stack (its `abi` service sets `ENV=local`) |
| `config.remote.yaml` | A remote deployment (`ENV=remote`), with its secrets in `.env.remote`: see [Production and remote deployments](/user-guide/deploy/production) |

`ABI_CONFIG_OVERLAY` names a YAML file merged over the config; `abi dev up`
uses it (`.abi/dev/dev.overlay.yaml`) for the broker it runs. Secrets belong in
`.env` (gitignored) and are referenced as `{{ secret.NAME }}`. Config belongs in
the config files (committed, no secrets).

---

## Top-level structure

```yaml
api:
  title: "ABI API"
  description: "API for ABI"
  cors_origins:
    - "http://localhost:9879"

global_config:
  ai_mode: "cloud"       # "cloud", "local" or "airgap"

nats:                    # NATS mode (the default); omit only for the legacy in-process engine
  nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@127.0.0.1:4222"
  auth_callout:          # modules log in with a service key; the engine admits them
    nats_url: "nats://auth:{{ secret.NATS_AUTH_PASSWORD }}@127.0.0.1:4222"
    issuer_seed: "{{ secret.NATS_AUTH_CALLOUT_SEED }}"
  discovery:
    project: "my_ai"
    lease_seconds: 180

telemetry:               # OpenTelemetry tracing (optional)
  enabled: false

services:
  triple_store: ...
  vector_store: ...
  object_storage: ...
  document: ...
  dataset: ...
  secret: ...
  kv: ...
  cache: ...

modules:
  - module: "naas_abi"
    enabled: true

dev:                     # remote modules `abi dev up` runs
  modules:
    - name: research
      module: research
```

`nats`, `telemetry` and `dev` are new in 3.0: a config that used one of these
names for something else must rename it.

---

## API section

```yaml
api:
  title: "My ABI"
  description: "My organization's AI platform"
  cors_origins:
    - "http://localhost:9879"
    - "https://myapp.example.com"
```

`cors_origins` is the single source of truth for CORS - applies to both the core API and the embedded Nexus API. See [ADR: CORS single source](/user-guide/release-notes/cors-single-source-of-truth).

---

## global_config

```yaml
global_config:
  ai_mode: "cloud"   # "cloud" uses OpenRouter; "local" uses Ollama; "airgap" uses local models only
```

---

## nats

A top-level `nats:` block puts the engine in NATS mode: it serves its kernel
services on the broker, the bus is JetStream, module jobs run, and remote
modules register through discovery. See [NATS and the Kernel Services](/developer-guide/architecture/nats).

```yaml
nats:
  # The broker, logged in as the engine's user `engine`. `nats` is the Compose
  # service; use 127.0.0.1 in config.yaml (`abi dev up` overlays its own URL).
  nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222"
  # The broker's auth callout, answered by the serving engine as the user `auth`:
  # every other connection (a module, a script) logs in as `sa` with a service
  # key and is admitted with the subjects its approved permission manifest allows.
  # The seed signs the users the engine admits; nats.conf trusts its public key
  # (NATS_AUTH_CALLOUT_ISSUER).
  auth_callout:
    nats_url: "nats://auth:{{ secret.NATS_AUTH_PASSWORD }}@nats:4222"
    issuer_seed: "{{ secret.NATS_AUTH_CALLOUT_SEED }}"
  # One engine per project hosts the module registry.
  discovery:
    project: "my_ai"
    lease_seconds: 180
  # The broker's monitoring endpoint, for the Nexus System app. No auth.
  monitoring_url: "http://nats:8222"
```

| Key | Default | Meaning |
|---|---|---|
| `client_timeout_seconds` | 10 | How long the engine's service calls wait for a reply. |
| `max_concurrent_requests` | 64 | Calls each kernel service handles at once. |
| `discovery.project`, `discovery.lease_seconds` | `default`, 20 | The discovery project, a module instance's lease. |
| `object_storage_streaming.chunk_bytes`, `.max_sessions`, `.max_upload_bytes`, `.idle_seconds` | 64 KiB, 32, none, 60 | Chunked object transfers. |
| `models.generation_timeout_seconds`, `models.streaming.max_upload_bytes`, `.max_buffered_upload_bytes` | none, 16 MiB, 64 MiB | Remote model calls. |
| `rpc_overflow.enabled`, `.max_value_bytes`, `.max_sessions` | on, 256 MiB, 64 | Requests and replies above the broker limit. |
| `jobs.enabled` | true | Host module jobs in this engine (`false` on one-off engines). |
| `jobs.interrupt_grace_seconds` | 5 | Before a timed-out synchronous job is interrupted (`null`: never). |
| `jobs.retention.max_age_days`, `.max_runs_per_job`, `.skipped_max_age_minutes`, `.interval_minutes` | 7, 1000, 60, 10 | Finished job runs kept. |
| `engine.role` | `serve` | `serve`, `client` or `auto` (`ABI_ENGINE_ROLE` overrides). |
| `engine.rollout_id` | empty | Deploys without downtime (`ABI_ROLLOUT_ID` overrides). |
| `engine.lease_seconds`, `.standby_timeout_seconds`, `.drain_seconds` | 20, 900, 60 | The serving engine's lease, a standby's wait, the drain at shutdown. |
| `monitoring_url` | none | The broker's HTTP monitoring endpoint. |

In NATS mode, an explicit `services.bus` must use `nats_jetstream` on the same
URL (or be omitted), and cache tiers are all local or all `nats_rpc`.

---

## telemetry

OpenTelemetry tracing across processes (needs `naas-abi-core[otel]`, part of
`[all]`). See [Observability](/developer-guide/architecture/observability).

```yaml
telemetry:
  enabled: true
  otlp_endpoint: "http://jaeger:4318"   # OTLP/HTTP
  service_name: "abi-engine"
  sample_ratio: 1.0
  ui_url: "http://localhost:16686"      # the trace viewer the System app links to
  query_url: "http://jaeger:16686"      # where the API reads spans (default: ui_url)
```

`abi dev up --with-tracing` adds this block to its overlay.

---

## dev

The remote modules `abi dev up` runs next to the engine in NATS mode. `abi new
module` adds an entry. The engine validates the block and otherwise ignores it.

```yaml
dev:
  modules:
    - name: research                  # process name: logs, --service
      module: research                # run as `python -m research`
      identity: my_ai.research        # its module id (default: its ABIModule's)
      args: []
      env: {RESEARCH_CHAT_MODEL: ""}  # may name ${ABI_NATS_URL}, ${ABI_DISCOVERY_PROJECT}...
      enabled: true
      restart: on-failure             # or always, never
```

---

## Services

A project made by `abi new project` picks these adapters. The engine's built-in defaults,
described under each service below, apply to a service you leave out.

| Service | `config.yaml` (`abi dev up`) | `config.local.yaml` (Docker) |
|---|---|---|
| `triple_store` | `oxigraph` (HTTP; `abi dev up` runs the server) | `apache_jena_tdb2` (Fuseki) |
| `vector_store` | `sqlite_vec` (a SQLite file) | `qdrant` |
| `object_storage` | `fs` (`storage/datastore`) | `s3` (MinIO) |
| `document` | `sqlite` (`storage/documents.sqlite`) | `postgresql` |
| `dataset` | `ducklake` (SQLite catalog) | `ducklake` |
| `kv` | `python` (SQLite) | `redis` |
| `bus` | NATS JetStream (no `bus:` block) | NATS JetStream (no `bus:` block) |

### Triple Store

Default in the engine is **`oxigraph_embedded`** (embedded Oxigraph on disk under `storage/triplestore/oxigraph`). Full Docker setups that load **`config.local.yaml`** usually use **`apache_jena_tdb2`** (Apache Jena Fuseki). Other adapters include `oxigraph` (HTTP), `fs`, `aws_neptune`, and `object_storage`.

```yaml
services:
  triple_store:
    triple_store_adapter:
      adapter: "oxigraph_embedded"
      config:
        store_path: "storage/triplestore/oxigraph"
        graph_base_iri: "http://ontology.naas.ai/graph/default"
```

Apache Jena Fuseki (TDB2) over HTTP:

```yaml
      adapter: "apache_jena_tdb2"
      config:
        jena_tdb2_url: "http://localhost:3030/ds"
```

Filesystem adapter (no Docker required, dev/test only):

```yaml
      adapter: "fs"
      config:
        store_path: "storage/triplestore"
        triples_path: "triples"
```

### Vector Store

Default is **`qdrant_in_memory`** (persistent path under `storage/vectorstore/qdrant` with an in-process client). Use **`qdrant`** when pointing at a remote Qdrant service.

```yaml
services:
  vector_store:
    vector_store_adapter:
      adapter: "qdrant_in_memory"   # default
      config:
        storage_path: "storage/vectorstore/qdrant"
        timeout: 300
```

Remote Qdrant example:

```yaml
      adapter: "qdrant"
      config:
        host: "localhost"
        port: 6333
```

### Object Storage

Default is **`fs`** with `base_path` **`storage/datastore`**. Alternatives: **`s3`**, **`naas`**.

```yaml
services:
  object_storage:
    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "storage/datastore"
```

### Secret

Default is a single **`dotenv`** adapter reading **`.env`** (path can be overridden). Multiple adapters are supported; secrets are resolved in order.

```yaml
services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config:
          path: ".env"
```

### Message Bus

In NATS mode the bus is NATS JetStream: omit the `bus:` section, or keep it
only for `emit_message_events`, with the `nats_jetstream` adapter on the same
URL as `nats.nats_url`:

```yaml
services:
  bus:
    emit_message_events: true
    bus_adapter:
      adapter: "nats_jetstream"
      config:
        nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222"
```

Without NATS the bus is `python_queue` or the `rabbitmq` adapter, both described under
[Classic configuration (legacy)](#classic-configuration-legacy).

### Key-Value Store

Default is **`python`** (SQLite-backed store under `storage/kv/`). Use **`redis`** when you need a shared Redis instance.

```yaml
services:
  kv:
    kv_adapter:
      adapter: "python"
      config: {}
```

### Cache

Optional; a list of tiers read in order (`hot` first, `cold` by default). Adapters: **`fs`**, **`redis`**, **`object_storage`**, **`keyvalue`**, and **`nats_rpc`** for another engine's cache. In NATS mode, tiers are all local or all `nats_rpc`.

```yaml
services:
  cache:
    adapters:
      - adapter: redis
        tier: hot
        config:
          redis_url: "{{ secret.REDIS_URL }}"
          prefix: "naas:cache"
      - adapter: fs
        tier: cold
        config:
          base_path: "storage/cache"
```

### Document and Dataset

The Document Service holds agent memory, job runs and the activity log in NATS
mode; the dataset service holds tabular data (DuckLake). `abi new project`
configures both: SQLite files for `config.yaml`, PostgreSQL for
`config.local.yaml`.

```yaml
services:
  document:
    document_adapter:
      adapter: "postgresql"
      config:
        dsn: "postgresql://{{ secret.POSTGRES_USER }}:{{ secret.POSTGRES_PASSWORD }}@postgres:5432/{{ secret.POSTGRES_DB }}"
  dataset:
    dataset_adapter:
      adapter: "ducklake"
      config:
        catalog: "sqlite:storage/datasets.sqlite"
        data_path: "storage/datasets/"
```

### Another engine's service

In NATS mode, an engine can use a service another engine owns with the
`nats_rpc` adapter (every kernel service except the model registry and the
bus, which is the broker's JetStream in NATS mode):

```yaml
services:
  object_storage:
    object_storage_adapter:
      adapter: "nats_rpc"
      config:
        nats_url: "nats://engine:{{ secret.NATS_ENGINE_PASSWORD }}@nats:4222"
        # A key of the owning engine's IAM: `abi iam service-account create worker --key`
        service_key: "{{ secret.WORKER_SERVICE_KEY }}"
```

---

## Modules

```yaml
modules:
  - module: "naas_abi_core.modules.templatablesparqlquery"
    enabled: true
    config: {}

  - module: "naas_abi"
    enabled: true

  - module: "naas_abi_marketplace.ai.openrouter"
    enabled: true
    config:
      openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
```

These are the modules the engine loads (in-engine modules). Modules are loaded
in dependency order. Disabled modules and their dependencies are skipped.
Remote modules are not listed here: they run in their own process and register
through discovery (see `dev:` above).

---

## Classic configuration (legacy)

:::warning Legacy
A project without a `nats:` block, Dagster and the RabbitMQ bus are **legacy**: opt-in
since 3.0 and removed in the next major. See [Legacy mode: without
NATS](/user-guide/get-started/legacy-mode), and
[Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3) to move off them.
:::

With no `nats:` block, the engine runs in one process, as in 2.x, and the
services it reaches by NATS in 3.0 are plain adapters:

- **No `nats:` block.** `abi dev up` runs Oxigraph, the API, Nexus web
  and, with the `naas-abi-core[dagster]` extra, Dagster. There are no remote modules,
  no discovery and no module jobs (declared jobs are logged, not run).
- **Bus.** `python_queue` (the default: SQLite under `storage/bus/`) or `rabbitmq`
  (needs the `naas-abi-core[rabbitmq]` extra):

  ```yaml
  services:
    bus:
      bus_adapter:
        adapter: "python_queue"          # or "rabbitmq"
        # config:
        #   rabbitmq_url: "{{ secret.RABBITMQ_URL }}"
  ```

- **Scheduling.** Dagster orchestrations (`abi new orchestration`), from the
  `naas-abi-core[dagster]` extra: see [Dagster](/user-guide/build/applications/dagster).
- **Install the extras** with `uv add 'naas-abi-core[all,dagster,rabbitmq]'`.
  `abi new project --without-nats` and `abi deploy local` add them for you.

`abi new project --without-nats` generates this configuration. `abi dev up --without-nats`
forces it for a project whose config has a `nats:` block.

---

## Environment variables (.env)

```bash
# Model providers (use OpenRouter for unified access)
OPENROUTER_API_KEY=sk-or-...

# Individual providers (if not using OpenRouter)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Storage
POSTGRES_URL=postgresql://abi_user:abi_password@localhost:5432/abi_memory

# Naas platform (optional, for cloud storage and publishing)
NAAS_API_KEY=...

# NATS (written by `abi new project`, `abi deploy local` and `abi dev up`)
NATS_ENGINE_PASSWORD=...     # the broker user `engine` (the engine's processes)
NATS_AUTH_PASSWORD=...       # the broker user `auth` (the engine's auth callout)
NATS_AUTH_CALLOUT_SEED=...   # the account seed the callout signs admitted users with
NATS_AUTH_CALLOUT_ISSUER=... # its public key, which nats.conf trusts
ABI_IDP_CLIENT_SECRET=...    # the secret of the client Nexus signs in to the built-in identity provider with
RESEARCH_SERVICE_KEY=...     # a remote module's key (`abi iam service-account create <account> --key`)
```

Process variables of 3.0: `ABI_ENGINE_ROLE` and `ABI_ROLLOUT_ID` (the engine's
role and rollout), `ABI_CONFIG_OVERLAY`, and for remote modules `ABI_NATS_URL`,
`ABI_SERVICE_KEY`, `ABI_DISCOVERY_PROJECT`, `ABI_HEALTH_PORT` and
`OTEL_EXPORTER_OTLP_ENDPOINT`.
