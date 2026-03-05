# UpdateSkillPipeline

## What it is
- A pipeline that updates RDF triples for an existing **Skill** individual in an ontology.
- It conditionally inserts:
  - `ABI.hasDescription` (if a new description is provided and not already present)
  - `ABI.isSkillOf` (if a person URI is provided and not already present)
- Uses a configured triple store service to fetch existing triples and insert new ones.

## Public API
### Classes
- `UpdateSkillPipelineConfiguration(PipelineConfiguration)`
  - Holds dependencies for the pipeline.
  - Fields:
    - `triple_store: ITripleStoreService` — triple store service used to read/insert graphs.

- `UpdateSkillPipelineParameters(PipelineParameters)`
  - Input schema for `run`.
  - Fields:
    - `individual_uri: str` — URI of the skill (must match `URI_REGEX`).
    - `description: Optional[str] = None` — description text to add (if not already present).
    - `person_uri: Optional[str] = None` — person URI to link via `ABI.isSkillOf` (must match `URI_REGEX`).

- `UpdateSkillPipeline(Pipeline)`
  - Main pipeline implementation.

### Methods
- `UpdateSkillPipeline.run(parameters: PipelineParameters) -> rdflib.Graph`
  - Validates `parameters` is `UpdateSkillPipelineParameters`.
  - Loads the current subject graph for `individual_uri`.
  - Builds an insert graph with only missing triples.
  - Inserts the new triples into the triple store.
  - Returns the merged graph (`existing + inserted`).

- `UpdateSkillPipeline.as_tools() -> list[langchain_core.tools.BaseTool]`
  - Exposes a single LangChain `StructuredTool`:
    - Name: `update_skill`
    - Args schema: `UpdateSkillPipelineParameters`
    - Calls `run(...)` internally.

- `UpdateSkillPipeline.as_api(...) -> None`
  - Currently a no-op (returns `None` and does not register routes).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation providing at least:
  - `get_subject_graph(subject: rdflib.term.URIRef) -> rdflib.Graph`
  - `insert(graph: rdflib.Graph) -> None`
- Uses RDF predicates from `naas_abi_core.utils.Graph.ABI`:
  - `ABI.hasDescription`
  - `ABI.isSkillOf`
- Input URI validation uses `URI_REGEX`.

## Usage
```python
from naas_abi.pipelines.UpdateSkillPipeline import (
    UpdateSkillPipeline,
    UpdateSkillPipelineConfiguration,
    UpdateSkillPipelineParameters,
)

# triple_store must implement ITripleStoreService
config = UpdateSkillPipelineConfiguration(triple_store=triple_store)
pipeline = UpdateSkillPipeline(config)

params = UpdateSkillPipelineParameters(
    individual_uri="https://example.org/skill/123",
    description="Can write technical documentation",
    person_uri="https://example.org/person/456",
)

result_graph = pipeline.run(params)
print(len(result_graph))
```

## Caveats
- Only inserts triples when the exact triple is not already present in the subject graph.
- `as_api(...)` does not expose any HTTP endpoints (it does nothing).
- `run(...)` raises `ValueError` if called with a parameters object that is not `UpdateSkillPipelineParameters`.
