# `new_pipeline`

## What it is
- Implements the `naas-abi-cli new pipeline` command.
- Scaffolds a pipeline from a bundled template into a target path, for the kind of module it runs in: a `naas_abi_core` pipeline in an in-engine module, a `naas_abi_sdk` one in a remote module.

## Public API
- `new_pipeline(pipeline_name: str, pipeline_path: str = ".", extra_values: dict | None = None, remote: bool = False)`
  - Converts `pipeline_name` to PascalCase.
  - Resolves `pipeline_path` (`"."` becomes `os.getcwd()`) and creates the directory if it does not exist.
  - With `remote=True`, makes the folder a package (`ensure_package`): the scaffold's test imports the class relatively, and the module imports it by its dotted name.
  - Copies the templates, chosen by `remote`:
    - `remote=False` → `cli/new/templates/pipeline`
    - `remote=True` → `cli/new/templates/remote_pipeline` (imports `naas_abi_sdk` only, with a `<Name>Pipeline_test.py` beside it)
  - Template values: `pipeline_name_pascal`, `pipeline_name_snake` and `pipeline_name_upper`, merged with `extra_values` (dict union `|`).

- Click command: `naas-abi-cli new pipeline PIPELINE_NAME [PIPELINE_NAME_PATH]`
  - `_new_pipeline` detects the target with `is_remote_module(target_dir(pipeline_path))` and calls `new_pipeline(..., remote=remote)`.
  - In a remote module it prints what to do next: the module builds the pipeline after `on_initialized` under its snake-case class name, other modules start it as the durable workflow `pipeline.<name>`, and an agent needs `await self.build_processes()` before `self.get_pipeline_instance(name).as_tools()`; it needs the `naas-abi-sdk[workflows,rdf]` extras.
  - It does not refuse in a remote module (only `abi new orchestration` does).

## Configuration/Dependencies
- **Python packages**
  - `click` (CLI command wiring)
  - `naas_abi_cli` (used to locate installed template files)
- **Internal utilities**
  - `Copier` from `naas_abi_cli.cli.utils.Copier` (copy/render step)
  - `to_pascal_case`, `to_snake_case` from `.utils`
  - `ensure_package`, `is_remote_module`, `target_dir` from `.remote_module`

## Usage

### CLI
```bash
naas-abi-cli new pipeline MyPipeline .
```

### Python
```python
from naas_abi_cli.cli.new.pipeline import new_pipeline

new_pipeline("my_pipeline", "./out")                 # naas_abi_core
new_pipeline("my_pipeline", "./out", remote=True)    # naas_abi_sdk
```

## Caveats
- If `pipeline_path == "."`, it is replaced with `os.getcwd()`.
- `pipeline_name` is converted to PascalCase; the template receives it under `pipeline_name_pascal`.
- The remote scaffold's `run` is `async` and returns an rdflib `Graph`; other modules call the pipeline over NATS and it can declare `job = JobSettings(...)`.
