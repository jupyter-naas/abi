from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from abi.utils.SPARQL import results_to_list

@dataclass
class GetIndividualsFromClassConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for GetIndividualsFromClass workflow."""
    triple_store: ITripleStoreService

class GetIndividualsFromClassWorkflowParameters(WorkflowParameters):
    """Parameters for GetIndividualsFromClass workflow."""
    class_uri: str = Field(..., description="Class URI to use to get all individuals of this class.")

class GetIndividualsFromClassWorkflow(Workflow):
    """Workflow for getting all individuals of a class."""
    __configuration: GetIndividualsFromClassConfigurationWorkflow
    
    def __init__(self, configuration: GetIndividualsFromClassConfigurationWorkflow):
        super().__init__(configuration)
        self.__configuration = configuration

    def get_individuals(self, parameters: GetIndividualsFromClassWorkflowParameters) -> dict:
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?label
        WHERE {{
            ?class a <{parameters.class_uri}> ;
                    rdfs:label ?label .
        }}
        ORDER BY ?label
        """
        results = self.__configuration.triple_store.query(query)
        return results_to_list(results)
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_get_individuals",
                description="Retrieve individuals/instances from a class from the ontology store.",
                func=lambda class_uri: self.get_individuals(GetIndividualsFromClassWorkflowParameters(class_uri=class_uri)),
                args_schema=GetIndividualsFromClassWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 