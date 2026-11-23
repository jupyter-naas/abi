"""Find a person's LinkedIn profile page with Google Search
(``workflow.search_linked_in_profile_page_workflow``)."""

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

PROFILE_URL = re.compile(r"https://.+\.linkedin\.[^/]+/in/[^?]+")


@dataclass
class SearchLinkedInProfilePageWorkflowConfiguration(WorkflowConfiguration):
    integration: GoogleProgrammableSearchEngineIntegrationConfiguration | None = None


class SearchLinkedInProfilePageWorkflowParameters(WorkflowParameters):
    profile_name: str = Field(..., description="Name of the profile to search for")
    organization_name: str | None = Field(
        None, description="Name of the organization to search for"
    )


class SearchLinkedInProfilePageWorkflow(
    Workflow[SearchLinkedInProfilePageWorkflowParameters]
):
    """Search for LinkedIn profile page URL using Google Programmable Search Engine."""

    def __init__(self, configuration: SearchLinkedInProfilePageWorkflowConfiguration):
        super().__init__(configuration)
        assert configuration.integration is not None
        self.integration_configuration = configuration.integration

    @classmethod
    async def New(cls, module: Any) -> SearchLinkedInProfilePageWorkflow:
        return cls(
            SearchLinkedInProfilePageWorkflowConfiguration(
                integration=module.integration_configuration(await credentials(module))
            )
        )

    async def run(
        self, parameters: SearchLinkedInProfilePageWorkflowParameters
    ) -> list[dict[str, Any]]:
        query = parameters.profile_name.replace(" ", "+")
        if parameters.organization_name:
            query += f"+organization:{parameters.organization_name.replace(' ', '+')}"
        query += "+LinkedIn+profile+site:linkedin.com"
        results = await GoogleProgrammableSearchEngineIntegration(
            self.integration_configuration
        ).query(query)
        pages = []
        for result in results:
            if PROFILE_URL.search(result.get("link", "")) is None:
                continue
            page = page_of(result)
            profile_id = page["link"].split("/in/")[-1].split("/")[0].split("?")[0]
            await archive_json(
                self.integration_configuration.storage,
                f"{self.integration_configuration.datastore_path}/linkedin_profile_pages/{profile_id}",
                f"{profile_id}.json",
                page,
            )
            pages.append(page)
        return pages
