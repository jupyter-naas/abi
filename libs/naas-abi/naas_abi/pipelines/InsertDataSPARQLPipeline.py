from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from pydantic import Field
from rdflib import Graph, Namespace

BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")


@dataclass
class InsertDataSPARQLPipelineConfiguration(PipelineConfiguration):
    """Configuration for InsertDataSPARQLPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService


class InsertDataSPARQLPipelineParameters(PipelineParameters):
    """Parameters for InsertDataSPARQLPipeline execution.

    Attributes:
        sparql_statement (str): The SPARQL INSERT DATA statement to execute
    """

    sparql_statement: Annotated[
        str,
        Field(
            description="SPARQL INSERT DATA statement to execute. Must be a valid SPARQL INSERT DATA query."
        ),
    ]


class InsertDataSPARQLPipeline(Pipeline):
    """Pipeline for executing SPARQL INSERT DATA statements on the ontology."""

    __configuration: InsertDataSPARQLPipelineConfiguration

    def __init__(self, configuration: InsertDataSPARQLPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def get_sparql_from_text(
        self, parameters: InsertDataSPARQLPipelineParameters
    ) -> str:
        """Get the SPARQL INSERT DATA statement from the text.

        Args:
            text (str): The text to extract the SPARQL INSERT DATA statement from

        Returns:
            str: The SPARQL INSERT DATA statement
        """
        text = parameters.sparql_statement

        # Clean the statement from the ```sparql and ```
        text = text.split("```sparql")[-1].split("```")[0].strip()
        if "INSERT DATA" in text:
            logger.info(f"✅ SPARQL INSERT DATA statement found: {text}")
            return text
        return f"No SPARQL INSERT DATA statement found in statement: {parameters.sparql_statement}"

    def run(self, parameters: PipelineParameters) -> Graph:
        """Execute the SPARQL INSERT DATA statement.

        Args:
            parameters (PipelineParameters): Must be InsertDataSPARQLPipelineParameters

        Returns:
            Graph: The graph with the inserted data

        Raises:
            ValueError: If parameters are not of the correct type
        """
        if not isinstance(parameters, InsertDataSPARQLPipelineParameters):
            raise ValueError(
                "Parameters must be of type InsertDataSPARQLPipelineParameters"
            )

        logger.info("Executing SPARQL INSERT DATA statement...")

        # Initialize a new graph with common namespace bindings
        graph = Graph()
        graph.bind("bfo", BFO)
        graph.bind("cco", CCO)
        graph.bind("abi", ABI)

        # Execute the SPARQL INSERT DATA statement
        try:
            sparql_statement = self.get_sparql_from_text(parameters)
            graph.update(sparql_statement)
            logger.info("✅ SPARQL INSERT DATA is valid.")
        except Exception as e:
            logger.error(f"❌ Failed to execute SPARQL INSERT DATA: {e}")
            return Graph()

        # Insert the graph into the triple store
        if len(graph) > 0:
            logger.info("✅ Inserting data to triplestore:")
            logger.info(graph.serialize(format="turtle"))
            self.__configuration.triple_store.insert(graph)
        else:
            logger.info("❌ No data to insert")
        return graph

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this pipeline.

        Returns:
            list[BaseTool]: List containing the pipeline tool
        """
        return [
            StructuredTool(
                name="insert_data_sparql",
                description="Execute a SPARQL INSERT DATA statement to add triples to the triple store",
                func=lambda **kwargs: self.run(
                    InsertDataSPARQLPipelineParameters(**kwargs)
                ),
                args_schema=InsertDataSPARQLPipelineParameters,
            ),
            StructuredTool(
                name="extract_sparql_from_text",
                description="Extract a SPARQL INSERT DATA statement from the text",
                func=lambda **kwargs: self.get_sparql_from_text(
                    InsertDataSPARQLPipelineParameters(**kwargs)
                ),
                args_schema=InsertDataSPARQLPipelineParameters,
            ),
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        """Register API endpoints for this pipeline.

        Args:
            router: FastAPI router to register endpoints on
            route_name: Name for the route
            name: Display name for the endpoint
            description: Description for the endpoint
            description_stream: Description for streaming endpoint
            tags: Tags for the endpoint
        """
        if tags is None:
            tags = []
        return None


if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi"])
    triple_store_service = engine.services.triple_store

    sparql_statement = """
    PREFIX abi: <http://ontology.naas.ai/abi/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX cco: <https://www.commoncoreontologies.org/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    INSERT DATA {
        abi:john a cco:ont00001262, owl:NamedIndividual ;
                    abi:name "John Doe" ;
                    abi:age 30 ;
                    abi:email "john.doe@example.com" .
        
        abi:jane a cco:ont00001262, owl:NamedIndividual ;
                    abi:name "Jane Smith" ;
                    abi:age 28 ;
                    abi:email "jane.smith@example.com" .
    }
    """
    pipeline = InsertDataSPARQLPipeline(
        InsertDataSPARQLPipelineConfiguration(triple_store=triple_store_service)
    )
    # result = pipeline.get_sparql_from_text(InsertDataSPARQLPipelineParameters(sparql_statement=sparql_statement))
    # logger.info(result)

    result = pipeline.run(
        InsertDataSPARQLPipelineParameters(sparql_statement=sparql_statement)
    )
    logger.info(result)
