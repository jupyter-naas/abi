from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import Optional, List
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
@dataclass
class FeatureRequestWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating new feature GitHub issues and adding them to project.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration

class FeatureRequestWorkflowParameters(WorkflowParameters):
    """Parameters for FeatureRequestWorkflow execution.
    
    Attributes:
        repo_name: Repository name in format owner/repo (defaults to config's github_support_repository)
        issue_title: Title of the feature request
        issue_body: Body content of the feature request
        repo_name: Repository name in format owner/repo
        project_node_id: Project node ID
        assignees: List of assignees
        labels: List of labels
        status_field_id: Field ID for status column
        priority_field_id: Field ID for priority column
        status_option_id: Option ID for status value
        priority_option_id: Option ID for priority value
    """
    issue_title: str = Field(..., description="Title of the feature request")
    issue_body: str = Field(..., description="Body content of the feature request")
    repo_name: str = Field(default="jupyter-naas/support", description="Repository name in format owner/repo")
    project_node_id: str = Field(default=config.github_support_repository, description="Project node ID")
    assignees: Optional[List[str]] = Field(default_factory=list, description="List of assignees")
    labels: Optional[List[str]] = Field(default_factory=lambda: ["enhancement"], description="List of labels")
    status_field_id: Optional[str] = Field(None, description="Field ID for status column")
    priority_field_id: Optional[str] = Field(None, description="Field ID for priority column")
    status_option_id: Optional[str] = Field(None, description="Option ID for status value")
    priority_option_id: Optional[str] = Field(None, description="Option ID for priority value")

class FeatureRequestWorkflow(Workflow):
    __configuration: FeatureRequestWorkflowConfiguration
    
    def __init__(self, configuration: FeatureRequestWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="feature_request",
            description="Creates GitHub Issue to request a new feature and adds it to project",
            func=lambda **kwargs: self.run(FeatureRequestWorkflowParameters(**kwargs)),
            args_schema=FeatureRequestWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/feature_request")
        def feature_request(parameters: FeatureRequestWorkflowParameters):
            return self.run(parameters)

    def run(self, parameters: FeatureRequestWorkflowParameters) -> str:
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
            project_node_id=parameters.project_node_id,
            issue_node_id=issue_node_id,
            status_field_id=parameters.status_field_id,
            priority_field_id=parameters.priority_field_id,
            status_option_id=parameters.status_option_id,
            priority_option_id=parameters.priority_option_id
        )
        
        return f"Feature Request '{parameters.issue_title}' created and added to project: {issue}."

def main():
    configuration = FeatureRequestWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
    )
    
    parameters = FeatureRequestWorkflowParameters(
        issue_title="New Feature Request",
        issue_body="This is a new feature request.",
    )
    
    workflow = FeatureRequestWorkflow(configuration)
    result = workflow.run(parameters)
    print(result)

if __name__ == "__main__":
    main()