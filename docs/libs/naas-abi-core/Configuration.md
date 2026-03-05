# Configuration

Configuration is loaded from YAML through `EngineConfiguration`.

Related pages: [[Engine]], [[EngineConfiguration-Reference]], [[EngineConfiguration-Services-Reference]], [[services/Overview]], [[Troubleshooting]].

## File resolution rules

When no inline config is provided:

1. Read `ENV` from process environment.
2. If absent, try to bootstrap `ENV` from dotenv secret adapter in `config.yaml`.
3. If `ENV` exists and `config.<ENV>.yaml` exists, use it.
4. Otherwise use `config.yaml`.

If neither exists, engine startup fails.

Selection behavior is implemented in `EngineConfiguration.load_configuration()`.

## Secret templating in YAML

YAML is rendered with Jinja2 and can reference secrets:

```yaml
services:
  vector_store:
    vector_store_adapter:
      adapter: "qdrant"
      config:
        host: "{{ secret.QDRANT_HOST }}"
        api_key: "{{ secret.QDRANT_API_KEY }}"
```

Two-pass behavior:

- First pass loads only secret service to resolve secret placeholders.
- Second pass renders full configuration with resolved secrets.

If a secret is missing and no TTY is available, loading fails with an explicit error.

Secret lookup precedence during rendering:

1. Process environment variable.
2. Bootstrap dotenv adapter (first pass only).
3. Configured secret service adapters (second pass).
4. Interactive prompt (TTY only, second pass).

For full behavior details, see [[EngineConfiguration-Reference]].

## Top-level sections

- `api`: title, description, logos, CORS, reload.
- `global_config`: `ai_mode` in `cloud | local | airgap`.
- `services`: adapter selection and adapter-specific config.
- `modules`: enabled module entries and module config payload.
- `deploy` (optional): deployment metadata.
- `default_agent` (optional): runtime default agent string.

## Built-in defaults

If service blocks are omitted, defaults are applied:

- `object_storage`: filesystem (`storage/datastore`)
- `triple_store`: filesystem (`storage/triplestore`, `triples`)
- `vector_store`: `qdrant_in_memory`
- `secret`: dotenv (`.env`)
- `bus`: `python_queue`
- `kv`: `python`

## Default module behavior

If not explicitly configured, `naas_abi_core.modules.templatablesparqlquery` is auto-added.

This happens via model validation in `EngineConfiguration.validate_modules()`.

## Minimal complete example

See [[Quickstart]] for a ready-to-run local `config.yaml`.

## Advanced reference

For class-by-class documentation of `EngineConfiguration.py`, see [[EngineConfiguration-Reference]].

For adapter-by-adapter service and deploy configuration fields, see [[EngineConfiguration-Services-Reference]].
