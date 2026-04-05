# `openapi_doc`

## What it is
Static OpenAPI/Docs assets for the ABI API:
- `TAGS_METADATA`: tag definitions (names + rich Markdown descriptions) for grouping endpoints in generated API docs.
- `API_LANDING_HTML`: HTML template string for a simple landing page linking to `/redoc`.

## Public API
- `TAGS_METADATA` (`list[dict]`)
  - Purpose: Provide OpenAPI tag metadata (e.g., for FastAPI `openapi_tags`) including descriptions for:
    - `Overview`
    - `Authentication`
    - `Agents`
    - `Pipelines`
    - `Workflows`
- `API_LANDING_HTML` (`str`)
  - Purpose: HTML landing page template with placeholders:
    - `[TITLE]` (page title / product name)
    - `[LOGO_NAME]` (filename under `/static/`)

## Configuration/Dependencies
- No runtime dependencies in this module.
- Intended to be imported by the API application (commonly a FastAPI app) to configure documentation and serve a landing page.

## Usage
Minimal example showing how to use these constants in a FastAPI app:

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from naas_abi_core.apps.api.openapi_doc import TAGS_METADATA, API_LANDING_HTML

app = FastAPI(openapi_tags=TAGS_METADATA)

@app.get("/", response_class=HTMLResponse)
def landing():
    return API_LANDING_HTML.replace("[TITLE]", "ABI API").replace("[LOGO_NAME]", "logo.png")
```

## Caveats
- `API_LANDING_HTML` contains literal placeholders (`[TITLE]`, `[LOGO_NAME]`) that must be replaced before returning to clients.
- The HTML references `/static/favicon.ico` and `/static/[LOGO_NAME]`; your application must serve those static assets for the page to render correctly.
