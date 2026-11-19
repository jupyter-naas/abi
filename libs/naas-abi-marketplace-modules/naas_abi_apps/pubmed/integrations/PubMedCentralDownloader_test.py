"""Offline tests of the PMC open access dataset downloader (no network)."""

from __future__ import annotations

import pytest
from naas_abi_apps.pubmed.integrations.PubMedCentralDownloader import (
    PubMedCentralDownloader,
    https_url,
    normalize_pmcid,
)

BASE = "https://pmc-oa-opendata.s3.amazonaws.com"


def listing(*prefixes: str) -> bytes:
    common = "".join(
        f"<CommonPrefixes><Prefix>{p}</Prefix></CommonPrefixes>" for p in prefixes
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Name>pmc-oa-opendata</Name>{common}</ListBucketResult>"
    ).encode()


class FakeResponse:
    def __init__(self, content: bytes = b"", json_value: dict | None = None):
        self.content = content
        self._json = json_value

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict | None:
        return self._json


class FakeSession:
    def __init__(self, routes: dict[str, FakeResponse]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, url: str, params: dict | None = None, timeout: float = 0):
        self.calls.append((url, params))
        return self.routes[url]


def metadata(folder: str, pdf: bool = True) -> dict:
    return {
        "pmcid": folder.split(".")[0],
        "pdf_url": f"s3://pmc-oa-opendata/{folder}/{folder}.pdf?md5=abc"
        if pdf
        else None,
    }


def test_the_newest_version_pdf_is_downloaded() -> None:
    session = FakeSession(
        {
            f"{BASE}/": FakeResponse(listing("PMC123.1/", "PMC123.2/")),
            f"{BASE}/PMC123.2/PMC123.2.json": FakeResponse(
                json_value=metadata("PMC123.2")
            ),
            f"{BASE}/PMC123.2/PMC123.2.pdf": FakeResponse(b"%PDF v2"),
        }
    )

    stream = PubMedCentralDownloader(session=session).open_pmc_pdf_stream("123")

    assert stream.read() == b"%PDF v2"
    # The listing is scoped with a trailing dot: PMC123 must not match PMC1234.
    assert session.calls[0][1] == {
        "list-type": "2",
        "prefix": "PMC123.",
        "delimiter": "/",
    }


def test_an_article_outside_the_dataset_is_not_found() -> None:
    session = FakeSession({f"{BASE}/": FakeResponse(listing())})

    with pytest.raises(FileNotFoundError, match="not in the PubMed Central"):
        PubMedCentralDownloader(session=session).open_pmc_pdf_stream("PMC9")


def test_an_article_without_a_pdf_is_not_found() -> None:
    session = FakeSession(
        {
            f"{BASE}/": FakeResponse(listing("PMC7.1/")),
            f"{BASE}/PMC7.1/PMC7.1.json": FakeResponse(
                json_value=metadata("PMC7.1", pdf=False)
            ),
        }
    )

    with pytest.raises(FileNotFoundError, match="no PDF"):
        PubMedCentralDownloader(session=session).open_pmc_pdf_stream("PMC7")


def test_pmcids_and_pdf_locations_are_validated() -> None:
    assert normalize_pmcid(" pmc42 ") == "PMC42"
    with pytest.raises(ValueError):
        normalize_pmcid("PMC42/../x")
    assert https_url("s3://pmc-oa-opendata/PMC1.1/PMC1.1.pdf?md5=x") == (
        f"{BASE}/PMC1.1/PMC1.1.pdf"
    )
    with pytest.raises(ValueError):
        https_url("s3://another-bucket/PMC1.1/PMC1.1.pdf")
