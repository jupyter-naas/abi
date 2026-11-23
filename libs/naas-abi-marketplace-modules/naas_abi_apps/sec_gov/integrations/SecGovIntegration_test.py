"""Offline tests of the SEC integration and workflows: an httpx MockTransport."""

from __future__ import annotations

import asyncio
import json

import httpx
from naas_abi_apps.common.testing import MemoryStorage
from naas_abi_apps.sec_gov.integrations.SecGovIntegration import (
    SecGovIntegration,
    SecGovIntegrationConfiguration,
    normalize_cik,
)
from naas_abi_apps.sec_gov.workflows.DownloadCompanyTickersWorkflow import (
    DownloadCompanyTickersWorkflow,
    DownloadCompanyTickersWorkflowConfiguration,
    DownloadCompanyTickersWorkflowParameters,
)
from naas_abi_apps.sec_gov.workflows.GetCompanySubmissionsWorkflow import (
    GetCompanySubmissionsWorkflow,
    GetCompanySubmissionsWorkflowConfiguration,
    GetCompanySubmissionsWorkflowParameters,
)

SUBMISSIONS = {
    "name": "Apple Inc.",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "sic": "3571",
    "sicDescription": "Electronic Computers",
    "filings": {
        "recent": {
            "accessionNumber": ["a1", "a2", "a3"],
            "filingDate": ["2026-01-03", "2026-01-02", "2026-01-01"],
            "form": ["10-K", "8-K", "4"],
            "primaryDocument": ["d1", "d2", "d3"],
        }
    },
}


def handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["User-Agent"] == "ACME research (ops@acme.io)"
    if request.url.path == "/files/company_tickers.json":
        return httpx.Response(
            200, json={"0": {"ticker": "AAPL"}, "1": {"ticker": "MSFT"}}
        )
    if request.url.path == "/submissions/CIK0000320193.json":
        return httpx.Response(200, json=SUBMISSIONS)
    return httpx.Response(404)


def configuration(storage=None) -> SecGovIntegrationConfiguration:
    return SecGovIntegrationConfiguration(
        user_agent="ACME research (ops@acme.io)",
        storage=storage,
        transport=httpx.MockTransport(handler),
    )


def test_normalize_cik() -> None:
    assert normalize_cik("CIK320193") == normalize_cik(320193) == "0000320193"


def test_ticker_file_is_saved_only_when_asked() -> None:
    storage = MemoryStorage()
    integration = SecGovIntegration(configuration(storage))

    asyncio.run(integration.get_company_tickers())
    assert storage.objects == {}
    asyncio.run(integration.get_company_tickers(save_result=True))
    assert ("sec_gov/files/company_tickers", "company_tickers.json") in storage.objects


def test_download_workflow_stores_the_file_and_returns_where() -> None:
    storage = MemoryStorage()
    workflow = DownloadCompanyTickersWorkflow(
        DownloadCompanyTickersWorkflowConfiguration(integration=configuration(storage))
    )

    result = asyncio.run(workflow.run(DownloadCompanyTickersWorkflowParameters()))

    assert result == {
        "prefix": "sec_gov/files/company_tickers",
        "key": "company_tickers.json",
        "entries": 2,
    }
    assert (
        json.loads(storage.objects[(result["prefix"], result["key"])])["1"]["ticker"]
        == "MSFT"
    )


def test_submissions_workflow_returns_a_bounded_summary() -> None:
    storage = MemoryStorage()
    workflow = GetCompanySubmissionsWorkflow(
        GetCompanySubmissionsWorkflowConfiguration(integration=configuration(storage))
    )

    result = asyncio.run(
        workflow.run(GetCompanySubmissionsWorkflowParameters(cik="320193", recent=2))
    )

    assert result["name"] == "Apple Inc." and result["cik"] == "0000320193"
    assert result["recent_filings"] == [
        {
            "accessionNumber": "a1",
            "filingDate": "2026-01-03",
            "form": "10-K",
            "primaryDocument": "d1",
        },
        {
            "accessionNumber": "a2",
            "filingDate": "2026-01-02",
            "form": "8-K",
            "primaryDocument": "d2",
        },
    ]
    assert (result["stored"]["prefix"], result["stored"]["key"]) in storage.objects
