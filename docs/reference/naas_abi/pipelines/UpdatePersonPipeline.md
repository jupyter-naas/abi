# UpdatePersonPipeline

## What it is
- A pipeline that **adds missing person-related triples** (LinkedIn page, skill, first/last name, date of birth) into an RDF triple store.
- It **does not remove or overwrite** existing triples; it only inserts a triple if the exact triple does not already exist for the person.

## Public API
- `UpdatePersonPipelineConfiguration(triple_store: ITripleStoreService)`
  - Configuration container providing the triple store service.

- `UpdatePersonPipelineParameters`
  - Pydantic-style parameter model (`PipelineParameters`) with fields:
    - `individual_uri: str` (required; must match `URI_REGEX`)
    - `first_name: Optional[str]`
    - `last_name: Optional[str]`
    - `date_of_birth: Optional[str]` (format `YYYY-MM-DD`)
    - `linkedin_page_uri: Optional[str]` (must match `URI_REGEX`)
    - `skill_uri: str` (declared as `str` but default is `None` in `Field`; treat as optional in practice only if your validation allows it)

- `UpdatePersonPipeline(configuration: UpdatePersonPipelineConfiguration)`
  - `run(parameters: PipelineParameters) -> rdflib.Graph`
    - Validates `parameters` type is `UpdatePersonPipelineParameters`.
    - Fetches the existing subject graph via `triple_store.get_subject_graph(individual_uri)`.
    - Builds an insertion graph containing only missing triples.
    - Inserts via `triple_store.insert(graph_insert)`.
    - Returns the merged graph (`existing + inserted`).
  - `as_tools() -> list[langchain_core.tools.BaseTool]`
    - Exposes the pipeline as a LangChain `StructuredTool` named `update_person`.
  - `as_api(...) -> None`
    - Present but currently does nothing (returns `None`).

## Configuration/Dependencies
- Requires an `ITripleStoreService` implementation that provides:
  - `get_subject_graph(subject: URIRef) -> rdflib.Graph`
  - `insert(graph: rdflib.Graph) -> None`
- Uses RDF terms/predicates from `naas_abi_core.utils.Graph.ABI`:
  - `ABI.hasLinkedInPage`, `ABI.hasSkill`, `ABI.first_name`, `ABI.last_name`, `ABI.date_of_birth`
- Uses `rdflib` for RDF graph manipulation and `XSD.date` for date datatype.

## Usage
```python
from naas_abi.pipelines.UpdatePersonPipeline import (
    UpdatePersonPipeline,
    UpdatePersonPipelineConfiguration,
    UpdatePersonPipelineParameters,
)

# triple_store must implement ITripleStoreService
config = UpdatePersonPipelineConfiguration(triple_store=triple_store)

pipeline = UpdatePersonPipeline(config)

result_graph = pipeline.run(
    UpdatePersonPipelineParameters(
        individual_uri="https://www.commoncoreontologies.org/ont00001262/Florent_Ravenel",
        first_name="Florent",
        last_name="Ravenel",
        date_of_birth="1990-01-01",
        linkedin_page_uri="https://example.com/linkedin/profile",
        skill_uri="https://example.com/skill/python",
    )
)

print(len(result_graph))
```

## Caveats
- **No updates/overwrites:** if a different value already exists (e.g., another `first_name`), this pipeline **will add** the new triple rather than replacing old ones.
- `as_api()` is a stub and does not register any routes.
- `skill_uri` is typed as `str` but defined with `Field(None, ...)`; depending on your parameter validation setup, passing `None` may error.
