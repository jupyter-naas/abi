from src import services

ontology_store = services.ontology_store_service

class_uri = "https://www.commoncoreontologies.org/ont00000089"

query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?uri ?label
WHERE {{
  ?uri a <{class_uri}> ;
         rdfs:label ?label .
}}
ORDER BY ?label
"""

results = ontology_store.query(query)
data = []
for row in results:
    data_dict = {}
    for key in row.labels:
        data_dict[key] = str(row[key]) if row[key] else None
    data.append(data_dict)

print(data)