from src import services
from abi import logger
from rdflib import URIRef, query, Graph, RDFS, RDF, OWL, XSD, DCTERMS
from typing import List, Dict, Optional
from abi.utils.Graph import BFO, ABI, TEST, CCO

def results_to_list(
    results: query.Result
) -> Optional[List[Dict]]:
    """
    Transform SPARQL query results to a list of dictionaries using the labels as keys.

    Args:
        results (query.Result): The SPARQL query results to transform

    Returns:
        Optional[List[Dict]]: List of dictionaries with query results, or None if no results
    """
    data = []
    for row in results:
        assert isinstance(row, query.ResultRow)
        logger.debug(f"==> Row: {row}")
        data_dict = {}
        for key in row.labels:
            data_dict[key] = str(row[key]) if row[key] else None
        data.append(data_dict)
    return data if len(data) > 0 else None

def get_class_uri_from_individual_uri(
    uri: str | URIRef,
) -> Optional[str]:
    """
    Get the class URI for a given URI from the triple store.

    Args:
        uri (str): The URI to look up

    Returns:
        str: The class URI if found, None otherwise
    """
    sparql_query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?type
        WHERE {{
            <{uri}> rdf:type ?type .
            FILTER(?type != owl:NamedIndividual)
        }}
        LIMIT 1
    """

    try:
        results = services.triple_store_service.query(sparql_query)
        for row in results:
            assert isinstance(row, query.ResultRow)
            return URIRef(str(row.type))
        return None
    except Exception as e:
        logger.error(f"Error getting class URI for {uri}: {e}")
        return None
    
def get_rdfs_label_from_individual_uri(
    uri: str | URIRef,
) -> Optional[str]:
    """
    Get the RDFS label for a given URI from the triple store.
    
    Args:
        uri (str): The URI to look up

    Returns:
        str: The RDFS label if found, None otherwise
    """
    sparql_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?label
        WHERE {{
            <{uri}> rdfs:label ?label .
        }}
        LIMIT 1
    """
    
    try:
        results = services.triple_store_service.query(sparql_query)
        for row in results:
            assert isinstance(row, query.ResultRow)
            return str(row.label)
        return None
    except Exception as e:
        logger.error(f"Error getting label for {uri}: {e}")
        return None

def get_identifier(
    identifier: str, 
    type: URIRef = URIRef("http://ontology.naas.ai/abi/unique_id"),
    graph: Graph = Graph()
) -> Optional[URIRef]:
    """
    Get the URI for a given identifier from the triple store.

    Args:
        identifier (str): The identifier string to look up
        type (URIRef, optional): The predicate type to use for the lookup. 
                                Defaults to "http://ontology.naas.ai/abi/unique_id"

    Returns:
        Optional[URIRef]: The URI if found, None otherwise
    """
    sparql_query = f"""
        SELECT ?s
        WHERE {{
            ?s <{str(type)}> "{identifier}" .
        }}
        LIMIT 1
    """
    try:
        if len(graph) > 0:
            results = graph.query(sparql_query)
        else:
            results = services.triple_store_service.query(sparql_query) # type: ignore

        for row in results:
            assert isinstance(row, query.ResultRow)
            # Use existing URI if found
            return URIRef(str(row.s))
    except Exception as e:
        logger.error(f"Error getting identifier for {identifier}: {e}")
        return None
    return None

def get_subject_graph(
    uri: str | URIRef,
    depth: int = 1
) -> Graph:
    """
    Get a graph for a given URI with a specified depth of relationships.
    This recursively follows relationships to build a more detailed subgraph.

    Args:
        uri (str): The URI to build the graph around
        depth (int): How many levels deep to traverse relationships (default: 1)

    Returns:
        Graph: RDFlib Graph containing triples within the specified depth
    """
    if depth <= 0:
        return Graph()
    
    # Build the CONSTRUCT query dynamically based on depth
    construct_clauses = []
    where_clauses = []
    
    # Add patterns for each depth level
    for i in range(depth):
        if i == 0:
            construct_clauses.append(f"<{str(uri)}> ?p{i} ?o{i} .")
            where_clauses.append(f"<{str(uri)}> ?p{i} ?o{i} .")
        else:
            construct_clauses.append(f"?o{i-1} ?p{i} ?o{i} .")
            where_clauses.append(f"OPTIONAL {{ ?o{i-1} ?p{i} ?o{i} . FILTER(isURI(?o{i-1})) }}")
    
    sparql_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX cco: <https://www.commoncoreontologies.org/>
        CONSTRUCT {{ 
            {' '.join(construct_clauses)}
        }}
        WHERE {{
            {' '.join(where_clauses)}
        }}
    """
    try:
        results = services.triple_store_service.query(sparql_query)
    except Exception as e:
        logger.error(f"Error getting subject graph for {uri}: {e}")
        return Graph()
    
    graph = Graph()
    graph.bind("rdfs", RDFS)
    graph.bind("rdf", RDF)
    graph.bind("owl", OWL)
    graph.bind("xsd", XSD)
    graph.bind("dcterms", DCTERMS)
    graph.bind("abi", ABI)
    graph.bind("bfo", BFO)
    graph.bind("cco", CCO)
    graph.bind("test", TEST)
    for triple in results:
        # CONSTRUCT queries return triples directly, no need for ResultRow handling
        graph.add(triple)
    
    return graph
