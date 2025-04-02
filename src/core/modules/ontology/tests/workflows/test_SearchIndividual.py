from src import services

triple_store = services.triple_store_service

class_uri = "https://www.commoncoreontologies.org/ont00000089"

query = f"""
SELECT DISTINCT ?class_uri ?individual_uri ?label
WHERE {{
  # Filter On Class URI and ensure individual is a NamedIndividual
  ?individual_uri a ?class_uri ;            
                 a owl:NamedIndividual ;
                 rdfs:label ?label .
  FILTER(?class_uri = <{class_uri}>)
}}
ORDER BY DESC(?label)
"""

individual_label = "Onto"

query = f"""
SELECT DISTINCT ?class_uri ?individual_uri ?label ?score
WHERE {{
    # Filter On Class URI and ensure individual is a NamedIndividual
    ?individual_uri a ?class_uri ;            
                    a owl:NamedIndividual ;
                    rdfs:label ?label .
    FILTER(?class_uri = <{class_uri}>)

    # Calculate score based on label matching
    {{
        # If perfect match, score is 10
        FILTER(LCASE(STR(?label)) = LCASE("{individual_label}"))
        BIND(10 AS ?score)
    }}
    UNION
    {{
        # If partial match, score is 9
        FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{individual_label}")))
        BIND(9 AS ?score)
    }}
}}
ORDER BY DESC(?score) ?label
"""

query = f"""
SELECT DISTINCT ?class_uri ?individual_uri ?label (MAX(?temp_score) AS ?score)
WHERE {{
    # Filter On Class URI and ensure individual is a NamedIndividual
    ?individual_uri a ?class_uri ;
                    a owl:NamedIndividual ;
                    rdfs:label ?label .
    FILTER(?class_uri = <{class_uri}>)
    
    # Calculate scores for perfect and partial matches
    BIND(IF(LCASE(STR(?label)) = LCASE("{individual_label}"), 10, 0) AS ?perfect_score)
    BIND(IF(CONTAINS(LCASE(STR(?label)), LCASE("{individual_label}")), 8, 0) AS ?partial_score)
    
    # Use the higher of the two scores
    BIND(IF(?perfect_score > ?partial_score, ?perfect_score, ?partial_score) AS ?temp_score)
    
    # Only include results with a score > 0
    FILTER(?temp_score > 0)
}}
GROUP BY ?class_uri ?individual_uri ?label
ORDER BY DESC(?score) ?label
"""

results = triple_store.query(query)
data = []
for row in results:
    data_dict = {}
    for key in row.labels:
        data_dict[key] = str(row[key]) if row[key] else None
    data.append(data_dict)

print(data)