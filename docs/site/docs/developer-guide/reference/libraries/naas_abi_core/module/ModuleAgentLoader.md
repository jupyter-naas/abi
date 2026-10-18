# ModuleAgentLoader

## What it is
- Discovers and imports “agent” classes from an `agents/` directory under a given class’s module root.
- Collects classes that subclass `naas_abi_core.utils.Expose.Expose` and belong to the same top-level package as the input class.

## Public API
- `class ModuleAgentLoader`
  - `@classmethod load_agents(class_: type) -> list[type[Expose]]`
    - Resolves the module root directory for `class_`.
    - Looks for `<module_root>/agents`.
    - For each `*.py` file in `agents/` (excluding files ending with `test.py`):
      - Imports `<module_package(class_)>.agents.<module_name>`.
      - Scans module globals and collects values that:
        - are classes (`isinstance(value, type)`),
        - subclass `Expose`,
        - have the same top-level package as `class_` (`__module__.split(".")[0]`).
      - If the agent module defines `create_agent`, attempts to attach it as `New` on each discovered agent class (see caveats).
    - Returns a list of discovered agent classes.

## Configuration/Dependencies
- Expected filesystem layout:
  - `find_class_module_root_path(class_) / "agents"` must exist to load agents.
- Imports/Dependencies:
  - `naas_abi_core.module.ModuleUtils.find_class_module_root_path`
  - `naas_abi_core.module.ModuleUtils.module_package`
  - `naas_abi_core.utils.Expose.Expose`
  - `naas_abi_core.utils.Logger.logger`
  - Standard library: `importlib`, `os`

## Usage
```python
from naas_abi_core.module.ModuleAgentLoader import ModuleAgentLoader
from mypkg.some_module import SomeClass

agents = ModuleAgentLoader.load_agents(SomeClass)
for agent_cls in agents:
    print(agent_cls.__name__)
```

Example package layout:
```
mypkg/
  some_module.py          # defines SomeClass
  agents/
    agent_a.py            # defines class AgentA(Expose)
    agent_b.py            # defines class AgentB(Expose)
```

## Caveats
- Only direct `.py` files in `agents/` are considered; files ending with `test.py` are skipped.
- Agents are filtered to the same *top-level* package as `class_` (based on `__module__.split(".")[0]`).
- The `New` attachment guard uses `hasattr(key, "New")` where `key` is a string; this does not actually check whether the class already has `New` and may behave unexpectedly.
