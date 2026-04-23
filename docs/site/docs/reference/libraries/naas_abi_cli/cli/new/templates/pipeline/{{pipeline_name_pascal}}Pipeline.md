# `{{pipeline_name_pascal}}Pipeline`

## What it is
- A template pipeline module defining a `Pipeline` subclass (`{{pipeline_name_pascal}}Pipeline`) plus associated configuration and parameters classes.
- Intended to be extended by implementing `run()`; current template returns no result (`pass`).

## Public API
- `@dataclass {{pipeline_name_pascal}}PipelineConfiguration(PipelineConfiguration)`
  - Purpose: Holds pipeline configuration (currently empty template).

- `class {{pipeline_name_pascal}}PipelineParameters(PipelineParameters)`
  - Purpose: Defines the input schema for the pipeline (currently empty template; example field commented out).

- `class {{pipeline_name_pascal}}Pipeline(Pipeline[{{pipeline_name_pascal}}PipelineParameters])`
  - `__init__(configuration: {{pipeline_name_pascal}}PipelineConfiguration)`
    - Purpose: Initialize the pipeline with a configuration object.
  - `run(parameters: {{pipeline_name_pascal}}PipelineParameters) -> rdflib.Graph`
    - Purpose: Execute pipeline logic and return an RDFLib `Graph`.
    - Status: Not implemented in template (`pass`).
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Purpose: Expose the pipeline as a LangChain `StructuredTool`.
    - Tool details:
      - `name`: `"{{pipeline_name_pascal}}"`
      - `func`: Calls `self.run({{pipeline_name_pascal}}PipelineParameters(**kwargs))`
      - `args_schema`: `{{pipeline_name_pascal}}PipelineParameters`
  - `as_api(router: naas_abi_core.utils.Expose.APIRouter, ...) -> None`
    - Purpose: Placeholder for exposing the pipeline via an API router.
    - Status: No routes are registered; returns `None`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.pipeline`: `Pipeline`, `PipelineConfiguration`, `PipelineParameters`
  - `langchain_core.tools`: `BaseTool`, `StructuredTool` (used by `as_tools`)
  - `rdflib`: `Graph` and related RDF terms (only `Graph` is used in the template signature)
  - `pydantic.Field`, `typing.Annotated` (intended for parameter definitions; currently unused)

## Usage
Minimal usage requires implementing `run()` first.

```python
from rdflib import Graph
from naas_abi_core.pipeline import PipelineConfiguration

# Import the generated classes from your module path
# from your_module import (
#     {{pipeline_name_pascal}}Pipeline,
#     {{pipeline_name_pascal}}PipelineConfiguration,
#     {{pipeline_name_pascal}}PipelineParameters,
# )

class MyConfig({{pipeline_name_pascal}}PipelineConfiguration):
    pass

class MyPipeline({{pipeline_name_pascal}}Pipeline):
    def run(self, parameters: {{pipeline_name_pascal}}PipelineParameters) -> Graph:
        return Graph()

pipeline = MyPipeline(MyConfig())
g = pipeline.run({{pipeline_name_pascal}}PipelineParameters())
print(type(g))
```

Using as a LangChain tool:

```python
tools = pipeline.as_tools()
result = tools[0].invoke({})  # kwargs must match {{pipeline_name_pascal}}PipelineParameters
```

## Caveats
- `run()` is not implemented in the template; calling it as-is will return `None` despite the `Graph` return type annotation.
- `as_api()` is a stub and does not register any endpoints.
