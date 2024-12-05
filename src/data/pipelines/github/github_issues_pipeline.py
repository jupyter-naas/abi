from dataclasses import dataclass
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from abi.pipeline import Pipeline, PipelineConfiguration
from abi.utils.Graph import ABIGraph
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

from src.data.pipelines.github.github_issue_pipeline import GithubIssuePipeline, GithubIssuePipelineConfiguration
from rdflib import Graph
from src import secret
from abi import logger
import pydash as _

@dataclass
class GithubIssuesPipelineConfiguration(PipelineConfiguration):
    github_repository: str
    state: str = "all"
    github_project_id: int = 0
    ontology_store_name: str = "github"

class GithubIssuesPipeline(Pipeline):
    def __init__(self, integration: GithubIntegration, integration_graphql: GithubGraphqlIntegration, ontology_store: IOntologyStoreService, configuration: GithubIssuesPipelineConfiguration):
        super().__init__([integration], configuration)
        
        self.__integration = integration
        self.__integration_graphql = integration_graphql
        self.__configuration = configuration
        self.__ontology_store = ontology_store
        
    def run(self) -> Graph:
        # Get all issues from the repository
        issues_data = self.__integration.get_issues(self.__configuration.github_repository, state=self.__configuration.state)
        logger.debug(f"Issues fetched: {len(issues_data)}")

        # Get project data from GithubGraphqlIntegration
        if self.__configuration.github_project_id != 0:
            organization = self.__configuration.github_repository.split("/")[0]
            project_data : dict = self.__integration_graphql.get_org_project_node_id(organization, self.__configuration.github_project_id) # type: ignore
            project_node_id = _.get(project_data, "data.organization.projectV2.id")
            logger.debug(f"Project node ID: {project_node_id}")
        else:
            logger.debug("No project ID provided, skipping project data")
        
        # Create a combined graph
        combined_graph = ABIGraph()
        
        # Process each issue using the existing GithubIssuePipeline
        for issue in issues_data:
            issue_pipeline = GithubIssuePipeline(
                integration=self.__integration,
                integration_graphql=self.__integration_graphql,
                ontology_store=self.__ontology_store,
                configuration=GithubIssuePipelineConfiguration(
                    github_repository=self.__configuration.github_repository,
                    github_issue_id=str(issue["number"]),
                    github_project_node_id=project_node_id,
                    ontology_store_name=self.__configuration.ontology_store_name
                )
            )
            
            # Run the pipeline for this issue and merge the results
            issue_graph = issue_pipeline.run()
            combined_graph += issue_graph
            
        return combined_graph

# Add this to the if __name__ == "__main__" section for testing
if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--github_access_token', default=None, help='GitHub access token. If not provided, will use GITHUB_ACCESS_TOKEN from secrets.')
    @click.option('--github_repository', '--ghr', required=True, help='GitHub repository in format owner/repo')
    @click.option('--github_project_id', '--ghp', default=None, help='GitHub project ID')
    @click.option('--state', '--st', default="all", help='GitHub issue state')
    def main(github_access_token, github_repository, github_project_id, state):
        # Use provided token or fall back to secret
        token = github_access_token or secret.get("GITHUB_ACCESS_TOKEN")
        
        graph = GithubIssuesPipeline(
            integration=GithubIntegration(GithubIntegrationConfiguration(access_token=token)),
            integration_graphql=GithubGraphqlIntegration(GithubGraphqlIntegrationConfiguration(access_token=token)),
            ontology_store=OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store")),
            configuration=GithubIssuesPipelineConfiguration(
                github_repository=github_repository,
                github_project_id=github_project_id,
                state=state
            )
        ).run()
        
        print(graph.serialize(format="turtle"))

    main()
