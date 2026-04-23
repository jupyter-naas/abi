# openapi_doc

## What it is
Static OpenAPI/Docs metadata and a simple HTML landing-page template used by the ABI API application to:
- Define tagged sections in generated API documentation.
- Serve a branded landing page that links to `/redoc`.

## Public API
Module-level constants:
- `TAGS_METADATA`: `list[dict]`
  - OpenAPI tags metadata (name + markdown description) for documentation sections:
    - `Overview`
    - `Authentication`
    - `Agents`
    - `Pipelines`
    - `Workflows`
- `API_LANDING_HTML`: `str`
  - HTML template containing placeholders for title/logo:
    - `[TITLE]`
    - `[LOGO_NAME]`

## Configuration/Dependencies
- No runtime dependencies in this module.
- Intended to be consumed by a web framework/app (e.g., FastAPI) that:
  - Uses `TAGS_METADATA` in OpenAPI generation.
  - Serves `API_LANDING_HTML` with placeholder substitution.
- Authentication description references an environment variable `ABI_API_KEY` (descriptive text only; not enforced here).

## Usage
Minimal example of consuming the constants and rendering the landing page:

```python
from naas_abi_core.apps.api.openapi_doc import TAGS_METADATA, API_LANDING_HTML

# Use in an OpenAPI-capable framework (example: pass TAGS_METADATA as openapi_tags)
openapi_tags = TAGS_METADATA

# Render landing HTML by replacing placeholders
html = (
    API_LANDING_HTML
    .replace("[TITLE]", "ABI API")
    .replace("[LOGO_NAME]", "logo.png")
)

print(openapi_tags[0]["name"])
print(html[:120])
```

## Caveats
- `API_LANDING_HTML` contains literal placeholders; consumers must replace them before serving.
- No validation is performed on `TAGS_METADATA` structure; incorrect edits may break documentation rendering in the consuming framework.
