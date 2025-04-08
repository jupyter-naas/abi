from src import services
from rdflib import URIRef
from abi.utils.SPARQL import results_to_list

def get_spo_from_class_uri(class_uri: str) -> dict:
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT DISTINCT ?subject ?predicate ?object
    WHERE {{
        ?subject a <{class_uri}> .
        ?subject ?predicate ?object .
    }}
    ORDER BY ?subject ?predicate
    """
    results = services.triple_store_service.query(query)
    return results_to_list(results)

# Example usage
if __name__ == "__main__":
    test_uri = "https://www.commoncoreontologies.org/ont00000443"
    triples = get_spo_from_class_uri(test_uri)
    print(f"SPO triples for class {test_uri}: {triples}")