from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from abi.pipeline import Pipeline, PipelineConfiguration
from abi.utils.Graph import ABIGraph
from src.data.pipelines.github.github_issue_pipeline import GithubIssuePipeline, GithubIssuePipelineConfiguration
from dataclasses import dataclass
from rdflib import Graph
from src import secret
from abi import logger
import pydash as _
from typing import Optional, List
import click

@dataclass
class GithubIssuesPipelineConfiguration(PipelineConfiguration):
    """Configuration for GithubIssuesPipeline.
    
    Attributes:
        github_repositories (list[str]): List of GitHub repositories in format owner/repo
        limit (int): Maximum number of issues to fetch per repository
        state (str): GitHub issue state
        github_project_id (int): GitHub project ID
        ontology_store_name (str): Name of the ontology store
    """
    github_repositories: List[str]
    limit: Optional[int] = 10
    state: Optional[str] = "all"
    github_project_id: Optional[int] = 0
    ontology_store_name: Optional[str] = "github"


class GithubIssuesPipeline(Pipeline):
    def __init__(self, integration: GithubIntegration, integration_graphql: GithubGraphqlIntegration, ontology_store: OntologyStoreService, configuration: GithubIssuesPipelineConfiguration):
        super().__init__([integration], configuration)
        
        self.__integration = integration
        self.__integration_graphql = integration_graphql
        self.__configuration = configuration
        self.__ontology_store = ontology_store
        
    def run(self) -> Graph:
        combined_graph = ABIGraph()

        # Process each repository
        for repository in self.__configuration.github_repositories:
            # Get all issues from the repository
            issues_data = self.__integration.get_issues(repository, state=self.__configuration.state, limit=self.__configuration.limit)
            logger.debug(f"Issues fetched for {repository}: {len(issues_data)}")

            # Get project data from GithubGraphqlIntegration
            if self.__configuration.github_project_id != 0:
                organization = repository.split("/")[0]
                project_data : dict = self.__integration_graphql.get_project_node_id(organization, self.__configuration.github_project_id)
                project_node_id = _.get(project_data, "data.organization.projectV2.id")
                logger.debug(f"Project node ID: {project_node_id}")
            else:
                logger.debug("No project ID provided, skipping project data")
                project_node_id = None

            # Process each issue using the existing GithubIssuePipeline
            for issue in issues_data:
                issue_pipeline = GithubIssuePipeline(
                    integration=self.__integration,
                    integration_graphql=self.__integration_graphql,
                    ontology_store=self.__ontology_store,
                    configuration=GithubIssuePipelineConfiguration(
                        github_repository=repository,
                        github_issue_id=str(issue["number"]),
                        github_project_node_id=project_node_id,
                        ontology_store_name=self.__configuration.ontology_store_name
                    )
                )
                
                issue_graph = issue_pipeline.run()
                combined_graph += issue_graph
            
        return combined_graph

# Update the CLI portion
if __name__ == "__main__":
    @click.command()
    @click.option('--github_access_token', default=None, help='GitHub access token. If not provided, will use GITHUB_ACCESS_TOKEN from secrets.')
    @click.option('--github_repository', '--ghr', multiple=True, required=True, help='GitHub repository in format owner/repo. Can be specified multiple times.')
    @click.option('--github_project_id', '--ghp', default=None, help='GitHub project ID')
    @click.option('--state', '--st', default="all", help='GitHub issue state')
    @click.option('--limit', '--l', default=10, help='Maximum number of issues to fetch per repository')
    def main(github_access_token, github_repository, github_project_id, state, limit):
        token = github_access_token or secret.get("GITHUB_ACCESS_TOKEN")
        
        graph = GithubIssuesPipeline(
            integration=GithubIntegration(GithubIntegrationConfiguration(access_token=token)),
            integration_graphql=GithubGraphqlIntegration(GithubGraphqlIntegrationConfiguration(access_token=token)),
            ontology_store=OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store")),
            configuration=GithubIssuesPipelineConfiguration(
                github_repositories=list(github_repository),
                github_project_id=github_project_id,
                state=state,
                limit=limit
            )
        ).run()
        
        print(graph.serialize(format="turtle"))

    main()
