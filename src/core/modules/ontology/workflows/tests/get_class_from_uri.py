from src import services
from rdflib import URIRef
from abi.utils.SPARQL import results_to_list

def get_class_label_from_uri(uri: str) -> tuple[str, str]:
    """
    Get the rdfs:label and class URI for a given URI from the triple store.
    
    Args:
        uri (str): The URI to look up
        
    Returns:
        tuple[str, str]: A tuple containing (label, class_uri) if found, (None, None) otherwise
    """
    triple_store = services.triple_store_service
    id = uri.split("/")[-1]
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX abi: <http://ontology.naas.ai/abi/>

    SELECT ?label ?class
    WHERE {{
        abi:{id} rdf:type ?class .
        ?class rdfs:label ?label .
        FILTER(?class != owl:NamedIndividual)
    }}
    """
    results = triple_store.query(query)
    result_list = results_to_list(results)
    
    return (result_list[0]['label'], result_list[0]['class']) if result_list else (None, None)

# Example usage
if __name__ == "__main__":
    test_uri = "https://ontology.naas.ai/abi/3458ae32-bdf1-42d6-b307-8945b53356de"
    label, class_uri = get_class_label_from_uri(test_uri)
    print(f"Label for {test_uri}: {label}, Class URI: {class_uri}")