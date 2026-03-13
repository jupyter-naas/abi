# ModuleOrchestrationLoader

## What it is
- A utility loader that discovers and imports orchestration classes (subclasses of `naas_abi_core.orchestrations.Orchestrations`) from a module’s `orchestrations/` directory.

## Public API
- `class ModuleOrchestrationLoader`
  - `@classmethod load_orchestrations(class_: type) -> List[type[Orchestrations]]`
    - Scans `<module_root>/orchestrations` for Python files (excluding `*test.py`), imports them, and returns orchestration classes that:
      - are subclasses of `Orchestrations`,
      - belong to the same top-level package as `class_`,
      - define a `New` attribute (expected to be a method).

## Configuration/Dependencies
- Filesystem/layout expectations:
  - The target module must have an `orchestrations/` folder at the module root returned by `find_class_module_root_path(class_)`.
  - Orchestration classes must be defined in `*.py` files within that folder.
- Imports used:
  - `importlib`, `os`
  - `naas_abi_core.module.ModuleUtils.find_class_module_root_path`
  - `naas_abi_core.orchestrations.Orchestrations.Orchestrations`
  - `naas_abi_core.utils.Logger.logger` (debug/error logging)

## Usage
```python
from naas_abi_core.module.ModuleOrchestrationLoader import ModuleOrchestrationLoader

# Any class located in the target package; used to locate the package root and module name.
from my_package.some_module import SomeClass

orchestrations = ModuleOrchestrationLoader.load_orchestrations(SomeClass)

for orch_cls in orchestrations:
    print(orch_cls.__name__)
```

## Caveats
- Only `.py` files are considered; files ending with `test.py` are skipped.
- A candidate orchestration class is ignored (with an error log) if it does not define a `New` attribute.
- Classes are filtered to the same *top-level package* as `class_` (`value.__module__.split(".")[0]` must match).
