# DeployConfiguration

## What it is
- A small Pydantic model that holds configuration needed for a “deploy” context: workspace, space, API key, and environment variables.

## Public API
- `class DeployConfiguration(pydantic.BaseModel)`
  - `workspace_id: str` — Target workspace identifier.
  - `space_name: str` — Target space name.
  - `naas_api_key: str` — API key for authentication.
  - `env: dict[str, str] = {}` — Optional environment variables mapping.

## Configuration/Dependencies
- Depends on `pydantic.BaseModel`.
- Requires Pydantic installed (`pydantic` package).

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Deploy import DeployConfiguration

cfg = DeployConfiguration(
    workspace_id="ws_123",
    space_name="my-space",
    naas_api_key="naas_xxx",
    env={"MODE": "prod"}
)

print(cfg.workspace_id)
print(cfg.env.get("MODE"))
```

## Caveats
- `env` defaults to an empty dict (`{}`). This is a mutable default value.
