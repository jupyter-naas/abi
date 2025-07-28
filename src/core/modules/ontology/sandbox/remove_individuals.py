from src import services
from rdflib import Graph
from src.utils.Storage import save_triples
from abi import logger


def get_all_triples_for_uri(uri: str):
    """
    Retrieve all triples where the given URI appears as either a subject or object.
    
    Args:
        uri (str): The URI to search for
        
    Returns:
        rdflib.query.Result: Query results containing all triples where the URI appears
    """
    sparql_query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT ?s ?p ?o
    WHERE {{
        {{
            # Find triples where the URI is the subject
            <{uri}> ?p ?o .
            BIND(<{uri}> AS ?s)
        }}
        UNION
        {{
            # Find triples where the URI is the object
            ?s ?p <{uri}> .
            BIND(<{uri}> AS ?o)
        }}
    }}
    """
    
    return services.triple_store_service.query(sparql_query)

def remove_individuals(uris: list[str]):
    output_dir = "datastore/ontology/removed_individual"
    for uri in uris:
        logger.info(f"Getting triples for URI: {uri}")
        results = get_all_triples_for_uri(uri)
        graph_remove = Graph()
        for row in results:
            s, p, o = row
            graph_remove.add((s, p, o))

        if len(graph_remove) > 0:
            logger.info(graph_remove.serialize(format="turtle"))
            save_triples(graph_remove, output_dir, f"{uri.split('/')[-1]}.ttl")
            services.triple_store_service.remove(graph_remove)    
        else:   
            logger.info(f"No triples found for {uri}")

if __name__ == "__main__":
    uris_to_remove: list[str] = []
    remove_individuals(uris_to_remove)
