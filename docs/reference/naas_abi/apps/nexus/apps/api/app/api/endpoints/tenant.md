# tenant (Public Tenant Configuration Endpoint)

## What it is
- A FastAPI endpoint that exposes **public tenant branding/configuration** (e.g., tab title, favicon, colors) so a frontend can apply them **without authentication**.
- Values are read from `settings.tenant` (configured via the application’s config system).

## Public API
- **`router: fastapi.APIRouter`**
  - FastAPI router containing the tenant configuration endpoint.

- **`class TenantResponse(pydantic.BaseModel)`**
  - Response schema returned by the endpoint.
  - Fields:
    - `tab_title: str`
    - `favicon_url: str | None`
    - `logo_url: str | None`
    - `logo_rectangle_url: str | None`
    - `logo_emoji: str | None`
    - `primary_color: str`
    - `accent_color: str`
    - `background_color: str`
    - `font_family: str | None`
    - `font_url: str | None`
    - `login_card_max_width: str`
    - `login_card_padding: str`
    - `login_card_color: str`
    - `login_text_color: str | None`
    - `login_input_color: str`
    - `login_border_radius: str`
    - `login_bg_image_url: str | None`
    - `show_terms_footer: bool`
    - `show_powered_by: bool`
    - `login_footer_text: str | None`

- **`async def get_tenant_config() -> TenantResponse`**
  - HTTP: `GET ""` (path relative to where the router is included)
  - Auth: **none**
  - Returns a `TenantResponse` populated from `settings.tenant.*`.

## Configuration/Dependencies
- **FastAPI**: `APIRouter`
- **Pydantic**: `BaseModel`
- **Application settings**: `from naas_abi.apps.nexus.apps.api.app.core.config import settings`
  - Must provide `settings.tenant` with the attributes referenced in `get_tenant_config()`.

## Usage
Minimal example of mounting the router in a FastAPI app:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import tenant

app = FastAPI()
app.include_router(tenant.router, prefix="/tenant", tags=["tenant"])
```

Then call:

```bash
curl http://localhost:8000/tenant
```

## Caveats
- The route path is `""` on the router; the final URL depends on the `include_router(..., prefix=...)` configuration.
- The endpoint assumes all referenced `settings.tenant` attributes exist; missing settings will raise errors at runtime.
