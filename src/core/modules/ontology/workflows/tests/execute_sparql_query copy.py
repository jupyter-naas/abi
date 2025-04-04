from src import services
from abi.utils.SPARQL import results_to_list
triple_store = services.triple_store_service

person_uri = "https://ontology.naas.ai/abi/338c7210-92d5-4bfe-9ebb-334bcc29931c"

# Simplified query to just get the LinkedIn page first
query = f"""
PREFIX abi: <http://ontology.naas.ai/abi/>

SELECT ?linkedin_page
WHERE {{
    <https://ontology.naas.ai/abi/338c7210-92d5-4bfe-9ebb-334bcc29931c> abi:hasLinkedInPage ?linkedin_page .
}}
""" 
search_label = "Jeremy Ravenel"
class_uri = "https://www.commoncoreontologies.org/ont00001262"
query = f"""
SELECT DISTINCT ?class_uri ?individual_uri ?label (MAX(?temp_score) AS ?score)
WHERE {{
    # Filter On Class URI and ensure individual is a NamedIndividual
    ?individual_uri a ?class_uri ;
                    a owl:NamedIndividual ;
                    rdfs:label ?label .
    FILTER(?class_uri = <{class_uri}>)
    
    # Calculate scores for perfect and partial matches
    BIND(IF(LCASE(STR(?label)) = LCASE("{search_label}"), 10, 0) AS ?perfect_score)
    BIND(IF(CONTAINS(LCASE(STR(?label)), LCASE("{search_label}")), 8, 0) AS ?partial_score)
    
    # Use the higher of the two scores
    BIND(IF(?perfect_score > ?partial_score, ?perfect_score, ?partial_score) AS ?temp_score)
    
    # Only include results with a score > 0
    FILTER(?temp_score > 0)
}}
GROUP BY ?class_uri ?individual_uri ?label
ORDER BY DESC(?score) ?label
"""

results = triple_store.query(query)
print(results_to_list(results))