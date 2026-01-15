from dotenv import load_dotenv
from naas_abi_core import logger
from naas_abi_core.utils.StorageUtils import StorageUtils
from rdflib import Graph, URIRef
from rdflib.query import ResultRow

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

    # Execute query and add results to export graph
    results = triple_store_service.query(sparql_query)
    for row in results:
        assert isinstance(row, ResultRow)
        s, p, o = row["s"], row["p"], row["o"]
        export_graph.add((URIRef(s), URIRef(p), o))

    # Save exported graph
    dir_path = "triplestore/export/turtle"
    storage_utils.save_triples(export_graph, dir_path, "graph_instances_export.ttl")
    logger.info(f"💾 Graph exported to {dir_path}/graph_instances_export.ttl")
