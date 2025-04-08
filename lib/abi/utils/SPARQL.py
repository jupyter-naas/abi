from src import services

# Transform SPARQL results to list of dictionaries using the labels as keys
def results_to_list(results: list[dict]) -> list[dict]:
    data = []
    for row in results:
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
    id = uri.split("/")[-1]
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX abi: <http://ontology.naas.ai/abi/>

    SELECT ?class
    WHERE {{
        abi:{id} rdf:type ?class .
        FILTER(?class != owl:NamedIndividual)
    }}
    """
    results = services.triple_store_service.query(query)
    result_list = results_to_list(results)
    
    return result_list[0]['class'] if result_list else None