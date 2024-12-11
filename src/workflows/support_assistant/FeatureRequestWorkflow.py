from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret, config
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import Optional, List
from abi import logger

@dataclass
class FeatureRequestWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating new feature GitHub issues and adding them to project.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
        repo_name: Repository name in format owner/repo (defaults to config's github_support_repository)
        issue_title: Title of the feature request
        issue_body: Body content of the feature request
        project_node_id: Project node ID (defaults to "PVT_kwDOBESWNM4AKRt3")
        assignees: List of assignees
        labels: List of labels
        status_field_id: Field ID for status column
        priority_field_id: Field ID for priority column
        status_option_id: Option ID for status value
        priority_option_id: Option ID for priority value
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration
    issue_title: str
    issue_body: str
    repo_name: str = config.github_support_repository
    project_node_id: str = "PVT_kwDOBESWNM4AKRt3"
    assignees: Optional[List[str]] = field(default_factory=list)
    labels: Optional[List[str]] = field(default_factory=lambda: ["enhancement"])
    status_field_id: Optional[str] = None
    priority_field_id: Optional[str] = None
    status_option_id: Optional[str] = None
    priority_option_id: Optional[str] = None

class FeatureRequestWorkflow(Workflow):
    __configuration: FeatureRequestWorkflowConfiguration
    
    def __init__(self, configuration: FeatureRequestWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def run(self) -> str:
        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=self.__configuration.repo_name,
            title=self.__configuration.issue_title,
            body=self.__configuration.issue_body,
            assignees=self.__configuration.assignees,
            labels=self.__configuration.labels
        )
        
        # Add the issue to project using direct project_node_id
        issue_node_id = issue['node_id']
        logger.debug(f"Issue node ID: {issue_node_id}")
        self.__github_graphql_integration.add_issue_to_project(
            project_node_id=self.__configuration.project_node_id,
            issue_node_id=issue_node_id,
            status_field_id=self.__configuration.status_field_id,
            priority_field_id=self.__configuration.priority_field_id,
            status_option_id=self.__configuration.status_option_id,
            priority_option_id=self.__configuration.priority_option_id
        )
        
        return f"Feature Request '{self.__configuration.issue_title}' created and added to project: {issue}."
    
def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.post("/feature_request")
    def feature_request(issue_title: str, issue_body: str, assignees: Optional[List[str]] = None, labels: Optional[List[str]] = None):
        configuration = FeatureRequestWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            issue_title=issue_title,
            issue_body=issue_body,
        )
    
        workflow = FeatureRequestWorkflow(configuration)
        
        return workflow.run()
        
    uvicorn.run(app, host="0.0.0.0", port=9878)

def main():
    configuration = FeatureRequestWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        issue_title="New Feature Request",
        issue_body="This is a new feature request.",
    )
    
    workflow = FeatureRequestWorkflow(configuration)
    result = workflow.run()
    print(result)

def as_tool():
    from langchain_core.tools import StructuredTool

    class FeatureRequestSchema(BaseModel):
        issue_title: str = Field(..., description="The title of the feature request")
        issue_body: str = Field(..., description="The description of the feature request")

    def feature_request_tool(
        issue_title: str, 
        issue_body: str,
    ):
        configuration = FeatureRequestWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            issue_title=issue_title,
            issue_body=issue_body,
        )
        workflow = FeatureRequestWorkflow(configuration)
        return workflow.run()

    return StructuredTool(
        name="feature_request",
        description="Creates GitHub Issue to request a new feature",
        func=lambda **kwargs: feature_request_tool(**kwargs),
        args_schema=FeatureRequestSchema
    )

if __name__ == "__main__":
    main()