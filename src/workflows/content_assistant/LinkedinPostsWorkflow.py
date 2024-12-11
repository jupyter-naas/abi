from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.LinkedinIntegration import LinkedinIntegration, LinkedinIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from datetime import datetime, date, timedelta
import pandas as pd
import pytz
from abi import logger
from typing import Optional

@dataclass
class LinkedinPostsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for LinkedIn Posts Workflow.
    
    Attributes:
        linkedin_integration_config (LinkedinIntegrationConfiguration): LinkedIn integration configuration
        linkedin_url (str): LinkedIn profile or organization post URL
        days_start (int): Number of days back to fetch posts from. Defaults to 3.
        timezone (str): Timezone to use for date calculations. Defaults to "Europe/Paris".
    """
    linkedin_integration_config: LinkedinIntegrationConfiguration
    linkedin_url: str
    days_start: int = 3
    timezone: str = "Europe/Paris"

class LinkedinPostsWorkflow(Workflow):
    __configuration: LinkedinPostsWorkflowConfiguration
    
    def __init__(self, configuration: LinkedinPostsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.__linkedin_integration = LinkedinIntegration(self.__configuration.linkedin_integration_config)

    def run(self) -> pd.DataFrame:
        # Initialize empty DataFrame
        df = pd.DataFrame()
        TIMEZONE = pytz.timezone(self.__configuration.timezone)
        
        # Calculate start date
        date_start = date.today() - timedelta(days=datetime.now(TIMEZONE).weekday() + self.__configuration.days_start)

        # Initialize pagination variables
        logger.info(f"Linkedin URL: {self.__configuration.linkedin_url}")
        logger.info(f"Days Back to Start: {self.__configuration.days_start}")
        logger.info(f"⚠️ Limit Date: {date_start}")
        i = 1
        start = 0
        pagination_token = None

        while True:
            try:
                if "/in/" in self.__configuration.linkedin_url:
                    # Get profile posts
                    tmp_df = self.__linkedin_integration.get_profile_posts(
                        linkedin_url=self.__configuration.linkedin_url,
                        pagination_token=pagination_token,
                        limit=1,
                        sleep=False
                    )
                    pagination_token = tmp_df.loc[0, "PAGINATION_TOKEN"] if not tmp_df.empty else None
                    
                elif "/company/" or "/school/" or "/showcase/" in self.__configuration.linkedin_url:
                    # Get organization posts
                    tmp_df = self.__linkedin_integration.get_organization_posts(
                        linkedin_url=self.__configuration.linkedin_url,
                        start=start,
                        limit=1,
                        sleep=False
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
                date_format = "%Y-%m-%d %H:%M:%S%z" if "/in/" in self.__configuration.linkedin_url else "%Y-%m-%d %H:%M:%S"
                datetime_obj = datetime.strptime(published_date, date_format).date()

                # Check if published date > date_limit
                if date_start > datetime_obj:
                    break

                # Concat dataframes
                logger.info(f"{i} - ✅ '{title}' published on {published_date} ({post_url})")
                df = pd.concat([df, tmp_df])
                i += 1

            except Exception as e:
                logger.debug(f"Error: {str(e)}")
                if hasattr(e, 'response') and e.response.status_code == 302:
                    raise e
                break

        return df.reset_index(drop=True)

def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.post("/linkedin/posts")
    def get_posts(
        linkedin_url: str,
        days_start: Optional[int] = 3,
        timezone: Optional[str] = "Europe/Paris"
    ):
        configuration = LinkedinPostsWorkflowConfiguration(
            linkedin_integration_config=LinkedinIntegrationConfiguration(
                li_at=secret.get('li_at'),
                jsessionid=secret.get('jsessionid')
            ),
            linkedin_url=linkedin_url,
            days_start=days_start,
            timezone=timezone
        )
        workflow = LinkedinPostsWorkflow(configuration)
        return workflow.run().to_dict('records')
    
    uvicorn.run(app, host="0.0.0.0", port=9878)

def main():
    configuration = LinkedinPostsWorkflowConfiguration(
        linkedin_integration_config=LinkedinIntegrationConfiguration(
            li_at=secret.get('li_at'),
            jsessionid=secret.get('jsessionid')
        ),
        linkedin_url="https://www.linkedin.com/in/username/"
    )
    workflow = LinkedinPostsWorkflow(configuration)
    df = workflow.run()
    print(df)

def as_tool():
    from langchain_core.tools import StructuredTool
    
    class LinkedinPostsSchema(BaseModel):
        linkedin_url: str = Field(..., description="LinkedIn profile or organization URL")
        days_start: Optional[int] = Field(default=3, description="Number of days back to fetch posts from")
        timezone: Optional[str] = Field(default="Europe/Paris", description="Optional timezone to use for date calculations")
    
    def get_posts_tool(
        linkedin_url: str,
        days_start: Optional[int] = 3,
        timezone: Optional[str] = "Europe/Paris"
    ) -> pd.DataFrame:
        configuration = LinkedinPostsWorkflowConfiguration(
            linkedin_integration_config=LinkedinIntegrationConfiguration(
                li_at=secret.get('li_at'),
                jsessionid=secret.get('jsessionid')
            ),
            linkedin_url=linkedin_url,
            days_start=days_start,
            timezone=timezone
        )
        workflow = LinkedinPostsWorkflow(configuration)
        return workflow.run()
    
    return StructuredTool(
        name="get_linkedin_posts",
        description="Get LinkedIn posts for a profile or organization within date range",
        func=lambda **kwargs: get_posts_tool(**kwargs),
        args_schema=LinkedinPostsSchema
    )

if __name__ == "__main__":
    main()