# CreateWorkspaceOntologyWorkflow

## What it is
A `Workflow` that creates or updates a Naas workspace ontology from YAML data, optionally uploading a Turtle (`.ttl`) graph as a public asset and linking it as the ontology download URL.

## Public API

- **`CreateWorkspaceOntologyWorkflowConfiguration` (dataclass)**
  - Purpose: Workflow configuration container.
  - Fields:
    - `naas_integration_config: NaasIntegrationConfiguration` — configuration for `NaasIntegration`.

- **`CreateWorkspaceOntologyWorkflowParameters` (`WorkflowParameters`)**
  - Purpose: Input schema for creating/updating an ontology.
  - Fields:
    - `yaml_data: dict` — YAML-serializable ontology source content.
    - `label: str` — ontology label (also used to detect existing ontology by label).
    - `level: str = "USE_CASE"` — ontology level.
    - `description: Optional[str] = "Ontology description not provided."`
    - `logo_url: Optional[str] = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"`
    - `ontology_id: Optional[str] = None` — if not provided, the workflow searches by `label`.
    - `graph: Optional[str] = None` — Turtle string; when provided, it is parsed and uploaded as an asset.

- **`CreateWorkspaceOntologyWorkflow` (`Workflow`)**
  - **`create_or_update_workspace_ontology(parameters) -> str`**
    - Purpose:
      - If `parameters.ontology_id` is `None`, lists existing ontologies in the workspace and reuses the one with matching `label` if found.
      - Otherwise creates a new ontology (if none exists) or updates the existing one.
      - If `parameters.graph` is provided, uploads it as a public asset named `<label>.ttl` and passes its URL as `download_url`.
    - Returns: the ontology id (`str`).
    - Raises: `ValueError` if creation/update fails to produce an ontology id.
  - **`as_tools() -> list[BaseTool]`**
    - Purpose: Exposes the workflow as a LangChain `StructuredTool` named `convert_graph_to_yaml` (despite performing create/update).
  - **`as_api(...) -> None`**
    - Purpose: declared but not implemented (`pass`).

## Configuration/Dependencies

- Depends on:
  - `NaasIntegration` for:
    - `list_ontologies(workspace_id)`
    - `create_ontology(...)`
    - `update_ontology(...)`
    - `upload_asset(...)`
  - `NaasABIModule.get_instance().configuration` for:
    - `workspace_id`
    - `storage_name`
  - `yaml.dump(..., Dumper=yaml.Dumper)` to serialize `yaml_data` into YAML source.
  - `rdflib.Graph().parse(data=..., format="turtle")` to parse `graph` when provided.

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
        # populate with required integration settings
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

- If `ontology_id` is not provided, the workflow identifies an existing ontology **only by exact `label` match**.
- When `graph` is provided:
  - It is parsed as Turtle; invalid Turtle will raise during `rdflib` parsing.
  - Upload failure is logged, but the ontology can still be created/updated with `download_url=None`.
- `as_tools()` exposes a tool named `convert_graph_to_yaml`, but it actually performs create/update of the workspace ontology.
