# TenantResponse

## What it is
- A set of **Pydantic** models describing a tenant branding/configuration response payload.
- Includes tenant UI theming fields and a list of external apps.

## Public API
- `class TenantResponse(pydantic.BaseModel)`
  - Response schema for tenant settings:
    - Branding: `tab_title`, `favicon_url`, `logo_url`, `logo_rectangle_url`, `logo_emoji`
    - Colors: `primary_color`, `accent_color`, `background_color`
    - Fonts: `font_family`, `font_url`
    - Login card layout: `login_card_max_width`, `login_card_padding`, `login_card_color`
    - Login appearance: `login_text_color`, `login_input_color`, `login_border_radius`, `login_bg_image_url`
    - Footer flags/text: `show_terms_footer`, `show_powered_by`, `login_footer_text`
    - External apps: `apps` (defaults to empty list)

- `class TenantResponse.ExternalAppResponse(pydantic.BaseModel)`
  - Schema for each external app entry:
    - `name`, `url`, `description`, `icon_emoji`

## Configuration/Dependencies
- Depends on:
  - `pydantic.BaseModel`
  - `pydantic.Field` (used to default `apps` to an empty list via `default_factory=list`)

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.services.tenant.tenant__schema import TenantResponse

tenant = TenantResponse(
    tab_title="Acme Portal",
    primary_color="#1f2937",
    accent_color="#3b82f6",
    background_color="#ffffff",
    login_card_max_width="420px",
    login_card_padding="24px",
    login_card_color="#ffffff",
    login_input_color="#f3f4f6",
    login_border_radius="12px",
    show_terms_footer=True,
    show_powered_by=False,
    apps=[
        TenantResponse.ExternalAppResponse(
            name="Docs",
            url="https://docs.example.com",
            description="Product documentation",
            icon_emoji="📚",
        )
    ],
)

print(tenant.model_dump())
```

## Caveats
- `apps` is always a list (defaults to `[]` when omitted).
- Many fields are required (non-optional) and must be provided to instantiate `TenantResponse`.
