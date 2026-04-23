# PubMedIntegration

## What it is
A PubMed (NCBI E-utilities) integration that:
- Searches PubMed within a date range (splitting windows to avoid the 9,999 record cap).
- Retrieves paper summaries via `esummary`.
- Downloads PubMed Central PDFs by PMCID.

It includes caching for fetched IDs and per-PMID summaries, and rate-limits outbound API calls.

## Public API

### `PubMedAPIConfiguration`
Dataclass configuration for the integration.
- `base_url: str` — E-utilities base URL (default `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`)
- `api_key: Optional[str]` — NCBI API key (optional)
- `retmax: int` — default max records for simple searches (not directly used in `search_date_range`)
- `timeout: int` — HTTP timeout seconds
- `page_size: int` — page size for paginated `esearch` requests (default `200`)

### `PubMedIntegration(configuration: PubMedAPIConfiguration)`
Main integration class.

#### `search_date_range(query, *, start_date, end_date=None, sort=None, max_results=None) -> List[PubMedPaperSummary]`
Search PubMed over an inclusive date range and return a list of `PubMedPaperSummary`.
- Splits the date window if an `esearch` count exceeds 9,999.
- Deduplicates PMIDs while preserving order.
- `end_date` defaults to today.
- `max_results` caps total returned across the whole range.

Raises:
- `IntegrationConnectionError` for invalid date formats or PubMed API errors.

#### `download_pubmed_central_pdf(pmcid: str) -> BinaryIO`
Download a PubMed Central PDF for a given PMCID.
- Returns a `BinaryIO` (wraps `bytes` in `io.BytesIO`).

## Configuration/Dependencies
- HTTP: `requests`
- Rate limiting: `ratelimit.limits` (configured as 3 calls per 1 second)
- Caching:
  - Uses `naas_abi_core.services.cache`:
    - A module-level cache store: `CacheFactory.CacheFS_find_storage(subpath="pubmed")`
    - Per-PMID summaries cached under keys like `pubmed_paper_summary_{pmid}`
    - `_fetch_ids_for_range` results cached via a decorator (pickle), keyed by a SHA1 of inputs
- Ontology models:
  - `PubMedPaperSummary`, `Journal`, `JournalIssue` from `naas_abi_marketplace.applications.pubmed.ontologies.PubMed`
- PDF download:
  - `PubMedCentralDownloader.open_pmc_pdf_stream(pmcid)` (returns `bytes` or `BinaryIO`)

## Usage

```python
from naas_abi_marketplace.applications.pubmed.integrations.PubMedAPI.PubMedAPI import (
    PubMedIntegration,
    PubMedAPIConfiguration,
)

cfg = PubMedAPIConfiguration(api_key=None, timeout=30, page_size=200)
pm = PubMedIntegration(cfg)

papers = pm.search_date_range(
    "cancer immunotherapy",
    start_date="2023-01-01",
    end_date="2023-01-31",
    max_results=10,
)

for p in papers:
    print(p.pubmedIdentifier, p.title, p.doi, p.pmcid)

# Download a PMC PDF (requires a valid PMCID)
if papers and papers[0].pmcid:
    pdf_io = pm.download_pubmed_central_pdf(papers[0].pmcid)
    with open("paper.pdf", "wb") as f:
        f.write(pdf_io.read())
```

## Caveats
- Date parsing accepts several common formats; invalid `start_date`/`end_date` raises `IntegrationConnectionError`.
- If a single-day window exceeds 9,999 results, it is skipped (to avoid infinite splitting).
- `_summaries()` fetches summaries in chunks of 200 via `esummary` POST, but caching logic assumes positional alignment between requested IDs and returned docs; missing docs may lead to incomplete caching for some IDs.
- Outbound calls are rate-limited to **3 requests/second** (may raise if exceeded, depending on `ratelimit` behavior).
