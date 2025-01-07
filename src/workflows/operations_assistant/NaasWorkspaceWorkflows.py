from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict, Any
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class NaasWorkspaceWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for NaasWorkspaceWorkflows.
    
    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for Naas integration
    """
    naas_integration_config: NaasIntegrationConfiguration

class NaasWorkspaceWorkflowParameters(WorkflowParameters):
    """Parameters for NaasWorkspaceWorkflow execution.
    
    This workflow doesn't require any parameters as it lists all workspaces.
    """
    pass

class GetPersonalWorkspaceParameters(WorkflowParameters):
    """Parameters for GetPersonalWorkspace execution.
    
    This workflow doesn't require any parameters.
    """
    pass

class NaasWorkspaceWorkflows(Workflow):
    """Workflows for listing all Naas workspaces with their IDs and names and getting the personal workspace."""
    
    __configuration: NaasWorkspaceWorkflowsConfiguration
    
    def __init__(self, configuration: NaasWorkspaceWorkflowsConfiguration):
        self.__configuration = configuration
        self.__naas = NaasIntegration(self.__configuration.naas_integration_config)

    def get_workspaces(self, parameters: NaasWorkspaceWorkflowParameters) -> List[Dict[str, str]]:
        """Lists all workspaces with their IDs and names.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing workspace IDs and names
        """
        workspaces = self.__naas.get_workspaces()
        
        # Extract and format workspace information
        workspace_list = []
        for workspace in workspaces.get("workspaces", []):
            workspace_list.append({
                "id": workspace.get("id"),
                "name": workspace.get("name"),
                "is_personal": workspace.get("is_personal", False)
            })
            
        return workspace_list
    
    def get_personal_workspace(self, parameters: GetPersonalWorkspaceParameters) -> Dict[str, str]:
        """Gets the personal workspace.
        
        Returns:
            Dict[str, str]: Dictionary containing the personal workspace ID and name
        """
        return self.__naas.get_personal_workspace()

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="list_naas_workspaces",
                description="List all Naas workspaces with their IDs and names",
                func=lambda **kwargs: self.get_workspaces(NaasWorkspaceWorkflowParameters(**kwargs)),
                args_schema=NaasWorkspaceWorkflowParameters
            ),
            StructuredTool(
                name="get_personal_workspace",
                description="Get the personal workspace",
                func=lambda **kwargs: self.get_personal_workspace(GetPersonalWorkspaceParameters(**kwargs)),
                args_schema=None
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/list_workspaces")
        def list_workspaces(parameters: NaasWorkspaceWorkflowParameters):
            return self.run(parameters) 