# CreateWorkspaceOntologyWorkflow

## What it is
A `Workflow` that creates or updates a Naas workspace ontology from YAML data, optionally uploading a Turtle (`.ttl`) graph as a public asset and linking it as the ontology `download_url`.

## Public API

- **`CreateWorkspaceOntologyWorkflowConfiguration` (dataclass, `WorkflowConfiguration`)**
  - Purpose: Holds configuration for the workflow.
  - Fields:
    - `naas_integration_config: NaasIntegrationConfiguration` — configuration used to instantiate `NaasIntegration`.

- **`CreateWorkspaceOntologyWorkflowParameters` (`WorkflowParameters`)**
  - Purpose: Input schema for creating/updating a workspace ontology.
  - Fields:
    - `yaml_data: dict` — ontology source content (serialized to YAML).
    - `label: str` — ontology label; also used to find an existing ontology when `ontology_id` is not provided.
    - `level: str = "USE_CASE"` — ontology level.
    - `description: str | None = "Ontology description not provided."`
    - `logo_url: str | None = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"`
    - `ontology_id: str | None = None` — explicit ontology id; if omitted, the workflow searches by `label`.
    - `graph: str | None = None` — Turtle string; if provided, is parsed and uploaded as `<label>.ttl` to build a public `download_url`.

- **`CreateWorkspaceOntologyWorkflow` (`Workflow`)**
  - **`create_or_update_workspace_ontology(parameters: CreateWorkspaceOntologyWorkflowParameters) -> str`**
    - Purpose:
      - If `parameters.ontology_id` is `None`, lists ontologies in the current workspace and reuses the one whose `label` matches exactly.
      - Creates a new ontology if none is found; otherwise updates the existing ontology.
      - If `parameters.graph` is provided, parses it as Turtle and uploads it as a public asset; uses the asset URL as `download_url`.
    - Returns: `ontology_id` as `str`.
    - Raises: `ValueError` if no ontology id is produced.
  - **`as_tools() -> list[BaseTool]`**
    - Purpose: Exposes the workflow as a LangChain `StructuredTool` (tool name: `convert_graph_to_yaml`) that calls `create_or_update_workspace_ontology`.
  - **`as_api(...) -> None`**
    - Declared but not implemented (`pass`).

## Configuration/Dependencies

- **Workspace context**
  - Reads `workspace_id` and `storage_name` from: `NaasABIModule.get_instance().configuration`.

- **Integrations**
  - Uses `NaasIntegration` methods:
    - `list_ontologies(workspace_id)`
    - `create_ontology(...)`
    - `update_ontology(...)`
    - `upload_asset(...)`

- **Serialization / parsing**
  - Serializes YAML with `yaml.dump(parameters.yaml_data, Dumper=yaml.Dumper)`.
  - Validates/parses Turtle with `rdflib.Graph().parse(data=..., format="turtle")` when `graph` is provided.

## Usage

```python
from naas_abi_marketplace.applications.naas.workflows.CreateWorkspaceOntologyWorkflow import (
    CreateWorkspaceOntologyWorkflow,
    CreateWorkspaceOntologyWorkflowConfiguration,
    CreateWorkspaceOntologyWorkflowParameters,
)
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)

cfg = CreateWorkspaceOntologyWorkflowConfiguration(
    naas_integration_config=NaasIntegrationConfiguration(
        # Fill with required Naas integration settings for your environment
    )
)

wf = CreateWorkspaceOntologyWorkflow(cfg)

params = CreateWorkspaceOntologyWorkflowParameters(
    yaml_data={"entities": [], "relations": []},
    label="My Ontology",
    level="USE_CASE",
    # graph="... turtle content ..."  # optional
)

ontology_id = wf.create_or_update_workspace_ontology(params)
print(ontology_id)
```

## Caveats

- If `ontology_id` is not provided, an existing ontology is detected **only by exact `label` match**.
- If `graph` is provided:
  - It must be valid Turtle; invalid Turtle will raise during `rdflib` parsing.
  - Asset upload failure is logged; the ontology is still created/updated but with `download_url=None`.
- `as_tools()` exposes a tool named `convert_graph_to_yaml`, but it actually performs create/update of the workspace ontology.
