from dotenv import load_dotenv
from naas_abi_core import logger
from naas_abi_core.utils.StorageUtils import StorageUtils
from rdflib import Graph, URIRef

load_dotenv()


if __name__ == "__main__":
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi"])
    triple_store_service = engine.services.triple_store

    storage_utils = StorageUtils(storage_service=engine.services.object_storage)

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

    # Read the result as a stream: no RPC size cap, no result next to the graph.
    with triple_store_service.query_stream(sparql_query) as result:
        for row in result.rows:
            export_graph.add((URIRef(row["s"]), URIRef(row["p"]), row["o"]))

    # Save exported graph
    dir_path = "triplestore/export/turtle"
    storage_utils.save_triples(export_graph, dir_path, "graph_instances_export.ttl")
    logger.info(f"💾 Graph exported to {dir_path}/graph_instances_export.ttl")
