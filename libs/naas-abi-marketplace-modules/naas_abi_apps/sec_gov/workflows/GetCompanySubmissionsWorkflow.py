"""A company's SEC filings summary (``workflow.get_company_submissions_workflow``).

The full submissions JSON is stored in object storage; the result holds the
company identity and its most recent filings, within the 60 KiB result limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from naas_abi_apps.sec_gov.integrations.SecGovIntegration import (
    SecGovIntegration,
    SecGovIntegrationConfiguration,
    normalize_cik,
)
from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import Field

RECENT_FIELDS = ("accessionNumber", "filingDate", "form", "primaryDocument")


@dataclass
class GetCompanySubmissionsWorkflowConfiguration(WorkflowConfiguration):
    integration: SecGovIntegrationConfiguration | None = None


class GetCompanySubmissionsWorkflowParameters(WorkflowParameters):
    cik: str = Field(
        ...,
        description="Central Index Key of the company, e.g. 320193 or CIK0000320193",
    )
    recent: int = Field(
        20, ge=0, le=200, description="How many of the most recent filings to return"
    )


class GetCompanySubmissionsWorkflow(Workflow[GetCompanySubmissionsWorkflowParameters]):
    """Get a company's identity (name, tickers, exchanges, SIC) and most recent
    SEC filings by CIK; the full submissions file is stored in object storage."""

    def __init__(self, configuration: GetCompanySubmissionsWorkflowConfiguration):
        super().__init__(configuration)
        assert configuration.integration is not None
        self.integration_configuration = configuration.integration

    @classmethod
    def New(cls, module: Any) -> GetCompanySubmissionsWorkflow:
        return cls(
            GetCompanySubmissionsWorkflowConfiguration(
                integration=module.integration_configuration()
            )
        )

    async def run(
        self, parameters: GetCompanySubmissionsWorkflowParameters
    ) -> dict[str, Any]:
        integration = SecGovIntegration(self.integration_configuration)
        submissions = await integration.get_submissions(
            parameters.cik, save_result=True
        )
        recent = (submissions.get("filings") or {}).get("recent") or {}
        columns = [recent.get(name) or [] for name in RECENT_FIELDS]
        filings = [
            dict(zip(RECENT_FIELDS, row, strict=False))
            for row in zip(*columns, strict=False)
        ]
        cik_10 = normalize_cik(parameters.cik)
        return {
            "cik": cik_10,
            "name": submissions.get("name"),
            "tickers": submissions.get("tickers", []),
            "exchanges": submissions.get("exchanges", []),
            "sic": submissions.get("sic"),
            "sic_description": submissions.get("sicDescription"),
            "recent_filings": filings[: parameters.recent],
            "stored": {
                "prefix": f"{self.integration_configuration.datastore_path}/submissions",
                "key": f"CIK{cik_10}.json",
            },
        }
