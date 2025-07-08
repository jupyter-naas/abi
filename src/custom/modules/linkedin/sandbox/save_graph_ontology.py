from abi.utils.Storage import get_triples, save_triples
from abi.utils.Graph import ABI, BFO, CCO
from rdflib import URIRef, Literal, RDF, OWL, Graph, RDFS, BNode
from src import services
from abi import logger


profile_id = "jeremyravenel"
input_dir = f"datastore/linkedin/get_profile_view/{profile_id}"
output_dir = f"src/custom/modules/linkedin/ontologies"
graph_insert = get_triples(input_dir, f"{profile_id}.ttl")

# Save schema
classes = set()
object_properties = set()
data_properties = set()
schema_graph = Graph()
schema_graph.bind("rdfs", RDFS)
schema_graph.bind("rdf", RDF)
schema_graph.bind("owl", OWL)
schema_graph.bind("cco", CCO)
schema_graph.bind("abi", ABI)
schema_graph.bind("bfo", BFO)

# Collect classes
for s, p, o in graph_insert.triples((None, RDF.type, None)):
    if o != OWL.NamedIndividual:
        classes.add(o)

# Collect properties
for s, p, o in graph_insert:
    if p in [RDF.type, RDFS.label]:
        continue
    if isinstance(o, Literal):
        data_properties.add(p)
    elif isinstance(o, URIRef):
        object_properties.add(p)

# Query triple store for additional schema information
def add_schema_information(graph: Graph, uri: URIRef, type: URIRef) -> Graph:
    # Query for basic schema info
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        
        SELECT ?p ?o 
        WHERE {{
            <{str(uri)}> ?p ?o .
            FILTER(?p IN (rdfs:label, skos:example, skos:definition, rdfs:domain, rdfs:range, rdfs:subClassOf, rdf:type))
        }}
    """
    
    # Query for domain/range details if they exist
    domain_range_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        
        SELECT DISTINCT ?p ?list ?member 
        WHERE {{
            <{str(uri)}> ?p ?list .
            FILTER(?p IN (rdfs:domain, rdfs:range))
            ?list rdf:type owl:Class ;
                    owl:unionOf ?collection .
            ?collection rdf:rest*/rdf:first ?member .
        }}
    """
    
    try:
        # Add basic schema info
        results = services.triple_store_service.query(query)
        for row in results:
            graph.add((uri, row.p, row.o))
            
        # Add domain/range details    
        domain_range_results = services.triple_store_service.query(domain_range_query)
        seen = set()
        for row in domain_range_results:
            key = (row.p, row.list, row.member)
            if key in seen:
                continue
            seen.add(key)
            
            blank = BNode()
            collection = BNode()
            graph.add((uri, row.p, blank))
            graph.add((blank, RDF.type, OWL.Class))
            graph.add((blank, OWL.unionOf, collection))
            graph.add((collection, RDF.first, row.member))
            graph.add((collection, RDF.rest, RDF.nil))
            
    except Exception as e:
        logger.error(f"Error querying triple store for {uri}: {e}")
        graph.add((uri, RDF.type, type))
        
    return graph

for uri in list(classes):
    schema_graph = add_schema_information(schema_graph, uri, OWL.Class)
for uri in list(object_properties):
    schema_graph = add_schema_information(schema_graph, uri, OWL.ObjectProperty)
for uri in list(data_properties):
    schema_graph = add_schema_information(schema_graph, uri, OWL.DatatypeProperty)

save_triples(schema_graph, output_dir, f"LinkedInOntology_schema.ttl")
logger.info(f"LinkedInOntology_schema.ttl saved in {output_dir}")