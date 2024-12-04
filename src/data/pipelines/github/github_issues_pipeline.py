from dataclasses import dataclass
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from abi.pipeline import Pipeline, PipelineConfiguration
from abi.utils.Graph import ABIGraph
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

from src.data.pipelines.github.github_issue_pipeline import GithubIssuePipeline, GithubIssuePipelineConfiguration
from rdflib import Graph
from src import secret

@dataclass
class GithubIssuesPipelineConfiguration(PipelineConfiguration):
    github_repository: str
    ontology_store_name: str = "github"

class GithubIssuesPipeline(Pipeline):
    def __init__(self, integration: GithubIntegration, ontology_store: IOntologyStoreService, configuration: GithubIssuesPipelineConfiguration):
        super().__init__([integration], configuration)
        
        self.__integration = integration
        self.__configuration = configuration
        self.__ontology_store = ontology_store
        
    def run(self) -> Graph:
        # Get all issues from the repository
        issues_data = self.__integration.get_issues(self.__configuration.github_repository)
        
        # Create a combined graph
        combined_graph = ABIGraph()
        
        # Process each issue using the existing GithubIssuePipeline
        for issue in issues_data:
            issue_pipeline = GithubIssuePipeline(
                integration=self.__integration,
                ontology_store=self.__ontology_store,
                configuration=GithubIssuePipelineConfiguration(
                    github_repository=self.__configuration.github_repository,
                    github_issue_id=str(issue["number"]),
                    ontology_store_name=self.__configuration.ontology_store_name
                )
            )
            
            # Run the pipeline for this issue and merge the results
            issue_graph = issue_pipeline.run()
            combined_graph += issue_graph
            
        return combined_graph

# Add this to the if __name__ == "__main__" section for testing
if __name__ == "__main__":
    graph = GithubIssuesPipeline(
        integration=GithubIntegration(GithubIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN"))),
        ontology_store=OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store")),
        configuration=GithubIssuesPipelineConfiguration(
            github_repository="jupyter-naas/abi"
        )
    ).run()
    
    print(graph.serialize(format="turtle"))
