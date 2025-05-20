from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from datetime import datetime, timedelta
from rdflib import Graph
from abi import logger
from typing import Optional
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool


@dataclass
class GetTopPrioritiesConfiguration(WorkflowConfiguration):
    """Configuration for GetTopPriorities workflow.

    Attributes:
        triple_store (ITripleStoreService): Ontology store service
    """

    triple_store: ITripleStoreService


class GetTopPrioritiesParameters(WorkflowParameters):
    """Parameters for GetTopPriorities workflow.

    Attributes:
        days (int): Number of days to look ahead for issues
        assignee_label (Optional[str]): Filter tasks by assignee label
    """

    days: int = Field(default=7, description="Number of days to look ahead for tasks")
    assignee_label: Optional[str] = Field(
        default=None, description="Filter tasks by assignee label"
    )


class GetTopPrioritiesWorkflow(Workflow):
    """Workflow for getting top priorities from the ontology."""

    __configuration: GetTopPrioritiesConfiguration

    def __init__(self, configuration: GetTopPrioritiesConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__triple_store = self.__configuration.triple_store

    def run(self, parameters: GetTopPrioritiesParameters) -> dict:
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
        g.parse("src/core/ontologies/ConsolidatedOntology.ttl", format="turtle")
        task_types = g.query(task_subclasses_query)

        # Create VALUES clause instead of UNION
        task_types_values = (
            "VALUES ?taskType {"
            + " ".join([f"<{str(row['taskType'])}>" for row in task_types])
            + "}"
        )
        logger.info(f"Task subclasses: {task_types_values}")

        # Calculate the due date based on configuration
        today = datetime.now()
        due_date = today + timedelta(days=parameters.days)
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
        results = self.__triple_store.query(query)

        # Convert tasks to a list of dictionaries for better LLM consumption
        data = []
        for row in results:
            data_dict = {}
            for key in row.labels:
                data_dict[key] = str(row[key]) if row[key] else None

            # Only add the task if it matches the assignee filter (if provided)
            if (
                parameters.assignee_label is None
                or data_dict.get("assignee_label") == parameters.assignee_label
            ):
                data.append(data_dict)

        return {
            "message": "Sort data providedby due date and priority in descending order",
            "data": data,
        }

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="get_top_priorities",
                description="Get top priorities. If user wants to filter by user, ask to provide the assignee label else return all tasks.",
                func=lambda **kwargs: self.run(GetTopPrioritiesParameters(**kwargs)),
                args_schema=GetTopPrioritiesParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.

        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """

        @router.post("/get_top_priorities")
        def get_priorities(parameters: GetTopPrioritiesParameters):
            return self.run(parameters)
