"""U.S. SEC EDGAR public data, async, on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.sec_gov.integrations``: same
files and endpoints. SEC requires a descriptive ``User-Agent``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from naas_abi_apps.common.http import HttpConfiguration, request_json
from naas_abi_apps.common.storage import ObjectStorage, archive_json
from naas_abi_sdk.integration import Integration

SERVICE = "SEC"
FILES_URL = "https://www.sec.gov/files"
SUBMISSIONS_URL = "https://data.sec.gov/submissions"
# The ticker files are large: give them longer than the default 60 s.
TIMEOUT = 120.0
# The public ticker files: name -> file under FILES_URL.
TICKER_FILES = {
    "tickers": "company_tickers",
    "exchange": "company_tickers_exchange",
    "mf": "company_tickers_mf",
}


def normalize_cik(cik: str | int) -> str:
    """``"CIK320193"``, ``320193`` -> ``"0000320193"``."""
    digits = "".join(ch for ch in str(cik).strip().removeprefix("CIK") if ch.isdigit())
    return digits.zfill(10)


@dataclass
class SecGovIntegrationConfiguration(HttpConfiguration):
    user_agent: str
    datastore_path: str = "sec_gov"
    storage: ObjectStorage | None = None


class SecGovIntegration(Integration):
    """Company ticker files and per-company submissions."""

    def __init__(self, configuration: SecGovIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration

    async def _get(self, url: str) -> Any:
        return await request_json(
            self.configuration,
            "GET",
            url,
            service=SERVICE,
            headers={
                "User-Agent": self.configuration.user_agent,
                "Accept": "application/json",
            },
        )

    async def get_ticker_file(
        self, file: str = "tickers", save_result: bool = False
    ) -> Any:
        """One of the public ticker files: ``tickers``, ``exchange`` or ``mf``."""
        name = TICKER_FILES[file]
        result = await self._get(f"{FILES_URL}/{name}.json")
        if save_result:
            await archive_json(
                self.configuration.storage,
                f"{self.configuration.datastore_path}/files/{name}",
                f"{name}.json",
                result,
            )
        return result

    async def get_company_tickers(self, save_result: bool = False) -> Any:
        return await self.get_ticker_file("tickers", save_result)

    async def get_company_tickers_exchange(self, save_result: bool = False) -> Any:
        return await self.get_ticker_file("exchange", save_result)

    async def get_company_tickers_mf(self, save_result: bool = False) -> Any:
        return await self.get_ticker_file("mf", save_result)

    async def get_submissions(
        self, cik: str | int, save_result: bool = False
    ) -> dict[str, Any]:
        """Submissions (filings history) of a company by CIK."""
        cik_10 = normalize_cik(cik)
        result = await self._get(f"{SUBMISSIONS_URL}/CIK{cik_10}.json")
        if save_result:
            await archive_json(
                self.configuration.storage,
                f"{self.configuration.datastore_path}/submissions",
                f"CIK{cik_10}.json",
                result,
            )
        return result
