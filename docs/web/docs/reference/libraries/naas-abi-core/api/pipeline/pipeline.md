# Pipeline

## What it is
- A small base framework for RDF-processing pipelines.
- Defines:
  - A base **configuration** type (`PipelineConfiguration`)
  - A base **runtime parameters** type (`PipelineParameters`)
  - An abstract **pipeline** base class (`Pipeline`) that returns an `rdflib.Graph`

## Public API

### `PipelineConfiguration` (dataclass)
- Base class for pipeline configuration objects.
- Extend it in concrete pipelines to add configuration fields.

### `PipelineParameters` (`pydantic.BaseModel`)
- Base class for pipeline runtime parameters.
- Extend it in concrete pipelines to add validated execution parameters.

### `Pipeline` (class)
Base class for all pipelines.

- `__init__(configuration: PipelineConfiguration)`
  - Stores the pipeline configuration.

- `trigger(event: OntologyEvent, ontology_name: str, triple: tuple[Any, Any, Any]) -> rdflib.Graph`
  - Intended entry point to trigger a pipeline from an ontology/triple-store event.
  - **Not implemented** in the base class (raises `NotImplementedError`).
  - Note: marked with a TODO to become abstract, but currently is not decorated as abstract.

- `run(parameters: PipelineParameters) -> rdflib.Graph` (abstract)
  - Executes the pipeline with runtime parameters.
  - Must be implemented by subclasses.

## Configuration/Dependencies
- Depends on:
  - `rdflib.Graph` as the output type.
  - `pydantic.BaseModel` for parameter models.
  - `naas_abi_core.services.triple_store.TripleStorePorts.OntologyEvent` for `trigger()` event typing.
  - `naas_abi_core.utils.Expose.Expose` as the superclass of `Pipeline` (behavior defined elsewhere).

## Usage

```python
from dataclasses import dataclass
from rdflib import Graph

from naas_abi_core.pipeline.pipeline import Pipeline, PipelineConfiguration, PipelineParameters

@dataclass
class MyConfig(PipelineConfiguration):
    pass

class MyParams(PipelineParameters):
    pass

class MyPipeline(Pipeline):
    def run(self, parameters: MyParams) -> Graph:
        g = Graph()
        return g

pipeline = MyPipeline(MyConfig())
result = pipeline.run(MyParams())
print(type(result))  # <class 'rdflib.graph.Graph'>
```

## Caveats
- `Pipeline.trigger(...)` is **not abstract** but always raises `NotImplementedError` in the base class; subclasses should override it if they intend to support event-driven triggering.
- `Pipeline.run(...)` is **abstract**; instantiating a subclass without implementing it will fail.
