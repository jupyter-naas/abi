# EngineConfiguration

## What it is
- Pydantic models and loader utilities for configuring the ABI engine from YAML.
- Supports:
  - Jinja2-templated YAML (including `{% include %}` relative to the config file directory).
  - Two-pass secret resolution (bootstrap pass to load the secret service, then full pass).
  - Optional deep-merged configuration overlay via an environment variable.
  - Process-wide configuration caching for file-based loads.

## Public API

### Functions
- `deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]`
  - Recursively merges mappings; non-mapping values replace base values.
  - Special rule: if an overlay mapping contains `"adapter"`, it replaces the base mapping entirely (no deep merge for that node).

### Classes

- `ServicesConfiguration`
  - Aggregates service configurations with defaults (document, object storage, dataset, triple store, vector store, secret, bus, kv, email, coding environment, source control, activity log, event, model registry, cache).
  - Methods:
    - `local_backends(owned: Iterable[str]) -> dict[str, str]`: returns a mapping of owned service names to their local storage locations (when applicable).

- `ApiConfiguration`
  - API server settings: `title`, `description`, `logo_path`, `favicon_path`, `cors_origins`, `reload`, `host`, `port`.

- `DiscoveryConfiguration`
  - NATS discovery settings: `project`, `lease_seconds`.

- `NATSStreamingConfiguration`, `NATSModelStreamingConfiguration`, `NATSModelConfiguration`
  - NATS streaming/model streaming limits and timeouts.

- `NATSRPCOverflowConfiguration`
  - Controls overflow handling for large NATS RPC payloads.

- `NATSJobsRetentionConfiguration`
  - Job retention policy controls.
  - Method:
    - `to_retention() -> Any`: returns an SDK `JobRetention` instance or `None` when disabled.

- `NATSJobsConfiguration`
  - Controls whether the engine hosts jobs and related behavior.

- `NATSEngineConfiguration`
  - Engine serving role/lease/standby/drain settings.
  - Methods:
    - `resolved(environ: Mapping[str, str]) -> NATSEngineConfiguration`: applies `ABI_ENGINE_ROLE` / `ABI_ROLLOUT_ID` overrides.
    - `timing() -> Any`: returns an `OwnershipTiming` instance.

- `NATSConfiguration`
  - Top-level NATS boundary configuration: `nats_url`, `jwt_secret`, timeouts, concurrency, discovery, streaming, RPC overflow, jobs, engine, monitoring URL.

- `TelemetryConfiguration`
  - OpenTelemetry export settings: `enabled`, `otlp_endpoint`, `service_name`, `sample_ratio`, `ui_url`, `query_url`.

- `OpencodeProviderConfiguration`, `OpencodeConfiguration`
  - Opencode authentication configuration: `auth_file_path`, `providers`.

- `FirstPassConfiguration`
  - Minimal schema used for the first pass to load the secret service (`services.secret` only).

- `ModuleConfig`
  - Module loading entry:
    - Fields: `path` or `module` (at least one required), `enabled`, `config`.
  - Validates that at least one of `path` / `module` is provided.

- `GlobalConfig`
  - Global settings: `ai_mode` (`"cloud" | "local" | "airgap"`), `skip_ontology_loading`, `public_api_host`.
  - Applies env override:
    - `ABI_SKIP_ONTOLOGY_LOADING` truthy value forces `skip_ontology_loading=True`.

- `EngineConfiguration`
  - Top-level configuration model:
    - `api`, `deploy`, `services`, `global_config`, `nats`, `telemetry`, `modules`, `default_agent`, `opencode`, `dev`.
  - Methods:
    - `ensure_default_modules() -> None`: ensures default modules are present in `modules`:
      - `naas_abi_core.modules.templatablesparqlquery`
      - `naas_abi_core.modules.bfo`
      - `naas_abi_core.modules.cco`
    - `render_without_secrets(yaml_content: str, base_dir: str | None = None) -> Any`: renders Jinja with empty/undefined secrets and parses YAML.
    - `configuration_file() -> str`: selects `config.{ENV}.yaml` if present else `config.yaml`; may read `ENV` from bootstrap dotenv adapter declared in `config.yaml`.
    - `from_yaml(yaml_path: str, overlay: dict[str, Any] | None = None) -> EngineConfiguration`: loads from a YAML file path.
    - `from_yaml_content(yaml_content: str, base_dir: str | None = None, overlay: dict[str, Any] | None = None) -> EngineConfiguration`: loads from YAML string with two-pass secret resolution; optionally deep-merges `overlay`.
    - `reset_configuration_cache() -> None`: clears process-wide cached configuration (intended for tests).
    - `load_configuration(configuration_yaml: str | None = None) -> EngineConfiguration`:
      - If `configuration_yaml` provided: loads from inline YAML and **does not cache**.
      - Else: loads from selected file, applies optional overlay, and caches the result.

## Configuration/Dependencies

### YAML rendering (Jinja2)
- Jinja is evaluated before YAML parsing.
- Base directory for includes:
  - `from_yaml(...)`: config file’s directory.
  - Inline content: current working directory.
- Full-line YAML comments (lines whose first non-space/tab char is `#`) are wrapped in `{% raw %}` so Jinja expressions inside comments are **not evaluated**.
- A helper is available in templates:
  - `load_csv(path: str, **csv.DictReader kwargs) -> list[dict]` (path relative to the config directory).

### Secret resolution (two-pass)
- Pass 1: renders YAML with a `secret` object that resolves:
  - environment variables first,
  - then a bootstrap dotenv adapter (if configured),
  - else returns a placeholder string (does not raise).
- Loads secret service from the parsed first-pass configuration.
- Pass 2: re-renders YAML with `secret` backed by the loaded secret service:
  - environment variables override secret service values,
  - missing secrets:
    - if no TTY: raises `ValueError`,
    - else prompts via `rich.prompt.Prompt` and stores the value in the secret service.

### Overlay file (optional)
- Environment variable: `ABI_CONFIG_OVERLAY`
- If set, must point to an existing YAML file containing a mapping.
- The overlay is deep-merged over the rendered config data using `deep_merge`.

### NATS mode validation
When `EngineConfiguration.nats` is set:
- If `services.bus` is explicitly set:
  - it must use adapter `"nats_jetstream"`,
  - its `nats_url` must match `nats.nats_url`.
- Cache adapters cannot mix local and remote tiers in NATS mode:
  - if any cache adapter is `"nats_rpc"`, then all must be `"nats_rpc"`.

### Non-NATS activity log default tweak
- If `nats is None` and `activity_log` was **not** explicitly set in `services`, the configuration forces the activity log adapter to SQLite (and treats it as a default, not user config).

## Usage

### Load from default config file (with optional overlay)
```python
import os
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

# Optional: overlay file path
# os.environ["ABI_CONFIG_OVERLAY"] = "overlay.yaml"

config = EngineConfiguration.load_configuration()
print(config.api.host, config.api.port)
```

### Load from in-memory YAML (no caching)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

yaml_text = """
api: {}
services: {}
global_config:
  ai_mode: "local"
modules: []
"""
config = EngineConfiguration.load_configuration(configuration_yaml=yaml_text)
print([m.module for m in config.modules if m.module])
```

## Caveats
- Missing secrets during the second pass:
  - raise `ValueError` in non-interactive environments (no TTY),
  - otherwise trigger an interactive prompt and are written into the configured secret service.
- `load_configuration()` caches file-based loads process-wide; use `reset_configuration_cache()` in tests to avoid cross-test contamination.
- In NATS mode, cache tier configuration cannot mix `"nats_rpc"` adapters with local cache adapters in the same process.
