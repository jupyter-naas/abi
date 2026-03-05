# `Workflow`

## What it is
A minimal workflow abstraction intended to package business logic that can be exposed through multiple interfaces (e.g., background jobs, AI tools, APIs, direct Python execution). This module defines the base types for workflow configuration and parameters.

## Public API

- `WorkflowConfiguration` (`@dataclass`)
  - Placeholder configuration container for workflows.

- `WorkflowParameters` (`pydantic.BaseModel`)
  - Base model for workflow input parameters (Pydantic-validated).

- `Workflow[P]` (`Expose`, `typing.Generic[P]`)
  - Base workflow class parametrized by a `WorkflowParameters` subtype.
  - **Constructor**
    - `__init__(configuration: WorkflowConfiguration)`
      - Stores the workflow configuration.
  - **Method**
    - `run(parameters: P)`
      - Placeholder method intended to execute the workflow.

## Configuration/Dependencies
- Depends on:
  - `dataclasses.dataclass`
  - `pydantic.BaseModel`
  - `naas_abi_core.utils.Expose.Expose` (base class; behavior not shown here)
- `WorkflowConfiguration` is currently empty and intended to be extended.

## Usage
Minimal subclassing example:

```python
from dataclasses import dataclass
from pydantic import BaseModel

from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration, WorkflowParameters

@dataclass
class MyConfig(WorkflowConfiguration):
    greeting: str = "Hello"

class MyParams(WorkflowParameters):
    name: str

class MyWorkflow(Workflow[MyParams]):
    def run(self, parameters: MyParams):
        return f"{self._Workflow__configuration.greeting}, {parameters.name}!"

wf = MyWorkflow(MyConfig(greeting="Hi"))
print(wf.run(MyParams(name="Ada")))
```

## Caveats
- `Workflow.run()` is unimplemented (`pass`) in the base class; you must override it.
- `Workflow` stores configuration in a name-mangled private attribute (`__configuration`); direct access requires mangled name (`_Workflow__configuration`) unless your subclass adds its own accessor.
