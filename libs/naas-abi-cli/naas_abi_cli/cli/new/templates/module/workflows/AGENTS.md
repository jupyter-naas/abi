# `workflows/` — AGENTS.md

> Scope: workflows for the `{{module_name_snake}}` module. See the module's [AGENTS.md](../AGENTS.md) for module-wide context.

## What goes here

Multi-step automations that combine one or more **integrations** to produce a typed result. Workflows are the **agent-callable** unit of work — they expose `as_tools()` so an agent can pick one up via tool calling.

Workflows differ from **pipelines** in intent:
- **Workflow** — orchestrates *integrations and agents*; returns dicts/objects callers consume directly.
- **Pipeline** — produces an *RDF Graph*; downstream agents/services reason over the triples.

If you're not generating RDF, you almost certainly want a workflow.

## File shape

Files are `PascalCase`, one workflow per file: `<Name>Workflow.py`.

```python
from dataclasses import dataclass
from typing import Annotated
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field

@dataclass
class <Name>WorkflowConfiguration(WorkflowConfiguration):
    """Configuration for <Name>Workflow."""
    # injected at module load — e.g. integrations, services
    pass

class <Name>WorkflowParameters(WorkflowParameters):
    """Run-time inputs for <Name>Workflow."""
    target: Annotated[str, Field(..., description="What to act on")]

class <Name>Workflow(Workflow[<Name>WorkflowParameters]):
    """One-line description (becomes the tool docstring)."""

    __configuration: <Name>WorkflowConfiguration

    def __init__(self, configuration: <Name>WorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: <Name>WorkflowParameters) -> dict | list[dict]:
        ...  # call integrations, return typed result

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                func=self.run,
                name="<Name>",
                description="...",
                args_schema=<Name>WorkflowParameters,
            )
        ]
```

## Conventions

- **Three classes per file**: `<Name>WorkflowConfiguration`, `<Name>WorkflowParameters`, `<Name>Workflow`.
- **`run(parameters)`** is the single entry point. Return JSON-serialisable values.
- **`as_tools()`** is what agents consume — keep the tool `name` short and the `description` action-oriented (the LLM picks tools by these).
- **`WorkflowParameters` uses Pydantic `Field`** with `description=` and `example=` — these surface to the LLM during tool selection.
- **Inject dependencies via Configuration**, not via module-level singletons.

## Scaffold a new workflow

```bash
abi new workflow <name> .
```

This drops `<Name>Workflow.py` with the canonical 3-class skeleton.

## Tests

Colocated as `<Name>Workflow_test.py`. Drive `.run(...)` with a parameter instance:

```python
def test_run():
    wf = <Name>Workflow(<Name>WorkflowConfiguration(...))
    result = wf.run(<Name>WorkflowParameters(target="foo"))
    assert result == {...}
```

Run:

```bash
uv run pytest {{module_name_snake}}/workflows
uv run pytest {{module_name_snake}}/workflows/<Name>Workflow_test.py -v
```

## Wiring into the module

- **Expose to an agent**: in `../agents/<Name>Agent.py`, instantiate the workflow and add `workflow.as_tools()` to the agent's `tools=[]`.
- **Expose over HTTP**: workflows have access to `APIRouter` (`from naas_abi_core.utils.Expose import APIRouter`) — wire routes inside the module's `api(app)` hook.
- **Schedule a recurring run**: wrap it in an `../orchestrations/<Name>Orchestration.py` Dagster job.

## See also

- Reference scaffold: [`.abi/libs/naas-abi-marketplace/.../__demo__/workflows/ExecutePythonCodeWorkflow.py`](../../../.abi/libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/workflows/ExecutePythonCodeWorkflow.py)
- Per-domain workflow examples: [`.abi/libs/naas-abi-marketplace/.../domains/software-engineer/workflows/`](../../../.abi/libs/naas-abi-marketplace/naas_abi_marketplace/domains/software-engineer/workflows)
