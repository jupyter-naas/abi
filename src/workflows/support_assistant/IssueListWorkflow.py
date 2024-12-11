from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class IssueListWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for listing GitHub issues.
    
    Attributes:
        github_integration_config (GithubIntegrationConfiguration): Configuration for GitHub REST API
    """
    github_integration_config: GithubIntegrationConfiguration

class IssueListWorkflowParameters(WorkflowParameters):
    """Parameters for IssueListWorkflow execution.
    
    Attributes:
        repo_name (str): Repository name in format owner/repo
        state (str): Filter issues by state
        limit (int): Maximum number of issues to return
    """
    repo_name: str = Field("jupyter-naas/support", description="Repository name in format owner/repo")
    state: str = Field("open", description="Filter issues by state (open, closed, or all)")
    limit: int = Field(-1, description="Maximum number of issues to return (-1 for all issues)")

class IssueListWorkflow(Workflow):
    __configuration: IssueListWorkflowConfiguration
    
    def __init__(self, configuration: IssueListWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="list_github_issues",
            description="Lists GitHub issues from the specified repository",
            func=lambda **kwargs: self.run(IssueListWorkflowParameters(**kwargs)),
            args_schema=IssueListWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/list_issues")
        def list_issues(parameters: IssueListWorkflowParameters):
            return self.run(parameters)

    def run(self, parameters: IssueListWorkflowParameters) -> List[str]:
        # Get issues using the GitHub integration
        issues = self.__github_integration.get_issues(
            repo_name=parameters.repo_name,
            state=parameters.state,
            limit=parameters.limit
        )
        logger.info(f"Found {len(issues)} issues:")
        return [f"#{issue['number']} - {issue['title']}: {issue['body']}" for issue in issues]

def main():
    configuration = IssueListWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(
            access_token=secret.get('GITHUB_ACCESS_TOKEN')
        )
    )
    
    workflow = IssueListWorkflow(configuration)
    parameters = IssueListWorkflowParameters()
    issues = workflow.run(parameters)
    print(f"Found {len(issues)} issues:")
    for issue in issues:
        print(issue)

if __name__ == "__main__":
    main() 