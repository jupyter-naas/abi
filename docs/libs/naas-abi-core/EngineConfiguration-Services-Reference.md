# EngineConfiguration Services Reference

This page documents service and deploy configuration models defined in:

- `naas_abi_core/engine/engine_configuration/EngineConfiguration_BusService.py`
- `naas_abi_core/engine/engine_configuration/EngineConfiguration_KeyValueService.py`
- `naas_abi_core/engine/engine_configuration/EngineConfiguration_ObjectStorageService.py`
- `naas_abi_core/engine/engine_configuration/EngineConfiguration_SecretService.py`
- `naas_abi_core/engine/engine_configuration/EngineConfiguration_TripleStoreService.py`
- `naas_abi_core/engine/engine_configuration/EngineConfiguration_VectorStoreService.py`
- `naas_abi_core/engine/engine_configuration/EngineConfiguration_Deploy.py`
- `naas_abi_core/engine/engine_configuration/EngineConfiguration_GenericLoader.py`

Related pages: [[Configuration]], [[EngineConfiguration-Reference]], [[services/Overview]], [[Troubleshooting]].

## Adapter model pattern

Most services follow the same shape:

```yaml
services:
  <service_name>:
    <adapter_field>:
      adapter: "<adapter_name>"
      config:
        # adapter-specific keys
```

For any adapter value `custom`, config is loaded through `GenericLoader` and requires top-level keys on the adapter block:

- `python_module`
- `module_callable`
- `custom_config`

Example:

```yaml
services:
  vector_store:
    vector_store_adapter:
      adapter: "custom"
      python_module: "my_project.adapters"
      module_callable: "MyVectorAdapter"
      custom_config:
        endpoint: "http://localhost:9999"
```

## Deploy configuration

`deploy` is optional in `EngineConfiguration`, but when present it uses:

- `workspace_id: str`
- `space_name: str`
- `naas_api_key: str`
- `env: dict[str, str]` (default `{}`)

```yaml
deploy:
  workspace_id: "workspace_123"
  space_name: "prod"
  naas_api_key: "{{ secret.NAAS_API_KEY }}"
  env:
    ENV: "prod"
```

## `services.bus`

Path: `services.bus.bus_adapter`

Supported adapters:

- `rabbitmq`
  - `rabbitmq_url: str` (default `amqp://abi:abi@127.0.0.1:5672`)
- `python_queue`
  - no fields (use `config: {}`)
- `custom`
  - uses GenericLoader fields

```yaml
services:
  bus:
    bus_adapter:
      adapter: "rabbitmq"
      config:
        rabbitmq_url: "{{ secret.RABBITMQ_URL }}"
```

## `services.kv`

Path: `services.kv.kv_adapter`

Supported adapters:

- `redis`
  - `redis_url: str` (default `redis://localhost:6379`)
- `python`
  - no fields (use `config: {}`)
- `custom`
  - uses GenericLoader fields

```yaml
services:
  kv:
    kv_adapter:
      adapter: "redis"
      config:
        redis_url: "{{ secret.REDIS_URL }}"
```

## `services.object_storage`

Path: `services.object_storage.object_storage_adapter`

Supported adapters:

- `fs`
  - `base_path: str` (required)
- `s3`
  - `bucket_name: str` (required)
  - `base_prefix: str` (required)
  - `access_key_id: str` (required)
  - `secret_access_key: str` (required)
  - `session_token: str | None` (optional)
  - `endpoint_url: str | None` (optional)
- `naas`
  - `naas_api_key: str` (required)
  - `workspace_id: str` (required)
  - `storage_name: str` (required)
  - `base_prefix: str` (default `""`)
- `custom`
  - uses GenericLoader fields

```yaml
services:
  object_storage:
    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "storage/datastore"
```

## `services.secret`

Path: `services.secret.secret_adapters` (list)

Supported adapters:

- `dotenv`
  - `path: str` (default `.env`)
- `naas`
  - `naas_api_key: str` (required)
  - `naas_api_url: str` (required)
- `base64`
  - `secret_adapter: SecretAdapterConfiguration` (nested adapter)
  - `base64_secret_key: str` (required)
- `custom`
  - uses GenericLoader fields

```yaml
services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config:
          path: ".env"
```

## `services.triple_store`

Path: `services.triple_store.triple_store_adapter`

Supported adapters:

- `oxigraph`
  - `oxigraph_url: str` (default `http://localhost:7878`)
  - `timeout: int` (default `60`)
- `apache_jena_tdb2`
  - `jena_tdb2_url: str` (default `http://localhost:3030/ds`)
  - `timeout: int` (default `60`)
- `aws_neptune`
  - `aws_region_name: str` (required)
  - `aws_access_key_id: str` (required)
  - `aws_secret_access_key: str` (required)
  - `db_instance_identifier: str` (required)
- `aws_neptune_sshtunnel`
  - all `aws_neptune` fields, plus:
  - `bastion_host: str` (required)
  - `bastion_port: int` (required)
  - `bastion_user: str` (required)
  - `bastion_private_key: str` (required)
- `fs`
  - `store_path: str` (required)
  - `triples_path: str` (default `triples`)
- `object_storage`
  - `object_storage_service: ObjectStorageServiceConfiguration` (required)
  - `triples_prefix: str` (default `triples`)
- `custom`
  - uses GenericLoader fields

```yaml
services:
  triple_store:
    triple_store_adapter:
      adapter: "fs"
      config:
        store_path: "storage/triplestore"
        triples_path: "triples"
```

## `services.vector_store`

Path: `services.vector_store.vector_store_adapter`

Supported adapters:

- `qdrant`
  - `host: str` (default `localhost`)
  - `port: int` (default `6333`)
  - `api_key: str | None` (optional)
  - `https: bool` (default `false`)
  - `timeout: int` (default `30`)
- `qdrant_in_memory`
  - no fields (use `config: {}`)
- `custom`
  - uses GenericLoader fields

```yaml
services:
  vector_store:
    vector_store_adapter:
      adapter: "qdrant"
      config:
        host: "{{ secret.QDRANT_HOST }}"
        port: {{ secret.QDRANT_PORT }}
        api_key: "{{ secret.QDRANT_API_KEY }}"
        https: false
        timeout: 30
```

## Validation and strictness notes

- Adapter config models use `extra="forbid"`, so unknown keys fail validation.
- For non-`custom` adapters, `config` is required by model validators.
- `python_queue`, `python`, and `qdrant_in_memory` still require an empty object (`config: {}`) to satisfy validation.
