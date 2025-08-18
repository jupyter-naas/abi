from src import services
from rdflib import Graph, URIRef, Literal, RDFS, SKOS, Namespace
from src.utils.Storage import save_triples
from abi import logger

BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")

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

def merge_individuals(uri_to_keep: str, uri_to_merge: str):
    """
    Merge two URIs by transferring all triples from uri_to_merge to uri_to_keep.
    Removes uri_to_merge after merging.
    
    Args:
        uri_to_keep (str): The URI that will remain and receive the merged triples
        uri_to_merge (str): The URI that will be merged into uri_to_keep and then removed
    """
    output_dir = "datastore/triplestore/merged_individual"
    
    # Get all triples for both URIs
    keep_results = get_all_triples_for_uri(uri_to_keep)
    keep_graph = Graph()
    for row in keep_results:
        s, p, o = row
        keep_graph.add((s, p, o))
    logger.info(f"Found {len(keep_results)} triples for URI to keep: {uri_to_keep}")
    
    merge_results = get_all_triples_for_uri(uri_to_merge)
    merge_graph = Graph()
    for row in merge_results:
        s, p, o = row
        merge_graph.add((s, p, o))
    logger.info(f"Found {len(merge_results)} triples for URI to merge: {uri_to_merge}")

    graph_insert = Graph()
    graph_insert.bind("bfo", BFO)
    graph_insert.bind("cco", CCO)
    graph_insert.bind("abi", ABI)
    graph_remove = Graph()
    uri_to_keep_ref = URIRef(uri_to_keep)
    uri_to_keep_label = keep_graph.value(uri_to_keep_ref, RDFS.label)
    uri_to_merge_ref = URIRef(uri_to_merge)
    uri_to_merge_label = merge_graph.value(uri_to_merge_ref, RDFS.label)
    
    # Process triples from uri_to_merge
    logger.info(f"Merging '{uri_to_merge_label}' ({uri_to_merge}) into '{uri_to_keep_label}' ({uri_to_keep})")
    for row in merge_results:
        s, p, o = row
        if s == uri_to_merge_ref and p not in [RDFS.label, ABI.universal_name]:
            check_properties = keep_graph.triples((uri_to_keep_ref, p, o))
            if len(list(check_properties)) == 0:
                if isinstance(o, URIRef):
                    graph_insert.add((uri_to_keep_ref, URIRef(p), URIRef(o)))
                elif isinstance(o, Literal):
                    # Preserve datatype and language tag if present
                    datatype = o.datatype if hasattr(o, 'datatype') else None
                    lang = o.language if hasattr(o, 'language') else None
                    graph_insert.add((uri_to_keep_ref, URIRef(p), Literal(str(o), datatype=datatype, lang=lang)))

        elif s == uri_to_merge_ref and p in [RDFS.label, ABI.universal_name]:
            datatype = o.datatype if hasattr(o, 'datatype') else None
            lang = o.language if hasattr(o, 'language') else None
            graph_insert.add((uri_to_keep_ref, SKOS.altLabel, Literal(str(o), datatype=datatype, lang=lang)))
                    
        elif o == uri_to_merge_ref:
            check_properties = keep_graph.triples((s, p, uri_to_keep_ref))
            if len(list(check_properties)) == 0:
                graph_insert.add((s, p, uri_to_keep_ref))

        # Always add original triple for removal
        graph_remove.add((s, p, o))

    if len(graph_insert) > 0:
        logger.info(f"Inserting {len(graph_insert)} triples")
        logger.info(graph_insert.serialize(format='turtle'))
        save_triples(graph_insert, output_dir, f"{uri_to_keep_label}_{uri_to_keep.split('/')[-1]}_merged.ttl")
        services.triple_store_service.insert(graph_insert)
    if len(graph_remove) > 0:
        logger.info(f"Removing {len(graph_remove)} triples")
        logger.info(graph_remove.serialize(format='turtle'))
        save_triples(graph_remove, output_dir, f"{uri_to_merge_label}_{uri_to_merge.split('/')[-1]}_removed.ttl")
        services.triple_store_service.remove(graph_remove)

if __name__ == "__main__":
    uri_to_keep = "http://ontology.naas.ai/abi/4b910ad9-f950-41c7-ae3f-9792b75c177a"  # URI that will remain
    uri_to_merge = "http://ontology.naas.ai/abi/755b45a1-3683-4726-80d9-fdda9d284a89" # URI that will be merged and removed
    merge_individuals(uri_to_keep, uri_to_merge)
