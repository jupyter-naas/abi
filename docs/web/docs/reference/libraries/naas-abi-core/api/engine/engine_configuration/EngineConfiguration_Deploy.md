# DeployConfiguration

## What it is
- A small [Pydantic](https://docs.pydantic.dev/) model that holds deployment-related settings: workspace, space, API key, and environment variables.

## Public API
- **Class `DeployConfiguration(BaseModel)`**
  - **Fields**
    - `workspace_id: str` - Workspace identifier.
    - `space_name: str` - Target space name.
    - `naas_api_key: str` - API key used for authentication.
    - `env: dict[str, str] = {}` - Optional environment variables mapping.

## Configuration/Dependencies
- **Dependency:** `pydantic.BaseModel`
- **Input types:**
  - `workspace_id`, `space_name`, `naas_api_key` must be strings.
  - `env` is a `dict[str, str]` (defaults to an empty dict).

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Deploy import DeployConfiguration

cfg = DeployConfiguration(
    workspace_id="ws_123",
    space_name="my-space",
    naas_api_key="naas_api_key_value",
    env={"MODE": "prod"}
)

print(cfg.workspace_id)
print(cfg.env)
```

## Caveats
- `env` defaults to `{}`; it is a mutable default value in the class definition.
