# ProviderService

## What it is
- Service that returns the list of AI model providers available to a user based on the presence of API keys in:
  - workspace secrets
  - environment keys
- Always includes the local provider **Ollama (Local)**.

## Public API
- `class ProviderService(adapter: ProviderAvailabilityPort)`
  - Constructs the service with an adapter that can query workspaces and keys.

- `async ProviderService.list_available_providers(user_id: str) -> list[ProviderInfo]`
  - Returns a list of `ProviderInfo` entries for providers considered available for the given user.
  - Provider availability is determined by whether required key names exist in the union of:
    - workspace secret keys
    - environment keys (limited to a fixed allowlist)

## Configuration/Dependencies
- Depends on:
  - `ProviderAvailabilityPort` (adapter interface), expected async methods:
    - `list_workspace_ids_for_user(user_id: str) -> list[str]`
    - `list_secret_keys_for_workspaces(workspace_ids: list[str]) -> set[str]`
    - `list_environment_keys(key_names: list[str]) -> set[str]`
  - Model registry functions:
    - `get_models_for_provider(provider: str)` (used to populate `ProviderModelInfo` list)
    - `get_logo_for_provider(provider: str)` (used to set `logo_url`)
  - Schemas:
    - `ProviderInfo`
    - `ProviderModelInfo`

- Key names checked (environment lookups are limited to this list):
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `XAI_API_KEY`
  - `MISTRAL_API_KEY`
  - `PERPLEXITY_API_KEY`
  - `GOOGLE_API_KEY`
  - `OPENROUTER_API_KEY`
  - `CLOUDFLARE_API_TOKEN`
  - `CLOUDFLARE_ACCOUNT_ID`

- Cloudflare availability requires **both**:
  - `CLOUDFLARE_API_TOKEN`
  - `CLOUDFLARE_ACCOUNT_ID`

## Usage
```python
import asyncio

from naas_abi.apps.nexus.apps.api.app.services.providers.service import ProviderService
from naas_abi.apps.nexus.apps.api.app.services.providers.port import ProviderAvailabilityPort

class DummyAdapter(ProviderAvailabilityPort):
    async def list_workspace_ids_for_user(self, user_id: str):
        return ["ws_1"]

    async def list_secret_keys_for_workspaces(self, workspace_ids):
        return {"OPENAI_API_KEY"}

    async def list_environment_keys(self, key_names):
        return set()

async def main():
    service = ProviderService(adapter=DummyAdapter())
    providers = await service.list_available_providers(user_id="user_1")
    print([p.id for p in providers])  # e.g. ["openai", "ollama"]

asyncio.run(main())
```

## Caveats
- If the user has no workspaces, the method logs a warning and returns an empty list (Ollama is **not** added in that case).
- Provider entries are added only if the corresponding key name(s) exist; it does not validate that keys are correct or usable.
