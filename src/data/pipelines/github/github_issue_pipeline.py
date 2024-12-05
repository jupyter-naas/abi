from abi.pipeline import Pipeline, PipelineConfiguration, Pipeline
from dataclasses import dataclass
from src.integrations.GithubIntegration import GithubIntegration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration
from abi.utils.Graph import ABIGraph, ABI, BFO
from rdflib import Graph
from datetime import datetime, timedelta
from abi.services.ontology_processor.OntologyService import OntologyService
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
import pydash as _
from src import secret
from abi import logger

@dataclass
class GithubIssuePipelineConfiguration(PipelineConfiguration):
    github_repository: str
    github_issue_id: str
    github_project_id: int = 0
    github_project_node_id: str = ""
    ontology_store_name: str = "github"

class GithubIssuePipeline(Pipeline):
    def __init__(self, integration: GithubIntegration, integration_graphql: GithubGraphqlIntegration, ontology_store: IOntologyStoreService, configuration: GithubIssuePipelineConfiguration):
        super().__init__([integration], configuration)
        
        self.__integration = integration
        self.__integration_graphql = integration_graphql
        self.__ontology_store = ontology_store
        self.__configuration = configuration

    def run(self) -> Graph:
        # Init graph
        graph = ABIGraph()

        # Get issue data from GithubIntegration
        issue_data : dict = self.__integration.get_issue(self.__configuration.github_repository, self.__configuration.github_issue_id) # type: ignore
        issue_id = issue_data.get("id")
        logger.debug(f"Issue ID: {issue_id}")
        issue_label = issue_data.get("title")
        logger.debug(f"Issue label: {issue_label}")
        issue_node_id = issue_data.get("node_id")
        logger.debug(f"Issue node ID: {issue_node_id}")
        issue_description = issue_data.get("body")
        logger.debug(f"Issue description: {issue_description}")
        issue_url = issue_data.get("html_url")
        logger.debug(f"Issue URL: {issue_url}")
        issue_state = issue_data.get("state")
        logger.debug(f"Issue state: {issue_state}")
        issue_labels = ", ".join([x.get("name") for x in issue_data.get("labels")])
        logger.debug(f"Issue labels: {issue_labels}")
        issue_created_at = datetime.strptime(issue_data['created_at'], "%Y-%m-%dT%H:%M:%SZ")
        issue_updated_at = datetime.strptime(issue_data['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
        issue_closed_at = datetime.strptime(issue_data['closed_at'], "%Y-%m-%dT%H:%M:%SZ") if issue_data.get("closed_at") else None

        # Init issue properties from GithubGraphQLIntegration
        issue_status = None
        issue_priority = None
        issue_estimate = 0
        issue_due_date = None
        project_node_id = self.__configuration.github_project_node_id
        if self.__configuration.github_project_id != 0:
            # Get project data from GithubGraphqlIntegration
            organization = self.__configuration.github_repository.split("/")[0]
            project_data : dict = self.__integration_graphql.get_org_project_node_id(organization, self.__configuration.github_project_id) # type: ignore
            logger.debug(f"Project data: {project_data}")
            project_node_id = _.get(project_data, "data.organization.projectV2.id")
            logger.debug(f"Project node ID: {project_node_id}")
        
        if project_node_id != "":
            # Get item id from node id from GithubGraphqlIntegration
            project_item = dict = self.__integration_graphql.get_project_item_from_node(issue_node_id) # type: ignore
            logger.debug(f"Project item: {project_item}")
            item_id = None
            for x in project_item.get("data").get("node").get("projectItems").get("nodes"):
                if x.get("project", {}).get("id") == project_node_id:
                    item_id = _.get(x, "id")
                    break
            logger.debug(f"Item ID: {item_id}")

            # Get item data from GithubGraphqlIntegration
            item_data : dict = self.__integration_graphql.get_project_item_by_id(item_id) # type: ignore
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
        
        self.__ontology_store.insert(self.__configuration.ontology_store_name, graph)
        
        return graph
    
if __name__ == "__main__":
    from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
    from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
    from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
    
    graph = GithubIssuePipeline(
        integration=GithubIntegration(GithubIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN"))),
        ontology_store=OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store")),
        configuration=GithubIssuePipelineConfiguration(
            github_repository="jupyter-naas/abi",
            github_issue_id="177",
            github_project_id=0
        )
    ).run()
    
    print(graph.serialize(format="turtle"))