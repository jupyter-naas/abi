# `naas_abi.cli`

## What it is
A small interactive CLI module that scaffolds ABI modules and components by copying from `src/core/__templates__`, performing string substitutions, and (for modules) enabling the new module in YAML config.

## Public API
- `format_module_name(name: str) -> str`  
  Normalize a module name to lowercase, underscore-separated, and alphanumeric/underscore only.

- `get_component_selection() -> dict`  
  Interactive prompt to choose which template components to include in a new module. If `agents` is selected, `models` is automatically included.

- `enable_module_in_config(module_path: str) -> None`  
  Attempts to enable a module in a YAML config by adding/updating an entry in `modules: [{path, enabled}]`. Chooses `config.{ENV}.yaml` when possible, otherwise `config.yaml`.

- `create_new_module() -> None`  
  Interactive scaffolding:
  - asks for module name and destination (one of predefined `src/...` roots)
  - copies template base files and selected component directories
  - rewrites references in `.py`, `.md`, `.ttl` files
  - renames files containing `Template`
  - calls `enable_module_in_config(...)`

- `create_agent() -> None`  
  Interactive agent scaffolding:
  - copies `TemplateAgent.py` and `TemplateAgent_test.py` into a target `.../agents` folder
  - adjusts some import strings based on relative path
  - creates/copies a `models/` folder from templates if missing (required for agents)

- `create_component(component_type: str, template_files: list[str], file_suffix: str) -> None`  
  Generic interactive scaffolding for:
  - integrations, workflows, pipelines (Python + pytest file)
  - ontologies (two `.ttl` files)  
  Copies template files, replaces `Template/template` tokens, and rewrites some import strings for Python files.

- `create_integration() -> None`  
  Wrapper for `create_component("integration", ["TemplateIntegration.py", "TemplateIntegration_test.py"], "Integration")`.

- `create_workflow() -> None`  
  Wrapper for `create_component("workflow", ["TemplateWorkflow.py", "TemplateWorkflow_test.py"], "Workflow")`.

- `create_pipeline() -> None`  
  Wrapper for `create_component("pipeline", ["TemplatePipeline.py", "TemplatePipeline_test.py"], "Pipeline")`.

- `create_ontology() -> None`  
  Wrapper for `create_component("ontology", ["TemplateOntology.ttl", "TemplateSparqlQueries.ttl"], "Ontology")`.

- `main() -> None`  
  Dispatches on `sys.argv[1]`:
  - `create-module`, `create-agent`, `create-integration`, `create-workflow`, `create-pipeline`, `create-ontology`

## Configuration/Dependencies
- Runtime dependencies:
  - `rich` (`Console`, `Prompt`) for interactive I/O
  - `PyYAML` (`yaml.safe_load`, `yaml.dump`) for config updates
- Filesystem expectations:
  - Templates are read from `src/core/__templates__/...`
  - Module creation targets one of:
    - `src/core/<module_name>`
    - `src/custom/<module_name>`
    - `src/marketplace/applications/<module_name>`
    - `src/marketplace/domains/<module_name>`
- Config update behavior (`enable_module_in_config`):
  - Uses `ENV` environment variable when set
  - Otherwise may read `config.yaml` and, if configured with a `dotenv` secret adapter, attempts to resolve `ENV` from that `.env` via:
    `naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor.DotenvSecretSecondaryAdaptor`
  - Updates `config.{ENV}.yaml` if resolved and present; falls back to `config.yaml`

## Usage
### Run as a module script (command dispatch)
```python
import sys
from naas_abi import cli

sys.argv = ["naas-abi", "create-module"]
cli.main()
```

### Call a specific interactive scaffolder
```python
from naas_abi.cli import create_integration

create_integration()
```

## Caveats
- This CLI is interactive (uses `Prompt.ask`); it is not suitable for non-interactive automation without additional wrapping/mocking.
- Scaffolding relies on the presence and structure of `src/core/__templates__`. Missing templates will raise filesystem errors during creation.
- Config updates are best-effort; failures are caught and reported to the console (module creation proceeds unless earlier steps fail).
- Name validation differs by scaffold:
  - module names are normalized via `format_module_name` and must match `^[a-z][a-z0-9_\-\.]*$` after formatting
  - component/agent names must match `^[a-zA-Z][a-zA-Z0-9_]*$` (no hyphens/dots)
