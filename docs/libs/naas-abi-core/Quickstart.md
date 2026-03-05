# Quickstart

This page gets you from zero to a running `naas-abi-core` runtime.

Related pages: [[Configuration]], [[Engine]], [[apps/API-App]].

## 1) Install

```bash
uv sync --all-extras
uv pip install greenlet
```

If you only need this package:

```bash
pip install naas-abi-core
```

Optional extras:

- `pip install naas-abi-core[qdrant]`
- `pip install naas-abi-core[aws]`
- `pip install naas-abi-core[ssh]`
- `pip install naas-abi-core[redis]`
- `pip install naas-abi-core[rabbitmq]`

## 2) Create `config.yaml`

Minimal local example:

```yaml
api:
  title: "ABI API"
  description: "API for ABI"
  cors_origins:
    - "http://localhost:9879"

global_config:
  ai_mode: "local"

services:
  object_storage:
    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "storage/datastore"

  triple_store:
    triple_store_adapter:
      adapter: "fs"
      config:
        store_path: "storage/triplestore"
        triples_path: "triples"

  vector_store:
    vector_store_adapter:
      adapter: "qdrant_in_memory"
      config: {}

  secret:
    secret_adapters:
      - adapter: "dotenv"
        config:
          path: ".env"

  bus:
    bus_adapter:
      adapter: "python_queue"
      config: {}

  kv:
    kv_adapter:
      adapter: "python"
      config: {}

modules:
  - module: "naas_abi_core.modules.templatablesparqlquery"
    enabled: true
```

## 3) Start the API

```bash
uv run python -m naas_abi_core.apps.api.api
```

Then open:

- `http://localhost:9879/`
- `http://localhost:9879/docs`
- `http://localhost:9879/redoc`

## 4) Use the Engine in code

```python
from naas_abi_core.engine.Engine import Engine

engine = Engine()
engine.load()

print(engine.modules.keys())
```

Next: [[Engine]] and [[Module-System]].
