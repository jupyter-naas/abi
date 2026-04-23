# CreateIndividualOntologyYamlWorkflow

## What it is
A workflow that:
- Extracts a subject-centered RDF graph for a given individual URI from a triple store.
- Converts that RDF graph to a YAML ontology (via `ConvertOntologyGraphToYamlWorkflow`) and pushes it to a Naas workspace.
- Optionally writes back a generated `naas_ontology_id` to the triple store if the individual did not already have one.

It also supports an event trigger path for certain individual types.

## Public API

### Classes

- `CreateIndividualOntologyYamlWorkflowConfiguration(WorkflowConfiguration)`
  - **Purpose:** Provides dependencies for the workflow.
  - **Fields:**
    - `triple_store: ITripleStoreService` — triple store service port used for SPARQL and inserts.
    - `convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration` — config for downstream conversion workflow.

- `CreateIndividualOntologyYamlWorkflowParameters(WorkflowParameters)`
  - **Purpose:** Input parameters for converting an individual’s graph to YAML.
  - **Fields:**
    - `individual_uri: str` — required; must match `URI_REGEX`.
    - `depth: int = 2` — how deep to traverse the subject graph (1 = direct properties only, etc.).

- `CreateIndividualOntologyYamlWorkflow(Workflow)`
  - **Purpose:** Orchestrates graph extraction, YAML conversion, and optional triple-store backfill.
  - **Methods:**
    - `trigger(event: OntologyEvent, triple: tuple[Any, Any, Any]) -> str | None`
      - Reacts only to:
        - `OntologyEvent.INSERT`
        - subject `s` and object `o` URIs starting with `http://ontology.naas.ai/abi/`
        - individual class URI in a fixed allow-list (Person / Commercial Organization)
      - If matched, runs `graph_to_yaml(...)` and returns the resulting `ontology_id`.
    - `graph_to_yaml(parameters: CreateIndividualOntologyYamlWorkflowParameters) -> str | None`
      - Fetches a subject graph for `parameters.individual_uri` at `parameters.depth`.
      - Extracts from the graph (if present on the subject):
        - `rdfs:label` → used as ontology label; description becomes `"{label} Ontology"`.
        - `http://ontology.naas.ai/abi/logo` → ontology logo URL.
        - `http://ontology.naas.ai/abi/naas_ontology_id` → existing ontology id (if present).
      - Calls `ConvertOntologyGraphToYamlWorkflow.graph_to_yaml(...)` with the turtle-serialized graph plus metadata.
      - If no `naas_ontology_id` was present, inserts it back into the triple store in graph:
        - `http://ontology.naas.ai/graph/default`
      - Returns the `ontology_id`.
    - `as_tools() -> list[BaseTool]`
      - Exposes a LangChain `StructuredTool` named `create_individual_ontology_yaml` that calls `graph_to_yaml`.
    - `as_api(...) -> None`
      - Currently a no-op (does not register routes).

## Configuration/Dependencies
- Requires an implementation of `ITripleStoreService` (used by `SPARQLUtils` and for inserts).
- Requires `ConvertOntologyGraphToYamlWorkflowConfiguration` for downstream conversion/push logic.
- Uses:
  - `SPARQLUtils.get_subject_graph(individual_uri, depth)`
  - `SPARQLUtils.get_class_uri_from_individual_uri(individual_uri)`
- RDF libraries: `rdflib` (`Graph`, `URIRef`, `Literal`, `RDFS.label`).
- Parameter validation uses Pydantic `Field(..., pattern=URI_REGEX)`.

## Usage

### Convert an individual to YAML and get/update its `ontology_id`
```python
from naas_abi_marketplace.applications.naas.workflows.CreateIndividualOntologyYamlWorkflow import (
    CreateIndividualOntologyYamlWorkflow,
    CreateIndividualOntologyYamlWorkflowConfiguration,
    CreateIndividualOntologyYamlWorkflowParameters,
)

# You must provide:
# - triple_store: an ITripleStoreService implementation
# - convert_ontology_graph_config: ConvertOntologyGraphToYamlWorkflowConfiguration instance
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
- `trigger(...)` only runs for `INSERT` events where both `s` and `o` start with `http://ontology.naas.ai/abi/`, and only if the individual’s class URI is one of:
  - `https://www.commoncoreontologies.org/ont00001262` (Person)
  - `https://www.commoncoreontologies.org/ont00000443` (Commercial Organization)
- `as_api(...)` does nothing; no HTTP endpoints are exposed by this module.
- If the individual has no `rdfs:label`, the ontology label will be empty and description becomes `" Ontology"`.
- When creating a new ontology id, it is inserted into the fixed graph `http://ontology.naas.ai/graph/default`.
