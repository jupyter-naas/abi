from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

import pydash as _
import yaml
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_marketplace.applications.naas import ABIModule as NaasABIModule
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from pydantic import Field
from rdflib import Graph
from yaml import Dumper


@dataclass
class CreateWorkspaceOntologyWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CreateWorkspaceOntology workflow.

    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """

    naas_integration_config: NaasIntegrationConfiguration


class CreateWorkspaceOntologyWorkflowParameters(WorkflowParameters):
    """Parameters for CreateWorkspaceOntology workflow execution.

    Attributes:
        ontology_name (str): The name of the ontology store to use
        label (str): The label of the ontology
        description (str): The description of the ontology
        logo_url (str): The URL of the ontology logo
        level (str): The level of the ontology (e.g., 'TOP_LEVEL', 'MID_LEVEL', 'DOMAIN', 'USE_CASE')
        display_relations_names (bool): Whether to display relation names in the visualization
    """

    yaml_data: Annotated[dict, Field(..., description="The YAML data of the ontology")]
    label: Annotated[str, Field(..., description="The label of the ontology")]
    level: Annotated[str, Field(..., description="The level of the ontology")] = (
        "USE_CASE"
    )
    description: Optional[
        Annotated[
            str,
            Field(
                ...,
                description="The description of the ontology. Example: 'Represents ABI Ontology with agents, workflows, ontologies, pipelines and integrations.'",
            ),
        ]
    ] = "Ontology description not provided."
    logo_url: Optional[
        Annotated[str, Field(..., description="The logo URL of the ontology")]
    ] = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
    ontology_id: Optional[
        Annotated[str, Field(..., description="The ID of the ontology")]
    ] = None
    graph: Optional[
        Annotated[str, Field(..., description="The graph serialized as turtle format")]
    ] = None


class CreateWorkspaceOntologyWorkflow(Workflow):
    """Workflow for creating a workspace ontology."""

    __configuration: CreateWorkspaceOntologyWorkflowConfiguration

    def __init__(self, configuration: CreateWorkspaceOntologyWorkflowConfiguration):
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(
            self.__configuration.naas_integration_config
        )

    def create_or_update_workspace_ontology(
        self, parameters: CreateWorkspaceOntologyWorkflowParameters
    ) -> str:
        # Initialize parameters
        logger.debug(f"==> Creating or updating workspace ontology: {parameters.label}")

        workspace_id = NaasABIModule.get_instance().configuration.workspace_id
        storage_name = NaasABIModule.get_instance().configuration.storage_name

        # Get ontology ID if it exists
        ontology_id = None
        if parameters.ontology_id is None:
            result = self.__naas_integration.list_ontologies(workspace_id)
            ontologies = result.get("ontologies", [])
            for ontology in ontologies:
                if (
                    ontology
                    and isinstance(ontology, dict)
                    and ontology.get("label") == parameters.label
                ):
                    ontology_id = ontology.get("id")
                    break

        # Create download URL if graph is provided
        asset_url = None
        if parameters.graph is not None:
            g = Graph()
            g.parse(data=parameters.graph, format="turtle")

            # Upload asset to Naas
            asset = self.__naas_integration.upload_asset(
                data=parameters.graph.encode("utf-8"),  # Use the original turtle string
                workspace_id=workspace_id,
                storage_name=storage_name,
                prefix="assets",
                object_name=str(parameters.label + ".ttl"),
                visibility="public",
            )
            # Save asset URL to JSON
            if asset is None:
                logger.error(f"Failed to upload asset to Naas: {parameters.label}")
            else:
                asset_url = asset.get("asset", {}).get("url")
                if asset_url.endswith("/"):
                    asset_url = asset_url[:-1]

        # Convert data dict to YAML
        yaml_data = yaml.dump(parameters.yaml_data, Dumper=Dumper)
        onto_label = parameters.label
        onto_description = parameters.description
        onto_logo_url = parameters.logo_url
        onto_level = parameters.level
        if ontology_id is None:
            # Create new ontology
            res = self.__naas_integration.create_ontology(
                workspace_id=workspace_id,
                label=onto_label,
                source=yaml_data,
                level=onto_level,
                description=onto_description,
                download_url=asset_url,
                logo_url=onto_logo_url,
            )
            ontology_id = str(_.get(res, "ontology.id", ""))
            message = (
                f"✅ Ontology '{onto_label}' ({ontology_id}) successfully created."
            )
        else:
            # Update existing ontology
            res = self.__naas_integration.update_ontology(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                source=yaml_data,
                level=onto_level,
                description=onto_description,
                download_url=asset_url,
                logo_url=onto_logo_url,
            )
            message = (
                f"✅ Ontology '{onto_label}' ({ontology_id}) successfully updated."
            )

        logger.debug(message)
        if ontology_id is None:
            raise ValueError("Failed to create or update ontology")
        return ontology_id

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="convert_graph_to_yaml",
                description="Convert an ontology graph to YAML.",
                func=lambda **kwargs: self.create_or_update_workspace_ontology(
                    CreateWorkspaceOntologyWorkflowParameters(**kwargs)
                ),
                args_schema=CreateWorkspaceOntologyWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        pass
