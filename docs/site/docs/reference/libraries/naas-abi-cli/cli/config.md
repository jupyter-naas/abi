# `config` (naas_abi_cli.cli.config)

## What it is
A `click` command group that provides CLI commands to validate and render an engine configuration, optionally loaded from a file.

## Public API
- **Command group:** `config`
  - Container for configuration-related subcommands.

- **Command:** `config validate`
  - **Options:**
    - `--configuration-file TEXT` (optional)
  - **Purpose:** Loads configuration content (from file if provided) via `EngineConfiguration.load_configuration(...)` and prints `Configuration is valid` if no exception is raised.

- **Command:** `config render`
  - **Options:**
    - `--configuration-file TEXT` (optional)
  - **Purpose:** Loads configuration via `EngineConfiguration.load_configuration(...)`, then prints a YAML dump of `configuration.model_dump()`.

## Configuration/Dependencies
- **Reads from filesystem** when `--configuration-file` is provided.
- **Depends on:**
  - `click` for CLI definitions.
  - `yaml` (PyYAML) for rendering YAML output.
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration.EngineConfiguration`
    - Uses `EngineConfiguration.load_configuration(configuration_content)`.
    - Uses `EngineConfiguration.model_dump()` (implies a Pydantic-like model).

## Usage
Minimal CLI usage (exact entrypoint depends on how your CLI is wired):

```bash
# Validate default/implicit configuration (passes None to load_configuration)
python -m naas_abi_cli.cli.config validate

# Validate configuration from a file
python -m naas_abi_cli.cli.config validate --configuration-file path/to/config.yml

# Render configuration as YAML
python -m naas_abi_cli.cli.config render --configuration-file path/to/config.yml
```

## Caveats
- If `--configuration-file` is provided and the path does not exist, a `FileNotFoundError` is raised.
- Validation/rendering success depends on `EngineConfiguration.load_configuration(...)`; any exceptions it raises will propagate.
