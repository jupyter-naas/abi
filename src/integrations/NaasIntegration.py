from typing import Dict, List, Optional
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field
import requests
import json
import os
from abi import logger
import jwt

LOGO_URL = "https://logo.clearbit.com/naas.ai"

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
    """Naas integration class for interacting with Naas API.
    
    This class provides methods to interact with Naas's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (NaasIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: NaasIntegrationConfiguration

    def __init__(self, configuration: NaasIntegrationConfiguration):
        """Initialize Naas client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.__configuration.api_key}"
        }
        
        self.base_url = self.__configuration.base_url

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
        
    def get_user_id_from_jwt(self, jwt_token):
        try:
            decoded = jwt.decode(jwt_token, algorithms=["HS256"], options={"verify_signature": False})
            user_id = decoded.get("sub")
            logger.debug(f"User ID from JWT: {user_id}")
            return user_id
        except Exception as e:
            logger.error(f"Error decoding JWT: {str(e)}")
            return None

    def create_workspace(self, name: str, is_personal: bool = False, **kwargs) -> Dict:
        """Create a new workspace.
        
        Args:
            name (str): Name of the workspace
            is_personal (bool, optional): Whether this is a personal workspace. Defaults to True.
            **kwargs: Optional workspace customization parameters including:
                - fav_icon (str): Favicon URL
                - large_logo (str): Large logo URL
                - small_logo (str): Small logo URL
                - primary_color (str): Primary color hex code
                - secondary_color (str): Secondary color hex code
                - tertiary_color (str): Tertiary color hex code
                - text_primary_color (str): Primary text color hex code
                - text_secondary_color (str): Secondary text color hex code
        
        Returns:
            Dict: Response from the API containing the created workspace details
        """
        payload = {
            "user_id": self.get_user_id_from_jwt(self.__configuration.api_key),  # API expects this field but uses the authenticated user
            "workspace": {
                "name": name,
                "is_personal": is_personal,
                "fav_icon": kwargs.get("fav_icon", ""),
                "large_logo": kwargs.get("large_logo", ""),
                "small_logo": kwargs.get("small_logo", ""),
                "primary_color": kwargs.get("primary_color", "#48DD82"),
                "secondary_color": kwargs.get("secondary_color", "#181a1c"), 
                "tertiary_color": kwargs.get("tertiary_color", "#3c3f40"),
                "text_primary_color": kwargs.get("text_primary_color", "#fff"),
                "text_secondary_color": kwargs.get("text_secondary_color", "#747677")
            }
        }
        logger.debug(f"Payload: {payload}")
        return self._make_request("POST", "/workspace", payload)

    def get_workspace(self, workspace_id: str) -> Dict:
        """Get workspace details by ID.
        
        Args:
            workspace_id (str): ID of the workspace to retrieve
        
        Returns:
            Dict: Response from the API containing the workspace details
        """
        payload = {
            "user_id": self.get_user_id_from_jwt(self.__configuration.api_key),  # API expects this field but uses the authenticated user
            "workspace_id": workspace_id
        }
        return self._make_request("GET", f"/workspace/{workspace_id}", payload)
    
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
    
    def update_workspace(self, workspace_id: str, **kwargs) -> Dict:
        """Update an existing workspace.
        
        Args:
            workspace_id (str): ID of the workspace to update
            **kwargs: Optional workspace customization parameters including:
                - name (str): New name for the workspace
                - fav_icon (str): Favicon URL
                - large_logo (str): Large logo URL
                - small_logo (str): Small logo URL
                - primary_color (str): Primary color hex code
                - secondary_color (str): Secondary color hex code
                - tertiary_color (str): Tertiary color hex code
                - text_primary_color (str): Primary text color hex code
                - text_secondary_color (str): Secondary text color hex code
        """
        workspace = {
            "workspace_id": workspace_id,
            "workspace": {
                "name": kwargs.get("name", ""),
                "fav_icon": kwargs.get("fav_icon", ""),
                "large_logo": kwargs.get("large_logo", ""),
                "small_logo": kwargs.get("small_logo", ""),
                "primary_color": kwargs.get("primary_color", ""),
                "secondary_color": kwargs.get("secondary_color", ""),
                "tertiary_color": kwargs.get("tertiary_color", ""),
                "text_primary_color": kwargs.get("text_primary_color", ""),
                "text_secondary_color": kwargs.get("text_secondary_color", "")
            }
        }
        return self._make_request("PUT", f"/workspace/{workspace_id}", workspace)
    
    def delete_workspace(self, workspace_id: str) -> Dict:
        """Delete a workspace.
        
        Args:
            workspace_id (str): ID of the workspace to delete
        
        Returns:
            Dict: Response from the API containing the deletion status
        """
        payload = {
            "user_id": self.get_user_id_from_jwt(self.__configuration.api_key),  # API expects this field but uses the authenticated user
            "workspace_id": workspace_id
        }
        return self._make_request("DELETE", f"/workspace/{workspace_id}", payload)

    def create_plugin(self, workspace_id: str, data: Dict) -> Dict:
        """Create a new plugin.
        
        Args:
            workspace_id (str): Workspace ID
            data (Dict): Plugin configuration data
        """
        payload = {
            "workspace_id": workspace_id,
            "payload": json.dumps(data)
        }
        return self._make_request("POST", f"/workspace/{workspace_id}/plugin", payload)

    def get_plugin(self, workspace_id: str, plugin_id: str = None) -> Dict:
        """Get plugin details by ID or list all plugins.
        
        Args:
            workspace_id (str): Workspace ID
            plugin_id (str): Plugin ID
        """
        endpoint = f"/workspace/{workspace_id}/plugin/{plugin_id}" if plugin_id else f"/workspace/{workspace_id}/plugin"
        return self._make_request("GET", endpoint)

    def get_plugins(self, workspace_id: str) -> Dict:
        """Get all plugins in the workspace."""
        return self._make_request("GET", f"/workspace/{workspace_id}/plugin")

    def update_plugin(self, workspace_id: str, plugin_id: str, data: Dict) -> Dict:
        """Update an existing plugin.
        
        Args:
            workspace_id (str): Workspace ID
            plugin_id (str): Plugin ID
            data (Dict): Updated plugin configuration data
        """
        payload = {
            "workspace_id": workspace_id,
            "plugin_id": plugin_id,
            "workspace_plugin": {
                "payload": json.dumps(data)
            }
        }
        return self._make_request("PUT", f"/workspace/{workspace_id}/plugin/{plugin_id}", payload)

    def delete_plugin(self, workspace_id: str, plugin_id: str) -> Dict:
        """Delete a plugin.
        
        Args:
            workspace_id (str): Workspace ID
            plugin_id (str): Plugin ID
        """
        return self._make_request("DELETE", f"/workspace/{workspace_id}/plugin/{plugin_id}")
    
    def search_plugin(self, key: str, value: str, plugins: List[Dict[str, str]] = [], workspace_id: str = None) -> Dict[str, str]:
        """Search for an assistant by key/value pair in payload.
        
        Returns:
            Dict[str, str]: Dictionary containing the assistant ID and name
        """
        if not plugins:
            plugins = self.get_plugins(workspace_id).get("workspace_plugins", [])
        for i, a in enumerate(plugins):
            plugin_id = a.get("id")
            a_json = json.loads(a.get("payload"))
            identifier = a_json.get(key)
            if identifier == value:
                return plugin_id
        return None
    
    # Ontology methods
    def create_ontology(
        self,
        workspace_id: str,
        label: str,
        source: str,
        level: str,
        description: str = None,
        logo_url: str = None,
        is_public: bool = False
    ) -> Dict:
        """Create a new ontology.
        
        Args:
            workspace_id (str): Workspace ID
            label (str): Label for the ontology
            source (str): Ontology source/content
            level (str): Level of the ontology - one of: USE_CASE, DOMAIN, MID, TOP
            description (str, optional): Description of the ontology
            logo_url (str, optional): Logo URL for the ontology
            is_public (bool, optional): Whether the ontology is public
        """
        payload = {"ontology": {
            "label": label,
            "source": source,
            "workspace_id": workspace_id,
            "level": level,
            "description": description,
            "logo_url": logo_url,
            "is_public": is_public
        }}
        return self._make_request("POST", "/ontology/", payload)

    def get_ontology(self, workspace_id: str, ontology_id: str = "") -> Dict:
        """Get ontology by ID.
        
        Args:
            workspace_id (str): Workspace ID
            ontology_id (str): Ontology ID
        """
        params = {
            "workspace_id": workspace_id
        }
        if ontology_id:
            params["id"] = ontology_id
        return self._make_request("GET", f"/ontology/{ontology_id}", params=params)

    def get_ontologies(self, workspace_id: str) -> Dict:
        """List all ontologies.
        
        Args:
            workspace_id (str): Workspace ID
        """
        params = {
            "workspace_id": workspace_id,
            "page_size": 100,
            "page_number": 0
        }
        return self._make_request("GET", "/ontology/", params=params)

    def update_ontology(
            self,
            workspace_id: str,
            ontology_id: str,
            download_url: str = None,
            source: str = None,
            level: str = None,
            description: str = None,
            logo_url: str = None,
            is_public: bool = False
        ) -> Dict:
        """Update an existing ontology.
        
        Args:
            workspace_id (str): Workspace ID
            ontology_id (str): Ontology ID
            download_url (str): Download URL
            source (str): Source
            level (str): Level
            description (str): Description
            logo_url (str): Logo URL
            is_public (bool): Whether the ontology is public
        """
        field_masks = []

        ontology = {}
        ontology["id"] = ontology_id
        ontology['workspace_id'] = workspace_id

        if download_url:
            ontology["download_url"] = download_url
            field_masks.append("download_url")
        if source:
            ontology["source"] = source
            field_masks.append("source")
        if level:
            ontology["level"] = level
            field_masks.append("level")
        if description:
            ontology["description"] = description
            field_masks.append("description")
        if logo_url:
            ontology["logo_url"] = logo_url
            field_masks.append("logo_url")
        if is_public:
            ontology["is_public"] = is_public
            field_masks.append("is_public")

        ontology["field_mask"] = {"paths": field_masks}

        payload = {"ontology": ontology}

        return self._make_request("PATCH", f"/ontology/{ontology_id}", payload)

    def delete_ontology(self, workspace_id: str, ontology_id: str) -> Dict:
        """Delete an ontology.
        
        Args:
            workspace_id (str): Workspace ID
            ontology_id (str): Ontology ID
        """
        params = {"workspace_id": workspace_id}
        return self._make_request("DELETE", f"/ontology/{ontology_id}", params=params)

    def get_workspace_users(self, workspace_id: str) -> Dict:
        """List all users in a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
        
        Returns:
            Dict: Response containing list of workspace users
        """
        return self._make_request("GET", f"/workspace/{workspace_id}/user")

    def invite_workspace_user(self, workspace_id: str, role: str = "member", email: str = None, user_id: str = None) -> Dict:
        """Invite a user to a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            role (str): Role to assign to the user - one of: "member", "admin", "owner"
            email (str, optional): Email of the user to invite. Required if user_id not provided.
            user_id (str, optional): User ID if known. Required if email not provided.
        
        Returns:
            Dict: Response containing the created workspace user details
            
        Raises:
            ValueError: If neither email nor user_id is provided
        """
        if not email and not user_id:
            raise ValueError("Either email or user_id must be provided")
            
        payload = {
            "workspace_id": workspace_id,
            "role": role
        }
        
        if email:
            payload["email"] = email
        if user_id:
            payload["user_id"] = user_id
            
        return self._make_request("POST", f"/workspace/{workspace_id}/user/", payload)

    def get_workspace_user(self, workspace_id: str, user_id: str) -> Dict:
        """Get details of a specific user in a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            user_id (str): ID of the user
        
        Returns:
            Dict: Response containing the workspace user details
        """
        payload = {
            "user_id": user_id,
            "workspace_id": workspace_id
        }
        return self._make_request("GET", f"/workspace/{workspace_id}/user/{user_id}", payload)

    def update_workspace_user(self, workspace_id: str, user_id: str, role: str = None, status: str = None) -> Dict:
        """Update a user's role or status in a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            user_id (str): ID of the user
            role (str, optional): New role for the user
            status (str, optional): New status for the user
        
        Returns:
            Dict: Response containing the updated workspace user details
        """
        workspace_user = {}
        if role is not None:
            workspace_user["role"] = role
        if status is not None:
            workspace_user["status"] = status
        
        payload = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "workspace_user": workspace_user
        }
        return self._make_request("PUT", f"/workspace/{workspace_id}/user/{user_id}", payload)

    def delete_workspace_user(self, workspace_id: str, user_id: str) -> Dict:
        """Remove a user from a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            user_id (str): ID of the user to remove
        
        Returns:
            Dict: Response containing the deletion status
        """
        payload = {
            "user_id": user_id,
            "workspace_id": workspace_id
        }
        return self._make_request("DELETE", f"/workspace/{workspace_id}/user/{user_id}", payload)

    def get_secret(self, secret_id: str) -> Dict:
        """Get a specific secret from a workspace.
        
        Args:
            secret_id (str): ID of the secret
        
        Returns:
            Dict: Response containing the secret details
        """
        return self._make_request("GET", f"/secret/{secret_id}")

    def list_secrets(self) -> Dict:
        """List all secrets in a workspace.
    
        Returns:
            Dict: Response containing list of secrets
        """
        payload = {
            "page_size": 100,
            "page_number": 0
        }
        return self._make_request("GET", f"/secret/", payload).get("secrets", [])
    
    def list_secrets_names(self) -> Dict:
        secrets = self.list_secrets()
        return [secret.get("name") for secret in secrets]

    def create_secret(self, name: str, value: str) -> Dict:
        """Create a new secret in a workspace.
        
        Args:
            name (str): Name of the secret
            value (str): Value of the secret
        
        Returns:
            Dict: Response containing the created secret details
        """
        payload = {
            "secret": {
                "name": name,
                "value": value
            }
        }
        return self._make_request("POST", f"/secret/", payload)

    def update_secret(self, secret_id: str, value: str) -> Dict:
        """Update an existing secret in a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            secret_id (str): ID of the secret to update
            value (str): New value for the secret
        
        Returns:
            Dict: Response containing the updated secret details
        """
        payload = {
            "secret": {
                "value": value
            }
        }
        return self._make_request("PUT", f"/secret/{secret_id}", payload)

    def delete_secret(self, secret_id: str) -> Dict:
        """Delete a secret from a workspace.
        
        Args:
            secret_id (str): ID of the secret to delete
        
        Returns:
            Dict: Response containing the deletion status
        """
        return self._make_request("DELETE", f"/secret/{secret_id}")

    def list_workspace_storage(self, workspace_id: str) -> Dict:
        """List all storage in a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            
        Returns:
            Dict: Response containing list of storage
        """
        return self._make_request("GET", f"/workspace/{workspace_id}/storage/")
    
    def list_workspace_storage_objects(self, workspace_id: str, storage_name: str, prefix: str) -> Dict:
        """List objects and subdirectories in a workspace storage location.
        
        Args:
            workspace_id (str): ID of the workspace containing the storage
            storage_name (str): Name of the storage to list objects from
            prefix (str): Directory prefix to list objects under
            
        Returns:
            Dict: Response containing list of objects or error details
            
        Raises:
            IntegrationConnectionError: If API request fails
        """
        params = {"prefix": prefix}
        return self._make_request(
            "GET", 
            f"/workspace/{workspace_id}/storage/{storage_name}/",
            params=params
        )

    def create_workspace_storage(self, workspace_id: str, storage_name: str) -> Dict:
        """Create a new storage in a workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            storage_name (str): Name of the storage
            
        Returns:
            Dict: Response containing the created storage details
        """
        payload = {"storage": {"name": storage_name}}
        return self._make_request("POST", f"/workspace/{workspace_id}/storage/", payload)

    def create_workspace_storage_credentials(self, workspace_id: str, storage_name: str) -> Dict:
        """Create credentials for workspace storage.
        
        Args:
            workspace_id (str): ID of the workspace
            storage_name (str): Name of the storage
            
        Returns:
            Dict: Response containing the storage credentials
        """
        payload = {
            "name": storage_name,
            "workspace_id": workspace_id
        }
        return self._make_request("POST", f"/workspace/{workspace_id}/storage/credentials/", payload)

    def get_storage_credentials(self, workspace_id: str = None, storage_name: str = None) -> tuple[Dict, str]:
        """Get or create storage credentials.
        
        Args:
            workspace_id (str, optional): ID of the workspace. If not provided, uses personal workspace
            storage_name (str, optional): Name of the storage
            
        Returns:
            tuple[Dict, str]: Tuple containing (credentials, workspace_id)
        """

        # List storage
        result = self.list_workspace_storage(workspace_id)
        storages = result.get("storage", [])
        storage_exist = False
        for storage in storages:
            if storage.get("name") == storage_name:
                storage_exist = True
                break
                
        # Create storage if it doesn't exist
        if not storage_exist:
            new_storage = self.create_workspace_storage(workspace_id, storage_name)
            logger.info(f"Created storage {storage_name} in workspace {workspace_id}")
            
        # Get storage credentials
        credentials = self.create_workspace_storage_credentials(workspace_id, storage_name)
        return credentials
    
    def create_asset(
        self,
        workspace_id: str,
        storage_name: str,
        object_name: str,
        visibility: str = "public",
        content_disposition: str = "inline",
        password: str = None
    ) -> Dict:
        """Create a new asset in the workspace.
        
        Args:
            workspace_id (str): ID of the workspace
            storage_name (str): Name of the storage to create asset in
            object_name (str): Name of the object/file in storage
            visibility (str, optional): Asset visibility. Defaults to "private"
            content_disposition (str, optional): Content disposition header. Defaults to "inline"
            password (str, optional): Password protection for asset. Defaults to None
            
        Returns:
            Dict: Response containing the created asset details
        """
        data = {
            "workspace_id": workspace_id,
            "asset_creation": {
                "workspace_id": workspace_id,
                "storage_name": storage_name,
                "object_name": object_name,
                "visibility": visibility,
                "content_disposition": content_disposition,
                "password": password,
            }
        }
        return self._make_request("POST", f"/workspace/{workspace_id}/asset/", data)

    def update_asset(self, workspace_id: str, asset_id: str, data: Dict) -> Dict:
        """Update an existing asset.
        
        Args:
            workspace_id (str): ID of the workspace
            asset_id (str): ID of the asset to update
            data (Dict): Updated asset data
            
        Returns:
            Dict: Response containing the updated asset details
        """
        return self._make_request("PUT", f"/workspace/{workspace_id}/asset/{asset_id}", data)

    def get_asset(self, workspace_id: str, asset_id: str) -> Dict:
        """Get asset details by ID.
        
        Args:
            workspace_id (str): ID of the workspace
            asset_id (str): ID of the asset to retrieve
            
        Returns:
            Dict: Response containing the asset details
        """
        return self._make_request("GET", f"/workspace/{workspace_id}/asset/{asset_id}")


def as_tools(configuration: NaasIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration = NaasIntegration(configuration)

    class CreateWorkspaceSchema(BaseModel):
        name: str = Field(..., description="Name of the workspace")
        fav_icon: Optional[str] = Field("", description="Favicon URL")
        large_logo: Optional[str] = Field("", description="Large logo URL")
        small_logo: Optional[str] = Field("", description="Small logo URL")
        primary_color: Optional[str] = Field("", description="Primary color hex code")
        secondary_color: Optional[str] = Field("", description="Secondary color hex code")
        tertiary_color: Optional[str] = Field("", description="Tertiary color hex code")
        text_primary_color: Optional[str] = Field("", description="Primary text color hex code")
        text_secondary_color: Optional[str] = Field("", description="Secondary text color hex code")

    class GetWorkspacesSchema(BaseModel):
        pass

    class GetPersonalWorkspaceSchema(BaseModel):
        pass

    class GetWorkspaceSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace to retrieve")

    class UpdateWorkspaceSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace to update")
        name: Optional[str] = Field(None, description="New name for the workspace")
        fav_icon: Optional[str] = Field(None, description="Favicon URL")
        large_logo: Optional[str] = Field(None, description="Large logo URL")
        small_logo: Optional[str] = Field(None, description="Small logo URL")
        primary_color: Optional[str] = Field(None, description="Primary color hex code")
        secondary_color: Optional[str] = Field(None, description="Secondary color hex code")
        tertiary_color: Optional[str] = Field(None, description="Tertiary color hex code")
        text_primary_color: Optional[str] = Field(None, description="Primary text color hex code")
        text_secondary_color: Optional[str] = Field(None, description="Secondary text color hex code")
        
    class DeleteWorkspaceSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace to delete")
        
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

    class CreateOntologySchema(BaseModel): 
        workspace_id: str = Field(..., description="Workspace ID to create an ontology in")
        label: str = Field(..., description="Label for the ontology")
        source: str = Field(..., description="Ontology source/content")
        level: str = Field(..., description="Level of the ontology - one of: USE_CASE, DOMAIN, MID, TOP")
        description: Optional[str] = Field(None, description="Description of the ontology")
        logo_url: Optional[str] = Field(None, description="Logo URL for the ontology")
        is_public: Optional[bool] = Field(False, description="Whether the ontology is public")

    class GetOntologySchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to get an ontology from")
        ontology_id: Optional[str] = Field("", description="Optional ontology ID to get a specific ontology. If not provided, lists all ontologies")

    class GetOntologiesSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to get ontologies from")

    class UpdateOntologySchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to update an ontology in")
        ontology_id: str = Field(..., description="ID of the ontology to update")
        download_url: Optional[str] = Field(None, description="Updated ontology download URL")
        source: Optional[str] = Field(None, description="Updated ontology source")
        level: Optional[str] = Field(None, description="Updated ontology level")
        description: Optional[str] = Field(None, description="Updated ontology description")
        logo_url: Optional[str] = Field(None, description="Updated ontology logo URL")
        is_public: Optional[bool] = Field(False, description="Whether the ontology is public")

    class DeleteOntologySchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID to delete an ontology from")
        ontology_id: str = Field(..., description="ID of the ontology to delete")

    class GetWorkspaceUsersSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace to list users from")

    class InviteWorkspaceUserSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")
        email: str = Field(..., description="Email of the user to invite")
        role: str = Field("member", description="Role to assign to the user - one of: 'member', 'admin', 'owner'")
        user_id: Optional[str] = Field("", description="User ID if known")

    class GetWorkspaceUserSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")
        user_id: str = Field(..., description="ID of the user")

    class UpdateWorkspaceUserSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")
        user_id: str = Field(..., description="ID of the user")
        role: Optional[str] = Field(None, description="New role for the user")
        status: Optional[str] = Field(None, description="New status for the user")

    class DeleteWorkspaceUserSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")
        user_id: str = Field(..., description="ID of the user to remove")

    class ListSecretsSchema(BaseModel):
        pass

    class CreateSecretSchema(BaseModel):
        name: str = Field(..., description="Name of the secret")
        value: str = Field(..., description="Value of the secret")

    class GetSecretSchema(BaseModel):
        secret_id: str = Field(..., description="ID of the secret")

    class UpdateSecretSchema(BaseModel):
        secret_id: str = Field(..., description="ID of the secret")
        value: str = Field(..., description="New value for the secret")

    class DeleteSecretSchema(BaseModel):
        secret_id: str = Field(..., description="ID of the secret to delete")

    class ListWorkspaceStorageSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")

    class ListWorkspaceStorageObjectsSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")
        storage_name: str = Field(..., description="Name of the storage")
        prefix: str = Field(..., description="Prefix to list objects under") 

    class CreateWorkspaceStorageSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")
        storage_name: str = Field(..., description="Name of the storage")

    class CreateWorkspaceStorageCredentialsSchema(BaseModel):
        workspace_id: str = Field(..., description="ID of the workspace")
        storage_name: str = Field(..., description="Name of the storage")

    class GetStorageCredentialsSchema(BaseModel):
        workspace_id: Optional[str] = Field(None, description="Optional ID of the workspace. If not provided, uses personal workspace")
        storage_name: str = Field(..., description="Name of the storage")

    return [
        StructuredTool(
            name="create_naas_workspace",
            description="Create a new workspace on naas.ai platform",
            func=lambda **kwargs: integration.create_workspace(**kwargs),
            args_schema=CreateWorkspaceSchema
        ),
        StructuredTool(
            name="get_naas_workspace",
            description="Get details of a specific workspace from naas.ai platform",
            func=lambda workspace_id: integration.get_workspace(workspace_id),
            args_schema=GetWorkspaceSchema
        ),
        StructuredTool(
            name="get_naas_workspaces",
            description="Get all workspaces from naas.ai platform",
            func=lambda: integration.get_workspaces(),
            args_schema=GetWorkspacesSchema
        ),
        StructuredTool(
            name="get_naas_personal_workspace",
            description="Get personal workspace ID from naas.ai platform",
            func=lambda: integration.get_personal_workspace(),
            args_schema=GetPersonalWorkspaceSchema
        ),
        StructuredTool(
            name="update_naas_workspace",
            description="Update an existing workspace on naas.ai platform",
            func=lambda **kwargs: integration.update_workspace(**kwargs),
            args_schema=UpdateWorkspaceSchema
        ),
        StructuredTool(
            name="delete_naas_workspace",
            description="Delete an existing workspace from naas.ai platform",
            func=lambda workspace_id: integration.delete_workspace(workspace_id),
            args_schema=DeleteWorkspaceSchema
        ),
        StructuredTool(
            name="create_naas_assistant",
            description="Create a new plugin or assistant from workspace",
            func=lambda workspace_id, data: integration.create_plugin(workspace_id, data),
            args_schema=CreatePluginSchema
        ),
        StructuredTool(
            name="get_naas_assistant",
            description="Get plugin detail or assistant from workspace",
            func=lambda workspace_id, plugin_id: integration.get_plugin(workspace_id, plugin_id),
            args_schema=GetPluginSchema
        ),
        StructuredTool(
            name="get_naas_assistants",
            description="Get all plugins or assistants from workspace",
            func=lambda workspace_id: integration.get_plugins(workspace_id),
            args_schema=GetPluginsSchema
        ),
        StructuredTool(
            name="update_naas_assistant",
            description="Update an existing plugin or assistant from workspace",
            func=lambda workspace_id, plugin_id, data: integration.update_plugin(workspace_id, plugin_id, data),
            args_schema=UpdatePluginSchema
        ),
        StructuredTool(
            name="delete_naas_assistant",
            description="Delete an existing plugin or assistant from workspace",
            func=lambda workspace_id, plugin_id: integration.delete_plugin(workspace_id, plugin_id),
            args_schema=DeletePluginSchema
        ),
        StructuredTool(
            name="create_naas_ontology",
            description="Create a new ontology from workspace",
            func=lambda workspace_id, label, source, level, description, logo_url, is_public: integration.create_ontology(workspace_id, label, source, level, description, logo_url, is_public),
            args_schema=CreateOntologySchema
        ),
        StructuredTool(
            name="get_naas_ontology",
            description="Get ontology by ID",
            func=lambda workspace_id, ontology_id: integration.get_ontology(workspace_id, ontology_id),
            args_schema=GetOntologySchema
        ),
        StructuredTool(
            name="get_naas_ontologies",
            description="Get all ontologies from workspace",
            func=lambda workspace_id: integration.get_ontologies(workspace_id),
            args_schema=GetOntologiesSchema
        ),
        StructuredTool(
            name="update_naas_ontology",
            description="Update an existing ontology from workspace",
            func=lambda workspace_id, ontology_id, download_url, source, level, description, logo_url, is_public: integration.update_ontology(workspace_id, ontology_id, download_url, source, level, description, logo_url, is_public),
            args_schema=UpdateOntologySchema
        ),
        StructuredTool(
            name="delete_naas_ontology",
            description="Delete an existing ontology from workspace",
            func=lambda workspace_id, ontology_id: integration.delete_ontology(workspace_id, ontology_id),
            args_schema=DeleteOntologySchema
        ),
        StructuredTool(
            name="get_naas_workspace_users",
            description="List all users in a workspace",
            func=lambda workspace_id: integration.get_workspace_users(workspace_id),
            args_schema=GetWorkspaceUsersSchema
        ),
        StructuredTool(
            name="invite_naas_workspace_user",
            description="Invite a user to a workspace",
            func=lambda **kwargs: integration.invite_workspace_user(**kwargs),
            args_schema=InviteWorkspaceUserSchema
        ),
        StructuredTool(
            name="get_naas_workspace_user",
            description="Get details of a specific user in a workspace",
            func=lambda workspace_id, user_id: integration.get_workspace_user(workspace_id, user_id),
            args_schema=GetWorkspaceUserSchema
        ),
        StructuredTool(
            name="update_naas_workspace_user",
            description="Update a user's role or status in a workspace",
            func=lambda **kwargs: integration.update_workspace_user(**kwargs),
            args_schema=UpdateWorkspaceUserSchema
        ),
        StructuredTool(
            name="delete_naas_workspace_user",
            description="Remove a user from a workspace",
            func=lambda workspace_id, user_id: integration.delete_workspace_user(workspace_id, user_id),
            args_schema=DeleteWorkspaceUserSchema
        ),
        StructuredTool(
            name="list_naas_secrets",
            description="List all secrets in a workspace",
            func=lambda: integration.list_secrets(),
            args_schema=ListSecretsSchema
        ),
        StructuredTool(
            name="list_secrets_names",
            description="List all secrets names.",
            func=lambda: integration.list_secrets_names(),
            args_schema=ListSecretsSchema
        ),
        StructuredTool(
            name="create_naas_secret",
            description="Create a new secret.",
            func=lambda name, value: integration.create_secret(name, value),
            args_schema=CreateSecretSchema
        ),
        StructuredTool(
            name="get_naas_secret",
            description="Get a specific secret.",
            func=lambda secret_id: integration.get_secret(secret_id),
            args_schema=GetSecretSchema
        ),
        StructuredTool(
            name="update_naas_secret",
            description="Update an existing secret.",
            func=lambda secret_id, value: integration.update_secret(secret_id, value),
            args_schema=UpdateSecretSchema
        ),
        StructuredTool(
            name="delete_naas_secret",
            description="Delete a secret.",
            func=lambda secret_id: integration.delete_secret(secret_id),
            args_schema=DeleteSecretSchema
        ),
        StructuredTool(
            name="list_naas_workspace_storage",
            description="List all storage in a workspace",
            func=lambda workspace_id: integration.list_workspace_storage(workspace_id),
            args_schema=ListWorkspaceStorageSchema
        ),
        StructuredTool(
            name="list_naas_workspace_storage_objects",
            description="List all objects and subdirectories in a workspace storage location",
            func=lambda workspace_id, storage_name, prefix: integration.list_workspace_storage_objects(workspace_id, storage_name, prefix),
            args_schema=ListWorkspaceStorageObjectsSchema
        ),
        StructuredTool(
            name="create_naas_workspace_storage",
            description="Create a new storage in a workspace",
            func=lambda workspace_id, storage_name: integration.create_workspace_storage(workspace_id, storage_name),
            args_schema=CreateWorkspaceStorageSchema
        ),
        StructuredTool(
            name="create_naas_workspace_storage_credentials",
            description="Create credentials for workspace storage",
            func=lambda workspace_id, storage_name: integration.create_workspace_storage_credentials(workspace_id, storage_name),
            args_schema=CreateWorkspaceStorageCredentialsSchema
        ),
        StructuredTool(
            name="get_naas_storage_credentials",
            description="Get or create storage credentials",
            func=lambda **kwargs: integration.get_storage_credentials(**kwargs),
            args_schema=GetStorageCredentialsSchema
        ),
    ]