# EngineConfiguration

## What it is
- Pydantic-based configuration loader for the ABI engine.
- Loads YAML configuration files, supports Jinja2 templating, and resolves secrets via:
  - Environment variables
  - A bootstrap `.env` secret adapter (for first-pass loading)
  - The configured secret service (with optional interactive prompting)

## Public API

### Classes

- `ServicesConfiguration`
  - Holds service configurations and **provides defaults** for:
    - object storage, triple store, vector store, secret service, bus, key-value, email, cache.

- `ApiConfiguration`
  - API/UI metadata and runtime settings:
    - title, description, logo/favicon paths, CORS origins, reload flag.

- `OpencodeProviderConfiguration`
  - Provider record: `id`, `key`, `type="api"`, `metadata`.

- `OpencodeConfiguration`
  - Opencode auth file path and providers list.

- `FirstPassConfiguration`
  - Minimal configuration used to load the secret service first.
  - Contains nested `FirstPassServicesConfiguration(secret: SecretServiceConfiguration)`.

- `ModuleConfig`
  - Module loading configuration:
    - `path` or `module` (one must be provided), `enabled`, `config` dict.
  - Validator enforces: **either** `path` **or** `module` is required.

- `GlobalConfig`
  - Global engine flags:
    - `ai_mode`: `"cloud" | "local" | "airgap"`
    - `skip_ontology_loading`: bool

- `EngineConfiguration`
  - Top-level configuration model containing:
    - `api`, `deploy`, `services`, `global_config`, `modules`, `default_agent`, `opencode`.

### `EngineConfiguration` methods

- `ensure_default_modules() -> None`
  - Ensures these modules are present in `modules` (added if missing, enabled=True):
    - `naas_abi_core.modules.templatablesparqlquery`
    - `naas_abi_core.modules.bfo`
    - `naas_abi_core.modules.cco`

- `from_yaml(yaml_path: str) -> EngineConfiguration`
  - Loads and parses a YAML file.

- `from_yaml_content(yaml_content: str) -> EngineConfiguration`
  - Loads configuration from a YAML string.
  - Two-pass process:
    - Pass 1: resolve enough secrets to load the secret service.
    - Pass 2: re-render YAML template with full secret service available, then parse.

- `load_configuration(configuration_yaml: str | None = None) -> EngineConfiguration`
  - Main entry point:
    - If `configuration_yaml` is provided: parse it directly (useful for tests).
    - Otherwise:
      - Determine config file:
        - If `ENV` is set and `config.{ENV}.yaml` exists, use it.
        - Else use `config.yaml` if it exists.
        - Else raise `FileNotFoundError`.
      - Special case: if `ENV` is not set, but `config.yaml` exists and contains a dotenv secret adapter, it will attempt to read `ENV` from that `.env`.

## Configuration/Dependencies

### YAML templating
- YAML is rendered using Jinja2 with a `secret` object available:
  - Example usage in YAML: `{{ secret.SOME_KEY }}`

### Secret resolution order
- During *first pass* (before secret service is loaded):
  1. Environment variables
  2. Bootstrap dotenv adapter (if configured in YAML under `services.secret.secret_adapters` with `adapter: dotenv`)
  3. If still missing, a placeholder string is rendered into the template.

- During *second pass* (after secret service is loaded):
  1. Environment variables
  2. Configured secret service
  3. If missing and TTY is available: prompt the user and store it in the secret service
  4. If missing and **no TTY**: raises `ValueError`

### Bootstrap dotenv adapter detection
- `_load_bootstrap_dotenv_adapter_from_yaml_content()` scans the YAML for:
  - `services.secret.secret_adapters:`
    - `- adapter: dotenv`
      - `config.path` (defaults to `.env`)
- If `config.path` is present but empty/invalid, it raises `ValueError`.

### External dependencies used
- `pydantic` (models and validation)
- `yaml` (PyYAML)
- `jinja2` (templating)
- `rich` (interactive prompting)
- Various `naas_abi_core.engine.engine_configuration.*` configuration classes
- `naas_abi_core.services.secret.Secret` and `ISecretAdapter`

## Usage

### Load from default config files (`config.yaml` or `config.{ENV}.yaml`)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

config = EngineConfiguration.load_configuration()
print(config.api.title)
```

### Load from an in-memory YAML string (useful for tests)
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration import EngineConfiguration

yaml_text = """
api:
  title: "ABI API"
  description: "API for ABI"
  logo_path: "assets/logo.png"
  favicon_path: "assets/favicon.ico"
  cors_origins: ["http://localhost:9879"]
  reload: true
services:
  secret:
    secret_adapters:
      - adapter: dotenv
        config:
          path: ".env"
global_config:
  ai_mode: "local"
  skip_ontology_loading: false
modules:
  - module: "naas_abi_core.modules.templatablesparqlquery"
    enabled: true
    config: {}
"""
config = EngineConfiguration.load_configuration(configuration_yaml=yaml_text)
print([m.module for m in config.modules])
```

## Caveats
- `modules` will be automatically augmented to include default modules if missing.
- If a referenced secret is missing:
  - In non-interactive environments (no TTY) it may raise `ValueError` during loading.
- A bootstrap dotenv adapter is only used if explicitly configured under `services.secret.secret_adapters` with `adapter: dotenv`.
