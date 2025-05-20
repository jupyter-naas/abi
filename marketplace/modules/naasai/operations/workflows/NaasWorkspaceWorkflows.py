from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.modules.common.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict, Any
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import json
from src import config
import importlib
from abi import logger
from pathlib import Path
import re
from src import secret
from typing import Optional


@dataclass
class NaasWorkspaceWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for NaasWorkspaceWorkflows.

    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for Naas integration
    """

    naas_integration_config: NaasIntegrationConfiguration


class ListWorkspacesParameters(WorkflowParameters):
    """Parameters for ListWorkspaces execution.

    This workflow doesn't require any parameters as it lists all workspaces.
    """

    pass


class GetWorkspaceParameters(WorkflowParameters):
    """Parameters for GetWorkspace execution.

    Attributes:
        workspace_id (str): The ID of the workspace to get.
    """

    workspace_id: str = Field(description="The ID of the workspace to get.")


class GetPersonalWorkspaceParameters(WorkflowParameters):
    """Parameters for GetPersonalWorkspace execution.

    This workflow doesn't require any parameters.
    """

    pass


class ListAgentsParameters(WorkflowParameters):
    """Parameters for ListAgents execution.

    Attributes:
        workspace_id (str): The ID of the workspace to list plugins from.
    """

    workspace_id: str = Field(
        description="The ID of the workspace to list agents from."
    )


class GetAssistantParameters(WorkflowParameters):
    """Parameters for GetAssistant execution.

    Attributes:
        workspace_id (str): The ID of the workspace to get the assistant from.
        assistant_id (str): The ID of the assistant to get.
    """

    workspace_id: str = Field(
        description="The ID of the workspace to get the assistant from."
    )
    assistant_id: str = Field(description="The ID of the assistant to get.")


class ListOntologiesParameters(WorkflowParameters):
    """Parameters for ListOntologies execution.

    Attributes:
        workspace_id (str): The ID of the workspace to get ontologies from.
    """

    workspace_id: str = Field(
        description="The ID of the workspace to get ontologies from."
    )


class GetOntologyParameters(WorkflowParameters):
    """Parameters for GetOntology execution.

    Attributes:
        workspace_id (str): The ID of the workspace to get ontologies from.
        ontology_id (str): The ID of the ontology to get.
    """

    workspace_id: str = Field(
        description="The ID of the workspace to get ontologies from."
    )
    ontology_id: str = Field(description="The ID of the ontology to get.")


class NaasWorkspaceWorkflows(Workflow):
    """Workflows for listing all Naas workspaces with their IDs and names and getting the personal workspace."""

    __configuration: NaasWorkspaceWorkflowsConfiguration

    def __init__(self, configuration: NaasWorkspaceWorkflowsConfiguration):
        self.__configuration = configuration
        self.__naas = NaasIntegration(self.__configuration.naas_integration_config)

    def list_workspaces(
        self, parameters: ListWorkspacesParameters
    ) -> List[Dict[str, str]]:
        """Lists all workspaces with their IDs and names.

        Returns:
            List[Dict[str, str]]: List of dictionaries containing workspace IDs and names
        """
        workspaces = self.__naas.get_workspaces().get("workspaces", [])
        return [
            {"id": workspace["id"], "name": workspace["name"]}
            for workspace in workspaces
        ]

    def get_workspace(self, parameters: GetWorkspaceParameters) -> Dict[str, str]:
        """Gets the workspace.

        Returns:
            Dict[str, str]: Dictionary containing the workspace ID and name
        """
        workspace = self.__naas.get_workspace(parameters.workspace_id).get(
            "workspace", {}
        )
        return workspace

    def get_personal_workspace(
        self, parameters: GetPersonalWorkspaceParameters
    ) -> Dict[str, str]:
        """Gets the personal workspace.

        Returns:
            Dict[str, str]: Dictionary containing the personal workspace ID and name
        """
        return self.__naas.get_personal_workspace()

    def list_agents(self, parameters: ListAgentsParameters) -> List[Dict[str, str]]:
        """Lists the agents.

        Returns:
            List[Dict[str, str]]: List of dictionaries containing assistant IDs and names
        """
        agents = self.__naas.get_plugins(parameters.workspace_id).get(
            "workspace_plugins", []
        )
        return [
            {
                "id": assistant["id"],
                "name": assistant["name"],
                "description": assistant["description"],
            }
            for assistant in agents
        ]

    def get_agent(self, parameters: GetAssistantParameters) -> Dict[str, str]:
        """Gets the assistant.

        Returns:
            Dict[str, str]: Dictionary containing the assistant ID and name
        """
        assistant = self.__naas.get_plugin(
            workspace_id=parameters.workspace_id, plugin_id=parameters.assistant_id
        ).get("plugin", {})
        return assistant

    def list_ontologies(
        self, parameters: ListOntologiesParameters
    ) -> List[Dict[str, str]]:
        """Gets the ontologies.

        Returns:
            List[Dict[str, str]]: List of dictionaries containing ontology IDs and names
        """
        ontologies = self.__naas.get_ontologies(parameters.workspace_id).get(
            "ontologies", []
        )
        return [
            {
                "id": ontology["id"],
                "name": ontology["name"],
                "description": ontology["description"],
            }
            for ontology in ontologies
        ]

    def get_ontology(self, parameters: GetOntologyParameters) -> Dict[str, str]:
        """Gets the ontology.

        Returns:
            Dict[str, str]: Dictionary containing the ontology ID and name
        """
        ontology = self.__naas.get_ontology(
            workspace_id=parameters.workspace_id, ontology_id=parameters.ontology_id
        ).get("ontology", {})
        return ontology

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="naas_list_workspaces",
                description="List all Naas workspaces with their IDs and names",
                func=lambda: self.list_workspaces(ListWorkspacesParameters()),
                args_schema=ListWorkspacesParameters,
            ),
            StructuredTool(
                name="naas_get_workspace",
                description="Get a Naas workspace detailsby its ID",
                func=lambda workspace_id: self.get_workspace(
                    GetWorkspaceParameters(workspace_id=workspace_id)
                ),
                args_schema=GetWorkspaceParameters,
            ),
            StructuredTool(
                name="naas_get_personal_workspace",
                description="Get the personal workspace",
                func=lambda: self.get_personal_workspace(
                    GetPersonalWorkspaceParameters()
                ),
                args_schema=GetPersonalWorkspaceParameters,
            ),
            StructuredTool(
                name="naas_list_workspace_agents",
                description="List the agents in a given Naas workspace",
                func=lambda workspace_id: self.list_agents(
                    ListAgentsParameters(workspace_id=workspace_id)
                ),
                args_schema=ListAgentsParameters,
            ),
            StructuredTool(
                name="naas_get_workspace_agent",
                description="Get an assistant by its ID",
                func=lambda workspace_id, assistant_id: self.get_agent(
                    GetAssistantParameters(
                        workspace_id=workspace_id, assistant_id=assistant_id
                    )
                ),
                args_schema=GetAssistantParameters,
            ),
            StructuredTool(
                name="naas_list_workspace_ontologies",
                description="List the ontologies in a given Naas workspace",
                func=lambda workspace_id: self.list_ontologies(
                    ListOntologiesParameters(workspace_id=workspace_id)
                ),
                args_schema=ListOntologiesParameters,
            ),
            StructuredTool(
                name="naas_get_workspace_ontology",
                description="Get an ontology by its ID",
                func=lambda workspace_id, ontology_id: self.get_ontology(
                    GetOntologyParameters(
                        workspace_id=workspace_id, ontology_id=ontology_id
                    )
                ),
                args_schema=GetOntologyParameters,
            ),
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
