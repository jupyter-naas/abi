from typing import Dict, List, Optional
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field
import requests
import json
import os
import datetime
import time

@dataclass
class NaasIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Naas integration.
    
    Attributes:
        api_key (str): Naas API key for authentication
        base_url (str): Base URL for Naas API
    """
    api_key: str
    base_url: str = "https://api.naas.ai"

class NaasIntegration(Integration):
    def __init__(self, configuration: NaasIntegrationConfiguration):
        """Initialize Naas client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.__configuration.api_key}"
        }
        
        self.base_url = self.__configuration.base_url
        
        # Test connection
        try:
            self.get_workspaces()
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to connect to Naas: {str(e)}")

    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make HTTP request to Naas API."""
        url = os.path.join(self.base_url, endpoint.lstrip('/'))
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data if method != "POST" else None,
                data=json.dumps(data) if method == "POST" else None,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Naas API request failed: {str(e)}")

    # Workspace methods
    def get_workspaces(self) -> Dict:
        """Get all workspaces."""
        return self._make_request("GET", "/workspace/")

    def get_personal_workspace(self) -> str:
        """Get personal workspace ID."""
        workspaces = self.get_workspaces()
        for workspace in workspaces.get("workspaces", []):
            if workspace.get("is_personal"):
                return workspace.get("id")
        return None

    # Plugin methods
    def create_plugin(self, workspace_id: str, data: Dict) -> Dict:
        """Create a new plugin."""
        payload = {
            "workspace_id": workspace_id,
            "payload": json.dumps(data)
        }
        return self._make_request("POST", f"/workspace/{workspace_id}/plugin", payload)

    def get_plugin(self, workspace_id: str, plugin_id: str = None) -> Dict:
        """Get plugin details by ID or list all plugins."""
        endpoint = f"/workspace/{workspace_id}/plugin/{plugin_id}" if plugin_id else f"/workspace/{workspace_id}/plugin"
        return self._make_request("GET", endpoint)

    def get_plugins(self, workspace_id: str) -> Dict:
        """Get all plugins in the workspace."""
        return self._make_request("GET", f"/workspace/{workspace_id}/plugin")

    def update_plugin(self, workspace_id: str, plugin_id: str, data: Dict) -> Dict:
        """Update an existing plugin."""
        payload = {
            "workspace_id": workspace_id,
            "plugin_id": plugin_id,
            "workspace_plugin": {
                "payload": json.dumps(data)
            }
        }
        return self._make_request("PUT", f"/workspace/{workspace_id}/plugin/{plugin_id}", payload)

    def delete_plugin(self, workspace_id: str, plugin_id: str) -> Dict:
        """Delete a plugin."""
        return self._make_request("DELETE", f"/workspace/{workspace_id}/plugin/{plugin_id}")

    def duplicate_plugin(self, workspace_id: str, plugin_id: str) -> Dict:
        """Duplicate an existing plugin."""
        plugin = self.get_plugin(workspace_id, plugin_id)
        payload = json.loads(plugin['workspace_plugin']['payload'])
        
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        date = f'{date}-utc'
        
        payload['id'] = f"{payload['id']} ({date})"
        payload['name'] = f"{payload['name']} ({date})"
        payload['slug'] = f"{payload['slug']}-{date}"
        
        return self.create_plugin(workspace_id, payload)

    # Ontology methods
    def create_ontology(self, workspace_id: str, label: str, ontology: str, level: str) -> Dict:
        """Create a new ontology."""
        payload = {"ontology": {
            "label": label,
            "source": ontology,
            "workspace_id": workspace_id,
            "level": level
        }}
        return self._make_request("POST", "/ontology/", payload)

    def get_ontology(self, workspace_id: str, ontology_id: str = "") -> Dict:
        """Get ontology by ID."""
        params = {
            "workspace_id": workspace_id
        }
        if ontology_id:
            params["id"] = ontology_id
        return self._make_request("GET", f"/ontology/{ontology_id}", params=params)

    def get_ontologies(self, workspace_id: str) -> Dict:
        """List all ontologies."""
        params = {
            "workspace_id": workspace_id,
            "page_size": 100,
            "page_number": 0
        }
        return self._make_request("GET", "/ontology/", params=params)

    def update_ontology(self, workspace_id: str, ontology_id: str, ontology_source: str = None, level: str = None) -> Dict:
        """Update an existing ontology."""
        field_masks = []

        ontology = {}
        ontology["id"] = ontology_id
        ontology['workspace_id'] = workspace_id

        if ontology_source:
            ontology["source"] = ontology_source
            field_masks.append("source")
        if level:
            ontology["level"] = level
            field_masks.append("level")

        ontology["field_mask"] = {"paths": field_masks}

        payload = {"ontology": ontology}

        return self._make_request("PATCH", f"/ontology/{ontology_id}", payload)

    def delete_ontology(self, workspace_id: str, ontology_id: str) -> Dict:
        """Delete an ontology."""
        params = {"workspace_id": workspace_id}
        return self._make_request("DELETE", f"/ontology/{ontology_id}", params=params)

def as_tools(configuration: NaasIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration = NaasIntegration(configuration)

    class GetWorkspacesSchema(BaseModel):
        pass

    class GetPersonalWorkspaceSchema(BaseModel):
        pass

    class CreatePluginSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to create a plugin in")
        data: Dict = Field(..., description="Plugin configuration data")

    class GetPluginSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to get a plugin from")
        plugin_id: Optional[str] = Field(None, description="Optional plugin ID to get a specific plugin. If not provided, lists all plugins")

    class GetPluginsSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to get plugins from")

    class UpdatePluginSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to update a plugin in")
        plugin_id: str = Field(..., description="ID of the plugin to update")
        data: Dict = Field(..., description="Updated plugin configuration data")

    class DeletePluginSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to delete a plugin from")
        plugin_id: str = Field(..., description="ID of the plugin to delete")

    class DuplicatePluginSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to duplicate a plugin in")
        plugin_id: str = Field(..., description="ID of the plugin to duplicate")

    class CreateOntologySchema(BaseModel): 
        workspace_id: str = Field(..., description="Workspace ID to create an ontology in")
        label: str = Field(..., description="Label for the ontology")
        ontology: str = Field(..., description="Ontology source/content")
        level: str = Field(..., description="Level of the ontology - one of: USE_CASE, DOMAIN, MID, TOP")
    class GetOntologySchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to get an ontology from")
        ontology_id: Optional[str] = Field("", description="Optional ontology ID to get a specific ontology. If not provided, lists all ontologies")

    class GetOntologiesSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to get ontologies from")

    class UpdateOntologySchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to update an ontology in")
        ontology_id: str = Field(..., description="ID of the ontology to update")
        ontology_source: Optional[str] = Field(None, description="Updated ontology source")
        level: Optional[str] = Field(None, description="Updated ontology level")

    class DeleteOntologySchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to delete an ontology from")
        ontology_id: str = Field(..., description="ID of the ontology to delete")

    return [
        StructuredTool(
            name="get_workspaces",
            description="Get all workspaces from naas.ai platform",
            func=lambda: integration.get_workspaces(),
            args_schema=GetWorkspacesSchema
        ),
        StructuredTool(
            name="get_personal_workspace",
            description="Get personal workspace ID from naas.ai platform",
            func=lambda: integration.get_personal_workspace(),
            args_schema=GetPersonalWorkspaceSchema
        ),
        StructuredTool(
            name="create_plugin",
            description="Create a new plugin or assistant from workspace",
            func=lambda workspace_id, data: integration.create_plugin(workspace_id, data),
            args_schema=CreatePluginSchema
        ),
        StructuredTool(
            name="get_plugin",
            description="Get plugin detail or assistant from workspace",
            func=lambda workspace_id, plugin_id: integration.get_plugin(workspace_id, plugin_id),
            args_schema=GetPluginSchema
        ),
        StructuredTool(
            name="get_plugins",
            description="Get all plugins or assistants from workspace",
            func=lambda workspace_id: integration.get_plugins(workspace_id),
            args_schema=GetPluginsSchema
        ),
        StructuredTool(
            name="update_plugin",
            description="Update an existing plugin or assistant from workspace",
            func=lambda workspace_id, plugin_id, data: integration.update_plugin(workspace_id, plugin_id, data),
            args_schema=UpdatePluginSchema
        ),
        StructuredTool(
            name="delete_plugin",
            description="Delete a plugin or assistant from workspace",
            func=lambda workspace_id, plugin_id: integration.delete_plugin(workspace_id, plugin_id),
            args_schema=DeletePluginSchema
        ),
        StructuredTool(
            name="duplicate_plugin",
            description="Duplicate an existing plugin or assistant from workspace",
            func=lambda workspace_id, plugin_id: integration.duplicate_plugin(workspace_id, plugin_id),
            args_schema=DuplicatePluginSchema
        ),
        StructuredTool(
            name="create_ontology",
            description="Create a new ontology from workspace",
            func=lambda workspace_id, label, ontology, level: integration.create_ontology(workspace_id, label, ontology, level),
            args_schema=CreateOntologySchema
        ),
        StructuredTool(
            name="get_ontology",
            description="Get ontology by ID",
            func=lambda workspace_id, ontology_id: integration.get_ontology(workspace_id, ontology_id),
            args_schema=GetOntologySchema
        ),
        StructuredTool(
            name="get_ontologies",
            description="Get all ontologies from workspace",
            func=lambda workspace_id: integration.get_ontologies(workspace_id),
            args_schema=GetOntologiesSchema
        ),
        StructuredTool(
            name="update_ontology",
            description="Update an existing ontology from workspace",
            func=lambda workspace_id, ontology_id, ontology_source, level: integration.update_ontology(workspace_id, ontology_id, ontology_source, level),
            args_schema=UpdateOntologySchema
        ),
        StructuredTool(
            name="delete_ontology",
            description="Delete an ontology from workspace",
            func=lambda workspace_id, ontology_id: integration.delete_ontology(workspace_id, ontology_id),
            args_schema=DeleteOntologySchema
        )
    ]