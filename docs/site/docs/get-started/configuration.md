---
sidebar_position: 2
---

# Configuration Reference

ABI is configured through `config.yaml`. This page documents every top-level section.

---

## Environment files

ABI loads a config file based on the `ABI_ENV` environment variable:

| `ABI_ENV` | Config file loaded |
|-----------|-------------------|
| (unset) | `config.yaml` |
| `development` | `config.development.yaml` |
| `production` | `config.production.yaml` |
| `airgap` | `config.airgap.yaml` |

Secrets belong in `.env` (gitignored). Config belongs in `config.yaml` (can be committed, no secrets).

---

## Top-level structure

```yaml
api:
  title: "ABI API"
  description: "API for ABI"
  cors_origins:
    - "http://localhost:9879"

global_config:
  ai_mode: "cloud"       # "cloud" or "local"

services:
  triple_store: ...
  vector_store: ...
  object_storage: ...
  secret: ...
  bus: ...
  kv: ...
  cache: ...

modules:
  - module: "naas_abi_core.modules.templatablesparqlquery"
    enabled: true
```

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

`cors_origins` is the single source of truth for CORS - applies to both the core API and the embedded Nexus API. See [ADR: CORS single source](/updates/cors-single-source-of-truth).

---

## global_config

```yaml
global_config:
  ai_mode: "cloud"   # "cloud" uses OpenRouter; "local" uses Ollama
```

---

## Services

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

Default is **`python_queue`** (SQLite-backed queue under `storage/bus/`). Use **`rabbitmq`** for production deployments.

```yaml
services:
  bus:
    bus_adapter:
      adapter: "python_queue"
      config: {}
```

RabbitMQ for production:

```yaml
      adapter: "rabbitmq"
      config:
        host: "localhost"
        port: 5672
        username: "guest"
        password: "guest"
```

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

Optional; add a `cache` section when you need a dedicated cache layer. A typical local choice is **`fs`** with a path under `storage/`.

```yaml
services:
  cache:
    cache_adapter:
      adapter: "fs"
      config:
        base_path: "storage/cache"
```

---

## Modules

```yaml
modules:
  - module: "naas_abi_core.modules.templatablesparqlquery"
    enabled: true
    config: {}

  - module: "naas_abi.modules.core.abi"
    enabled: true
    config:
      github_repository: "jupyter-naas/abi"

  - module: "naas_abi_marketplace.modules.linkedin"
    enabled: false                  # Enable when LINKEDIN_API_KEY is set
```

Modules are loaded in dependency order. Disabled modules and their dependencies are skipped.

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
```
