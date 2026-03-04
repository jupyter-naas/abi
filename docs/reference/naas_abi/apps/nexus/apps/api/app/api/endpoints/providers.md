# providers (AI Providers API endpoints)

## What it is
FastAPI endpoints and schemas to **discover which AI providers are available** for the current user, based on:
- Workspace secrets stored in the database
- Environment variables (fallback)
- A local provider (`ollama`) that is always listed

It returns each available provider along with its model metadata from the model registry.

## Public API

### FastAPI router
- `router: fastapi.APIRouter`
  - Configured with `dependencies=[Depends(get_current_user_required)]` (authentication required for all routes).

### Pydantic models
- `class Model(BaseModel)`
  - Represents model metadata from the model registry.
  - Fields:
    - `id: str`
    - `name: str`
    - `provider: Literal["openai","anthropic","cloudflare","ollama","openrouter","xai","mistral","perplexity","google"]`
    - `context_window: int`
    - `supports_streaming: bool`
    - `supports_vision: bool`
    - `supports_function_calling: bool`
    - `max_output_tokens: int | None`
    - `released: str`

- `class Provider(BaseModel)`
  - Represents an available provider in the current context.
  - Fields:
    - `id: str`
    - `name: str`
    - `type: Literal["openai","anthropic","cloudflare","ollama","openrouter","xai","mistral","perplexity","google"]`
    - `has_api_key: bool`
    - `logo_url: str | None = None`
    - `models: list[Model]`

### Helper function
- `async def has_api_key_configured(key_name: str, workspace_ids: list[str], db: AsyncSession) -> bool`
  - Checks whether a given secret key exists:
    - First in DB secrets (`SecretModel`) for any of the provided `workspace_ids`
    - Then in the environment (`os.getenv`)
  - Note: This helper is defined but not used by the endpoint in this module.

### Endpoint
- `GET /available` → `async def list_available_providers(...) -> list[Provider]`
  - Purpose: returns providers that have required credentials available (via workspace secrets or environment), plus `ollama` always.
  - Provider inclusion rules:
    - `openai` if `OPENAI_API_KEY` present
    - `anthropic` if `ANTHROPIC_API_KEY` present
    - `xai` if `XAI_API_KEY` present
    - `mistral` if `MISTRAL_API_KEY` present
    - `perplexity` if `PERPLEXITY_API_KEY` present
    - `google` if `GOOGLE_API_KEY` present
    - `openrouter` if `OPENROUTER_API_KEY` present
    - `cloudflare` if **both** `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` present
    - `ollama` always included (with `has_api_key=False`)
  - Models are sourced via `get_models_for_provider(provider_id)`.
  - Logos are sourced via `get_logo_for_provider(provider_id)`.

## Configuration/Dependencies
- **Authentication**
  - `get_current_user_required` dependency is applied to the router and also to the endpoint parameter.
- **Database**
  - Requires an `AsyncSession` provided by `get_db`.
  - Reads:
    - `WorkspaceMemberModel` to get the current user’s workspace IDs
    - `SecretModel` to get secret keys present in those workspaces
- **Environment variables (fallback)**
  - Checked keys:
    - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`, `MISTRAL_API_KEY`
    - `PERPLEXITY_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`
    - `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
- **Model registry service**
  - `get_models_for_provider(provider: str)`
  - `get_logo_for_provider(provider: str)`

## Usage

### Calling the endpoint (example with FastAPI TestClient)
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from naas_abi.apps.nexus.apps.api.app.api.endpoints.providers import router

app = FastAPI()
app.include_router(router, prefix="/providers")

client = TestClient(app)

# Note: authentication is required by router dependencies.
# This call will fail unless your auth dependencies are satisfied in your test setup.
resp = client.get("/providers/available")
print(resp.status_code, resp.json())
```

## Caveats
- If the user has **no workspaces**, the endpoint returns an empty list and logs a warning.
- Provider availability is determined only by:
  - presence of secret keys in any workspace the user belongs to, or
  - environment variables (fallback)
- `cloudflare` requires **both** `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
- `ollama` is always returned regardless of secrets/environment.
