from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from dataclasses import dataclass
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from abi.utils.Graph import ABIGraph, ABI, BFO
from rdflib import Graph
from datetime import datetime, timedelta
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
import pydash as _
from abi import logger
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pydantic import Field
from typing import Optional


@dataclass
class GithubIssuePipelineConfiguration(PipelineConfiguration):
    """Configuration for GithubIssuePipeline.
    
    Attributes:
        github_integration_config (GithubIntegrationConfiguration): The GitHub REST API integration instance
        github_graphql_integration_config (GithubGraphqlIntegrationConfiguration): The GitHub GraphQL API integration instance
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "github"
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "github"


class GithubIssuePipelineParameters(PipelineParameters):
    github_repository: str = Field(..., description="GitHub repository in format owner/repo")
    github_issue_id: str = Field(..., description="GitHub issue ID")
    github_project_id: Optional[int] = Field(default=0, description="GitHub project ID")
    github_project_node_id: Optional[str] = Field(default="", description="GitHub project node ID")


class GithubIssuePipeline(Pipeline):
    __configuration: GithubIssuePipelineConfiguration
    
    def __init__(self, configuration: GithubIssuePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def run(self, parameters: GithubIssuePipelineParameters) -> Graph:
        # Init graph
        graph = ABIGraph()

        # Get issue data from GithubIntegration
        # GitHub Issue API Response Schema:
        # {
        #   "url": "API URL for the issue", 
        #   "repository_url": "API URL for the repository",
        #   "labels_url": "Template URL for labels with {/name} parameter",
        #   "comments_url": "API URL for comments",
        #   "events_url": "API URL for events", 
        #   "html_url": "Web URL for the issue",
        #   "id": "Unique identifier",
        #   "node_id": "Global node ID",
        #   "number": "Issue number in repository",
        #   "title": "Issue title",
        #   "user": {
        #     "login": "Username",
        #     "id": "User ID",
        #     "node_id": "User node ID",
        #     "type": "User type",
        #     "site_admin": "Admin status"
        #   },
        #   "labels": "Array of label objects",
        #   "state": "open/closed",
        #   "locked": "Lock status",
        #   "assignee": "User object of assignee",
        #   "assignees": "Array of assignee user objects",
        #   "comments": "Number of comments",
        #   "created_at": "Creation timestamp",
        #   "updated_at": "Last update timestamp", 
        #   "closed_at": "Close timestamp if closed",
        #   "author_association": "Author's association with repository",
        #   "body": "Issue description",
        #   "reactions": {
        #     "url": "Reactions API URL",
        #     "total_count": "Total reaction count",
        #     "+1": "Count of +1 reactions",
        #     "-1": "Count of -1 reactions"
        #   }
        # }

        # Get issue metadata
        issue_data = self.__github_integration.get_issue(parameters.github_repository, parameters.github_issue_id)
        issue_id = issue_data.get("id")
        issue_label = issue_data.get("title")
        issue_node_id = issue_data.get("node_id")
        issue_description = issue_data.get("body")
        issue_url = issue_data.get("html_url")
        issue_state = issue_data.get("state")
        issue_labels = ", ".join([x.get("name") for x in issue_data.get("labels")])
        issue_created_at = datetime.strptime(issue_data['created_at'], "%Y-%m-%dT%H:%M:%SZ")
        issue_updated_at = datetime.strptime(issue_data['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
        issue_closed_at = datetime.strptime(issue_data['closed_at'], "%Y-%m-%dT%H:%M:%SZ") if issue_data.get("closed_at") else None
        logger.debug(f"Issue: {issue_label} - {issue_url}")

        # Init issue properties from GithubGraphQLIntegration
        issue_status = None
        issue_priority = None
        issue_estimate = 0
        issue_due_date = None
        project_node_id = parameters.github_project_node_id
        if parameters.github_project_id != 0:
            # Get project data from GithubGraphqlIntegration
            organization = parameters.github_repository.split("/")[0]
            project_data : dict = self.__github_graphql_integration.get_project_node_id(organization, parameters.github_project_id) # type: ignore
            project_node_id = _.get(project_data, "data.organization.projectV2.id")
            logger.debug(f"Project node ID: {project_node_id}")
        
        if project_node_id != "":
            # Get item id from node id from GithubGraphqlIntegration
            project_item = dict = self.__github_graphql_integration.get_item_id_from_node_id(issue_node_id) # type: ignore
            logger.debug(f"Project item: {project_item}")
            item_id = None
            for x in project_item.get("data").get("node").get("projectItems").get("nodes"):
                if x.get("project", {}).get("id") == project_node_id:
                    item_id = _.get(x, "id")
                    break
            logger.debug(f"Item ID: {item_id}")

            if item_id:
                # Get item data from GithubGraphqlIntegration
                item_data : dict = self.__github_graphql_integration.get_item_details(item_id) # type: ignore
                issue_iteration = {}
                issue_eta = ""

                # Iterate through the field values
                for field_value in item_data.get("data", {}).get("node", {}).get("fieldValues", {}).get("nodes", []):
                    if field_value:
                        field_name = field_value.get("field", {}).get("name")
                        if field_name == "Status":
                            issue_status = field_value.get("name")
                            logger.debug(f"Issue status: {issue_status}")
                        elif field_name == "Priority":
                            issue_priority = field_value.get("name")
                            logger.debug(f"Issue priority: {issue_priority}")
                        elif field_name == "Iteration":
                            issue_iteration = {
                                "title": field_value.get("title"),
                                "startDate": field_value.get("startDate"),
                                "duration": field_value.get("duration")
                            }
                        elif field_name == "Estimate":
                            issue_estimate = field_value.get("number")
                            logger.debug(f"Issue estimate: {issue_estimate}")
                        elif field_name == "ETA":
                            issue_eta = field_value.get("date")
                            logger.debug(f"Issue ETA: {issue_eta}")

                # Calculate due date if eta is empty
                issue_due_date = issue_eta
                if not issue_eta and issue_iteration:
                    start_date = datetime.strptime(issue_iteration["startDate"], "%Y-%m-%d")
                    issue_due_date = start_date + timedelta(days=issue_iteration["duration"])
                    issue_due_date = issue_due_date.strftime("%Y-%m-%d")
                logger.debug(f"Issue due date: {issue_due_date}")

        # Add Process: Task Completion
        task_completion = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=str(issue_id) + "-" + str(int(issue_updated_at.timestamp())),
            label=issue_label,
            is_a=ABI.TaskCompletion,
            description=issue_description,
            issue_node_id=issue_node_id,
            url=issue_url,
            labels=issue_labels,
            status=issue_status,
            state=issue_state,
            priority=issue_priority,
            estimate=issue_estimate,
            due_date=issue_due_date,
            updated_date=issue_updated_at
        )

        # Add GDC: GitHubIssue
        github_issue = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=str(issue_id),
            label=issue_label,
            is_a=ABI.GitHubIssue,
            description=issue_description,
            issue_node_id=issue_node_id,
            url=issue_url,
            labels=issue_labels,
            status=issue_status,
            state=issue_state,
            priority=issue_priority,
            estimate=issue_estimate,
            due_date=issue_due_date,
            updated_date=issue_updated_at
        )
        graph.add((task_completion, BFO.BFO_0000058, github_issue))
        graph.add((github_issue, BFO.BFO_0000059, task_completion))

        # Add GDC: GitHubRepo
        repo_url = issue_data.get("repository_url")
        repo_name = repo_url.split("repos")[-1]
        github_repo = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=repo_name,
            label=repo_name,
            is_a=ABI.GitHubRepository,
            url=repo_url
        )
        graph.add((task_completion, BFO.BFO_0000058, github_repo))
        graph.add((github_repo, BFO.BFO_0000059, task_completion))

        # Add Temporal region
        first_instant = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=str(int(issue_created_at.timestamp())),
            label=issue_created_at.strftime("%Y-%m-%dT%H:%M:%S%z"),
            is_a=BFO.BFO_0000203
        )
        graph.add((task_completion, BFO.BFO_0000222, first_instant))

        if issue_closed_at:
            last_instant = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=str(int(issue_closed_at.timestamp())),
                label=issue_closed_at.strftime("%Y-%m-%dT%H:%M:%S%z"),
                is_a=BFO.BFO_0000203
            )
            graph.add((task_completion, BFO.BFO_0000224, last_instant))
            
        # Add User to Agent
        user = issue_data.get("user")
        user_id = user.get("id")
        user_label = user.get("login")
        user_url = user.get("html_url")
        github_user = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=user_id,
            label=user_label,
            is_a=ABI.GitHubUser,
            url=user_url,
        )
        graph.add((task_completion, ABI.hasCreator, github_user))

        # Add Assignees to Agent
        assignees = issue_data.get("assignees")
        for assignee in assignees:
            assignee_id = assignee.get("id")
            assignee_label = assignee.get("login")
            assignee_url = assignee.get("html_url")
            github_assignee = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=assignee_id,
                label=assignee_label,
                is_a=ABI.GitHubUser,
                url=assignee_url,
            )
            graph.add((task_completion, ABI.hasAssignee, github_assignee))
        
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        
        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [StructuredTool(
            name="github_issue_pipeline",
            description="Adds an issue to the ontology",
            func=lambda **kwargs: self.run(GithubIssuePipelineParameters(**kwargs)),
            args_schema=GithubIssuePipelineParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        @router.post("/GithubIssuePipeline")
        def run(parameters: GithubIssuePipelineParameters):
            return self.run(parameters).serialize(format="turtle")