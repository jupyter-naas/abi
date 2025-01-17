from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
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

class ListAssistantsParameters(WorkflowParameters):
    """Parameters for ListAssistants execution.
    
    Attributes:
        workspace_id (str): The ID of the workspace to list plugins from.
    """
    workspace_id: str = Field(description="The ID of the workspace to list assistants from.")

class GetAssistantParameters(WorkflowParameters):
    """Parameters for GetAssistant execution.
    
    Attributes:
        workspace_id (str): The ID of the workspace to get the assistant from.
        assistant_id (str): The ID of the assistant to get.
    """
    workspace_id: str = Field(description="The ID of the workspace to get the assistant from.")
    assistant_id: str = Field(description="The ID of the assistant to get.")
    
class ListOntologiesParameters(WorkflowParameters):
    """Parameters for ListOntologies execution.
    
    Attributes:
        workspace_id (str): The ID of the workspace to get ontologies from.
    """
    workspace_id: str = Field(description="The ID of the workspace to get ontologies from.")

class GetOntologyParameters(WorkflowParameters):
    """Parameters for GetOntology execution.
    
    Attributes:
        workspace_id (str): The ID of the workspace to get ontologies from.
        ontology_id (str): The ID of the ontology to get.
    """
    workspace_id: str = Field(description="The ID of the workspace to get ontologies from.")
    ontology_id: str = Field(description="The ID of the ontology to get.")

class PublishRemoteAssistantsParameters(WorkflowParameters):
    """Parameters for PublishRemoteAssistants execution.
    
    Attributes:
        workspace_id (str): The ID of the workspace to publish the remote assistants to.
        repo_name (str): The name of the repository storing the remote assistants.
    """
    workspace_id: str = Field(config.workspace_id, description="The ID of the workspace to publish the remote assistants to. Default is the workspace ID set in config.yaml. If default is set, display this value to the user.")
    repo_name: str = Field(config.github_project_repository.split("/")[-1], description="The name of the repository storing the remote assistants. Default is the project repository name set in config.yaml. If default is set, display this value to the user.")

class NaasWorkspaceWorkflows(Workflow):
    """Workflows for listing all Naas workspaces with their IDs and names and getting the personal workspace."""
    
    __configuration: NaasWorkspaceWorkflowsConfiguration
    
    def __init__(self, configuration: NaasWorkspaceWorkflowsConfiguration):
        self.__configuration = configuration
        self.__naas = NaasIntegration(self.__configuration.naas_integration_config)

    def list_workspaces(self, parameters: ListWorkspacesParameters) -> List[Dict[str, str]]:
        """Lists all workspaces with their IDs and names.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing workspace IDs and names
        """
        workspaces = self.__naas.get_workspaces().get("workspaces", [])
        return [{"id": workspace["id"], "name": workspace["name"]} for workspace in workspaces]
    
    def get_workspace(self, parameters: GetWorkspaceParameters) -> Dict[str, str]:
        """Gets the workspace.
        
        Returns:
            Dict[str, str]: Dictionary containing the workspace ID and name
        """
        workspace = self.__naas.get_workspace(parameters.workspace_id).get("workspace", {})
        return workspace    
    
    def get_personal_workspace(self, parameters: GetPersonalWorkspaceParameters) -> Dict[str, str]:
        """Gets the personal workspace.
        
        Returns:
            Dict[str, str]: Dictionary containing the personal workspace ID and name
        """
        return self.__naas.get_personal_workspace()
    
    def list_assistants(self, parameters: ListAssistantsParameters) -> List[Dict[str, str]]:
        """Lists the assistants.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing assistant IDs and names
        """
        assistants = self.__naas.get_plugins(parameters.workspace_id).get("workspace_plugins", [])
        return [{"id": assistant["id"], "name": assistant["name"], "description": assistant["description"]} for assistant in assistants]
    
    def get_assistant(self, parameters: GetAssistantParameters) -> Dict[str, str]:
        """Gets the assistant.
        
        Returns:
            Dict[str, str]: Dictionary containing the assistant ID and name
        """
        assistant = self.__naas.get_plugin(workspace_id=parameters.workspace_id, plugin_id=parameters.assistant_id).get("plugin", {})  
        return assistant  
    
    def list_ontologies(self, parameters: ListOntologiesParameters) -> List[Dict[str, str]]:
        """Gets the ontologies.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing ontology IDs and names
        """
        ontologies = self.__naas.get_ontologies(parameters.workspace_id).get("ontologies", [])
        return [{"id": ontology["id"], "name": ontology["name"], "description": ontology["description"]} for ontology in ontologies]
    
    def get_ontology(self, parameters: GetOntologyParameters) -> Dict[str, str]:
        """Gets the ontology.
        
        Returns:
            Dict[str, str]: Dictionary containing the ontology ID and name
        """
        ontology = self.__naas.get_ontology(workspace_id=parameters.workspace_id, ontology_id=parameters.ontology_id).get("ontology", {})
        return ontology
    
    def publish_remote_assistants(self, parameters: PublishRemoteAssistantsParameters) -> List[str]:
        """Publishes the remote assistants to the workspace.
        
        Returns:
            List[str]: List of messages indicating the status of the publication
        """
        # Init
        results = []

        # Get workspace plugins to check for existing ones
        workspace_plugins = self.__naas.get_plugins(parameters.workspace_id).get('workspace_plugins', [])
        logger.debug(f"Workspace plugins: {len(workspace_plugins)}")

        # Init
        api_path = Path("src/api.py")
        registry_name = f"{parameters.repo_name}-api"
        api_base_url = f"https://{registry_name}.default.space.naas.ai"
        logger.debug(f"API base URL: {api_base_url}")
        api_key = secret.get("ABI_API_KEY")

        # Read the content of the api.py file
        with open(api_path, 'r') as file:
            content = file.read()

        # Get full import paths and run functions
        import_matches = re.findall(r'from (src\.assistants(?:\.\w+)*\.\w+Assistant) import .*', content)

        # Extract run functions from imports
        for import_path in import_matches:
            try:
                # Convert module path to file path
                file_path = Path(*import_path.split('.')).with_suffix('.py')
                
                # Find route_name in content by looking at as_api() calls
                if file_path.exists():
                    with open(file_path, 'r') as file:
                        content = file.read()
                    find_route_name = re.findall(r'route_name:\s*str\s*=\s*"([^"]*)"', content)
                    if find_route_name:
                        route_name = find_route_name[0]
                    else:
                        logger.warning(f"Route name not found in {file_path}")
                        continue
                
                    # Import the module
                    module = importlib.import_module(import_path)
                    file_stem = import_path.split(".")[-1]
                    title = (file_stem.replace("Assistant", " ")) + "Assistant"
                    slug = title.lower().replace(" ", "-").replace("_", "-")
                    description = getattr(module, "DESCRIPTION", "")
                    prompt = getattr(module, "SYSTEM_PROMPT", "")
                    avatar = getattr(module, "AVATAR_URL", "")
                    route_name = file_stem.lower().replace("assistant", "")
                    if "foundation" in import_path:
                        type = "CORE"
                    elif "domain" in import_path:
                        type = "DOMAIN"
                    else:
                        type = "CUSTOM"
                    plugin_data = {
                        "id": "remote-" + slug, 
                        "name": title, 
                        "slug": slug, 
                        "avatar": avatar, 
                        "description": description, 
                        "prompt": prompt, 
                        "prompt_type": "system", 
                        "model": "gpt-4o", 
                        "temperature": 0,
                        "type": type, 
                        "include_ontology": "true",
                        "include_date": "true",
                        "remote": {"url": f"{api_base_url}/assistants/{route_name}/stream-completion?token={api_key}"}
                    }
                    # Check if plugin already exists
                    existing_plugin_id = self.__naas.search_plugin(key='id', value=plugin_data['id'], plugins=workspace_plugins)
                    if existing_plugin_id:
                        self.__naas.update_plugin(
                            workspace_id=parameters.workspace_id,
                            plugin_id=existing_plugin_id,
                            data=plugin_data
                        )
                        message = f"Plugin '{plugin_data['name']}' updated in workspace '{parameters.workspace_id}'"
                    else:
                        self.__naas.create_plugin(
                            workspace_id=parameters.workspace_id,
                            data=plugin_data
                        )
                        message = f"Plugin '{plugin_data['name']}' created in workspace '{parameters.workspace_id}'"
                    logger.debug(message)
                    results.append(message)
                else:
                    logger.warning(f"File not found: {file_path}")
            except Exception as e:
                logger.warning(f"Could not import module {import_path}: {str(e)}")
        return results

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="naas_list_workspaces",
                description="List all Naas workspaces with their IDs and names",
                func=lambda: self.list_workspaces(ListWorkspacesParameters()),
                args_schema=ListWorkspacesParameters
            ),
            StructuredTool(
                name="naas_get_workspace",
                description="Get a Naas workspace detailsby its ID",
                func=lambda workspace_id: self.get_workspace(GetWorkspaceParameters(workspace_id=workspace_id)),
                args_schema=GetWorkspaceParameters
            ),
            StructuredTool(
                name="naas_get_personal_workspace",
                description="Get the personal workspace",
                func=lambda: self.get_personal_workspace(GetPersonalWorkspaceParameters()),
                args_schema=GetPersonalWorkspaceParameters
            ),
            StructuredTool(
                name="naas_list_workspace_assistants",
                description="List the assistants in a given Naas workspace",
                func=lambda workspace_id: self.list_assistants(ListAssistantsParameters(workspace_id=workspace_id)),
                args_schema=ListAssistantsParameters
            ),
            StructuredTool(
                name="naas_get_workspace_assistant",
                description="Get an assistant by its ID",
                func=lambda workspace_id, assistant_id: self.get_assistant(GetAssistantParameters(workspace_id=workspace_id, assistant_id=assistant_id)),
                args_schema=GetAssistantParameters
            ),
            StructuredTool(
                name="naas_list_workspace_ontologies",
                description="List the ontologies in a given Naas workspace",
                func=lambda workspace_id: self.list_ontologies(ListOntologiesParameters(workspace_id=workspace_id)),
                args_schema=ListOntologiesParameters
            ),
            StructuredTool(
                name="naas_get_workspace_ontology",
                description="Get an ontology by its ID",
                func=lambda workspace_id, ontology_id: self.get_ontology(GetOntologyParameters(workspace_id=workspace_id, ontology_id=ontology_id)),
                args_schema=GetOntologyParameters
            ),
            StructuredTool(
                name="publish_remote_assistants_to_workspace",
                description="Publish the remote assistants (available in API) to a given Naas workspace.",
                func=lambda workspace_id, repo_name: self.publish_remote_assistants(PublishRemoteAssistantsParameters(workspace_id=workspace_id, repo_name=repo_name)),
                args_schema=PublishRemoteAssistantsParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass