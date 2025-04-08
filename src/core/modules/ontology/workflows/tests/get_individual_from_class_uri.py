from src import services
from rdflib import URIRef
from abi.utils.SPARQL import results_to_list

def get_individuals(class_uri: str) -> dict:
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?individual ?label
    WHERE {{
        ?individual a <{class_uri}> ;
                    rdfs:label ?label .
    }}
    ORDER BY ?label
    """
    results = services.triple_store_service.query(query)
    return results_to_list(results)

# Example usage
if __name__ == "__main__":
    test_uri = "https://www.commoncoreontologies.org/ont00000443"
    individuals = get_individuals(test_uri)
    print(f"Individuals for {test_uri}: {individuals}")