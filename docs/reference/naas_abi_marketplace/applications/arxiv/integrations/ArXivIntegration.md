# ArXivIntegration

## What it is
- An integration wrapper around the `arxiv` Python client for:
  - Searching ArXiv papers
  - Fetching metadata for a specific ArXiv paper
- Can also expose these capabilities as LangChain `StructuredTool` tools.

## Public API

### `ArXivIntegrationConfiguration`
- Dataclass extending `IntegrationConfiguration`.
- Fields:
  - `max_results: int = 10` — default maximum number of search results when not provided per-call.

### `ArXivIntegration`
Integration class (extends `naas_abi_core.integration.Integration`).

#### `__init__(configuration: ArXivIntegrationConfiguration)`
- Creates an `arxiv.Client()` and stores configuration.

#### `search_papers(query: str, max_results: Optional[int] = None) -> List[dict]`
- Searches ArXiv with `arxiv.Search(query=..., max_results=...)`.
- Returns a list of paper metadata dictionaries with keys:
  - `id`, `title`, `authors`, `summary`, `published`, `updated`, `categories`, `links`, `pdf_url`

#### `get_paper(paper_id: str) -> dict`
- Fetches metadata for one paper using `arxiv.Search(id_list=[paper_id])`.
- Returns a metadata dictionary with the same keys as `search_papers`.

#### `as_tools(configuration: ArXivIntegrationConfiguration) -> List[StructuredTool]` (staticmethod)
- Builds and returns two LangChain `StructuredTool` instances:
  - `search_arxiv_papers` → calls `search_papers`
  - `get_arxiv_paper` → calls `get_paper`
- Uses Pydantic argument schemas defined inside the method.

## Configuration/Dependencies
- Depends on:
  - `arxiv` (Python package)
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (`BaseModel`, `Field`)
  - `naas_abi_core.integration` (`Integration`, `IntegrationConfiguration`)
- Configuration:
  - `ArXivIntegrationConfiguration.max_results` controls default search result count.

## Usage

### Direct integration usage
```python
from naas_abi_marketplace.applications.arxiv.integrations.ArXivIntegration import (
    ArXivIntegration,
    ArXivIntegrationConfiguration,
)

cfg = ArXivIntegrationConfiguration(max_results=5)
client = ArXivIntegration(cfg)

papers = client.search_papers("cat:cs.CL")
print(papers[0]["id"], papers[0]["title"])

paper = client.get_paper(papers[0]["id"])
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
- `get_paper` uses `next(self.__client.results(search))`; if no results are returned for the given `paper_id`, it will raise `StopIteration`.
- `id` is derived from `paper.entry_id.split("/")[-1]` (the last URL segment of the entry id).
