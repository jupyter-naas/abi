# EngineConfiguration

## What it is
- A Pydantic-based configuration loader for the ABI engine.
- Loads YAML configuration, renders it with Jinja2, and resolves `{{ secret.* }}` placeholders via:
  - environment variables,
  - an optional bootstrap `.env` secret adapter (dotenv),
  - and the configured secret service (with interactive prompting if needed and available).

## Public API

### Classes (models)
- `ServicesConfiguration`
  - Aggregates service configurations with defaults for:
    - object storage (default: filesystem)
    - triple store (default: filesystem)
    - vector store (default: `qdrant_in_memory`)
    - secret service (default: dotenv adapter)
    - bus (default: `python_queue`)
    - key-value store (default: `python`)
- `ApiConfiguration`
  - API metadata and runtime flags (e.g., CORS origins, reload).
- `FirstPassConfiguration`
  - Minimal config used to load the secret service before rendering the full YAML template.
- `ModuleConfig`
  - Module entry with validation:
    - requires either `path` or `module`
    - `enabled` flag and free-form `config` dict
- `GlobalConfig`
  - Global mode flag: `ai_mode` ∈ `{ "cloud", "local", "airgap" }`
- `EngineConfiguration`
  - Top-level configuration model containing:
    - `api: ApiConfiguration`
    - `deploy: DeployConfiguration | None`
    - `services: ServicesConfiguration`
    - `global_config: GlobalConfig`
    - `modules: List[ModuleConfig]`
    - `default_agent: str` (default: `"naas_abi AbiAgent"`)

### EngineConfiguration methods
- `ensure_default_modules() -> None`
  - Ensures module `naas_abi_core.modules.templatablesparqlquery` is present in `modules` (by `path` or `module`), otherwise appends it enabled.
- `from_yaml(yaml_path: str) -> EngineConfiguration`
  - Reads a YAML file and delegates to `from_yaml_content`.
- `from_yaml_content(yaml_content: str) -> EngineConfiguration`
  - Two-pass load:
    1. Render YAML using a bootstrap secret resolver to load the configured secret service.
    2. Render again using the loaded secret service, then parse into `EngineConfiguration`.
- `load_configuration(configuration_yaml: str | None = None) -> EngineConfiguration`
  - Loads configuration from:
    - the provided YAML string (testing),
    - or `config.{ENV}.yaml` if `ENV` is set and file exists,
    - else `config.yaml`.
  - If `ENV` is not set, it may be obtained from a bootstrap dotenv adapter declared in `config.yaml`.

## Configuration/Dependencies
- **YAML parsing**: `yaml.safe_load`
- **Templating**: `jinja2.Template`
  - YAML content is treated as a Jinja2 template.
  - A `secret` object is injected; you can reference secrets like `{{ secret.MY_KEY }}`.
- **Secret resolution order**
  - During *first pass* (before secret service exists):
    1. `os.environ`
    2. bootstrap dotenv adapter (if declared in YAML)
    3. fallback string message (no prompt)
  - During *second pass* (secret service loaded):
    1. `os.environ`
    2. `secret_service.get(name)`
    3. if missing:
       - prompt on TTY and persist via `secret_service.set(name, value)`
       - raise `ValueError` if no TTY available
- **Bootstrap dotenv adapter detection**
  - Looks for: `services.secret.secret_adapters[]` entry with `adapter: "dotenv"`
  - Reads optional `config.path` (default `.env`); must be a non-empty string.

## Usage

### Load from standard files (`config.yaml` or `config.{ENV}.yaml`)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

config = EngineConfiguration.load_configuration()
print(config.api.title)
print([m.module or m.path for m in config.modules])
```

### Load from an in-memory YAML string (useful for tests)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

yaml_content = """
api:
  title: "ABI API"
  description: "API"
  logo_path: "assets/logo.png"
  favicon_path: "assets/favicon.ico"
  cors_origins: ["http://localhost:9879"]
  reload: true

global_config:
  ai_mode: "local"

services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config: { path: ".env" }

modules:
  - module: "some.module"
    enabled: true
    config: {}
"""

config = EngineConfiguration.load_configuration(configuration_yaml=yaml_content)
print(config.global_config.ai_mode)
```

## Caveats
- YAML is rendered as a Jinja2 template; invalid template expressions will fail during rendering/parsing.
- If a referenced secret is missing:
  - and the process has **no TTY**, loading can raise `ValueError` (second pass).
- `ModuleConfig` requires **either** `path` **or** `module`; providing neither raises `ValueError`.
- `EngineConfiguration` automatically appends the default module `naas_abi_core.modules.templatablesparqlquery` if not present.
