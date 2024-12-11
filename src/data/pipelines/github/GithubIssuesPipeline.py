from abi.pipeline.pipeline import PipelineParameters
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from abi.pipeline import Pipeline, PipelineConfiguration
from abi.utils.Graph import ABIGraph
from src.data.pipelines.github.GithubIssuePipeline import GithubIssuePipeline, GithubIssuePipelineConfiguration, GithubIssuePipelineParameters
from dataclasses import dataclass
from rdflib import Graph
from src import secret
from abi import logger
import pydash as _
from typing import Optional, List
import click
from langchain_core.tools import StructuredTool
from fastapi import APIRouter

@dataclass
class GithubIssuesPipelineConfiguration(PipelineConfiguration):
    """Configuration for GithubIssuesPipeline.
    
    Attributes:
        github_integration (GithubIntegration): The GitHub REST API integration instance
        github_graphql_integration (GithubGraphqlIntegration): The GitHub GraphQL API integration instance
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "github"
    """
    github_integration: GithubIntegration
    github_graphql_integration: GithubGraphqlIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "github"


class GithubIssuesPipelineParameters(PipelineParameters):
    """Parameters for GithubIssuesPipeline execution.
    
    Attributes:
        github_repositories (List[str]): List of GitHub repositories in format owner/repo
        limit (int): Maximum number of issues to fetch per repository
        state (str): GitHub issue state
        github_project_id (int): GitHub project ID
    """
    github_repositories: List[str]
    limit: int = 10
    state: str = "all"
    github_project_id: int = 0

class GithubIssuesPipeline(Pipeline):
    def __init__(self, configuration: GithubIssuesPipelineConfiguration):
        self.__configuration = configuration
        
    def run(self, parameters: GithubIssuesPipelineParameters) -> Graph:
        combined_graph = ABIGraph()

        # Process each repository
        for repository in parameters.github_repositories:
            # Get all issues from the repository
            issues_data = self.__configuration.github_integration.get_issues(repository, state=parameters.state, limit=parameters.limit)
            logger.debug(f"Issues fetched for {repository}: {len(issues_data)}")

            # Get project data from GithubGraphqlIntegration
            if parameters.github_project_id != 0:
                organization = repository.split("/")[0]
                project_data : dict = self.__configuration.github_graphql_integration.get_project_node_id(organization, parameters.github_project_id)
                project_node_id = _.get(project_data, "data.organization.projectV2.id")
                logger.debug(f"Project node ID: {project_node_id}")
            else:
                logger.debug("No project ID provided, skipping project data")
                project_node_id = None

            # Process each issue using the existing GithubIssuePipeline
            for issue in issues_data:
                issue_pipeline = GithubIssuePipeline(
                    configuration=GithubIssuePipelineConfiguration(
                        github_integration=self.__configuration.github_integration,
                        github_graphql_integration=self.__configuration.github_graphql_integration,
                        ontology_store=self.__configuration.ontology_store,
                        ontology_store_name=self.__configuration.ontology_store_name
                    )
                )
                
                issue_graph = issue_pipeline.run(GithubIssuePipelineParameters(
                    github_repository=repository,
                    github_issue_id=str(issue["number"]),
                    github_project_id=parameters.github_project_id,
                    github_project_node_id=project_node_id if project_node_id is not None else ""
                ))
                combined_graph += issue_graph
            
        return combined_graph

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the GithubIssuesPipeline tool
        """
        return [StructuredTool(
            name="github_issues_pipeline",
            description="Fetches multiple GitHub issues and adds them to the ontology",
            func=lambda **kwargs: self.run(GithubIssuesPipelineParameters(**kwargs)),
            args_schema=GithubIssuesPipelineParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/GithubIssuesPipeline")
        def run(parameters: GithubIssuesPipelineParameters):
            return self.run(parameters).serialize(format="turtle")

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
        
        pipeline = GithubIssuesPipeline(
            GithubIssuesPipelineConfiguration(
                github_integration=GithubIntegration(GithubIntegrationConfiguration(access_token=token)),
                github_graphql_integration=GithubGraphqlIntegration(GithubGraphqlIntegrationConfiguration(access_token=token)), 
                ontology_store=OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store"))
            )
        )
        
        graph = pipeline.run(GithubIssuesPipelineParameters(
            github_repositories=list(github_repository),
            github_project_id=github_project_id,
            state=state,
            limit=limit
        ))
        
        print(graph.serialize(format="turtle"))

    main()

