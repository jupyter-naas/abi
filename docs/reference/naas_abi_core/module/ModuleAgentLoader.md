# ModuleAgentLoader

## What it is
- A small utility for discovering and importing `Agent` subclasses from an `agents/` folder adjacent to a given module/class.
- Returns a list of agent classes found in `*.py` files (excluding files ending in `test.py`).

## Public API
- `class ModuleAgentLoader`
  - `@classmethod load_agents(class_: type) -> List[type[Agent]]`
    - Locates the module root for `class_`, then scans `<module_root>/agents`.
    - Imports each agent module and collects classes that:
      - are Python classes (`isinstance(value, type)`),
      - are subclasses of `naas_abi_core.services.agent.Agent.Agent`,
      - belong to the same top-level package as `class_` (by comparing `__module__.split(".")[0]`).
    - If the agent module defines `create_agent`, it sets a `New` attribute on each discovered agent class to reference `create_agent`.

## Configuration/Dependencies
- Filesystem expectations:
  - An `agents/` directory exists at the module root path returned by `find_class_module_root_path(class_)`.
  - Agent modules are importable as: `"{class_.__module__}.agents.<filename_without_py>"`.
- Dependencies:
  - `naas_abi_core.module.ModuleUtils.find_class_module_root_path`
  - `naas_abi_core.services.agent.Agent.Agent` (base class for agents)
  - `naas_abi_core.utils.Logger.logger` (debug logging)
  - Standard library: `importlib`, `os`

## Usage
```python
from naas_abi_core.module.ModuleAgentLoader import ModuleAgentLoader

# Any class from the target package/module; used to locate <module_root>/agents
from my_package.my_module import SomeClass

agents = ModuleAgentLoader.load_agents(SomeClass)
for agent_cls in agents:
    print(agent_cls.__name__)
    # If the agent module defined create_agent, agent_cls.New will be set.
```

## Caveats
- Only loads from `.py` files in the `agents/` directory; ignores files ending with `test.py`.
- Only agent classes whose top-level package matches `class_` are collected.
- The `New` attribute injection depends on `create_agent` existing in the agent module; no validation of its signature is performed.
