# OpenAIResponsesIntegration

## What it is
A Naas ABI `Integration` that calls the OpenAI **Responses API** to:
- run web search via the `web_search_preview` tool,
- analyze images from URLs,
- analyze PDFs by downloading them, extracting text, and sending the extracted text to the model.

Each call persists the raw JSON response under `datastore_path/responses/...`.

## Public API

### `OpenAIResponsesIntegrationConfiguration` (dataclass)
Configuration for the integration.
- `api_key: str` (**required**): OpenAI API key used for `Authorization: Bearer ...`.
- `model: str = "gpt-4.1-mini"`: Model name sent in requests.
- `base_url: str = "https://api.openai.com/v1/responses"`: Responses API endpoint.
- `datastore_path: str`: Defaults to `ABIModule.get_instance().configuration.datastore_path`.

### `OpenAIResponsesIntegration`
Integration implementation.

#### `search_web(query: str, search_context_size: str = "medium", return_text: bool = False) -> dict`
- Sends a `POST` to the Responses API using tool:
  - `{"type": "web_search_preview", "search_context_size": ...}`
- Saves response JSON to:
  - `{datastore_path}/responses/web_search/{model}/{timestamp}_{model}_{search_context_size}.json`
- If `return_text=True`:
  - scans `response["output"]` for the first `message` item containing `output_text`
  - returns **either** a string (when there are no annotations) **or** `{"content": <text>}`
  - if nothing found, returns `{"content": "No valid text content found in response"}`

#### `analyze_image(image_urls: list[str], user_prompt: str = "Describe this image:", detail: str = "auto", return_text: bool = False) -> dict`
- Sends a user message with:
  - an `input_text` prompt
  - one `input_image` per URL: `{"image": {"url": ..., "detail": ...}}`
- Saves response JSON to:
  - `{datastore_path}/responses/analyze_image/{model}/{timestamp}_{model}_{detail}.json`
- If `return_text=True`:
  - returns `{"content": <first text found>}` or a fallback `{"content": "No valid text content found in response"}`
  - on parsing error returns `{"error": "...", "content": None}`

#### `analyze_pdf(pdf_url: str, user_prompt: str = "Describe this PDF document:", system_prompt: str = "...", return_text: bool = False) -> dict | str`
- Downloads the PDF from `pdf_url` and extracts text using `pdfplumber`.
- Sends extracted text as `input_text` along with `user_prompt`; optionally includes a `system` message.
- Saves response JSON to:
  - `{datastore_path}/responses/analyze_pdf/{model}/{timestamp}_{model}.json`
- If `return_text=True`:
  - extracts `output_text` from message content
  - also collects `url_citation` items in message content and appends an `Annotations:` list (deduped by URL)
  - returns `{"content": <text>}`; if no text, returns a string `"No text content found in output"`
- On PDF download/extraction error, returns the error as a string.

### `as_tools(configuration: OpenAIResponsesIntegrationConfiguration) -> list`
Returns LangChain `StructuredTool` wrappers around the integration:
- `chatgpt_search_web` → `OpenAIResponsesIntegration.search_web`
- `chatgpt_analyze_image` → `OpenAIResponsesIntegration.analyze_image`
- `chatgpt_analyze_pdf` → `OpenAIResponsesIntegration.analyze_pdf`

## Configuration/Dependencies
- HTTP: `requests`
- PDF extraction: `pdfplumber`
- Tool schemas: `pydantic`, `langchain_core.tools.StructuredTool` (only for `as_tools`)
- Naas ABI: `Integration`, `IntegrationConfiguration`, `StorageUtils`, `ABIModule`
- Caching:
  - `_make_request(...)` is filesystem-cached (pickle) for **1 day** via `CacheFactory.CacheFS_find_storage(subpath="openai_responses")`
  - cache key includes `(method, endpoint, params, json)` stringified

## Usage

### Direct usage
```python
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIResponsesIntegration import (
    OpenAIResponsesIntegration,
    OpenAIResponsesIntegrationConfiguration,
)

cfg = OpenAIResponsesIntegrationConfiguration(api_key="YOUR_OPENAI_API_KEY")
client = OpenAIResponsesIntegration(cfg)

print(client.search_web("Naas ABI marketplace", return_text=True))
print(client.analyze_image(["https://example.com/image.jpg"], return_text=True))
print(client.analyze_pdf("https://example.com/file.pdf", return_text=True))
```

### LangChain tools
```python
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIResponsesIntegration import (
    as_tools, OpenAIResponsesIntegrationConfiguration
)

tools = as_tools(OpenAIResponsesIntegrationConfiguration(api_key="YOUR_OPENAI_API_KEY"))
```

## Caveats
- `search_web(return_text=True)` may return either a `str` or a `dict` depending on whether annotations are present.
- API errors are returned as `{"error": "...", "text": ...}` from `_make_request` (no exception raised).
- PDF analysis sends extracted text only; output quality depends on `pdfplumber` extraction.
- `_make_request` caches responses for 1 day; repeated identical calls may return cached data.
