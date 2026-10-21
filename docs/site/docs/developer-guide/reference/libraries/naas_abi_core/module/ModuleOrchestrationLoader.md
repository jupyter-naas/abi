# ModuleOrchestrationLoader

## What it is
- A loader that discovers and imports orchestration classes from an `orchestrations/` folder located at the root of the package containing a given class.
- Returns orchestration classes that subclass `naas_abi_core.orchestrations.Orchestrations.Orchestrations`.

## Public API
- `class ModuleOrchestrationLoader`
  - `@classmethod load_orchestrations(class_: type) -> list[type[Orchestrations]]`
    - Locates `<module_root>/orchestrations`.
    - Imports each `*.py` file in that folder (excluding files ending with `test.py`).
    - Collects classes from those modules that:
      - are `type` objects
      - are subclasses of `Orchestrations`
      - have the same top-level package as `class_` (`value.__module__.split(".")[0] == class_.__module__.split(".")[0]`)
      - define a `New` attribute (otherwise logs an error and skips)
    - If an import fails with `ModuleNotFoundError` tied to a recognized “legacy extra”, the module is skipped and later reported via `logger.info`.
    - Returns the list of collected orchestration classes.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.module.ModuleUtils.find_class_module_root_path` (to find the root path for `class_`)
  - `naas_abi_core.module.ModuleUtils.module_package` (to build the import path)
  - `naas_abi_core.orchestrations.Orchestrations.Orchestrations` (base class filter)
  - `naas_abi_core.utils.LegacyExtras.legacy_extra_of`, `install_hint`, `LEGACY_NOTICE` (for handling missing optional/legacy extras)
  - `naas_abi_core.utils.Logger.logger` (debug/info/error logging)
- Filesystem/import convention:
  - Orchestrations must live under `<module_root>/orchestrations/`.
  - Each file is imported as: `f"{module_package(class_)}.orchestrations.<module_name>"`.

## Usage
```python
from naas_abi_core.module.ModuleOrchestrationLoader import ModuleOrchestrationLoader
from my_pkg.some_module import SomeClass

orch_classes = ModuleOrchestrationLoader.load_orchestrations(SomeClass)

for orch_cls in orch_classes:
    # Loader requires orchestrations to expose a "New" attribute (typically a constructor/factory).
    orch = orch_cls.New()
```

## Caveats
- Only `.py` files are considered; files ending with `test.py` are ignored.
- Only orchestrations from the same top-level package as the provided `class_` are loaded.
- Classes missing a `New` attribute are skipped (an error is logged).
- If `orchestrations/` does not exist, returns an empty list.
- Some orchestration modules may be skipped if they require an uninstalled “legacy extra”; these are reported via an info log rather than raising.
