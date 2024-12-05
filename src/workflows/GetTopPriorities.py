from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from abi.utils.Graph import ABIGraph, ABI, URIRef
from src import secret
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field

@dataclass
class GetTopPrioritiesConfiguration(WorkflowConfiguration):
    pass

class GetTopPrioritiesWorkflow(Workflow):
    __configuration: GetTopPrioritiesConfiguration
    
    def __init__(self, configuration: GetTopPrioritiesConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        
        onto_store_adaptor = OntologyStoreService__SecondaryAdaptor__Filesystem(secret.get('ONTOLOGY_STORE_PATH'))
        self.__ontology_store = OntologyStoreService(onto_store_adaptor)
        

    def run(self) -> str:
        tasks = self.__ontology_store.query("""
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/> 
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT DISTINCT ?issue ?title ?description ?url ?status ?priority ?labels ?due_date ?updated_date ?assignee_label
            WHERE {
                # Match tasks of type Task
                ?issue a abi:GitHubIssue ;
                    rdfs:label ?title .
                
                # Get required properties
                OPTIONAL { ?issue abi:description ?description }
                OPTIONAL { ?issue abi:url ?url }
                OPTIONAL { ?issue abi:status ?status }
                OPTIONAL { ?issue abi:priority ?priority }
                OPTIONAL { ?issue abi:labels ?labels }
                OPTIONAL { ?issue abi:due_date ?due_date }
                OPTIONAL { ?issue abi:updated_date ?updated_date }
                
                # Get associated task completion if it exists
                OPTIONAL {
                    ?task_completion bfo:BFO_0000058 ?issue ;
                                    a abi:TaskCompletion .
                    
                    # Get assignee if it exists
                    OPTIONAL {
                        ?task_completion abi:hasAssignee ?assignee .
                        ?assignee a abi:GitHubUser ;  # Ensure it's a GitHub user
                                rdfs:label ?assignee_label .
                    }
                }
            }
            ORDER BY ?due_date ?priority ?title  # Order by due date first, then priority, then title
            """)
        # Convert tasks to a list of dictionaries for better LLM consumption
        formatted_tasks = []
        for task in tasks:
            task_dict = {
                "title": str(task["title"]),
                "description": str(task["description"]) if task["description"] else None,
                "url": str(task["url"]) if task["url"] else None,
                "status": str(task["status"]) if task["status"] else None,
                "priority": str(task["priority"]) if task["priority"] else None,
                "labels": str(task["labels"]) if task["labels"] else None,
                "due_date": str(task["due_date"]) if task["due_date"] else None,
                "assignee": str(task["assignee_label"]) if task["assignee_label"] else None
            }
            # Remove None values for cleaner output
            if task["due_date"] is not None:
                task_dict = {k: v for k, v in task_dict.items() if v is not None}
                formatted_tasks.append(task_dict)
            
        return formatted_tasks

def main():
    configuration = GetTopPrioritiesConfiguration()
    workflow = GetTopPrioritiesWorkflow(configuration)
    result = workflow.run()

def as_tool():
    from langchain_core.tools import StructuredTool
    
    def get_top_priorities():
        configuration = GetTopPrioritiesConfiguration()
        workflow = GetTopPrioritiesWorkflow(configuration)
        return workflow.run()
    
    class GetTopPrioritiesSchema(BaseModel):
        pass
    
    return StructuredTool(
        name="get_top_priorities",
        description="Intent: Get top priorities.",
        func=get_top_priorities,
        args_schema=GetTopPrioritiesSchema
    )

if __name__ == "__main__":
    main() 