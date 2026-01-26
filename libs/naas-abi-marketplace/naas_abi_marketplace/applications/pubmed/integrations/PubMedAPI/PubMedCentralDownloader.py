# pyright: reportMissingImports=false, reportMissingModuleSource=false, reportMissingTypeStubs=false
import io
import tarfile
import importlib
from typing import Any, BinaryIO

requests: Any = importlib.import_module("requests")

PMC_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/"

class PubMedCentralDownloader:

    def find_pdf_path(self, pmcid: str, oa_file_list_path: str) -> str:
        """
        Stream over oa_file_list.txt line by line to find the relative archive (or PDF) path
        for a given PMCID. Does not load the whole file into memory.
        """
        with open(oa_file_list_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                parts = line.strip().split("\t")
                if len(parts) < 2:
                    parts = line.strip().split()
                if len(parts) < 2:
                    continue

                path = parts[0]
                if any(col == pmcid for col in parts[1:]):
                    return path

        raise FileNotFoundError(f"No entry found for {pmcid}")

    def open_pmc_pdf_stream(self, pmcid: str, oa_file_list_path: str = "oa_file_list.txt") -> BinaryIO:
        """
        Returns an open binary stream to the PMC PDF.
        The caller is responsible for closing the stream.
        """
        relative_path = self.find_pdf_path(pmcid, oa_file_list_path)
        url = PMC_FTP_BASE + relative_path

        response = requests.get(
            url,
            stream=True,
            headers={
                "User-Agent": "PMC-open-stream/1.0 (mailto:you@example.com)"
            },
            timeout=60,
        )
        response.raise_for_status()

        if relative_path.endswith(".pdf"):
            return response.raw

        if relative_path.endswith(".tar.gz"):
            # The OA file list points to a tarball; download it fully then extract the first PDF.
            archive_bytes = response.content
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
                pdf_member = next((m for m in tar.getmembers() if m.name.lower().endswith(".pdf")), None)
                if not pdf_member:
                    raise FileNotFoundError(f"No PDF found inside archive for {pmcid}")

                extracted = tar.extractfile(pdf_member)
                if not extracted:
                    raise FileNotFoundError(f"Could not extract PDF for {pmcid}")

                pdf_bytes = extracted.read()

            response.close()
            return io.BytesIO(pdf_bytes)

        raise FileNotFoundError(f"Unsupported path type for {pmcid}: {relative_path}")

