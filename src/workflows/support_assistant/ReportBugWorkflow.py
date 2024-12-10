from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import Optional, List
from abi import logger

@dataclass
class ReportBugWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating new bug GitHub issues and adding them to project.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
        repo_name: Repository name in format owner/repo (defaults to "jupyter-naas/abi")
        issue_title: Title of the bug report
        issue_body: Body content of the bug report
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
    repo_name: str = "jupyter-naas/support"
    project_node_id: str = "PVT_kwDOBESWNM4AKRt3"
    assignees: Optional[List[str]] = field(default_factory=list)
    labels: Optional[List[str]] = field(default_factory=lambda: ["bug"])
    status_field_id: str = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
    priority_field_id: str = 'PVTSSF_lADOBESWNM4AKRt3zgGac0g'
    status_option_id: str = '97363483'
    priority_option_id: Optional[str] = '4fb76f2d'

class ReportBugWorkflow(Workflow):
    __configuration: ReportBugWorkflowConfiguration
    
    def __init__(self, configuration: ReportBugWorkflowConfiguration):
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
        
        return f"Bug Report '{self.__configuration.issue_title}' created and added to project: {issue}."

def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.post("/report_bug")
    def report_bug(issue_title: str, issue_body: str, assignees: Optional[List[str]] = None, labels: Optional[List[str]] = None):
        configuration = ReportBugWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            issue_title=issue_title,
            issue_body=issue_body,
            assignees=assignees or [],
            labels=labels or []
        )
    
        workflow = ReportBugWorkflow(configuration)
        return workflow.run()
        
    uvicorn.run(app, host="0.0.0.0", port=9879)

def main():
    configuration = ReportBugWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        issue_title="New Bug Report",
        issue_body="This is a new bug report.",
    )
    
    workflow = ReportBugWorkflow(configuration)
    result = workflow.run()
    print(result)

def as_tool():
    from langchain_core.tools import StructuredTool

    class ReportBugSchema(BaseModel):
        issue_title: str = Field(..., description="The title of the bug report")
        issue_body: str = Field(..., description="The description of the bug, including steps to reproduce")

    def report_bug_tool(
        issue_title: str, 
        issue_body: str,
    ):
        configuration = ReportBugWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            issue_title=issue_title,
            issue_body=issue_body,
        )
        workflow = ReportBugWorkflow(configuration)
        return workflow.run()

    return StructuredTool(
        name="report_bug",
        description="Creates GitHub Issue to report bug",
        func=lambda **kwargs: report_bug_tool(**kwargs),
        args_schema=ReportBugSchema
    )

if __name__ == "__main__":
    main() 