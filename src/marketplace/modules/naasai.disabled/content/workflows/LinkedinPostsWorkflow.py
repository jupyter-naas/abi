from abi.workflow import Workflow, WorkflowConfiguration
from src.core.modules.common.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration,
)
from dataclasses import dataclass
from pydantic import Field
from datetime import datetime, date, timedelta
import pandas as pd
import pytz
from abi import logger
from typing import Optional
from abi.workflow.workflow import WorkflowParameters
from langchain_core.tools import StructuredTool
from fastapi import APIRouter

LOGO_URL = "https://logo.clearbit.com/linkedin.com"


@dataclass
class LinkedinPostsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for LinkedIn Posts Workflow.

    Attributes:
        linkedin_integration_config (LinkedInIntegrationConfiguration): LinkedIn integration configuration
    """

    linkedin_integration_config: LinkedInIntegrationConfiguration


class LinkedinPostsWorkflowParameters(WorkflowParameters):
    """Parameters for LinkedIn Posts Workflow execution.

    Attributes:
        linkedin_url (str): LinkedIn profile or organization post URL
        days_start (int): Number of days back to fetch posts from
        timezone (str): Timezone to use for date calculations
    """

    linkedin_url: str = Field(..., description="LinkedIn profile or organization URL")
    days_start: Optional[int] = Field(
        default=3, description="Number of days back to fetch posts from"
    )
    timezone: Optional[str] = Field(
        default="Europe/Paris", description="Timezone to use for date calculations"
    )


class LinkedinPostsWorkflow(Workflow):
    """Workflow for fetching LinkedIn posts from a profile or organization."""

    __configuration: LinkedinPostsWorkflowConfiguration

    def __init__(self, configuration: LinkedinPostsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__linkedin_integration = LinkedInIntegration(
            self.__configuration.linkedin_integration_config
        )

    def run(self, parameters: LinkedinPostsWorkflowParameters) -> pd.DataFrame:
        # Initialize empty DataFrame
        df = pd.DataFrame()
        TIMEZONE = pytz.timezone(parameters.timezone)

        # Calculate start date
        date_start = date.today() - timedelta(
            days=datetime.now(TIMEZONE).weekday() + parameters.days_start
        )

        # Initialize pagination variables
        logger.info(f"Linkedin URL: {parameters.linkedin_url}")
        logger.info(f"Days Back to Start: {parameters.days_start}")
        logger.info(f"⚠️ Limit Date: {date_start}")
        i = 1
        start = 0
        pagination_token = None

        while True:
            try:
                if "/in/" in parameters.linkedin_url:
                    # Get profile posts
                    tmp_df = self.__linkedin_integration.get_profile_posts(
                        linkedin_url=parameters.linkedin_url,
                        pagination_token=pagination_token,
                        limit=1,
                        sleep=False,
                    )
                    pagination_token = (
                        tmp_df.loc[0, "PAGINATION_TOKEN"] if not tmp_df.empty else None
                    )

                elif (
                    "/company/" or "/school/" or "/showcase/" in parameters.linkedin_url
                ):
                    # Get organization posts
                    tmp_df = self.__linkedin_integration.get_organization_posts(
                        linkedin_url=parameters.linkedin_url,
                        start=start,
                        limit=1,
                        sleep=False,
                    )
                    start += 1
                else:
                    raise ValueError("URL must contain /in/ or /company/")

                if tmp_df.empty:
                    break

                # Extract post details
                title = tmp_df.loc[0, "TITLE"]
                published_date = tmp_df.loc[0, "PUBLISHED_DATE"]
                post_url = tmp_df.loc[0, "POST_URL"]

                # Parse date
                date_format = (
                    "%Y-%m-%d %H:%M:%S%z"
                    if "/in/" in parameters.linkedin_url
                    else "%Y-%m-%d %H:%M:%S"
                )
                datetime_obj = datetime.strptime(published_date, date_format).date()

                # Check if published date > date_limit
                if date_start > datetime_obj:
                    break

                # Concat dataframes
                logger.info(
                    f"{i} - ✅ '{title}' published on {published_date} ({post_url})"
                )
                df = pd.concat([df, tmp_df])
                i += 1

            except Exception as e:
                logger.debug(f"Error: {str(e)}")
                if hasattr(e, "response") and e.response.status_code == 302:
                    raise e
                break

        return df.to_dict("records")

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [
            StructuredTool(
                name="linkedin_get_posts_from_url",
                description="Get LinkedIn posts for a profile or organization within date range.",
                func=lambda **kwargs: self.run(
                    LinkedinPostsWorkflowParameters(**kwargs)
                ).to_dict("records"),
                args_schema=LinkedinPostsWorkflowParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
