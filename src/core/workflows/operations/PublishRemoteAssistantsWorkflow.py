from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import config, secret
from dataclasses import dataclass
from pydantic import Field
from typing import List
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from abi import logger
import re
import importlib
from pathlib import Path
import os

@dataclass
class PublishRemoteAssistantsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for PublishRemoteAssistantsWorkflow.
    
    Attributes:
        naas_integration_config (NaasIntegrationConfiguration): Configuration for Naas integration
        workspace_id (str): The ID of the workspace to publish the remote assistants to
        space_name (str): The name of the space to publish the remote assistants to
    """
    naas_integration_config: NaasIntegrationConfiguration
    workspace_id: str = config.workspace_id
    space_name: str = config.space_name

class PublishRemoteAssistantsWorkflow(Workflow):
    """Workflow for publishing remote assistants to a Naas workspace."""
    
    __configuration: PublishRemoteAssistantsWorkflowConfiguration
    
    def __init__(self, configuration: PublishRemoteAssistantsWorkflowConfiguration):
        self.__configuration = configuration
        self.__naas = NaasIntegration(self.__configuration.naas_integration_config)

    def publish_remote_assistants(self) -> List[str]:
        """Publishes the remote assistants to the workspace.
        
        Returns:
            List[str]: List of messages indicating the status of the publication
        """
        # Init
        results = []

        # Get workspace plugins to check for existing ones
        workspace_plugins = self.__naas.get_plugins(self.__configuration.workspace_id).get('workspace_plugins', [])
        logger.debug(f"Workspace plugins: {len(workspace_plugins)}")

        # Init
        api_path = Path("src/api.py")
        registry_name = f"{self.__configuration.space_name}-api"
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
                        "model": "anthropic.claude-3-5-sonnet-20240620-v1:0", 
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
                            workspace_id=self.__configuration.workspace_id,
                            plugin_id=existing_plugin_id,
                            data=plugin_data
                        )
                        message = f"Plugin '{plugin_data['name']}' updated in workspace '{self.__configuration.workspace_id}'"
                    else:
                        self.__naas.create_plugin(
                            workspace_id=self.__configuration.workspace_id,
                            data=plugin_data
                        )
                        message = f"Plugin '{plugin_data['name']}' created in workspace '{self.__configuration.workspace_id}'"
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
                name="publish_remote_assistants",
                description="Publish remote assistants to a Naas workspace",
                func=self.publish_remote_assistants,
                args_schema=None
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
    
if __name__ == "__main__":
    configuration = PublishRemoteAssistantsWorkflowConfiguration(
        naas_integration_config=NaasIntegrationConfiguration(
            api_key=secret.get('NAAS_API_KEY')
        )
    )
    workflow = PublishRemoteAssistantsWorkflow(configuration)
    workflow.publish_remote_assistants()