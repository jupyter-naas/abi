from rdflib import Graph, Namespace
from abi import logger
from src import services

ABI = Namespace("http://ontology.naas.ai/abi/")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
CCO = Namespace("https://www.commoncoreontologies.org/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")

query = """
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

logger.info("Inserting basic person triples...")
graph = Graph()
graph.bind('abi', ABI)
graph.bind('rdfs', RDFS) 
graph.bind('cco', CCO)
graph.bind('owl', OWL)
graph.update(query)
logger.info(graph.serialize(format="turtle"))

services.triple_store_service.insert(graph)