from naas_abi import services
from naas_abi.utils.Storage import save_triples
from naas_abi_core import logger
from rdflib import Graph, URIRef

if __name__ == "__main__":
    # Create new graph for export
    export_graph = Graph()

    # Query to get all named individuals and their properties
    sparql_query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?s ?p ?o 
    WHERE {
        ?s rdf:type owl:NamedIndividual .
        ?s ?p ?o .
        FILTER(STRSTARTS(STR(?s), "http://ontology.naas.ai/abi/"))
    }
    """

    # Execute query and add results to export graph
    results = services.triple_store_service.query(sparql_query)
    for row in results:
        s, p, o = row
        export_graph.add((URIRef(s), URIRef(p), o))

    # Save exported graph
    dir_path = "datastore/triplestore/export/turtle"
    save_triples(export_graph, dir_path, "graph_instances_export.ttl")
    logger.info(f"💾 Graph exported to {dir_path}/graph_instances_export.ttl")
