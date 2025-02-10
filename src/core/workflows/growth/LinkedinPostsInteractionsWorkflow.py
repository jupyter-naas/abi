from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.LinkedInIntegration import LinkedInIntegration, LinkedInIntegrationConfiguration
from src import secret
from dataclasses import dataclass   
from pydantic import Field
import pandas as pd
from abi import logger
from typing import List, Optional
from pytz.exceptions import NonExistentTimeError
import pytz
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class LinkedinPostsInteractionsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for LinkedIn Posts Interactions Workflow.
    
    Attributes:
        linkedin_integration_config (LinkedInIntegrationConfiguration): LinkedIn integration configuration
    """
    linkedin_integration_config: LinkedInIntegrationConfiguration

class LinkedinPostsInteractionsWorkflowParameters(WorkflowParameters):
    """Parameters for LinkedIn Posts Interactions Workflow.
    
    Attributes:
        linkedin_urls (List[str]): List of LinkedIn post URLs
        limit (Optional[int]): Maximum number of reactions and comments to retrieve. Defaults to 100.
    """
    linkedin_urls: List[str] = Field(..., description="List of LinkedIn post URLs. The URLs must contain 'activity'")
    limit: Optional[int] = Field(default=100, description="Optional. Maximum number of reactions and comments to retrieve. Defaults to 100.")

class LinkedinPostsInteractionsWorkflow(Workflow):
    """Workflow for fetching LinkedIn posts interactions (reactions and comments) from linkedin posts URLs."""
    __configuration: LinkedinPostsInteractionsWorkflowConfiguration
    
    def __init__(self, configuration: LinkedinPostsInteractionsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__linkedin = LinkedInIntegration(configuration.linkedin_integration_config)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="get_linkedin_posts_interactions",
            description="Get people (linkedin profiles) who interacted (reactions and comments) with one or more LinkedIn posts.",
            func=lambda **kwargs: self.run(LinkedinPostsInteractionsWorkflowParameters(**kwargs)),
            args_schema=LinkedinPostsInteractionsWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/linkedin/posts/interactions")
        def get_posts_interactions(parameters: LinkedinPostsInteractionsWorkflowParameters):
            return self.run(parameters).to_dict('records')

    def handle_time_error(self, df_init, column):
        # Handle NonExistentTimeError
        df = df_init.copy()
        if column in df.columns:
            for i in range(len(df[column])):
                try:
                    actual_time = pd.to_datetime(df.loc[i, column]).tz_localize(pytz.timezone("Europe/Paris"))
                except NonExistentTimeError:
                    actual_time = str(pd.to_datetime(df.loc[i, column]) + pd.DateOffset(hours=1))
                    df.loc[i, column] = actual_time       
        return df

    def run(self, parameters: LinkedinPostsInteractionsWorkflowParameters) -> pd.DataFrame:
        """Get reactions and comments for LinkedIn posts.
        
        Args:
            parameters (LinkedinPostsInteractionsWorkflowParameters): Workflow parameters
            
        Returns:
            pd.DataFrame: DataFrame containing combined reactions and comments data
        """
        # Initialize empty DataFrames
        df_reactions = pd.DataFrame()
        df_comments = pd.DataFrame()
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()
        
        logger.info(f"Linkedin URLs: {parameters.linkedin_urls}")
        logger.info(f"Limit: {parameters.limit}")
        
        if len(parameters.linkedin_urls) == 0:
            return pd.DataFrame()
        
        # Process each post
        for linkedin_url in parameters.linkedin_urls:
            # Get reactions
            tmp_reactions = self.__linkedin.get_post_reactions(
                linkedin_url, 
                limit=parameters.limit
            )
            
            if tmp_reactions is not None:
                df_reactions = pd.concat([df_reactions, tmp_reactions])

            # Get comments
            tmp_comments = self.__linkedin.get_post_comments(
                linkedin_url,
                limit=parameters.limit
            )
            
            if tmp_comments is not None:
                df_comments = pd.concat([df_comments, tmp_comments])
        
        logger.info(f"Total reactions: {len(df_reactions)}")
        logger.info(f"Total comments: {len(df_comments)}")

        # Handle NonExistentTimeError
        df_comments = self.handle_time_error(df_comments, "CREATED_TIME")
        
        if len(df_reactions) > 0:
            # Df reactions
            data_reaction = {
                "PROFILE_URL": df_reactions["PROFILE_URL"],
                "FULLNAME": df_reactions["FULLNAME"],
                "OCCUPATION": df_reactions["OCCUPATION"],
                "CONTENT_URL": df_reactions["POST_URL"],
                "TYPE": "POST_REACTION",
                "CONTENT": df_reactions["REACTION_TYPE"],
                "COMMENT_COMMENTS_COUNT": 0,
                "COMMENT_LIKES_COUNT": 0,
                "COMMENT_LANGUAGE": "NaN",
                "DATE_EXTRACT": pd.to_datetime(df_reactions['DATE_EXTRACT']).dt.tz_localize(pytz.timezone("Europe/Paris")).dt.strftime("%Y-%m-%d %H:%M:%S%z"),
            }
            df1 = pd.DataFrame(data_reaction)
            
        if len(df_comments) > 0:
            # Df comments
            data_comment = {
                "PROFILE_URL": df_comments["PROFILE_URL"],
                "FULLNAME": df_comments["FULLNAME"],
                "OCCUPATION": df_comments["OCCUPATION"],
                "CONTENT_URL": df_comments["POST_URL"],
                "TYPE": "POST_COMMENT",
                "CONTENT": df_comments["TEXT"],
                "COMMENT_COMMENTS_COUNT": df_comments["COMMENTS"],
                "COMMENT_LIKES_COUNT": df_comments["LIKES"],
                "COMMENT_LANGUAGE": df_comments["LANGUAGE"],
                "DATE_EXTRACT": pd.to_datetime(df_comments['DATE_EXTRACT']).dt.tz_localize(pytz.timezone("Europe/Paris")).dt.strftime("%Y-%m-%d %H:%M:%S%z"),
            }
            df2 = pd.DataFrame(data_comment)
        
        # Concat df
        df = pd.concat([df1, df2]).reset_index(drop=True)
        
        return df

def main():
    linkedin_urls = ["https://www.linkedin.com/feed/update/urn:li:activity:1234567890"]
    config = LinkedinPostsInteractionsWorkflowConfiguration(
        linkedin_integration_config=LinkedInIntegrationConfiguration(
            li_at=secret.get("LINKEDIN_LI_AT").value,
            jsessionid=secret.get("LINKEDIN_JSESSIONID").value
        )
    )
    workflow = LinkedinPostsInteractionsWorkflow(config)
    parameters = LinkedinPostsInteractionsWorkflowParameters(
        linkedin_urls=linkedin_urls,
        limit=100
    )
    df = workflow.run(parameters)
    print(df)

if __name__ == "__main__":
    main()
