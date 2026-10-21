# NaasIntegration

## What it is
A Python integration client for the Naas API (`https://api.naas.ai`) that:
- Authenticates using a bearer API key.
- Wraps common Naas resources (workspaces, plugins, ontologies, users, secrets, storage, assets, model completions).
- Optionally exposes the integration as LangChain `StructuredTool` instances via `as_tools()`.

## Public API

### `NaasIntegrationConfiguration`
Dataclass configuration for the integration.
- `api_key: str` — Naas API key (used as Bearer token).
- `workspace_id: str | None = None` — optional default workspace for `upload_asset()`.
- `storage_name: str | None = None` — optional default storage for `upload_asset()`.
- `base_url: str = "https://api.naas.ai"` — API base URL.

### `NaasIntegration(configuration)`
Main client class (inherits `naas_abi_core.integration.integration.Integration`).

#### Workspace
- `create_workspace(name: str, is_personal: bool = False, **kwargs) -> Dict`  
  Creates a workspace; supports logo/color customization fields via `kwargs`.
- `get_workspace(workspace_id: str) -> Dict`  
  Fetches workspace details by ID.
- `list_workspaces() -> Dict`  
  Lists accessible workspaces.
- `get_personal_workspace() -> str`  
  Returns the ID of the first workspace marked `is_personal`; raises `ValueError` if none found.
- `update_workspace(workspace_id: str, **kwargs) -> Dict`  
  Updates workspace fields (name/logo/color fields).
- `delete_workspace(workspace_id: str) -> Dict`  
  Deletes a workspace.

#### Plugins
- `create_plugin(workspace_id: str, data: Dict) -> Dict`  
  Creates a plugin; payload is JSON-stringified.
- `get_plugin(workspace_id: str, plugin_id: Optional[str] = None) -> Dict`  
  Gets a single plugin when `plugin_id` is provided; otherwise lists plugins.
- `list_plugins(workspace_id: str) -> Dict`  
  Lists all plugins in a workspace.
- `update_plugin(workspace_id: str, plugin_id: str, data: Dict) -> Dict`  
  Updates a plugin; payload is JSON-stringified.
- `delete_plugin(workspace_id: str, plugin_id: str) -> Dict`  
  Deletes a plugin.
- `search_plugin(key: str, value: str, plugins: List[Dict[str, str]] = [], workspace_id: Optional[str] = None) -> Optional[str]`  
  Searches for a plugin whose JSON-decoded `payload` contains `key == value`. If `plugins` is empty and `workspace_id` is provided, it fetches plugins first. Returns the matching plugin ID or `None`.

#### Ontologies
- `create_ontology(workspace_id: str, label: str, source: str, level: str, description: Optional[str] = None, download_url: Optional[str] = None, logo_url: Optional[str] = None, is_public: bool = False) -> Dict`
- `get_ontology(workspace_id: str, ontology_id: str = "") -> Dict`  
  Uses query param `workspace_id`; adds `id` when `ontology_id` is provided.
- `list_ontologies(workspace_id: str) -> Dict`  
  Requests page size 100, page number 0.
- `update_ontology(workspace_id: str, ontology_id: str, download_url: Optional[str] = None, source: Optional[str] = None, level: Optional[str] = None, description: Optional[str] = None, logo_url: Optional[str] = None, is_public: bool = False) -> Dict`  
  Builds a field mask from provided fields (only adds `is_public` when `True`).
- `delete_ontology(workspace_id: str, ontology_id: str) -> Dict`

#### Workspace users
- `get_workspace_users(workspace_id: str) -> Dict`
- `invite_workspace_user(workspace_id: str, role: str = "member", email: Optional[str] = None, user_id: Optional[str] = None) -> Dict`  
  Requires either `email` or `user_id`; raises `ValueError` otherwise.
- `get_workspace_user(workspace_id: str, user_id: str) -> Dict`
- `update_workspace_user(workspace_id: str, user_id: str, role: Optional[str] = None, status: Optional[str] = None) -> Dict`
- `delete_workspace_user(workspace_id: str, user_id: str) -> Dict`

#### Secrets
- `get_secret(secret_id: str) -> Dict`
- `list_secrets() -> List[Dict]`  
  Returns the `"secrets"` list from the API response (defaults to `[]`).
- `list_secrets_names() -> List[str]`
- `create_secret(name: str, value: str) -> Dict`
- `update_secret(secret_id: str, value: str) -> Dict`
- `delete_secret(secret_id: str) -> Dict`

#### Storage
- `list_workspace_storage(workspace_id: str) -> Dict`
- `list_workspace_storage_objects(workspace_id: str, storage_name: str, prefix: str) -> Dict`
- `create_workspace_storage(workspace_id: str, storage_name: str) -> Dict`
- `create_workspace_storage_credentials(workspace_id: str, storage_name: str) -> Dict`
- `get_storage_credentials(workspace_id: Optional[str] = None, storage_name: Optional[str] = None) -> Dict[str, Any]`  
  Requires both args; lists storage, creates it if missing, then creates credentials.

#### Assets
- `create_asset(workspace_id: str, storage_name: str, object_name: str, visibility: str = "public", content_disposition: str = "inline", password: Optional[str] = None) -> Dict`
- `upload_asset(data: bytes, prefix: str, object_name: str, workspace_id: Optional[str] = None, storage_name: Optional[str] = None, visibility: str = "public", content_disposition: str = "inline", password: Optional[str] = None, version: Optional[str] = None, return_url: bool = False) -> Dict`  
  Uploads bytes to Naas object storage via `ObjectStorageFactory.ObjectStorageServiceNaas(...).put_object(...)`, then creates/gets an asset via HTTP. If `return_url=True`, returns `{"asset_url": ...}`.
- `update_asset(workspace_id: str, asset_id: str, data: Dict) -> Dict`
- `get_asset(workspace_id: str, asset_id: str) -> Dict`

#### Models
- `create_completion(model_id: str, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.3) -> Dict`  
  Calls `/model/{model_id}/completion` and returns the first completion object: `completion_response["completion"]["completions"][0]`.

#### Utility
- `get_user_id_from_jwt(jwt_token) -> Optional[str]`  
  Decodes JWT without signature verification and returns the `"sub"` claim; logs errors and returns `None`.

### `as_tools(configuration: NaasIntegrationConfiguration) -> list`
Factory that returns a list of LangChain `StructuredTool` objects mapping to many integration methods (workspace/plugin/ontology/users/secrets/storage). Schemas are defined with Pydantic models.

## Configuration/Dependencies
- Requires an API key (`NaasIntegrationConfiguration.api_key`) used as `Authorization: Bearer ...`.
- HTTP client: `requests`.
- JWT parsing: `PyJWT` (`jwt.decode(..., verify_signature=False)`).
- Object storage upload in `upload_asset()` depends on:
  - `naas_abi_core.services.object_storage.ObjectStorageFactory`
  - `ObjectStorageServiceNaas` implementation.
- `as_tools()` requires `langchain_core.tools.StructuredTool` and `pydantic`.

## Usage

```python
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)

cfg = NaasIntegrationConfiguration(api_key="YOUR_NAAS_API_KEY")
client = NaasIntegration(cfg)

# List workspaces
workspaces = client.list_workspaces()
print(workspaces)

# Create a workspace
created = client.create_workspace(name="My Workspace", is_personal=False)
print(created)
```

## Caveats
- `get_user_id_from_jwt()` disables JWT signature verification; it should not be used to establish trust, only to extract claims.
- Several `GET` calls pass a request body (`data`) to `_make_request()`; behavior depends on the server and `requests` handling.
- `search_plugin()` uses a mutable default argument (`plugins=[]`), which can retain state across calls.
- `update_ontology(..., is_public=False)` will not include `is_public` in the update field mask unless it is `True`, so it cannot explicitly set `is_public` to `False` via this method.
- `upload_asset()` returns `{"error": ...}` (not an exception) when `workspace_id`/`storage_name` are missing and not present in configuration.
