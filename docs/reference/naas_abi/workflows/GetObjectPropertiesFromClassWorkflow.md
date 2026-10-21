# GetObjectPropertiesFromClassWorkflow

## What it is
A workflow that loads an OWL/RDF ontology (from a Turtle file or a triple store schema graph) and returns all **OWL object properties** whose **domain** matches a given **class URI**, including simple handling for domain expressions (e.g., `unionOf` / `intersectionOf` / `complementOf` mapped to `or` / `and` / `not`).

## Public API

- `GetObjectPropertiesFromClassWorkflowConfiguration`
  - Purpose: Configure the workflow.
  - Fields:
    - `triple_store: ITripleStoreService` (required) — used when no ontology file is provided.
    - `ontology_file_path: Optional[str]` — path to a Turtle ontology file; when set, it is parsed into an RDFLib `Graph`.

- `GetObjectPropertiesFromClassWorkflowParameters`
  - Purpose: Input parameters for execution.
  - Fields:
    - `class_uri: str` — must match `^http.*` (validated by Pydantic).

- `GetObjectPropertiesFromClassWorkflow(configuration)`
  - Purpose: Loads the ontology into an RDF graph and prepares internal indices for class/property traversal.

- `GetObjectPropertiesFromClassWorkflow.get_object_properties_from_class(parameters) -> dict`
  - Purpose: For a given class URI, returns matching object properties.
  - Output shape:
    - `{"class_uri": <str>, "object_properties": [{"object_property_uri": <str>, "object_property_label": <str>, "ranges": <processed ranges>}, ...]}`
  - Notes:
    - Validates the input URI is an `owl:Class` in the loaded graph; otherwise raises `ValueError`.
    - Matches properties typed as `owl:ObjectProperty`.
    - Domain matching supports:
      - direct string match to `class_uri`
      - simple `{"or": [...]}` and `{"and": [...]}` dicts produced by internal parsing.

- `GetObjectPropertiesFromClassWorkflow.as_tools() -> list[BaseTool]`
  - Purpose: Exposes the workflow as a LangChain `StructuredTool` named `get_object_properties_from_class`.

- `GetObjectPropertiesFromClassWorkflow.as_api(...) -> None`
  - Purpose: API exposure stub; currently does nothing and returns `None`.

## Configuration/Dependencies

- Requires an `ITripleStoreService` implementation (from `naas_abi_core.services.triple_store`).
- Ontology source:
  - `ontology_file_path` (Turtle) parsed via `rdflib.Graph.parse(..., format="turtle")`, **or**
  - `triple_store.get_schema_graph()` when `ontology_file_path` is not provided.
- Key libraries:
  - `rdflib` (Graph, RDF/OWL/RDFS vocabulary)
  - `pydash` (used for collection utilities)
  - `pydantic` (parameter validation)
  - `langchain_core` (tool wrapper)

## Usage

```python
from naas_abi import ABIModule
from naas_abi_core.engine.Engine import Engine
from naas_abi.workflows.GetObjectPropertiesFromClassWorkflow import (
    GetObjectPropertiesFromClassWorkflow,
    GetObjectPropertiesFromClassWorkflowConfiguration,
    GetObjectPropertiesFromClassWorkflowParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi"])

workflow = GetObjectPropertiesFromClassWorkflow(
    GetObjectPropertiesFromClassWorkflowConfiguration(
        triple_store=ABIModule.get_instance().engine.services.triple_store,
        # ontology_file_path="path/to/ontology.ttl",  # optional
    )
)

result = workflow.get_object_properties_from_class(
    GetObjectPropertiesFromClassWorkflowParameters(
        class_uri="http://purl.obolibrary.org/obo/BFO_0000015"
    )
)
print(result)
```

## Caveats

- `is_class()` prints the entire graph serialized as Turtle (`print(self.graph.serialize(...))`), which can be very noisy/expensive for large ontologies.
- Domain/range expression handling is limited to structures derived from `unionOf`, `intersectionOf`, and `complementOf`, mapped to `or`, `and`, `not`.
- `as_api()` is a no-op (no routes are registered).
