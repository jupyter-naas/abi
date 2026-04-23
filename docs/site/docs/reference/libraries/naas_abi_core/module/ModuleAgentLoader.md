# ModuleAgentLoader

## What it is
- Utility loader that discovers and imports “agent” classes from an `agents/` package located next to a given class’s module root.
- Returns agent classes that subclass `naas_abi_core.utils.Expose.Expose`.

## Public API
- `class ModuleAgentLoader`
  - `@classmethod load_agents(class_: type) -> List[type[Expose]]`
    - Scans `<module_root>/agents/*.py` (excluding `*test.py`), imports each module, and collects classes that:
      - are `type` objects,
      - are subclasses of `Expose`,
      - belong to the same top-level package as `class_` (same first segment of `__module__`).
    - If an agent module defines `create_agent`, it is attached to each discovered agent class as `New` (via `setattr`) when the (incorrectly implemented) guard passes.

## Configuration/Dependencies
- Filesystem structure:
  - Requires an `agents/` directory under the module root returned by `find_class_module_root_path(class_)`.
- Dependencies:
  - `naas_abi_core.module.ModuleUtils.find_class_module_root_path`
  - `naas_abi_core.utils.Expose.Expose`
  - `naas_abi_core.utils.Logger.logger`
  - Standard library: `importlib`, `os`

## Usage
```python
from naas_abi_core.module.ModuleAgentLoader import ModuleAgentLoader

# Any class within your package/module tree
from mypkg.some_module import SomeClass

agents = ModuleAgentLoader.load_agents(SomeClass)

for AgentCls in agents:
    print(AgentCls.__name__, AgentCls)
```

Expected package layout (example):
```
mypkg/
  some_module.py          # defines SomeClass
  agents/
    agent_a.py            # defines class AgentA(Expose)
    agent_b.py            # defines class AgentB(Expose)
```

## Caveats
- Only `.py` files in `agents/` are considered; files ending with `test.py` are skipped.
- Imported agents are filtered to the same top-level package as `class_` (based on `__module__.split(".")[0]`).
- The guard `if not hasattr(key, "New") ...` checks the *string name* (`key`), not the class; as written it is effectively always true for `"New"` and does not correctly detect whether the class already has `New`.
