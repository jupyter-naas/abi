"""Find an organization's LinkedIn page (company, school, showcase) with Google
Search (``workflow.search_linked_in_organization_page_workflow``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from naas_abi_apps.common.storage import archive_json
from naas_abi_apps.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegration,
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)
from naas_abi_apps.google_search.workflows._linkedin import credentials, page_of
from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import Field

ORGANIZATION_URL = re.compile(
    r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"
)


@dataclass
class SearchLinkedInOrganizationPageWorkflowConfiguration(WorkflowConfiguration):
    integration: GoogleProgrammableSearchEngineIntegrationConfiguration | None = None


class SearchLinkedInOrganizationPageWorkflowParameters(WorkflowParameters):
    organization_name: str = Field(
        ..., description="Name of the organization to search for"
    )


class SearchLinkedInOrganizationPageWorkflow(
    Workflow[SearchLinkedInOrganizationPageWorkflowParameters]
):
    """Search for LinkedIn organization page URL using Google Programmable Search Engine."""

    def __init__(
        self, configuration: SearchLinkedInOrganizationPageWorkflowConfiguration
    ):
        super().__init__(configuration)
        assert configuration.integration is not None
        self.integration_configuration = configuration.integration

    @classmethod
    async def New(cls, module: Any) -> SearchLinkedInOrganizationPageWorkflow:
        return cls(
            SearchLinkedInOrganizationPageWorkflowConfiguration(
                integration=module.integration_configuration(await credentials(module))
            )
        )

    async def run(
        self, parameters: SearchLinkedInOrganizationPageWorkflowParameters
    ) -> list[dict[str, Any]]:
        query = f"{parameters.organization_name.replace(' ', '+')}+site:linkedin.com"
        results = await GoogleProgrammableSearchEngineIntegration(
            self.integration_configuration
        ).query(query)
        pages = []
        for result in results:
            match = ORGANIZATION_URL.search(result.get("link", ""))
            if match is None:
                continue
            kind = match.group(1)
            page = page_of(result)
            organization_id = (
                page["link"].split(f"/{kind}/")[1].split("/")[0].split("?")[0]
            )
            await archive_json(
                self.integration_configuration.storage,
                f"{self.integration_configuration.datastore_path}/linkedin_{kind}_pages/{organization_id}",
                f"{organization_id}.json",
                page,
            )
            pages.append(page)
        return pages
