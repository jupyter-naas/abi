# `Workflow`

## What it is
- A small base module defining a **workflow pattern**:
  - `WorkflowConfiguration`: configuration container (currently empty).
  - `WorkflowParameters`: Pydantic model for runtime inputs (currently empty).
  - `Workflow[P]`: generic workflow base class intended to be **exposed via multiple interfaces** (inherits `Expose`) and run via `run(...)` (currently a stub).

## Public API
- **`WorkflowConfiguration`** (`@dataclass`)
  - Purpose: placeholder type for workflow configuration data.

- **`WorkflowParameters`** (`pydantic.BaseModel`)
  - Purpose: base class for workflow parameter models.

- **`Workflow[P]`** (`Expose`, `Generic[P]`)
  - **`__init__(configuration: WorkflowConfiguration)`**
    - Stores workflow configuration.
  - **`run(parameters: P)`**
    - Intended to execute the workflow using typed parameters.
    - Currently unimplemented (`pass`).

## Configuration/Dependencies
- Dependencies:
  - `pydantic.BaseModel`
  - `dataclasses.dataclass`
  - `typing.Generic`, `typing.TypeVar`
  - `naas_abi_core.utils.Expose.Expose` (base class; behavior not shown in this file)
- Configuration type:
  - `WorkflowConfiguration` is required by `Workflow.__init__`, but currently has no fields.

## Usage
```python
from dataclasses import dataclass
from pydantic import BaseModel

from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration, WorkflowParameters

@dataclass
class MyConfig(WorkflowConfiguration):
    name: str

class MyParams(WorkflowParameters):
    x: int

class MyWorkflow(Workflow[MyParams]):
    def run(self, parameters: MyParams):
        return f"{self._Workflow__configuration.name}: {parameters.x}"

wf = MyWorkflow(MyConfig(name="demo"))
print(wf.run(MyParams(x=1)))
```

## Caveats
- `Workflow.run()` is a stub in the base class; subclasses must implement it.
- `__configuration` is a private (name-mangled) attribute (`_Workflow__configuration`) and is not directly accessible as `self.__configuration` from subclasses.
