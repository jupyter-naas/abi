from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from rdflib import Graph
from abi import logger
from typing import Union, Optional


@dataclass
class GetTopPrioritiesConfiguration(WorkflowConfiguration):
    """Configuration for GetTopPriorities workflow.
    
    Attributes:
        days (int): Number of days to look ahead for issues. Defaults to 7.
        assignee_label (str, optional): Filter tasks by assignee label. Defaults to None.
    """
    days: int = 7
    assignee_label: Optional[str] = None


class GetTopPrioritiesWorkflow(Workflow):
    __configuration: GetTopPrioritiesConfiguration
    
    def __init__(self, configuration: GetTopPrioritiesConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        
        onto_store_adaptor = OntologyStoreService__SecondaryAdaptor__Filesystem(secret.get('ONTOLOGY_STORE_PATH'))
        self.__ontology_store = OntologyStoreService(onto_store_adaptor)
        
    def run(self) -> str:
        # First, get all task subclasses
        task_subclasses_query = """
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT DISTINCT ?taskType
            WHERE {
                ?taskType rdfs:subClassOf+ abi:Task .
            }
        """
        g = Graph()
        g.parse("src/ontologies/consolidated_ontology.ttl", format="turtle")
        task_types = g.query(task_subclasses_query)
        
        # Create VALUES clause instead of UNION
        task_types_values = "VALUES ?taskType {" + " ".join([f"<{str(row['taskType'])}>" for row in task_types]) + "}"
        logger.info(f"Task subclasses: {task_types_values}")

        # Calculate the due date based on configuration
        today = datetime.now()
        due_date = today + timedelta(days=self.__configuration.days)
        due_date_str = due_date.strftime("%Y-%m-%d")

        # Main query using dynamic task types
        query = f"""
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/> 
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT DISTINCT ?issue ?title ?description ?url ?status ?priority ?labels ?due_date ?updated_date ?assignee_label
            WHERE {{
                # Use VALUES clause for task types
                {task_types_values}
                ?issue a ?taskType .
                
                ?issue rdfs:label ?title ;
                       abi:state ?state .
                
                # Rest of the query remains the same
                FILTER (LCASE(STR(?state)) = "open")
                
                OPTIONAL {{ ?issue abi:description ?description }}
                OPTIONAL {{ ?issue abi:url ?url }}
                OPTIONAL {{ ?issue abi:status ?status }}
                OPTIONAL {{ ?issue abi:priority ?priority }}
                OPTIONAL {{ ?issue abi:labels ?labels }}
                OPTIONAL {{ ?issue abi:due_date ?due_date }}
                OPTIONAL {{ ?issue abi:updated_date ?updated_date }}
                
                FILTER (BOUND(?due_date) && ?due_date != "")
                FILTER (STR(?due_date) != '' && STR(?due_date) != 'None')
                FILTER (STR(?due_date) <= "{due_date_str}")
                
                OPTIONAL {{
                    ?task_completion bfo:BFO_0000058 ?issue ;
                                    a abi:TaskCompletion .
                    OPTIONAL {{
                        ?task_completion abi:hasAssignee ?assignee .
                        ?assignee a abi:GitHubUser ;
                                 rdfs:label ?assignee_label .
                    }}
                }}
            }}
            ORDER BY DESC(?due_date) ?title
        """
        logger.info(f"Query: {query}")
        results = self.__ontology_store.query(query)
        
        # Convert tasks to a list of dictionaries for better LLM consumption
        data = []
        for row in results:
            data_dict = {}
            for key in row.labels:
                data_dict[key] = str(row[key]) if row[key] else None
            
            # Only add the task if it matches the assignee filter (if provided)
            if (self.__configuration.assignee_label is None or 
                data_dict.get('assignee_label') == self.__configuration.assignee_label):
                data.append(data_dict)
            
        return {"message": "Sort data providedby due date and priority in descending order", "data": data}

def main():
    configuration = GetTopPrioritiesConfiguration()
    workflow = GetTopPrioritiesWorkflow(configuration)
    result = workflow.run()

def as_tool():
    from langchain_core.tools import StructuredTool
    
    def get_top_priorities(days: int = 7, assignee_label: Optional[str] = None):
        configuration = GetTopPrioritiesConfiguration(days=days, assignee_label=assignee_label)
        workflow = GetTopPrioritiesWorkflow(configuration)
        return workflow.run()
    
    class GetTopPrioritiesSchema(BaseModel):
        days: int = Field(default=7, description="Number of days to look ahead for tasks.")
        assignee_label: Optional[str] = Field(default=None, description="Filter tasks by assignee label.")
    
    return StructuredTool(
        name="get_top_priorities",
        description="Intent: Get top priorities. If user wants to filter by user, ask to provide the assignee label else return all tasks.",
        func=get_top_priorities,
        args_schema=GetTopPrioritiesSchema
    )

if __name__ == "__main__":
    main() 