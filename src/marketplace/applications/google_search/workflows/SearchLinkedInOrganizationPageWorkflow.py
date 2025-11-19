from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegration,
    GoogleProgrammableSearchEngineIntegrationConfiguration
)
from dataclasses import dataclass
from pydantic import Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from typing import Any, Annotated
from enum import Enum
import re
import os
from src.utils.Storage import save_json


@dataclass
class SearchLinkedInOrganizationPageWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for SearchLinkedInOrganizationPageWorkflow.
    
    Attributes:
        integration_config (GoogleProgrammableSearchEngineIntegrationConfiguration): Configuration for the integration
        pattern (str): Pattern to use to extract the LinkedIn organization URL
    """
    integration_config: GoogleProgrammableSearchEngineIntegrationConfiguration
    pattern = r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"
    data_store_path: str = "datastore/google_search/linkedin_organization_pages"

class SearchLinkedInOrganizationPageWorkflowParameters(WorkflowParameters):
    """Parameters for SearchLinkedInOrganizationPageWorkflow execution.
    
    Attributes:
        organization_name (str): Name of the organization to search for
    """
    organization_name: Annotated[str, Field(..., description="Name of the organization to search for")]

class SearchLinkedInOrganizationPageWorkflow(Workflow):
    __configuration: SearchLinkedInOrganizationPageWorkflowConfiguration
    
    def __init__(self, configuration: SearchLinkedInOrganizationPageWorkflowConfiguration):
        self.__configuration = configuration
        self.__integration = GoogleProgrammableSearchEngineIntegration(self.__configuration.integration_config)

    def search_linkedin_organization_page(self, parameters: SearchLinkedInOrganizationPageWorkflowParameters) -> Any:
        """Search for LinkedIn organization page URL using Google Search.
        
        Args:
            parameters (SearchLinkedInOrganizationPageWorkflowParameters): Parameters for the workflow
        
        Returns:
            list[dict]: List of LinkedIn organization page URLs
        """
        data = []
        organization_name = parameters.organization_name
        query = f"{organization_name.replace(' ', '+')}+site:linkedin.com"
        results = self.__integration.query(query)
        for result in results:
            url = result["link"]
            match = re.search(self.__configuration.pattern, url)
            if match is not None:
                organization_type = "company" if "/company/" in url else "school" if "/school/" in url else "showcase" if "/showcase/" in url else None
                if organization_type is not None:
                    page_data = {
                        "title": result["title"],
                        "link": url,
                        "snippet": result["snippet"],
                        "thumbnail_image": result.get("pagemap", {}).get("cse_thumbnail", [{}])[0].get("src", None)
                    }
                    save_json(page_data, os.path.join(self.__configuration.data_store_path.replace("organization", organization_type), organization_name), f"{organization_name}.json")
                    data.append(page_data)
        return data

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="googlesearch_search_linkedin_organization_page",
                description="Search for LinkedIn organization page URL using Google Programmable Search Engine",
                func=lambda **kwargs: self.search_linkedin_organization_page(**kwargs),
                args_schema=SearchLinkedInOrganizationPageWorkflowParameters
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