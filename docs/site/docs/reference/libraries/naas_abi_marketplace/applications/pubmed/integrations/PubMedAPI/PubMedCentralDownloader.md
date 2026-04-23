# PubMedCentralDownloader

## What it is
A small utility class to locate and download a PubMed Central (PMC) PDF given a PMCID, using the local `oa_file_list.txt` mapping file and streaming/downloading from the NCBI PMC FTP endpoint.

## Public API

- **Class: `PubMedCentralDownloader`**
  - **`find_pdf_path(pmcid: str, oa_file_list_path: str) -> str`**
    - Streams through the given OA file list to find the relative FTP path (PDF or `.tar.gz`) associated with a PMCID.
    - Raises `FileNotFoundError` if no matching entry is found.
  - **`open_pmc_pdf_stream(pmcid: str, oa_file_list_path: str = "oa_file_list.txt") -> BinaryIO`**
    - Returns an open binary stream containing the PMC PDF bytes.
    - If the OA entry points to a `.pdf`, returns the underlying HTTP raw stream.
    - If it points to a `.tar.gz`, downloads the archive content, extracts the first `.pdf` found, and returns a `BytesIO` stream.
    - Raises `FileNotFoundError` for missing PDFs or unsupported path types.
    - Caller is responsible for closing the returned stream.

## Configuration/Dependencies
- **External dependency:** `requests` (imported dynamically via `importlib.import_module("requests")`)
- **Local input file:** `oa_file_list.txt` (default name; path configurable via parameters)
- **Remote base URL constant:** `PMC_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/"`

## Usage

```python
from naas_abi_marketplace.applications.pubmed.integrations.PubMedAPI.PubMedCentralDownloader import (
    PubMedCentralDownloader
)

downloader = PubMedCentralDownloader()

pmcid = "PMC1234567"
with downloader.open_pmc_pdf_stream(pmcid, oa_file_list_path="oa_file_list.txt") as pdf_stream:
    pdf_bytes = pdf_stream.read()

with open(f"{pmcid}.pdf", "wb") as f:
    f.write(pdf_bytes)
```

## Caveats
- `open_pmc_pdf_stream` **fully downloads** `.tar.gz` archives into memory (`response.content`) before extracting a PDF.
- `find_pdf_path` expects the OA file list to contain tab-delimited (or whitespace-delimited) lines where:
  - `parts[0]` is the relative path, and
  - one of `parts[1:]` equals the provided `pmcid`.
- Network call uses a fixed `timeout=60` and a hardcoded `User-Agent` string.
