# NaasIntegration

## What it is
A Python integration client for the Naas API (`https://api.naas.ai`) that:
- Authenticates using a Bearer API key.
- Wraps common Naas resources: workspaces, plugins, ontologies, workspace users, secrets, storage, assets, and model completions.
- Optionally exposes selected operations as LangChain `StructuredTool` instances via `as_tools()`.

## Public API

### `NaasIntegrationConfiguration`
Dataclass configuration (extends `IntegrationConfiguration`):
- `api_key: str` — Naas API key (used as `Authorization: Bearer ...` and also decoded as a JWT for `sub` in some payloads).
- `workspace_id: str | None = None` — optional default workspace for `upload_asset()`.
- `storage_name: str | None = None` — optional default storage for `upload_asset()`.
- `base_url: str = "https://api.naas.ai"` — API base URL.

### `NaasIntegration(configuration: NaasIntegrationConfiguration)`
Main client (extends `naas_abi_core.integration.integration.Integration`).

#### Utility
- `get_user_id_from_jwt(jwt_token) -> Any | None`  
  Decodes a JWT **without** signature verification and returns the `sub` claim (or `None` on error).

#### Workspaces
- `create_workspace(name: str, is_personal: bool = False, **kwargs) -> dict`  
  Creates a workspace; supports branding fields via `kwargs` (logos/colors).
- `get_workspace(workspace_id: str) -> dict`  
  Retrieves workspace details.
- `list_workspaces() -> dict`  
  Lists accessible workspaces.
- `get_personal_workspace() -> str`  
  Returns the first workspace ID with `is_personal == True`; raises `ValueError` if none.
- `update_workspace(workspace_id: str, **kwargs) -> dict`  
  Updates workspace fields (name/logos/colors).
- `delete_workspace(workspace_id: str) -> dict`  
  Deletes a workspace.

#### Plugins
- `create_plugin(workspace_id: str, data: dict) -> dict`  
  Creates a plugin; `data` is JSON-stringified into `payload`.
- `get_plugin(workspace_id: str, plugin_id: str | None = None) -> dict`  
  Gets a specific plugin if `plugin_id` is provided; otherwise lists plugins.
- `list_plugins(workspace_id: str) -> dict`  
  Lists all plugins in a workspace.
- `update_plugin(workspace_id: str, plugin_id: str, data: dict) -> dict`  
  Updates a plugin; `data` is JSON-stringified into `workspace_plugin.payload`.
- `delete_plugin(workspace_id: str, plugin_id: str) -> dict`  
  Deletes a plugin.
- `search_plugin(key: str, value: str, plugins: list[dict[str, str]] | None = None, workspace_id: str | None = None) -> str | None`  
  Searches plugins whose JSON-decoded `payload` has `payload[key] == value`. If `plugins` is empty and `workspace_id` is provided, it fetches plugins first. Returns matching plugin `id` or `None`.

#### Ontologies
- `create_ontology(workspace_id: str, label: str, source: str, level: str, description: str | None = None, download_url: str | None = None, logo_url: str | None = None, is_public: bool = False) -> dict`
- `get_ontology(workspace_id: str, ontology_id: str = "") -> dict`  
  Uses `workspace_id` as query parameter; includes `id` param when `ontology_id` is provided.
- `list_ontologies(workspace_id: str) -> dict`  
  Requests `page_size=100`, `page_number=0`.
- `update_ontology(workspace_id: str, ontology_id: str, download_url: str | None = None, source: str | None = None, level: str | None = None, description: str | None = None, logo_url: str | None = None, is_public: bool = False) -> dict`  
  Builds `field_mask.paths` from provided (truthy) fields; only includes `is_public` when `True`.
- `delete_ontology(workspace_id: str, ontology_id: str) -> dict`

#### Workspace users
- `get_workspace_users(workspace_id: str) -> dict`
- `invite_workspace_user(workspace_id: str, role: str = "member", email: str | None = None, user_id: str | None = None) -> dict`  
  Requires `email` or `user_id`; raises `ValueError` if neither is provided.
- `get_workspace_user(workspace_id: str, user_id: str) -> dict`
- `update_workspace_user(workspace_id: str, user_id: str, role: str | None = None, status: str | None = None) -> dict`
- `delete_workspace_user(workspace_id: str, user_id: str) -> dict`

#### Secrets
- `get_secret(secret_id: str) -> dict`
- `list_secrets() -> list[dict]`  
  Returns the `secrets` list from the API response (defaults to `[]`).
- `list_secrets_names() -> list[str]`
- `create_secret(name: str, value: str) -> dict`
- `update_secret(secret_id: str, value: str) -> dict`
- `delete_secret(secret_id: str) -> dict`

#### Storage
- `list_workspace_storage(workspace_id: str) -> dict`
- `list_workspace_storage_objects(workspace_id: str, storage_name: str, prefix: str) -> dict`
- `create_workspace_storage(workspace_id: str, storage_name: str) -> dict`
- `create_workspace_storage_credentials(workspace_id: str, storage_name: str) -> dict`
- `get_storage_credentials(workspace_id: str | None = None, storage_name: str | None = None) -> dict[str, Any]`  
  Requires both args; lists storage, creates it if missing, then creates credentials.

#### Assets
- `create_asset(workspace_id: str, storage_name: str, object_name: str, visibility: str = "public", content_disposition: str = "inline", password: str | None = None) -> dict`
- `upload_asset(data: bytes, prefix: str, object_name: str, workspace_id: str | None = None, storage_name: str | None = None, visibility: str = "public", content_disposition: str = "inline", password: str | None = None, version: str | None = None, return_url: bool = False) -> dict`  
  Uploads bytes to Naas object storage via `ObjectStorageFactory.ObjectStorageServiceNaas(...).put_object(...)`, then POSTs asset creation to the API. If the response indicates an existing asset, it fetches it via `get_asset()`. If `return_url=True`, returns `{"asset_url": ...}`.
- `update_asset(workspace_id: str, asset_id: str, data: dict) -> dict`
- `get_asset(workspace_id: str, asset_id: str) -> dict`

#### Models
- `create_completion(model_id: str, prompt: str, system_prompt: str | None = None, temperature: float = 0.3) -> dict`  
  Calls `/model/{model_id}/completion` and returns `completion_response["completion"]["completions"][0]`.

### `as_tools(configuration: NaasIntegrationConfiguration) -> list`
Returns a list of LangChain `StructuredTool` wrappers for many integration methods:
- workspaces, plugins, ontologies, workspace users, secrets, storage, credentials.

## Configuration/Dependencies
- HTTP: `requests`
- JWT decoding: `PyJWT` (`jwt.decode(..., verify_signature=False)`)
- Object upload in `upload_asset()`:
  - `naas_abi_core.services.object_storage.ObjectStorageFactory`
  - `ObjectStorageServiceNaas` via `ObjectStorageFactory.ObjectStorageServiceNaas(...)`
- `as_tools()`:
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (`BaseModel`, `Field`)
- Exceptions: raises `IntegrationConnectionError` on request failures from `_make_request()`.

## Usage

```python
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)

cfg = NaasIntegrationConfiguration(api_key="YOUR_NAAS_API_KEY")
client = NaasIntegration(cfg)

# List workspaces
print(client.list_workspaces())

# Create a workspace
print(client.create_workspace(name="My Workspace", is_personal=False))
```

## Caveats
- `get_user_id_from_jwt()` disables JWT signature verification; use only for claim extraction, not trust decisions.
- `_make_request()` sends JSON as `data=` for `POST` but as `json=` for non-POST methods.
- `update_ontology(..., is_public=False)` will not include `is_public` in the field mask unless `is_public` is `True`.
- `upload_asset()` returns `{"error": ...}` (not an exception) when `workspace_id`/`storage_name` are missing (and not set on configuration).
