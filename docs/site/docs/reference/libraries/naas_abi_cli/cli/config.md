# `config` (naas_abi_cli.cli.config)

## What it is
A `click` command group providing CLI utilities to validate and render an `EngineConfiguration` from an optional configuration file.

## Public API
- **`config`** (`click` group): Top-level CLI group named `config`.
  - **`validate --configuration-file <path>`**: Loads configuration (from file if provided) via `EngineConfiguration.load_configuration()` and prints `Configuration is valid` if no exception is raised.
  - **`render --configuration-file <path>`**: Loads configuration (from file if provided), then prints a YAML dump of `configuration.model_dump()`.

## Configuration/Dependencies
- **Filesystem**: Optional `--configuration-file` path must exist; otherwise raises `FileNotFoundError`.
- **Dependencies**:
  - `click` for CLI parsing/commands.
  - `yaml` (PyYAML) for rendering output in `render`.
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration.EngineConfiguration` for loading and dumping configuration.

## Usage
Minimal example of registering and invoking these commands via `click`:

```python
import click
from naas_abi_cli.cli.config import config

@click.group()
def cli():
    pass

cli.add_command(config)

if __name__ == "__main__":
    cli()
```

Example CLI runs:

```bash
python app.py config validate --configuration-file ./config.yaml
python app.py config render --configuration-file ./config.yaml
```

## Caveats
- Validation/rendering behavior depends on `EngineConfiguration.load_configuration()`. Any parsing/validation errors are surfaced as exceptions from that loader.
- `render` outputs YAML using `yaml.dump(configuration.model_dump(), indent=2)`; key ordering/formatting is governed by PyYAML defaults.
