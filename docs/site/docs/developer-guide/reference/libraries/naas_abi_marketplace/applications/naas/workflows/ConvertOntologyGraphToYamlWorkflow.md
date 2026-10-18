# ConvertOntologyGraphToYamlWorkflow

## What it is
A workflow that:
- Parses an ontology graph provided as a Turtle (`.ttl`) string into an RDFLib `Graph`
- Uploads the Turtle content as a public asset to Naas storage
- Converts the RDF graph to a YAML representation via `OntologyYaml.rdf_to_yaml`
- Creates or updates an ontology in Naas using the generated YAML and uploaded asset URL
- Returns the resulting ontology ID

## Public API

### Classes

- `ConvertOntologyGraphToYamlWorkflowConfiguration(WorkflowConfiguration)`
  - Holds configuration required to initialize the workflow.
  - **Field**: `naas_integration_config: NaasIntegrationConfiguration`

- `ConvertOntologyGraphToYamlWorkflowParameters(WorkflowParameters)`
  - Input parameters for a conversion run.
  - **Fields**:
    - `graph: str` (required): Graph serialized in Turtle format.
    - `ontology_id: Optional[str]`: Optional ontology ID to update (if not provided, workflow may resolve by label or create new).
    - `label: str` (default `"New Ontology"`): Ontology label.
    - `description: str` (default `"New Ontology Description"`): Ontology description.
    - `logo_url: Optional[str]` (default provided): Ontology logo URL.
    - `level: str` (default `"USE_CASE"`): Ontology level.
    - `display_relations_names: bool` (default `True`): Controls relation name display in YAML conversion.
    - `class_colors_mapping: Dict` (default `COLORS_NODES`): Class-to-color mapping used in YAML conversion.

- `ConvertOntologyGraphToYamlWorkflow(Workflow)`
  - Main workflow implementation.

### Methods

- `ConvertOntologyGraphToYamlWorkflow.__init__(configuration)`
  - Creates a `NaasIntegration` from `naas_integration_config`.
  - Creates an `OntologyYaml` converter using the module triple store service.

- `graph_to_yaml(parameters: ConvertOntologyGraphToYamlWorkflowParameters) -> str`
  - Converts Turtle graph to YAML, uploads the Turtle as an asset, then creates/updates a Naas ontology.
  - **Returns**: `ontology_id` (string).
  - **Raises**:
    - `ValueError` if asset upload fails, asset URL missing, or ontology creation/update ultimately fails.
    - Re-raises exceptions from RDF-to-YAML conversion.

- `as_tools() -> list[BaseTool]`
  - Exposes the workflow as a LangChain `StructuredTool` named `convert_graph_to_yaml`.

- `as_api(...) -> None`
  - Present but not implemented (`pass`).

## Configuration/Dependencies

- External libraries:
  - `rdflib.Graph` for parsing Turtle.
  - `yaml` for dumping YAML content (`yaml.dump(..., Dumper=Dumper)`).
  - `pydash.get` for safe response access.
  - `langchain_core.tools.StructuredTool` for tool exposure.

- Internal dependencies/services:
  - `NaasIntegration` is used to:
    - `upload_asset(...)`
    - `list_ontologies(workspace_id)`
    - `create_ontology(...)`
    - `update_ontology(...)`
  - `NaasABIModule.get_instance()` is used to access:
    - `configuration.workspace_id`
    - `configuration.storage_name`
    - `engine.services.triple_store` (passed into `OntologyYaml`)
  - `OntologyYaml.rdf_to_yaml(...)` performs RDF graph → YAML conversion.
  - Default `class_colors_mapping` comes from `COLORS_NODES`.

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

# Configure Naas integration (fields depend on NaasIntegrationConfiguration definition)
naas_cfg = NaasIntegrationConfiguration(...)  # fill with your integration settings

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
result = tools[0].invoke(
    {
        "graph": ttl,
        "label": "Example Ontology",
        "description": "Example description",
        "level": "USE_CASE",
    }
)
print(result)  # ontology_id
```

## Caveats

- `graph` must be valid Turtle; invalid content will fail during `Graph.parse(...)`.
- Ontology selection logic:
  - If an existing ontology in the workspace has the same `label`, its `id` is used (even if `ontology_id` was not provided).
- `as_api(...)` is not implemented; no HTTP endpoints are registered by this workflow.
- Asset upload is required; the workflow fails if `upload_asset` returns no asset or no URL.
