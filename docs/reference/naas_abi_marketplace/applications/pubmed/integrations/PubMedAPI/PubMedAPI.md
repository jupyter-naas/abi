# PubMedIntegration

## What it is
A PubMed (NCBI E-utilities) integration that:
- Searches PubMed within a publication date range (splitting date windows to avoid the 9,999-record ESearch cap).
- Fetches article summaries via `esummary`.
- Downloads PubMed Central PDFs by PMCID.

Includes caching for:
- Per-PMID summaries (`pubmed_paper_summary_{pmid}`)
- ESearch ID lists for date windows (decorated cache keyed by SHA1)

All outbound E-utilities calls are rate-limited.

## Public API

### `PubMedAPIConfiguration`
Dataclass configuration (`IntegrationConfiguration`) for the integration.
- `base_url: str` — E-utilities base URL (default: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`)
- `api_key: str | None` — optional NCBI API key
- `retmax: int` — default max records for simple searches (not used by `search_date_range`)
- `timeout: int` — HTTP timeout (seconds)
- `page_size: int` — page size for paginated `esearch` requests (default: `200`)

### `PubMedIntegration(configuration: PubMedAPIConfiguration)`
Main integration class.

#### `search_date_range(query, *, start_date, end_date=None, sort=None, max_results=None) -> list[PubMedPaperSummary]`
Search PubMed over an inclusive date range and return summaries.
- Parses and normalizes dates; if `end_date` is `None`, defaults to today (UTC).
- Swaps dates if `start_date > end_date`.
- Uses `esearch` to count results per window; splits windows until each has `<= 9999` results.
- Fetches PMIDs per window (paged) and deduplicates while preserving order.
- `max_results` caps the total number of returned summaries.

Raises:
- `IntegrationConnectionError` if `start_date`/`end_date` cannot be parsed, or if PubMed returns an API error during ID fetching.

#### `download_pubmed_central_pdf(pmcid: str) -> BinaryIO`
Download a PubMed Central PDF by PMCID.
- Uses `PubMedCentralDownloader.open_pmc_pdf_stream(pmcid)`.
- Returns a `BinaryIO` (`io.BytesIO` if the downloader returns raw `bytes`).

## Configuration/Dependencies

- HTTP: `requests`
- Rate limiting: `ratelimit.limits` set to **3 calls per 1 second**
- Caching:
  - Cache storage: `CacheFactory.CacheFS_find_storage(subpath="pubmed")`
  - Per-PMID summary cache key: `pubmed_paper_summary_{pmid}`
  - ID list caching for `_fetch_ids_for_range` via `@cache(..., cache_type=DataType.PICKLE)` (SHA1 of inputs)
- Ontology models:
  - `PubMedPaperSummary`, `Journal`, `JournalIssue` from `naas_abi_marketplace.applications.pubmed.ontologies.PubMed`
- PDF download helper:
  - `.PubMedCentralDownloader.PubMedCentralDownloader`

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
    max_results=5,
)

for p in papers:
    print(p.pubmedIdentifier, p.title, p.doi, p.pmcid)

if papers and papers[0].pmcid:
    pdf_io = pm.download_pubmed_central_pdf(papers[0].pmcid)
    with open("paper.pdf", "wb") as f:
        f.write(pdf_io.read())
```

## Caveats
- Date parsing accepts multiple formats (e.g., `YYYY-MM-DD`, `YYYY/MM/DD`, `YYYY Mon`, `YYYY`); invalid inputs raise `IntegrationConnectionError`.
- If a single-day window has more than 9,999 results, it is skipped to avoid infinite splitting.
- `_summaries()` fetches new summaries in chunks of 200. Caching associates IDs to summaries by position in the returned list; if PubMed omits some docs for requested IDs, caching can miss or misalign entries for that chunk.
- Rate limit is enforced at 3 requests/second for E-utilities calls; exceeding it may raise errors depending on `ratelimit` behavior.
