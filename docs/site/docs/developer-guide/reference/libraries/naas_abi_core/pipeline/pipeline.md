# Pipeline

## What it is
A small base module defining shared types and an abstract base class for RDF-processing pipelines. Pipelines are expected to return an `rdflib.Graph` and can be invoked either directly (`run`) or via an event-style hook (`trigger`).

## Public API

- `PipelineConfiguration` (`@dataclass`)
  - Base class for pipeline configuration objects. Intended to be subclassed with concrete configuration fields.

- `PipelineParameters` (`pydantic.BaseModel`)
  - Base class for runtime execution parameters. Intended to be subclassed with concrete parameter fields.

- `Pipeline` (`Expose`)
  - Base class for pipeline implementations.
  - `__init__(configuration: PipelineConfiguration)`
    - Stores the pipeline configuration.
  - `trigger(event: OntologyEvent, ontology_name: str, triple: tuple[Any, Any, Any]) -> Graph`
    - Event-driven entry point for processing a triple.
    - Currently raises `NotImplementedError()` unless overridden.
    - Note: not marked abstract in code (commented TODO).
  - `run(parameters: PipelineParameters) -> Graph` *(abstract)*
    - Main execution method; must be implemented by subclasses.
    - Raises `NotImplementedError()` in base class.

## Configuration/Dependencies
- Depends on:
  - `rdflib.Graph` (return type for pipeline outputs)
  - `pydantic.BaseModel` (for parameters)
  - `naas_abi_core.services.triple_store.TripleStorePorts.OntologyEvent` (type for `trigger` event)
  - `naas_abi_core.utils.Expose.Expose` (base class)

## Usage
Minimal example of implementing a pipeline that returns an empty RDF graph:

```python
from dataclasses import dataclass
from rdflib import Graph

from naas_abi_core.pipeline.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)

@dataclass
class MyConfig(PipelineConfiguration):
    name: str = "demo"

class MyParams(PipelineParameters):
    pass

class MyPipeline(Pipeline):
    def trigger(self, event, ontology_name: str, triple):
        # Custom event handling; return a Graph
        return Graph()

    def run(self, parameters: MyParams) -> Graph:
        return Graph()

pipeline = MyPipeline(MyConfig())
g = pipeline.run(MyParams())
print(len(g))
```

## Caveats
- `Pipeline.trigger(...)` is not abstract but raises `NotImplementedError()` by default; subclasses must override it to use event-based triggering.
- `Pipeline.run(...)` is abstract; subclasses must implement it to be instantiable.
