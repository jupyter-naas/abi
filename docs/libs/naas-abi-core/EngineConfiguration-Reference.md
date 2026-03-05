# EngineConfiguration Reference

This page documents `naas_abi_core/engine/engine_configuration/EngineConfiguration.py` in detail.

Related pages: [[Configuration]], [[Engine]], [[EngineConfiguration-Services-Reference]], [[services/Overview]], [[Built-in-Module-Templatable-SPARQL]].

## Purpose

`EngineConfiguration` is the runtime configuration model and loader for ABI core. It combines:

- pydantic schema validation,
- Jinja2 templating,
- secret bootstrap/loading,
- environment-aware file selection,
- default service/module insertion.

## Data models defined in the file

## `ServicesConfiguration`

Defines top-level service configuration and built-in defaults.

Default services if omitted in YAML:

- `object_storage`: FS adapter, `base_path: storage/datastore`
- `triple_store`: FS adapter, `store_path: storage/triplestore`, `triples_path: triples`
- `vector_store`: `qdrant_in_memory`
- `secret`: dotenv adapter
- `bus`: `python_queue`
- `kv`: `python`

## `ApiConfiguration`

Default API settings:

- `title`: `ABI API`
- `description`: `API for ABI, your Artifical Business Intelligence`
- `logo_path`: `assets/logo.png`
- `favicon_path`: `assets/favicon.ico`
- `cors_origins`: `["http://localhost:9879"]`
- `reload`: `True`

## `FirstPassConfiguration`

Minimal model containing only `services.secret`.

Used during bootstrap so secrets can be resolved before validating/loading all other service configs.

## `ModuleConfig`

Module entry model:

- `path: str | None`
- `module: str | None`
- `enabled: bool`
- `config: dict`

Validation rule: at least one of `path` or `module` must be provided.

## `GlobalConfig`

Currently enforces:

- `ai_mode` in `cloud | local | airgap`

## `EngineConfiguration`

Top-level engine schema:

- `api: ApiConfiguration`
- `deploy: DeployConfiguration | None`
- `services: ServicesConfiguration`
- `global_config: GlobalConfig`
- `modules: list[ModuleConfig]`
- `default_agent: str` (default: `naas_abi AbiAgent`)

## Default module injection

`EngineConfiguration.ensure_default_modules()` auto-appends:

- `naas_abi_core.modules.templatablesparqlquery`

if not already present in either `modules[].module` or `modules[].path`.

This is called by `validate_modules()` model validator.

## Loading pipeline

## 1) `from_yaml(path)`

- Reads file content and forwards to `from_yaml_content(content)`.

## 2) `from_yaml_content(content)`

Performs two-pass rendering:

1. Detect bootstrap dotenv adapter directly from raw YAML.
2. First-pass Jinja render using `SecretServiceWrapper(secret_service=None, bootstrap_dotenv_adapter=...)`.
3. Validate/load `FirstPassConfiguration` and build real `Secret` service.
4. Second-pass Jinja render using `SecretServiceWrapper(secret_service=<loaded>)`.
5. Parse rendered YAML and validate full `EngineConfiguration`.

## 3) `load_configuration(configuration_yaml=None)`

- If `configuration_yaml` is passed, parse it directly (used by tests and inline configs).
- Otherwise resolve file with this algorithm:
  1. read `ENV` from process env;
  2. if missing and `config.yaml` exists, try bootstrap dotenv and read `ENV` from it;
  3. if `ENV` exists and `config.<ENV>.yaml` exists, pick that file;
  4. else fallback to `config.yaml`;
  5. if no file, raise `FileNotFoundError`.

## Secret resolution behavior (`SecretServiceWrapper`)

The wrapper powers `{{ secret.NAME }}` in Jinja templates.

## First pass (`secret_service is None`)

Lookup order:

1. `os.environ[NAME]`
2. bootstrap dotenv adapter value
3. fallback message string: "secret not found while loading secret service"

The fallback string is intentional to let the first pass continue even when some secrets are unresolved.

## Second pass (`secret_service is set`)

Lookup order:

1. `os.environ[NAME]` (environment wins)
2. `secret_service.get(NAME)`
3. if missing:
   - non-interactive runtime (`stdin` not TTY): raise `ValueError`
   - interactive runtime: prompt user via `rich.prompt.Prompt`, then persist using `secret_service.set(NAME, value)`

## Bootstrap dotenv adapter extraction

`_load_bootstrap_dotenv_adapter_from_yaml_content` inspects raw YAML (no template render) and returns a dotenv adapter if configured.

Validation rule:

- `services.secret.secret_adapters[].config.path` must be a non-empty string when adapter is `dotenv`.

If invalid, a `ValueError` is raised before full config load.

## Operational implications

- You can centralize secrets in `.env` and still move to other secret backends later.
- Environment variables always override secret backend values at load time.
- CI/CD should avoid interactive prompts by providing all required secrets in env or secret adapter.
- Missing `config.yaml` and `config.<ENV>.yaml` is a hard startup failure.

## Example with templated secrets

```yaml
services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config:
          path: ".env"

  vector_store:
    vector_store_adapter:
      adapter: "qdrant"
      config:
        host: "{{ secret.QDRANT_HOST }}"
        port: {{ secret.QDRANT_PORT }}
        api_key: "{{ secret.QDRANT_API_KEY }}"

global_config:
  ai_mode: "local"

modules:
  - module: "naas_abi_core.modules.templatablesparqlquery"
    enabled: true
```

## Service adapter field reference

For the adapter-specific schema (bus, kv, object storage, secret, triple store, vector store, and deploy), see [[EngineConfiguration-Services-Reference]].
