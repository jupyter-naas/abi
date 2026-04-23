# ModuleOrchestrationLoader

## What it is
- A utility loader that discovers and imports `Orchestrations` subclasses located in an `orchestrations/` package next to a given module’s root.
- Intended to dynamically register orchestration classes for a module based on filesystem contents.

## Public API
- `class ModuleOrchestrationLoader`
  - `@classmethod load_orchestrations(class_: type) -> List[type[Orchestrations]]`
    - Scans `<module_root>/orchestrations` for Python files (excluding `*test.py`), imports them, and returns a list of classes that:
      - are subclasses of `naas_abi_core.orchestrations.Orchestrations.Orchestrations`
      - belong to the same top-level package as `class_`
      - define a `New` attribute (expected to be a method)

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.module.ModuleUtils.find_class_module_root_path` to locate the module root directory for `class_`
  - `naas_abi_core.orchestrations.Orchestrations.Orchestrations` as the base class filter
  - `naas_abi_core.utils.Logger.logger` for debug/error logging
- Filesystem conventions:
  - Orchestrations must live in a folder named `orchestrations` under the module root.
  - Each orchestration module must be importable as:  
    `f"{class_.__module__}.orchestrations.<filename_without_py>"`

## Usage
Minimal example (assuming your package layout includes `my_pkg/orchestrations/*.py`):

```python
from naas_abi_core.module.ModuleOrchestrationLoader import ModuleOrchestrationLoader

# Any class defined under your module/package
from my_pkg.some_module import SomeClass

orchestration_classes = ModuleOrchestrationLoader.load_orchestrations(SomeClass)

for orch_cls in orchestration_classes:
    # The loader requires a `New` attribute to exist on each class
    orch = orch_cls.New()
```

## Caveats
- Only `.py` files are loaded; files ending with `test.py` are skipped.
- Only classes whose top-level package matches `class_.__module__.split(".")[0]` are included.
- Classes missing a `New` attribute are skipped and an error is logged.
- If `orchestrations/` does not exist, an empty list is returned.
