from rdflib import Graph

graph = Graph()
graph.parse("src/core/modules/common/ontologies/ConsolidatedOntology.ttl")

class_uri = "http://purl.obolibrary.org/obo/BFO_0000015"

query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?domain_uri ?range_uri ?data_property_uri ?label ?definition 
WHERE {
  # Find properties with the specified domain
  ?data_property_uri rdfs:domain <%s> .
  ?data_property_uri rdfs:range ?range_uri .
  ?data_property_uri rdfs:domain ?domain_uri .
  
  # Only get ObjectProperties
  ?data_property_uri a owl:DatatypeProperty .
  
  # Get property metadata
  OPTIONAL { ?data_property_uri rdfs:label ?label }
  OPTIONAL { ?data_property_uri skos:definition ?definition }
}
ORDER BY ?label
""" % class_uri

results = graph.query(query)
data = []
for row in results:
    data_dict = {}
    for key in row.labels:
        data_dict[key] = str(row[key]) if row[key] else None
    data.append(data_dict)

print(data)

import json
with open(f"src/core/modules/ontology/tests/workflows/test_GetDataProperties_{class_uri.split('/')[-1]}.json", "w") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)