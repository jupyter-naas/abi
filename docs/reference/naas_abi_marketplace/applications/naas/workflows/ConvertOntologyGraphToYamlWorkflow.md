# ConvertOntologyGraphToYamlWorkflow

## What it is
A workflow that:
- Parses an ontology graph provided as a Turtle (`.ttl`) string into an RDFLib `Graph`
- Uploads the Turtle content as a public asset to Naas storage
- Converts the RDF graph to a YAML structure via `OntologyYaml.rdf_to_yaml`
- Creates or updates a Naas ontology using the generated YAML and uploaded asset URL
- Returns the resulting ontology ID

## Public API

### Classes

- `ConvertOntologyGraphToYamlWorkflowConfiguration(WorkflowConfiguration)`
  - Workflow configuration container.
  - Fields:
    - `naas_integration_config: NaasIntegrationConfiguration` — configuration used to instantiate `NaasIntegration`.

- `ConvertOntologyGraphToYamlWorkflowParameters(WorkflowParameters)`
  - Input parameters for a run.
  - Fields:
    - `graph: str` — ontology graph serialized in Turtle format.
    - `ontology_id: str | None = None` — optional ID of an ontology to update.
    - `label: str = "New Ontology"` — ontology label.
    - `description: str = "New Ontology Description"` — ontology description.
    - `logo_url: str | None = <default URL>` — ontology logo URL.
    - `level: str = "USE_CASE"` — ontology level.
    - `display_relations_names: bool = True` — forwarded to YAML conversion.
    - `class_colors_mapping: dict = COLORS_NODES` — forwarded to YAML conversion.

- `ConvertOntologyGraphToYamlWorkflow(Workflow)`
  - Main workflow implementation.

### Methods

- `__init__(configuration: ConvertOntologyGraphToYamlWorkflowConfiguration)`
  - Creates:
    - `NaasIntegration` using `naas_integration_config`
    - `OntologyYaml` using `NaasABIModule.get_instance().engine.services.triple_store`

- `graph_to_yaml(parameters: ConvertOntologyGraphToYamlWorkflowParameters) -> str`
  - End-to-end conversion + upload + ontology create/update.
  - Behavior:
    - Parses Turtle to `rdflib.Graph`.
    - Uploads Turtle as a public asset (prefix `assets`, object name `<label>.ttl`).
    - Converts RDF graph to YAML data (`OntologyYaml.rdf_to_yaml`).
    - Resolves ontology ID by label if one exists in the workspace (overrides `ontology_id` if label matches).
    - Creates ontology if no ID found; otherwise updates.
  - Returns: `ontology_id` (string)
  - Raises:
    - `ValueError` if asset upload fails, asset URL missing, or final ontology ID is not resolved.
    - RDF parsing / conversion errors are not wrapped (conversion block builds a message but re-raises the original exception).

- `as_tools() -> list[BaseTool]`
  - Exposes a LangChain `StructuredTool`:
    - name: `convert_graph_to_yaml`
    - args schema: `ConvertOntologyGraphToYamlWorkflowParameters`
    - returns: ontology ID as a string

- `as_api(...) -> None`
  - Declared but not implemented (`pass`).

## Configuration/Dependencies

- External libraries:
  - `rdflib.Graph` — parsing Turtle strings.
  - `yaml.dump(..., Dumper=Dumper)` — serializing the YAML payload to send to Naas.
  - `pydash.get` — extracting `ontology.id` from create responses.
  - `langchain_core.tools.StructuredTool` — tool exposure.

- Internal dependencies:
  - `NaasIntegration`:
    - `upload_asset(...)`
    - `list_ontologies(workspace_id)`
    - `create_ontology(...)`
    - `update_ontology(...)`
  - `NaasABIModule.get_instance()` provides:
    - `configuration.workspace_id`
    - `configuration.storage_name`
    - `engine.services.triple_store` (used by `OntologyYaml`)
  - `COLORS_NODES` default color mapping.

## Usage

```python
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.naas.workflows.ConvertOntologyGraphToYamlWorkflow import (
    ConvertOntologyGraphToYamlWorkflow,
    ConvertOntologyGraphToYamlWorkflowConfiguration,
    ConvertOntologyGraphToYamlWorkflowParameters,
)

naas_cfg = NaasIntegrationConfiguration(...)  # provide required integration settings

workflow = ConvertOntologyGraphToYamlWorkflow(
    ConvertOntologyGraphToYamlWorkflowConfiguration(naas_integration_config=naas_cfg)
)

ttl = """
@prefix ex: <http://example.com/> .
ex:A ex:rel ex:B .
"""

ontology_id = workflow.graph_to_yaml(
    ConvertOntologyGraphToYamlWorkflowParameters(
        graph=ttl,
        label="Example Ontology",
        description="Example description",
        level="USE_CASE",
    )
)

print(ontology_id)
```

### As a LangChain tool

```python
tools = workflow.as_tools()
ontology_id = tools[0].invoke(
    {"graph": ttl, "label": "Example Ontology", "description": "Example description"}
)
print(ontology_id)
```

## Caveats
- `graph` must be valid Turtle; invalid input will fail during `Graph.parse(..., format="turtle")`.
- Ontology selection uses label matching:
  - If an ontology in the workspace has the same `label`, its `id` is used (even if `ontology_id` was provided).
- Asset upload is mandatory:
  - The workflow raises if `upload_asset` returns `None` or if the returned payload lacks `asset.asset.url`.
- `as_api` is not implemented; this workflow does not register HTTP routes.
