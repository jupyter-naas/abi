# ArXivIntegration

## What it is
- A thin integration wrapper around the `arxiv` Python client to:
  - Search ArXiv papers
  - Fetch metadata for a specific ArXiv paper by ID
- Can also expose these capabilities as LangChain `StructuredTool` tools.

## Public API

### `ArXivIntegrationConfiguration`
- Dataclass extending `IntegrationConfiguration`.
- Fields:
  - `max_results: int = 10` — default maximum number of search results when `max_results` is not provided per call.

### `ArXivIntegration`
Integration class (extends `naas_abi_core.integration.Integration`).

- `__init__(configuration: ArXivIntegrationConfiguration)`
  - Stores configuration and creates an `arxiv.Client()`.

- `search_papers(query: str, max_results: int | None = None) -> list[dict]`
  - Runs `arxiv.Search(query=..., max_results=...)`.
  - Returns a list of metadata dictionaries with keys:
    - `id` (derived from `paper.entry_id.split("/")[-1]`)
    - `title`
    - `authors` (list of strings)
    - `summary`
    - `published`
    - `updated`
    - `categories`
    - `links` (list of link href strings)
    - `pdf_url`

- `get_paper(paper_id: str) -> dict`
  - Runs `arxiv.Search(id_list=[paper_id])` and returns the first result.
  - Returns a metadata dictionary with the same keys as `search_papers`.

- `as_tools(configuration: ArXivIntegrationConfiguration) -> list[StructuredTool]` (staticmethod)
  - Builds two LangChain `StructuredTool` tools backed by an internal `ArXivIntegration` instance:
    - `search_arxiv_papers` → calls `search_papers`
    - `get_arxiv_paper` → calls `get_paper`
  - Uses inline Pydantic schemas for tool arguments:
    - `query: str`, `max_results: int | None`
    - `paper_id: str`

## Configuration/Dependencies
- Dependencies:
  - `arxiv`
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (`BaseModel`, `Field`)
  - `naas_abi_core.integration` (`Integration`, `IntegrationConfiguration`)
- Configuration:
  - `ArXivIntegrationConfiguration.max_results` sets the default search result count.

## Usage

### Direct usage
```python
from naas_abi_marketplace.applications.arxiv.integrations.ArXivIntegration import (
    ArXivIntegration,
    ArXivIntegrationConfiguration,
)

cfg = ArXivIntegrationConfiguration(max_results=5)
arxiv_integration = ArXivIntegration(cfg)

papers = arxiv_integration.search_papers("cat:cs.CL")
print(papers[0]["id"], papers[0]["title"])

paper = arxiv_integration.get_paper(papers[0]["id"])
print(paper["pdf_url"])
```

### As LangChain tools
```python
from naas_abi_marketplace.applications.arxiv.integrations.ArXivIntegration import (
    ArXivIntegration,
    ArXivIntegrationConfiguration,
)

tools = ArXivIntegration.as_tools(ArXivIntegrationConfiguration(max_results=3))

result = tools[0].func(query="quantum computing", max_results=2)
print(len(result))
```

## Caveats
- `get_paper()` uses `next(self.__client.results(search))`; if the ID yields no results, it raises `StopIteration`.
- Returned `id` is derived from the last path segment of `paper.entry_id` (not necessarily the full entry URL).
