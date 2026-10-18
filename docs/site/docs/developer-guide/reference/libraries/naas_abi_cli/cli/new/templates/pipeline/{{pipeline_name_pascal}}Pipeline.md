# `{{pipeline_name_pascal}}Pipeline`

## What it is
- A template pipeline module defining a `Pipeline` subclass (`{{pipeline_name_pascal}}Pipeline`) plus configuration and parameters types.
- Intended to be extended by implementing `run()`. In the template, `run()` is a stub (`pass`).

## Public API
- `@dataclass {{pipeline_name_pascal}}PipelineConfiguration(PipelineConfiguration)`
  - Holds pipeline configuration (currently empty).

- `class {{pipeline_name_pascal}}PipelineParameters(PipelineParameters)`
  - Defines the pipeline input schema (currently empty; example field is commented out).

- `class {{pipeline_name_pascal}}Pipeline(Pipeline)`
  - `__init__(configuration: {{pipeline_name_pascal}}PipelineConfiguration)`
    - Initializes the pipeline with a configuration object.
  - `run(parameters: {{pipeline_name_pascal}}PipelineParameters) -> rdflib.Graph`
    - Executes pipeline logic and is expected to return an RDFLib `Graph`.
    - Not implemented in the template.
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool`:
      - `name`: `"{{pipeline_name_pascal}}"`
      - `func`: builds `{{pipeline_name_pascal}}PipelineParameters(**kwargs)` then calls `run(...)`
      - `args_schema`: `{{pipeline_name_pascal}}PipelineParameters`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.pipeline`: `Pipeline`, `PipelineConfiguration`, `PipelineParameters`
  - `langchain_core.tools`: `BaseTool`, `StructuredTool` (used by `as_tools`)
  - `rdflib`: `Graph` (and additional RDF terms imported but unused in the template)
  - `dataclasses.dataclass`
  - `pydantic.Field`, `typing.Annotated` (intended for parameter fields; currently unused)
  - `naas_abi_core.logger` (imported but unused in the template)
  - `uuid` (imported but unused in the template)

## Usage
Implement `run()` before using the pipeline.

```python
from rdflib import Graph

# from your_module_path import (
#     {{pipeline_name_pascal}}Pipeline,
#     {{pipeline_name_pascal}}PipelineConfiguration,
#     {{pipeline_name_pascal}}PipelineParameters,
# )

class MyPipeline({{pipeline_name_pascal}}Pipeline):
    def run(self, parameters: {{pipeline_name_pascal}}PipelineParameters) -> Graph:
        return Graph()

pipeline = MyPipeline({{pipeline_name_pascal}}PipelineConfiguration())
g = pipeline.run({{pipeline_name_pascal}}PipelineParameters())
print(type(g))
```

Using as a LangChain tool:

```python
tool = pipeline.as_tools()[0]
result = tool.invoke({})  # kwargs must match {{pipeline_name_pascal}}PipelineParameters
```

## Caveats
- `run()` is a stub in the template; calling it as-is returns `None` despite the `Graph` return annotation.
- Many imports (e.g., `uuid`, `logger`, several `rdflib` terms) are unused in the template and may be removed if not needed.
