# PubMedCentralDownloader

## What it is
A small utility for locating and downloading a PubMed Central (PMC) PDF for a given **PMCID** by:
- looking up the file location in a local `oa_file_list.txt` mapping file, then
- fetching the content from the NCBI PMC FTP HTTPS endpoint.

## Public API

- **Constant: `PMC_FTP_BASE`**
  - Base URL used to fetch PMC files: `https://ftp.ncbi.nlm.nih.gov/pub/pmc/`

- **Class: `PubMedCentralDownloader`**
  - **`find_pdf_path(pmcid: str, oa_file_list_path: str) -> str`**
    - Streams `oa_file_list_path` line-by-line to find the relative path associated with `pmcid`.
    - Accepts tab-delimited lines; falls back to generic whitespace split.
    - Returns the matched relative path (e.g., `.pdf` or `.tar.gz`).
    - Raises `FileNotFoundError` if no entry is found.

  - **`open_pmc_pdf_stream(pmcid: str, oa_file_list_path: str = "oa_file_list.txt") -> BinaryIO`**
    - Resolves the PMC file path via `find_pdf_path`, downloads it, and returns a binary stream of the PDF bytes.
    - Behavior depends on resolved path:
      - **`.pdf`**: returns `response.raw` (streaming HTTP response body).
      - **`.tar.gz`**: downloads the archive (`response.content`), extracts the **first** `.pdf` member found, and returns an in-memory `io.BytesIO`.
    - Raises `FileNotFoundError` when:
      - no PDF exists in the archive,
      - extraction fails, or
      - the path extension is unsupported.
    - The caller is responsible for closing the returned stream.

## Configuration/Dependencies
- **Third-party dependency:** `requests` (imported dynamically via `importlib.import_module("requests")`).
- **Input file:** `oa_file_list.txt` (default in `open_pmc_pdf_stream`; configurable via `oa_file_list_path`).
- **Network behavior:**
  - `requests.get(..., stream=True, timeout=60)`
  - Sends header: `User-Agent: PMC-open-stream/1.0 (mailto:you@example.com)`

## Usage

```python
from naas_abi_marketplace.applications.pubmed.integrations.PubMedAPI.PubMedCentralDownloader import (
    PubMedCentralDownloader
)

downloader = PubMedCentralDownloader()
pmcid = "PMC1234567"

pdf_stream = downloader.open_pmc_pdf_stream(pmcid, oa_file_list_path="oa_file_list.txt")
try:
    with open(f"{pmcid}.pdf", "wb") as f:
        f.write(pdf_stream.read())
finally:
    pdf_stream.close()
```

## Caveats
- For `.tar.gz` entries, the archive is **fully loaded into memory** via `response.content` before extraction.
- For `.pdf` entries, the returned stream is `response.raw`; closing it is required to release the HTTP connection.
- `find_pdf_path` matches `pmcid` only if it appears exactly in one of the columns after the first column (the path).
