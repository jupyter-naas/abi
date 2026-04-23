# TenantService

## What it is
- A small service that converts tenant-related configuration from `settings.tenant` into a typed `TenantResponse`.

## Public API
- `class TenantService`
  - `@staticmethod async get_tenant_config() -> TenantResponse`
    - Builds and returns a `TenantResponse` populated from `settings.tenant`, including a list of external apps.

## Configuration/Dependencies
- Depends on:
  - `settings` from `naas_abi.apps.nexus.apps.api.app.core.config`
    - Must expose a `tenant` object with the following attributes:
      - `tab_title`, `favicon_url`, `logo_url`, `logo_rectangle_url`, `logo_emoji`
      - `primary_color`, `accent_color`, `background_color`
      - `font_family`, `font_url`
      - `login_card_max_width`, `login_card_padding`, `login_card_color`
      - `login_text_color`, `login_input_color`, `login_border_radius`
      - `login_bg_image_url`
      - `show_terms_footer`, `show_powered_by`, `login_footer_text`
      - `apps` iterable where each item has: `name`, `url`, `description`, `icon_emoji`
  - `TenantResponse` from `naas_abi.apps.nexus.apps.api.app.services.tenant.tenant__schema`
    - Must provide `ExternalAppResponse` for app entries.

## Usage
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.tenant.service import TenantService

async def main():
    tenant_config = await TenantService.get_tenant_config()
    print(tenant_config)

asyncio.run(main())
```

## Caveats
- The method is `async` but performs no awaits; it still must be called from an async context.
- Missing/invalid `settings.tenant` attributes (or malformed items in `settings.tenant.apps`) will raise runtime errors during object construction.
