from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Dict, Optional

import pydash as _
import yaml
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi import config, logger
from naas_abi.mappings import COLORS_NODES
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.OntologyYaml import OntologyYaml
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from pydantic import Field
from rdflib import Graph
from yaml import Dumper


@dataclass
class ConvertOntologyGraphToYamlWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ConvertOntologyGraphToYaml workflow.

    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """

    naas_integration_config: NaasIntegrationConfiguration


class ConvertOntologyGraphToYamlWorkflowParameters(WorkflowParameters):
    """Parameters for ConvertOntologyGraphToYaml workflow execution.

    Attributes:
        ontology_name (str): The name of the ontology store to use
        label (str): The label of the ontology
        description (str): The description of the ontology
        logo_url (str): The URL of the ontology logo
        level (str): The level of the ontology (e.g., 'TOP_LEVEL', 'MID_LEVEL', 'DOMAIN', 'USE_CASE')
        display_relations_names (bool): Whether to display relation names in the visualization
    """

    graph: Annotated[
        str, Field(..., description="The graph serialized as turtle format")
    ]
    ontology_id: Annotated[
        Optional[str], Field(..., description="The ID of the ontology")
    ] = None
    label: Annotated[str, Field(..., description="The label of the ontology")] = (
        "New Ontology"
    )
    description: Annotated[
        str,
        Field(
            ...,
            description="The description of the ontology. Example: 'Represents ABI Ontology with agents, workflows, ontologies, pipelines and integrations.'",
        ),
    ] = "New Ontology Description"
    logo_url: Annotated[
        Optional[str], Field(..., description="The logo URL of the ontology")
    ] = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ULO.png"
    level: Annotated[str, Field(..., description="The level of the ontology")] = (
        "USE_CASE"
    )
    display_relations_names: Annotated[
        bool,
        Field(
            ..., description="Whether to display relation names in the visualization"
        ),
    ] = True
    class_colors_mapping: Annotated[
        Dict, Field(..., description="The mapping of class colors")
    ] = COLORS_NODES


class ConvertOntologyGraphToYamlWorkflow(Workflow):
    """Workflow for converting ontology graph to YAML."""

    __configuration: ConvertOntologyGraphToYamlWorkflowConfiguration

    def __init__(self, configuration: ConvertOntologyGraphToYamlWorkflowConfiguration):
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(
            self.__configuration.naas_integration_config
        )

    def graph_to_yaml(
        self, parameters: ConvertOntologyGraphToYamlWorkflowParameters
    ) -> str:
        # Initialize parameters
        logger.debug(f"==> Converting ontology graph to YAML: {parameters.label}")
        yaml_data = None
        ontology_id = parameters.ontology_id

        # Create Graph from turtle string
        g = Graph()
        g.parse(data=parameters.graph, format="turtle")

        # Upload asset to Naas
        asset = self.__naas_integration.upload_asset(
            data=parameters.graph.encode("utf-8"),  # Use the original turtle string
            workspace_id=config.workspace_id,
            storage_name=config.storage_name,
            prefix="assets",
            object_name=str(parameters.label + ".ttl"),
            visibility="public",
        )
        # Save asset URL to JSON
        if asset is None:
            raise ValueError("Failed to upload asset to Naas")

        asset_url = asset.get("asset", {}).get("url")
        if not asset_url:
            raise ValueError("Asset URL not found in response")

        if asset_url.endswith("/"):
            asset_url = asset_url[:-1]

        # Convert to YAML
        try:
            yaml_data = OntologyYaml.rdf_to_yaml(
                g,
                display_relations_names=parameters.display_relations_names,
                class_colors_mapping=parameters.class_colors_mapping,
            )
        except Exception as e:
            message = f"Error converting ontology to YAML: {e}"
            raise e

        # Initialize parameters
        if yaml_data is not None:
            workspace_id = config.workspace_id
            onto_label = parameters.label
            onto_description = parameters.description
            onto_logo_url = parameters.logo_url
            onto_level = parameters.level

            # Get ontology ID if it exists
            ontologies = self.__naas_integration.get_ontologies(workspace_id).get(
                "ontologies", []
            )
            for ontology in ontologies:
                if (
                    ontology
                    and isinstance(ontology, dict)
                    and ontology.get("label") == onto_label
                ):
                    ontology_id = ontology.get("id")
                    break

            if ontology_id is None:
                # Create new ontology
                res = self.__naas_integration.create_ontology(
                    workspace_id=workspace_id,
                    label=onto_label,
                    source=yaml.dump(yaml_data, Dumper=Dumper),
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
                    source=yaml.dump(yaml_data, Dumper=Dumper),
                    level=onto_level,
                    description=onto_description,
                    download_url=asset_url,
                    logo_url=onto_logo_url,
                )
                message = (
                    f"✅ Ontology '{onto_label}' ({ontology_id}) successfully updated."
                )
        logger.info(message)
        if ontology_id is None:
            raise ValueError("Failed to create or update ontology")
        return ontology_id

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="convert_graph_to_yaml",
                description="Convert an ontology graph to YAML.",
                func=lambda **kwargs: self.graph_to_yaml(
                    ConvertOntologyGraphToYamlWorkflowParameters(**kwargs)
                ),
                args_schema=ConvertOntologyGraphToYamlWorkflowParameters,
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
