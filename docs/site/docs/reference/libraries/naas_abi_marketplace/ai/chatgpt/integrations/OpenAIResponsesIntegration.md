# OpenAIResponsesIntegration

## What it is
A Naas ABI `Integration` that calls the OpenAI **Responses API** to:
- run web search via the `web_search_preview` tool,
- analyze images from URLs,
- analyze PDFs by downloading and extracting text, then sending it to the model.

Each call stores the raw JSON response to a local/object storage-backed datastore path.

## Public API

### `OpenAIResponsesIntegrationConfiguration`
Dataclass configuration for the integration.
- `api_key: str` (required): OpenAI API key.
- `model: str = "gpt-4.1-mini"`: Model name sent in the payload.
- `base_url: str = "https://api.openai.com/v1/responses"`: Responses API endpoint base.
- `datastore_path: str`: Defaults to `ABIModule.get_instance().configuration.datastore_path`.

### `OpenAIResponsesIntegration`
Integration implementation.

#### `search_web(query: str, search_context_size: str = "medium", return_text: bool = False) -> Dict`
- Sends a Responses API request using the `web_search_preview` tool.
- Persists the JSON response under:
  - `{datastore_path}/responses/web_search/{model}/...json`
- If `return_text=True`, attempts to extract the first `output_text` from the first `message` in `response["output"]` and returns `{"content": <text>}` (or a fallback message).

#### `analyze_image(image_urls: list[str], user_prompt: str = "Describe this image:", detail: str = "auto", return_text: bool = False) -> Dict`
- Sends one user message containing:
  - an `input_text` prompt and one or more `input_image` entries (URLs).
- Persists the JSON response under:
  - `{datastore_path}/responses/analyze_image/{model}/...json`
- If `return_text=True`, returns `{"content": <first text found>}` or a fallback message.

#### `analyze_pdf(pdf_url: str, user_prompt: str = "Describe this PDF document:", system_prompt: str = "...", return_text: bool = False) -> Dict | str`
- Downloads the PDF from `pdf_url`, extracts text via `pdfplumber`, then sends extracted text as `input_text`.
- Persists the JSON response under:
  - `{datastore_path}/responses/analyze_pdf/{model}/...json`
- If `return_text=True`, returns `{"content": <text>}` and may append an “Annotations” section if `url_citation` items are found in message content.
- On PDF download/extraction error, returns the error as a string.

### `as_tools(configuration: OpenAIResponsesIntegrationConfiguration)`
Returns a list of LangChain `StructuredTool` objects wired to an `OpenAIResponsesIntegration` instance:
- `chatgpt_search_web` → `search_web`
- `chatgpt_analyze_image` → `analyze_image`
- `chatgpt_analyze_pdf` → `analyze_pdf`

## Configuration/Dependencies
- External libs:
  - `requests` (HTTP calls)
  - `pdfplumber` (PDF text extraction)
  - `pydantic` (tool schemas)
  - `langchain_core.tools.StructuredTool` (only used by `as_tools`)
- Naas ABI components:
  - `Integration`, `IntegrationConfiguration`
  - `StorageUtils` and `ABIModule` for saving responses
  - Filesystem cache via `CacheFactory.CacheFS_find_storage(...)`
- Caching:
  - `_make_request(...)` is cached for **1 day** (pickle), keyed by `(method, endpoint, params, json)`.

## Usage

### Direct integration usage
```python
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIResponsesIntegration import (
    OpenAIResponsesIntegration,
    OpenAIResponsesIntegrationConfiguration,
)

cfg = OpenAIResponsesIntegrationConfiguration(api_key="YOUR_OPENAI_API_KEY")
client = OpenAIResponsesIntegration(cfg)

# Web search
result = client.search_web("Latest Python release notes", return_text=True)
print(result)  # {"content": "..."} or full response if return_text=False

# Image analysis
img = client.analyze_image(
    image_urls=["https://example.com/image.jpg"],
    user_prompt="What is shown in this image?",
    return_text=True,
)
print(img)

# PDF analysis
pdf = client.analyze_pdf(
    pdf_url="https://example.com/file.pdf",
    user_prompt="Summarize this document",
    return_text=True,
)
print(pdf)
```

### LangChain tools
```python
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIResponsesIntegration import (
    as_tools, OpenAIResponsesIntegrationConfiguration
)

tools = as_tools(OpenAIResponsesIntegrationConfiguration(api_key="YOUR_OPENAI_API_KEY"))
# tools is a list of StructuredTool instances
```

## Caveats
- `_make_request(...)` uses mutable default arguments (`params={}`, `json={}`); avoid mutating these externally.
- `search_web(return_text=True)` returns a `dict` with `{"content": ...}` in most cases, but may return a raw string in one branch when no annotations exist.
- PDF analysis sends **extracted text only** (no images/pages), so results depend on extraction quality.
- API errors are returned as `{"error": "...", "text": response.text}` (when available) rather than raising.
