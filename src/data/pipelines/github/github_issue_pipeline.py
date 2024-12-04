from abi.pipeline import Pipeline, PipelineConfiguration, Pipeline
from dataclasses import dataclass
from src.integrations.GithubIntegration import GithubIntegration
from abi.utils.Graph import ABIGraph, ABI, BFO
from rdflib import Graph
from datetime import datetime
from abi.services.ontology_processor.OntologyService import OntologyService
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

from src import secret

@dataclass
class GithubIssuePipelineConfiguration(PipelineConfiguration):
    github_repository: str
    github_issue_id: str
    ontology_store_name: str = "github"

class GithubIssuePipeline(Pipeline):
    def __init__(self, integration: GithubIntegration, ontology_store: IOntologyStoreService, configuration: GithubIssuePipelineConfiguration):
        super().__init__([integration], configuration)
        
        self.__integration = integration
        self.__configuration = configuration
        self.__ontology_store = ontology_store
        
    def run(self) -> Graph:
        issue_data : dict = self.__integration.get_issue(self.__configuration.github_repository, self.__configuration.github_issue_id)
        
        graph = ABIGraph()
        
        issue_id = issue_data.get("number")
        issue_label = issue_data.get("title")
        hasDescription = issue_data.get("body")
        hasURL = issue_data.get("html_url")
        hasLabels = ", ".join([x.get("name") for x in issue_data.get("labels")])

        # Add Process: Task Completion
        task_completion = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=issue_id,
            label=issue_label,
            is_a=ABI.TaskCompletion,
            # hasDescription=hasDescription,
            # hasURL=hasURL,
            # hasLabels=hasLabels,
        )

        # Add GDC: GitHubIssue
        issue = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=issue_id,
            label=issue_label,
            is_a=ABI.GitHubIssue,
            # hasDescription=hasDescription,
            # hasURL=hasURL,
            # hasLabels=hasLabels
        )
        graph.add((task_completion, BFO.BFO_0000058, issue))
        graph.add((issue, BFO.BFO_0000059, task_completion))
        
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
            github_issue_id="177"
        )
    ).run()
    
    print(graph.serialize(format="turtle"))