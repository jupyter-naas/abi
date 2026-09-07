# CreateIndividualOntologyYamlWorkflow

## What it is
A workflow that:
- Extracts a subject-centered RDF graph for a given individual URI from a triple store.
- Converts that RDF graph to a YAML ontology (via `ConvertOntologyGraphToYamlWorkflow`) and pushes it to a Naas workspace.
- Optionally writes back a generated `naas_ontology_id` to the triple store if the individual did not already have one.
- Provides an event-trigger entrypoint (`trigger`) for specific individual types.

## Public API

### Classes

- `CreateIndividualOntologyYamlWorkflowConfiguration(WorkflowConfiguration)`
  - Holds required dependencies:
    - `triple_store: ITripleStoreService` — used for SPARQL querying and inserts.
    - `convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration` — configuration passed to the downstream conversion workflow.

- `CreateIndividualOntologyYamlWorkflowParameters(WorkflowParameters)`
  - Input parameters:
    - `individual_uri: str` — required; validated against `URI_REGEX`.
    - `depth: int = 2` — traversal depth for the subject graph.

- `CreateIndividualOntologyYamlWorkflow(Workflow)`
  - Orchestrates extraction → conversion → optional backfill.
  - Methods:
    - `trigger(event: OntologyEvent, triple: tuple[Any, Any, Any]) -> str | None`
      - Runs only when:
        - `event` is `OntologyEvent.INSERT`
        - subject `s` and object `o` URIs start with `http://ontology.naas.ai/abi/`
        - the subject’s class URI (from `get_class_uri_from_individual_uri`) is one of:
          - `https://www.commoncoreontologies.org/ont00001262` (Person)
          - `https://www.commoncoreontologies.org/ont00000443` (Commercial Organization)
      - If matched, calls `graph_to_yaml(...)` for `s` (depth fixed to `2`) and returns the resulting `ontology_id`.
    - `graph_to_yaml(parameters: CreateIndividualOntologyYamlWorkflowParameters) -> str | None`
      - Fetches a subject graph via `SPARQLUtils.get_subject_graph(individual_uri, depth)`.
      - Extracts metadata from triples where `s == individual_uri`:
        - `rdfs:label` → `label` and description `"{label} Ontology"`
        - `http://ontology.naas.ai/abi/logo` → `logo_url`
        - `http://ontology.naas.ai/abi/naas_ontology_id` → existing `ontology_id` (if present)
      - Calls downstream conversion:
        - `ConvertOntologyGraphToYamlWorkflow.graph_to_yaml(...)` with turtle-serialized graph and metadata.
      - If no existing `naas_ontology_id` was found, inserts `(individual_uri, naas_ontology_id, ontology_id)` into graph:
        - `http://ontology.naas.ai/graph/default`
      - Returns the `ontology_id`.
    - `as_tools() -> list[BaseTool]`
      - Exposes a LangChain `StructuredTool` named `create_individual_ontology_yaml` that calls `graph_to_yaml`.
    - `as_api(...) -> None`
      - Present but does not register any routes (no implementation beyond default parameter handling).

## Configuration/Dependencies
- Requires:
  - `ITripleStoreService` (injected via configuration)
  - `ConvertOntologyGraphToYamlWorkflowConfiguration` (injected via configuration)
- Uses:
  - `SPARQLUtils(triple_store)`:
    - `get_subject_graph(individual_uri, depth)`
    - `get_class_uri_from_individual_uri(individual_uri)`
  - `rdflib` (`Graph`, `URIRef`, `Literal`, `RDFS.label`)
  - `pydantic.Field` for parameter validation (`pattern=URI_REGEX`)
  - `langchain_core.tools.StructuredTool`

## Usage

### Convert an individual to YAML and get/update its `ontology_id`
```python
from naas_abi_marketplace.applications.naas.workflows.CreateIndividualOntologyYamlWorkflow import (
    CreateIndividualOntologyYamlWorkflow,
    CreateIndividualOntologyYamlWorkflowConfiguration,
    CreateIndividualOntologyYamlWorkflowParameters,
)

# Provide concrete implementations/configs:
# - triple_store: ITripleStoreService
# - convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration
config = CreateIndividualOntologyYamlWorkflowConfiguration(
    triple_store=triple_store,
    convert_ontology_graph_config=convert_ontology_graph_config,
)

wf = CreateIndividualOntologyYamlWorkflow(config)

ontology_id = wf.graph_to_yaml(
    CreateIndividualOntologyYamlWorkflowParameters(
        individual_uri="http://ontology.naas.ai/abi/some-individual",
        depth=2,
    )
)
print(ontology_id)
```

### Use as a LangChain tool
```python
tool = wf.as_tools()[0]
result = tool.run(
    individual_uri="http://ontology.naas.ai/abi/some-individual",
    depth=2,
)
print(result)
```

## Caveats
- `trigger(...)` only activates on `INSERT` events where both `s` and `o` start with `http://ontology.naas.ai/abi/`, and only for Person/Commercial Organization class URIs listed in code.
- If the individual has no `rdfs:label`, the label is `""` and description becomes `" Ontology"`.
- When creating a new ontology id (no existing `naas_ontology_id` triple), the workflow inserts into the fixed graph `http://ontology.naas.ai/graph/default`.
- `as_api(...)` does not expose any HTTP endpoints.
