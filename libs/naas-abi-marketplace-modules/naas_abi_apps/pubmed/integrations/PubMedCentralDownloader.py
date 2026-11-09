"""PubMed Central PDFs from the PMC Article Datasets on AWS (``pmc-oa-opendata``).

NCBI retired both sources the in-engine downloader used: the OA web service
(``/pmc/utils/oa/oa.fcgi``) and the ``oa_package`` / ``oa_pdf`` trees of its FTP
site. The in-engine code also needed a local ``oa_file_list.txt`` that no image
shipped. Each article is now a public bucket folder ``PMC<id>.<version>/``
holding ``PMC<id>.<version>.json``, whose ``pdf_url`` names the PDF when PMC has
one. Plain HTTPS, no credentials.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false, reportMissingTypeStubs=false
import importlib
import io
import re
import xml.etree.ElementTree as ET
from typing import Any, BinaryIO
from urllib.parse import urlsplit

requests: Any = importlib.import_module("requests")

PMC_OPEN_DATA_URL = "https://pmc-oa-opendata.s3.amazonaws.com"
PMC_OPEN_DATA_BUCKET = "pmc-oa-opendata"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
_PMCID = re.compile(r"^(?:PMC)?(\d+)$", re.IGNORECASE)


def normalize_pmcid(pmcid: str) -> str:
    """``"PMC123"``, ``"pmc123"`` or ``"123"`` -> ``"PMC123"``."""
    match = _PMCID.match(pmcid.strip())
    if not match:
        raise ValueError(f"Not a PMCID: {pmcid!r}")
    return f"PMC{match.group(1)}"


def https_url(s3_url: str, base_url: str = PMC_OPEN_DATA_URL) -> str:
    """``s3://pmc-oa-opendata/<key>?md5=...`` -> ``<base_url>/<key>``."""
    parts = urlsplit(s3_url)
    if parts.scheme != "s3" or parts.netloc != PMC_OPEN_DATA_BUCKET:
        raise ValueError(f"Unexpected PDF location: {s3_url!r}")
    return f"{base_url}{parts.path}"


class PubMedCentralDownloader:
    def __init__(
        self,
        base_url: str = PMC_OPEN_DATA_URL,
        timeout: float = 60,
        session: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session if session is not None else requests

    def _get(self, url: str, **params: str) -> Any:
        response = self.session.get(url, params=params or None, timeout=self.timeout)
        response.raise_for_status()
        return response

    def latest_version(self, pmcid: str) -> int:
        """The newest version of the article in the dataset.

        Raises FileNotFoundError when the article is not in it (not open access,
        or no such PMCID).
        """
        # The trailing dot keeps PMC123 from matching PMC1234.
        response = self._get(
            f"{self.base_url}/",
            **{"list-type": "2", "prefix": f"{pmcid}.", "delimiter": "/"},
        )
        root = ET.fromstring(response.content)
        versions = []
        for prefix in root.findall("s3:CommonPrefixes/s3:Prefix", S3_NS):
            version = (prefix.text or "").removeprefix(f"{pmcid}.").rstrip("/")
            if version.isdigit():
                versions.append(int(version))
        if not versions:
            raise FileNotFoundError(
                f"{pmcid} is not in the PubMed Central open access dataset"
            )
        return max(versions)

    def pdf_url(self, pmcid: str) -> str:
        """HTTPS URL of the article's PDF (newest version)."""
        pmcid = normalize_pmcid(pmcid)
        version = self.latest_version(pmcid)
        folder = f"{pmcid}.{version}"
        metadata = self._get(f"{self.base_url}/{folder}/{folder}.json").json()
        if not metadata.get("pdf_url"):
            raise FileNotFoundError(f"PubMed Central has no PDF for {pmcid}")
        return https_url(metadata["pdf_url"], self.base_url)

    def open_pmc_pdf_stream(self, pmcid: str) -> BinaryIO:
        """The article's PDF, read into memory."""
        return io.BytesIO(self._get(self.pdf_url(pmcid)).content)
