from src import services
from rdflib import URIRef
from abi.utils.SPARQL import results_to_list

triple_store = services.triple_store_service

# Example URI to look up
id = "46e9ab9c-19c5-445c-b962-3f6f3d576d21"

# Query to get rdfs:label from any URI
query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX abi: <http://ontology.naas.ai/abi/>

SELECT ?label
WHERE {{
    abi:{id} rdfs:label ?label .
}}
"""
results = triple_store.query(query)
print("Result 1:")
print(results_to_list(results))

# Example URI to look up
uri = "https://ontology.naas.ai/abi/46e9ab9c-19c5-445c-b962-3f6f3d576d21"

# Query to get rdfs:label from any URI
query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label
WHERE {{
    <{str(uri)}> rdfs:label ?label .
}}
"""
results = triple_store.query(query)
print("Result 2:")
print(results_to_list(results))
