from pydantic import BaseModel, Field
from typing import Optional, List
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS
from abi.services.ontology_store import OntologyStoreService
from abi.services.ontology_store.models.Graph import ABIGraph

class UexamplePipelineConfiguration(BaseModel):
    """Configuration for the Uexample Pipeline."""
    # Add configuration parameters here
    ontology_store: OntologyStoreService = Field(..., description="Ontology store service for persisting RDF data")

class UexamplePipelineParameters(BaseModel):
    """Parameters for running the Uexample Pipeline."""
    # Add input parameters here
    entity_id: str = Field(..., description="ID of the entity to process")
    attributes: List[str] = Field(default_factory=list, description="Attributes to include")

class UexamplePipeline:
    """A pipeline for transforming example data into RDF."""
    
    def __init__(self, configuration: UexamplePipelineConfiguration):
        self.__configuration = configuration
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [StructuredTool(
            name="example_pipeline",
            description="Executes the Uexample pipeline with the given parameters",
            func=lambda **kwargs: self.run(UexamplePipelineParameters(**kwargs)),
            args_schema=UexamplePipelineParameters
        )]
    
    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router."""
        @router.post("/UexamplePipeline")
        def run(parameters: UexamplePipelineParameters):
            return self.run(parameters).serialize(format="turtle")
    
    def run(self, parameters: UexamplePipelineParameters) -> Graph:
        """Runs the pipeline with the given parameters."""
        # Create a new RDF graph
        graph = ABIGraph()
        
        # Define namespaces
        YOUR = Namespace(f"http://ontology.naas.ai/{example}/")
        
        # Bind namespaces
        graph.bind("your", YOUR)
        
        # Create entity URI
        entity_uri = URIRef(f"{YOUR}entity/{parameters.entity_id}")
        
        # Add class assertion
        graph.add((entity_uri, RDF.type, YOUR.YourClass))
        
        # Add example attributes
        if parameters.attributes:
            for attr in parameters.attributes:
                graph.add((entity_uri, YOUR.hasAttribute, Literal(attr)))
        else:
            # Default attribute if none provided
            graph.add((entity_uri, YOUR.hasAttribute, Literal("default attribute")))
        
        # Optionally persist to ontology store
        # self.__configuration.ontology_store.add_graph(
        #    store_name="your_store",
        #    graph=graph
        # )
        
        return graph

# For testing purposes
if __name__ == "__main__":
    from abi.services.ontology_store import OntologyStoreService
    
    # Setup dependencies
    ontology_store = OntologyStoreService()
    
    # Create pipeline configuration
    config = UexamplePipelineConfiguration(
        ontology_store=ontology_store
    )
    
    # Initialize and run pipeline
    pipeline = UexamplePipeline(config)
    result = pipeline.run(UexamplePipelineParameters(
        entity_id="123",
        attributes=["attr1", "attr2"]
    ))
    
    # Print results in Turtle format
    print(result.serialize(format="turtle"))

