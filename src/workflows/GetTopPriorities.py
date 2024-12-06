from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from datetime import datetime, timedelta


@dataclass
class GetTopPrioritiesConfiguration(WorkflowConfiguration):
    """Configuration for GetTopPriorities workflow.
    
    Attributes:
        days (int): Number of days to look ahead for issues. Defaults to 7.
    """
    days: int = 7


class GetTopPrioritiesWorkflow(Workflow):
    __configuration: GetTopPrioritiesConfiguration
    
    def __init__(self, configuration: GetTopPrioritiesConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        
        onto_store_adaptor = OntologyStoreService__SecondaryAdaptor__Filesystem(secret.get('ONTOLOGY_STORE_PATH'))
        self.__ontology_store = OntologyStoreService(onto_store_adaptor)
        
    def run(self) -> str:
        # Calculate the due date based on configuration
        today = datetime.now()
        due_date = today + timedelta(days=self.__configuration.days)
        due_date_str = due_date.strftime("%Y-%m-%d")

        results = self.__ontology_store.query(f"""
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/> 
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT DISTINCT ?issue ?title ?description ?url ?status ?priority ?labels ?due_date ?updated_date ?assignee_label
            WHERE {{
                # Match tasks of type GitHubIssue
                ?issue a abi:GitHubIssue ;
                       rdfs:label ?title ;
                       abi:state ?state .
                
                # Filter for open state
                FILTER (LCASE(STR(?state)) = "open")
                
                # Get required properties
                OPTIONAL {{ ?issue abi:description ?description }}
                OPTIONAL {{ ?issue abi:url ?url }}
                OPTIONAL {{ ?issue abi:status ?status }}
                OPTIONAL {{ ?issue abi:priority ?priority }}
                OPTIONAL {{ ?issue abi:labels ?labels }}
                OPTIONAL {{ ?issue abi:due_date ?due_date }}
                OPTIONAL {{ ?issue abi:updated_date ?updated_date }}
                
                # Filter for due dates that exist and are not empty
                FILTER (BOUND(?due_date) && ?due_date != "")
                
                # Filter for due dates before or equal to the calculated end date
                FILTER (STR(?due_date) != '' && STR(?due_date) != 'None')
                FILTER (STR(?due_date) <= "{due_date_str}")
                
                # Get associated task completion if it exists
                OPTIONAL {{
                    ?task_completion bfo:BFO_0000058 ?issue ;
                                    a abi:TaskCompletion .
                    # Get assignee if it exists
                    OPTIONAL {{
                        ?task_completion abi:hasAssignee ?assignee .
                        ?assignee a abi:GitHubUser ; # Ensure it's a GitHub user
                                 rdfs:label ?assignee_label .
                    }}
                }}
            }}
            ORDER BY DESC(?due_date) ?title
        """)
        # Convert tasks to a list of dictionaries for better LLM consumption
        data = []
        for row in results:
            data_dict = {}
            for x in row.labels:
                data_dict[x] = str(row[x])
                data.append(data_dict)
            
        return data

def main():
    configuration = GetTopPrioritiesConfiguration()
    workflow = GetTopPrioritiesWorkflow(configuration)
    result = workflow.run()

def as_tool():
    from langchain_core.tools import StructuredTool
    
    def get_top_priorities(days: int = 7):
        configuration = GetTopPrioritiesConfiguration(days=days)
        workflow = GetTopPrioritiesWorkflow(configuration)
        return workflow.run()
    
    class GetTopPrioritiesSchema(BaseModel):
        days: int = Field(default=7, description="Number of days to look ahead for tasks.")
    
    return StructuredTool(
        name="get_top_priorities",
        description="Intent: Get top priorities",
        func=get_top_priorities,
        args_schema=GetTopPrioritiesSchema
    )

if __name__ == "__main__":
    main() 