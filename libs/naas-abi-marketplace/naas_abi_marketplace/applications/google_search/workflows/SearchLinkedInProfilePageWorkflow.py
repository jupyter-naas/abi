import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Optional

from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegration,
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)
from pydantic import Field
from naas_abi_marketplace.applications.google_search import ABIModule


@dataclass
class SearchLinkedInProfilePageWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for SearchLinkedInProfileWorkflow.

    Attributes:
        integration_config (GoogleProgrammableSearchEngineIntegrationConfiguration): Configuration for the integration
        pattern (str): Pattern to use to extract the LinkedIn profile URL
    """

    integration_config: GoogleProgrammableSearchEngineIntegrationConfiguration
    pattern = r"https://.+\.linkedin\.[^/]+/in/[^?]+"
    datastore_path: str = field(default_factory=lambda: os.path.join(ABIModule.get_instance().configuration.datastore_path, "linkedin_profile_pages"))


class SearchLinkedInProfilePageWorkflowParameters(WorkflowParameters):
    """Parameters for SearchLinkedInProfileWorkflow execution.

    Attributes:
        profile_name (str): Name of the profile to search for
        organization_name (str): Name of the organization to search for
    """

    profile_name: Annotated[
        str, Field(..., description="Name of the profile to search for")
    ]
    organization_name: Optional[
        Annotated[str, Field(description="Name of the organization to search for")]
    ] = None


class SearchLinkedInProfilePageWorkflow(Workflow):
    __configuration: SearchLinkedInProfilePageWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: SearchLinkedInProfilePageWorkflowConfiguration):
        self.__configuration = configuration
        self.__integration = GoogleProgrammableSearchEngineIntegration(
            self.__configuration.integration_config
        )
        self.__storage_utils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

    def search_linkedin_profile_page(
        self, parameters: SearchLinkedInProfilePageWorkflowParameters
    ) -> list[dict]:
        """Search for LinkedIn profile URL using Google Search.

        Args:
            parameters (SearchLinkedInProfileWorkflowParameters): Parameters for the workflow

        Returns:
            list[dict]: List of LinkedIn profile page URLs
        """
        data: list[dict] = []
        profile_name = parameters.profile_name
        organization_name = parameters.organization_name
        query = f"{profile_name.replace(' ', '+')}"
        if organization_name:
            query += f"+organization:{organization_name.replace(' ', '+')}"
        query += "+LinkedIn+profile+site:linkedin.com"
        results = self.__integration.query(query)
        for result in results:
            url = result["link"]
            match = re.search(self.__configuration.pattern, url)
            if match is not None:
                profile_id = url.split("/in/")[-1].split("/")[0].split("?")[0]
                page_data = {
                    "title": result["title"],
                    "link": url,
                    "description": (
                        result.get("pagemap", {})
                        .get("metatags", [{}])[0]
                        .get("og:description", result["snippet"])
                    ),
                    "cse_image": (
                        result.get("pagemap", {})
                        .get("cse_image", [{}])[0]
                        .get("src", None)
                    ),
                }
                self.__storage_utils.save_json(
                    page_data,
                    os.path.join(self.__configuration.datastore_path, profile_id),
                    f"{profile_id}.json",
                )
                data.append(page_data)
        return data

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="googlesearch_search_linkedin_profile_page",
                description="Search for LinkedIn profile page URL using Google Programmable Search Engine",
                func=lambda **kwargs: self.search_linkedin_profile_page(
                    SearchLinkedInProfilePageWorkflowParameters(**kwargs)
                ),
                args_schema=SearchLinkedInProfilePageWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
