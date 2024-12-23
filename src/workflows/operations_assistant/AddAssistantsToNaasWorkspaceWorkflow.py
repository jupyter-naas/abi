from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Dict, Optional
from abi import logger
from fastapi import APIRouter
import json

@dataclass
class AddAssistantsToNaasWorkspaceConfiguration(WorkflowConfiguration):
    """Configuration for adding assistants to a Naas workspace.
    
    Attributes:
        naas_integration_config: Configuration for Naas integration
    """
    naas_integration_config: NaasIntegrationConfiguration

class AddAssistantsToNaasWorkspaceParameters(BaseModel):
    """Parameters for AddAssistantsToNaasWorkspace execution.
    
    Attributes:
        workspace_id: ID of the workspace to create the plugin in
        name: Name of the plugin
        description: Description of the plugin
        model: LLM model to use (default: gpt-4)
        temperature: Model temperature (default: 0.7)
        system_prompt: System prompt for the plugin
        tools: List of tools to enable (optional)
    """
    workspace_id: str = Field(..., description="The workspace ID where the plugin will be created. Must comes from user input.")

class AddAssistantsToNaasWorkspace(Workflow):
    """Workflow for adding assistants to a Naas workspace."""
    __configuration: AddAssistantsToNaasWorkspaceConfiguration
    
    def __init__(self, configuration: AddAssistantsToNaasWorkspaceConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__naas_integration = NaasIntegration(self.__configuration.naas_integration_config)

    def find_existing_plugin(self, plugins, key, value):
        """Helper function to find existing plugin by key/value pair."""
        for i, p in enumerate(plugins):
            plugin_id = p.get("id")
            p_json = json.loads(p.get("payload"))
            identifier = p_json.get(key)
            if identifier == value:
                return plugin_id
        return None

    def run(self, parameters: AddAssistantsToNaasWorkspaceParameters) -> Dict:
        """Creates a new plugin in the specified Naas workspace.
        
        Args:
            parameters: Plugin creation parameters
            
        Returns:
            Dict: Created plugin details
        """
        # Import assistant modules dynamically
        from importlib import import_module
        
        # List of assistant module paths and names
        assistant_configs = [
            ('OpenDataAssistant', 'OpenData Assistant'),
            ('ContentAssistant', 'Content Assistant'), 
            ('GrowthAssistant', 'Growth Assistant'),
            ('SalesAssistant', 'Sales Assistant'),
            ('OperationsAssistant', 'Operations Assistant'),
            ('FinanceAssistant', 'Finance Assistant')
        ]
        
        # Build assistants dict dynamically
        assistants = {}
        for module_name, assistant_name in assistant_configs:
            try:
                # Import each assistant module dynamically
                module = import_module(f'src.assistants.domain.{module_name}')
                assistants[assistant_name] = {
                    'instructions': module.SYSTEM_PROMPT,
                    'description': module.DESCRIPTION,
                    'avatar_url': module.AVATAR_URL
                }
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to load assistant {assistant_name}: {str(e)}")
                continue
        logger.debug(f"Assistants: {assistants}")
        
        # Get workspace plugins to check for existing ones
        workspace_plugins = self.__naas_integration.get_plugins(parameters.workspace_id).get('workspace_plugins', [])
        logger.debug(f"Workspace plugins: {len(workspace_plugins)}")
        
        results = []
        for assistant_name, assistant_config in assistants.items():
            plugin_data = {
                'id': assistant_name.lower().replace(' ', '_'),
                "name": f"{assistant_name}",
                "prompt": assistant_config['instructions'],
                "prompt_type": "system", 
                "slug": f"{assistant_name.lower().replace(' ', '-')}",
                "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "temperature": 0.1,
                "description": assistant_config['description'],
                "avatar": assistant_config['avatar_url'],
                "include_ontology": "true",
                "include_date": "true",
                "type": "DOMAIN"
            }
            logger.debug(f"Plugin data: {plugin_data}")

            # Check if plugin already exists
            existing_plugin_id = self.find_existing_plugin(workspace_plugins, 'id', plugin_data['id'])
            if existing_plugin_id:
                result = self.__naas_integration.update_plugin(
                    workspace_id=parameters.workspace_id,
                    plugin_id=existing_plugin_id,
                    data=plugin_data
                )
            else:
                result = self.__naas_integration.create_plugin(
                    workspace_id=parameters.workspace_id,
                    data=plugin_data
                )
            results.append(result)
        
        return results
    
    def as_tools(self) -> list:
        """Returns a list of LangChain tools for this workflow."""
        from langchain_core.tools import StructuredTool
        
        return [StructuredTool(
            name="publish_assistants_to_naas_workspace",
            description="Publish domain assistants (OpenDataAssistant, ContentAssistant, GrowthAssistant, SalesAssistant, OperationsAssistant, FinanceAssistant) to a given Naas workspace",
            func=lambda **kwargs: self.run(AddAssistantsToNaasWorkspaceParameters(**kwargs)),
            args_schema=AddAssistantsToNaasWorkspaceParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/add_assistants_to_naas_workspace")
        def add_assistants_to_naas_workspace(parameters: AddAssistantsToNaasWorkspaceParameters):
            return self.run(parameters)
