from abi.pipeline.pipeline import PipelineParameters, PipelineConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from src.core.modules.common.integrations.GithubIntegration import (
    GithubIntegration,
    GithubIntegrationConfiguration,
)
from src.core.modules.common.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegration,
    GithubGraphqlIntegrationConfiguration,
)
from abi.pipeline import Pipeline
from abi.utils.Graph import ABIGraph
from src.core.modules.operations.pipelines.github.GithubIssuePipeline import (
    GithubIssuePipeline,
    GithubIssuePipelineConfiguration,
    GithubIssuePipelineParameters,
)
from dataclasses import dataclass
from rdflib import Graph
from abi import logger
import pydash as _
from typing import List, Optional
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pydantic import Field
from src import secret, config

LOGO_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"


@dataclass
class GithubIssuesPipelineConfiguration(PipelineConfiguration):
    """Configuration for GithubIssuesPipeline.

    Attributes:
        github_integration_config (GithubIntegrationConfiguration): The GitHub REST API integration instance
        github_graphql_integration_config (GithubGraphqlIntegrationConfiguration): The GitHub GraphQL API integration instance
        triple_store (ITripleStoreService): The ontology store service to use
        triple_store_name (str): Name of the ontology store to use. Defaults to "github"
    """

    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration
    triple_store: ITripleStoreService
    triple_store_name: str = "github"


class GithubIssuesPipelineParameters(PipelineParameters):
    """Parameters for GithubIssuesPipeline execution.

    Attributes:
        github_repositories (List[str]): List of GitHub repositories in format owner/repo
        limit (int): Maximum number of issues to fetch per repository
        state (str): GitHub issue state
        github_project_id (int): GitHub project ID
    """

    github_repositories: List[str] = Field(
        ..., description="List of GitHub repositories in format owner/repo"
    )
    limit: Optional[int] = Field(
        default=10, description="Maximum number of issues to fetch per repository"
    )
    state: Optional[str] = Field(default="all", description="GitHub issue state")
    github_project_id: Optional[int] = Field(default=0, description="GitHub project ID")


class GithubIssuesPipeline(Pipeline):
    """Pipeline for adding multiple GitHub issues to the ontology."""

    def __init__(self, configuration: GithubIssuesPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(
            self.__configuration.github_integration_config
        )
        self.__github_graphql_integration = GithubGraphqlIntegration(
            self.__configuration.github_graphql_integration_config
        )

    def run(self, parameters: GithubIssuesPipelineParameters) -> Graph:
        combined_graph = ABIGraph()

        # Process each repository
        for repository in parameters.github_repositories:
            # Get all issues from the repository
            issues_data = self.__github_integration.list_issues(
                repository, state=parameters.state, limit=parameters.limit
            )
            logger.debug(f"Issues fetched for {repository}: {len(issues_data)}")

            # Get project data from GithubGraphqlIntegration
            if parameters.github_project_id != 0:
                organization = repository.split("/")[0]
                project_data: dict = (
                    self.__github_graphql_integration.get_project_node_id(
                        organization, parameters.github_project_id
                    )
                )
                project_node_id = _.get(project_data, "data.organization.projectV2.id")
                logger.debug(f"Project node ID: {project_node_id}")
            else:
                logger.debug("No project ID provided, skipping project data")
                project_node_id = None

            # Process each issue using the existing GithubIssuePipeline
            for issue in issues_data:
                issue_pipeline = GithubIssuePipeline(
                    configuration=GithubIssuePipelineConfiguration(
                        github_integration_config=self.__configuration.github_integration_config,
                        github_graphql_integration_config=self.__configuration.github_graphql_integration_config,
                        triple_store=self.__configuration.triple_store,
                        triple_store_name=self.__configuration.triple_store_name,
                    )
                )

                issue_graph = issue_pipeline.run(
                    GithubIssuePipelineParameters(
                        github_repository=repository,
                        github_issue_id=str(issue["number"]),
                        github_project_id=parameters.github_project_id,
                        github_project_node_id=project_node_id
                        if project_node_id is not None
                        else "",
                    )
                )
                combined_graph += issue_graph

        return combined_graph

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.

        Returns:
            list[StructuredTool]: List containing the GithubIssuesPipeline tool
        """
        return [
            StructuredTool(
                name="map_github_issues_to_ontology",
                description="Fetches multiple GitHub issues and adds them to the ontology",
                func=lambda **kwargs: self.run(
                    GithubIssuesPipelineParameters(**kwargs)
                ),
                args_schema=GithubIssuesPipelineParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "githubissues",
        name: str = "Github Issues from Repository to Ontology",
        description: str = "Fetches multiple GitHub issues from a repository, extracts their metadata, and maps them to the ontology as task completions with temporal information and agent relationships.",
        tags: list[str] = [],
    ) -> None:
        @router.post(f"/{route_name}", name=name, description=description, tags=tags)
        def run(parameters: GithubIssuesPipelineParameters):
            return self.run(parameters).serialize(format="turtle")


if __name__ == "__main__":
    from abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
        TripleStoreService__SecondaryAdaptor__Filesystem,
    )
    from abi.services.triple_store.TripleStoreService import TripleStoreService

    # Initialize ontology store
    triple_store = TripleStoreService(
        TripleStoreService__SecondaryAdaptor__Filesystem(
            store_path=config.triple_store_path
        )
    )

    # Initialize Github integration
    github_integration_config = GithubIntegrationConfiguration(
        access_token=secret.get("GITHUB_ACCESS_TOKEN")
    )

    # Initialize Github GraphQL integration
    github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(
        access_token=secret.get("GITHUB_ACCESS_TOKEN")
    )

    # Initialize pipeline
    pipeline = GithubIssuesPipeline(
        GithubIssuesPipelineConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
            triple_store=triple_store,
            triple_store_name="github",
        )
    )

    # Run pipeline
    pipeline.run(
        GithubIssuesPipelineParameters(
            github_repositories=["jupyter-naas/abi"], limit=10, state="all"
        )
    )
