from src import services
from abi import logger

# Transform SPARQL results to list of dictionaries using the labels as keys
def results_to_list(results: list[dict]) -> list[dict]:
    data = []
    for row in results:
        logger.debug(f"==> Row: {row}")
        data_dict = {}
        for key in row.labels:
            data_dict[key] = str(row[key]) if row[key] else None
        data.append(data_dict)
    return data

# Get the class URI for a given URI from the triple store
def get_class_uri_from_individual_uri(uri: str) -> str:
    """
    Get the class URI for a given URI from the triple store.
    
    Args:
        uri (str): The URI to look up
        
    Returns:
        str: The class URI if found, None otherwise
    """
    if not str(uri).startswith("http://ontology.naas.ai/abi/"):
        return None
        
    # Use the full URI in the query instead of trying to extract the ID
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT ?class
    WHERE {{
        <{uri}> rdf:type ?class .
        FILTER(?class != owl:NamedIndividual)
    }}
    """
    try:    
        results = services.triple_store_service.query(query)
        result_list = results_to_list(results)
        logger.debug(f"==> Result List: {result_list}")
        class_uri = result_list[0]['class'] if result_list else None
        return class_uri
    except Exception as e:
        logger.error(f"Error getting class URI from individual URI {uri}: {e}")
        return None