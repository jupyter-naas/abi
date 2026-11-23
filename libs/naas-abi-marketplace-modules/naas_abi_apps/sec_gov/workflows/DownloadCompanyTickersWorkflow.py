"""Download an SEC ticker file into object storage (``workflow.download_company_tickers_workflow``).

The files are over a megabyte, past a durable workflow's 60 KiB result: the
workflow stores the file and returns where it is, with its entry count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from naas_abi_apps.sec_gov.integrations.SecGovIntegration import (
    TICKER_FILES,
    SecGovIntegration,
    SecGovIntegrationConfiguration,
)
from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import Field


@dataclass
class DownloadCompanyTickersWorkflowConfiguration(WorkflowConfiguration):
    integration: SecGovIntegrationConfiguration | None = None


class DownloadCompanyTickersWorkflowParameters(WorkflowParameters):
    file: Literal["tickers", "exchange", "mf"] = Field(
        "tickers",
        description="tickers: company_tickers.json, exchange: company_tickers_exchange.json, mf: company_tickers_mf.json",
    )


class DownloadCompanyTickersWorkflow(
    Workflow[DownloadCompanyTickersWorkflowParameters]
):
    """Download an SEC EDGAR company tickers file into object storage and return
    its location and number of entries."""

    def __init__(self, configuration: DownloadCompanyTickersWorkflowConfiguration):
        super().__init__(configuration)
        assert configuration.integration is not None
        self.integration_configuration = configuration.integration

    @classmethod
    def New(cls, module: Any) -> DownloadCompanyTickersWorkflow:
        return cls(
            DownloadCompanyTickersWorkflowConfiguration(
                integration=module.integration_configuration()
            )
        )

    async def run(
        self, parameters: DownloadCompanyTickersWorkflowParameters
    ) -> dict[str, Any]:
        integration = SecGovIntegration(self.integration_configuration)
        data = await integration.get_ticker_file(parameters.file, save_result=True)
        name = TICKER_FILES[parameters.file]
        entries = len(data.get("data", data)) if isinstance(data, dict) else len(data)
        return {
            "prefix": f"{self.integration_configuration.datastore_path}/files/{name}",
            "key": f"{name}.json",
            "entries": entries,
        }
