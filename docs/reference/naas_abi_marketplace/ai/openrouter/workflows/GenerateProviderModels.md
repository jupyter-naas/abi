# GenerateProviderModels

## What it is
A script that generates:
- Provider module `__init__.py` files under `naas_abi_marketplace/ai/<provider>/` from a template.
- OpenRouter model Python files under `naas_abi_marketplace/ai/openrouter/models/<provider>/` from provider `models.json` data and a template.

It uses a minimal placeholder renderer with `{{variable_name}}` (only `\w+`), intentionally leaving constructs like `{{ secret.X }}` untouched.

## Public API
### Functions
- `generate_provider_modules(ai_dir: Path = _AI_DIR, templates_dir: Path = _TEMPLATES_DIR) -> int`
  - Renders `templates/module_init.py.template` once per provider in `PROVIDERS`.
  - Writes `ai/<module_name>/__init__.py`.
  - Returns number of files written.

- `generate_provider_models(storage_dir: Path = _STORAGE_DIR, models_dir: Path = _MODELS_DIR, templates_dir: Path = _TEMPLATES_DIR) -> int`
  - For providers with both `storage_key` and `models_subdir`, loads `<storage_dir>/<storage_key>/models.json`.
  - Renders `templates/model.py.template` once per model entry.
  - Writes `openrouter/models/<models_subdir>/<sanitized_model_id>.py`.
  - Ensures `openrouter/models/<models_subdir>/__init__.py` exists.
  - Returns number of model files written.
  - Logs skips to `stderr` if `models.json` is missing.

### CLI helpers (internal)
- `_parser() -> argparse.ArgumentParser`
  - Defines CLI arguments used when running as a script.

## Configuration/Dependencies
- **Templates directory**: `<this_file_dir>/templates`
  - `module_init.py.template`
  - `model.py.template`
- **Default paths (auto-resolved except storage)**:
  - `ai_dir`: `.../naas_abi_marketplace/ai/` (derived from file location)
  - `models_dir`: `.../naas_abi_marketplace/ai/openrouter/models/` (derived)
  - `storage_dir` default is hardcoded: `/home/florentlvr/axi-ai/storage/datastore/openrouter/models`
- **Input data**:
  - `models.json` per provider at: `<storage_dir>/<storage_key>/models.json`
- **Provider list**: `PROVIDERS` constant controls which modules/models are generated.
- **Canonical mapping**: `CANONICAL_MAP` maps short model IDs to enum member names used in generated templates via `CanonicalModelId.<MEMBER>`; unknown IDs are rendered as a string literal.

## Usage
### Run as a script
```bash
python libs/naas-abi-marketplace/naas_abi_marketplace/ai/openrouter/workflows/GenerateProviderModels.py
```

### Common options
```bash
python libs/naas-abi-marketplace/naas_abi_marketplace/ai/openrouter/workflows/GenerateProviderModels.py \
  --storage-dir /path/to/datastore/openrouter/models \
  --only-models
```

### Programmatic usage
```python
from pathlib import Path
from naas_abi_marketplace.ai.openrouter.workflows.GenerateProviderModels import (
    generate_provider_modules,
    generate_provider_models,
)

generate_provider_modules(ai_dir=Path("libs/naas-abi-marketplace/naas_abi_marketplace/ai"))
generate_provider_models(
    storage_dir=Path("/path/to/datastore/openrouter/models"),
    models_dir=Path("libs/naas-abi-marketplace/naas_abi_marketplace/ai/openrouter/models"),
)
```

## Caveats
- Providers with `storage_key` or `models_subdir` set to `None` will **not** generate model files.
- If `<storage_dir>/<storage_key>/models.json` is missing, that provider is skipped and a message is printed to `stderr`.
- The template renderer only replaces `{{word}}` placeholders (`\w+`); more complex placeholders are left unchanged by design.
- Model filenames are derived by lowercasing and replacing non-`[a-z0-9]` with `_`, collapsing repeats; name collisions are possible if different model IDs sanitize to the same filename.
