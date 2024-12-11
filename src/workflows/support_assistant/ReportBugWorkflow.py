from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import Optional, List
from abi import logger
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class ReportBugWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating new bug GitHub issues and adding them to project.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration

class ReportBugWorkflowParameters(WorkflowParameters):
    """Parameters for ReportBugWorkflow execution.
    
    Attributes:
        issue_title: Title of the bug report
        issue_body: Body content of the bug report
        repo_name: Repository name in format owner/repo
        assignees: Optional list of assignees
        labels: Optional list of labels
    """
    issue_title: str = Field(..., description="The title of the bug report")
    issue_body: str = Field(..., description="The description of the bug, including steps to reproduce")
    project_node_id: str = Field(default=config.github_project_id, description="Project node ID (defaults to config's config.github_project_id)")
    repo_name: str = Field(default="jupyter-naas/support", description="Repository name in format owner/repo (defaults to config's github_support_repository)")
    assignees: Optional[List[str]] = Field(default_factory=list, description="Optional list of GitHub usernames to assign")
    labels: Optional[List[str]] = Field(default_factory=lambda: ["bug"], description="Optional list of labels to apply")
    status_field_id: Optional[str] = Field(default="PVTSSF_lADOBESWNM4AKRt3zgGZRV8", description="Field ID for status column")
    priority_field_id: Optional[str] = Field(default="PVTSSF_lADOBESWNM4AKRt3zgGac0g", description="Field ID for priority column") 
    status_option_id: Optional[str] = Field(default="97363483", description="Option ID for status value")
    priority_option_id: Optional[str] = Field(default="4fb76f2d", description="Option ID for priority value")

class ReportBugWorkflow(Workflow):
    __configuration: ReportBugWorkflowConfiguration
    
    def __init__(self, configuration: ReportBugWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="report_bug",
            description="Creates GitHub Issue to report bug",
            func=lambda **kwargs: self.run(ReportBugWorkflowParameters(**kwargs)),
            args_schema=ReportBugWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/report_bug")
        def report_bug(parameters: ReportBugWorkflowParameters):
            return self.run(parameters)

    def run(self, parameters: ReportBugWorkflowParameters) -> str:
        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=parameters.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            assignees=parameters.assignees,
            labels=parameters.labels
        )
        
        # Add the issue to project using direct project_node_id
        issue_node_id = issue['node_id']
        logger.debug(f"Issue node ID: {issue_node_id}")
        self.__github_graphql_integration.add_issue_to_project(
            project_node_id="PVT_kwDOBESWNM4AKRt3",  # Could be moved to configuration if needed
            issue_node_id=issue_node_id,
            status_field_id="PVTSSF_lADOBESWNM4AKRt3zgGZRV8",
            priority_field_id='PVTSSF_lADOBESWNM4AKRt3zgGac0g',
            status_option_id='97363483',
            priority_option_id='4fb76f2d'
        )
        
        return f"Bug Report '{parameters.issue_title}' created and added to project: {issue}."

def main():
    configuration = ReportBugWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
    )
    
    parameters = ReportBugWorkflowParameters(
        issue_title="New Bug Report",
        issue_body="This is a new bug report.",
    )
    
    workflow = ReportBugWorkflow(configuration)
    result = workflow.run(parameters)
    print(result)

if __name__ == "__main__":
    main() 