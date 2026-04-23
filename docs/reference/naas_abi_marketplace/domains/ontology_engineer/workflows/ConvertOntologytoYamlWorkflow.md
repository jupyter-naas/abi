# ConvertOntologytoYamlWorkflow

## What it is
A `naas_abi_core.workflow.Workflow` implementation that:
- Parses a Turtle (`.ttl`) ontology (plus optional imported ontologies),
- Extracts OWL classes, relationships, and OWL named individuals,
- Writes a YAML file with two sections: `classes` and `entities`,
- Optionally publishes the resulting YAML ontology to a Naas workspace via `CreateWorkspaceOntologyWorkflow`.

## Public API

### Constants
- `GROUP_TO_STYLE: dict`
  - Maps high-level ontology “groups” (e.g., `WHO`, `WHAT`) to visualization style fields used in YAML entity entries.

### Configuration
- `ConvertOntologytoYamlWorkflowConfiguration(WorkflowConfiguration)`
  - `create_workspace_ontology_config: CreateWorkspaceOntologyWorkflowConfiguration` (required)
  - `default_output_dir: Optional[str]` (optional fallback output directory)

### Parameters
- `ConvertOntologytoYamlWorkflowParameters(WorkflowParameters)`
  - `turtle_path: str` — path to `.ttl` file (must exist)
  - `output_dir: Optional[str]` — output directory; if omitted uses `default_output_dir` then TTL’s directory
  - `imported_ontologies: Optional[List[str]]` — additional ontology paths/URLs to load
  - `publish_to_workspace: bool` — if `True`, publishes YAML data to workspace
  - `ontology_name: str` — label used when publishing to workspace
  - `display_individuals_classes: bool` — if `True`, includes `owl:Class` entries in `entities` section

### Workflow
- `ConvertOntologytoYamlWorkflow(Workflow)`
  - `convert_ontology_to_yaml(parameters: ConvertOntologytoYamlWorkflowParameters) -> str`
    - Produces `<ttl_stem>.yaml` in the chosen output directory.
    - Returns the generated YAML file path as a string.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named `convert_ontology_to_yaml_and_publish_to_workspace`.
  - `as_api(...) -> None`
    - No API routes are registered (currently returns `None`).

## Configuration/Dependencies
- Python packages:
  - `PyYAML` (`yaml`) for YAML output
  - `rdflib` for RDF/OWL parsing and querying
  - `fastapi` (only for type `APIRouter`; API not implemented here)
  - `langchain_core` tools (`BaseTool`, `StructuredTool`)
- Internal dependencies:
  - `CreateWorkspaceOntologyWorkflow` for workspace publishing
  - `naas_abi_marketplace.domains.ontology_engineer.utils.graph`:
    - `parse_turtle_ontology`, `get_rdfs_label`, `get_short_name`, `get_class_id_prefix`,
      `get_group_from_class_hierarchy`, `get_inverse_property`
- Output YAML structure:
  - `classes`: list of class dictionaries (id/name/description/examples/class/relations/style)
  - `entities`: list of entity dictionaries (classes optionally + named individuals)

## Usage

### Minimal conversion to YAML (no publishing)
```python
from naas_abi_marketplace.domains.ontology_engineer.workflows.ConvertOntologytoYamlWorkflow import (
    ConvertOntologytoYamlWorkflow,
    ConvertOntologytoYamlWorkflowConfiguration,
    ConvertOntologytoYamlWorkflowParameters,
)
from naas_abi_marketplace.applications.naas.workflows.CreateWorkspaceOntologyWorkflow import (
    CreateWorkspaceOntologyWorkflowConfiguration,
)
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)

config = ConvertOntologytoYamlWorkflowConfiguration(
    create_workspace_ontology_config=CreateWorkspaceOntologyWorkflowConfiguration(
        naas_integration_config=NaasIntegrationConfiguration(
            api_key="NAAS_API_KEY",
            workspace_id="WORKSPACE_ID",
            storage_name="STORAGE_NAME",
        )
    ),
    default_output_dir=None,
)

workflow = ConvertOntologytoYamlWorkflow(config)

yaml_path = workflow.convert_ontology_to_yaml(
    ConvertOntologytoYamlWorkflowParameters(
        turtle_path="path/to/ontology.ttl",
        imported_ontologies=None,
        output_dir=None,
        publish_to_workspace=False,
        display_individuals_classes=True,
    )
)

print(yaml_path)
```

### Publishing to workspace
Set `publish_to_workspace=True` and provide `ontology_name`:
```python
params = ConvertOntologytoYamlWorkflowParameters(
    turtle_path="path/to/ontology.ttl",
    publish_to_workspace=True,
    ontology_name="My Ontology",
)
workflow.convert_ontology_to_yaml(params)
```

## Caveats
- The input TTL path must exist; otherwise `FileNotFoundError` is raised.
- If `PyYAML` is unavailable, conversion fails with an `ImportError`.
- Relationship deduplication for `owl:NamedIndividual` entities attempts to skip inverse duplicates using `owl:inverseOf` (via `get_inverse_property`).
- `as_api()` is a stub; no FastAPI endpoints are created by this workflow.
