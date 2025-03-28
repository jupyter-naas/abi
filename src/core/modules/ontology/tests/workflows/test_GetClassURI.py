from rdflib import Graph

graph = Graph()
graph.parse("src/core/modules/common/ontologies/ConsolidatedOntology.ttl")

searchLabel = "Person"

query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

# This query finds a class URI based on its label
# If the label doesn't match exactly, it finds the nearest result
# by checking rdfs:label, skos:definition, skos:example, or skos:comment

# Input parameter: ?searchLabel - the label text to search for

SELECT DISTINCT ?class ?label ?score ?definition ?example ?comment
WHERE {
  # Find all classes in the ontology
  {
    ?class a owl:Class .
  } UNION {
    ?class a rdfs:Class .
  }
  
  # Create a score for each class based on matching properties
  {
    # Exact match with rdfs:label gets highest score (10)
    ?class rdfs:label ?label .
    FILTER(LCASE(STR(?label)) = LCASE(?searchLabel))
    BIND(10 AS ?score)
  } UNION {
    # Contains match with rdfs:label gets good score (8)
    ?class rdfs:label ?label .
    FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
    BIND(8 AS ?score)
  } UNION {
    # Exact match with skos:definition gets medium score (6)
    ?class skos:definition ?label .
    FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
    BIND(6 AS ?score)
  } UNION {
    # Contains match with skos:example gets lower score (4)
    ?class skos:example ?label .
    FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
    BIND(4 AS ?score)
  } UNION {
    # Contains match with skos:comment gets lowest score (2)
    ?class skos:comment ?label .
    FILTER(CONTAINS(LCASE(STR(?label)), LCASE(?searchLabel)))
    BIND(2 AS ?score)
  }
  
  # Get additional properties if they exist
  OPTIONAL { ?class skos:definition ?definition }
  OPTIONAL { ?class skos:example ?example }
  OPTIONAL { ?class skos:comment ?comment }
}
ORDER BY DESC(?score)
LIMIT 10
"""

results = graph.query(query.replace("?searchLabel", f'"{searchLabel}"'))
data = []
for row in results:
    data_dict = {}
    for key in row.labels:
        data_dict[key] = str(row[key]) if row[key] else None
    data.append(data_dict)

print(data)
import json
with open(f"src/core/modules/ontology/tests/workflows/test_GetClassURI_{searchLabel}.json", "w") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)