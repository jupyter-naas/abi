from src import services

ontology_name = "person_ont00001262"
graph = services.triple_store_service.get(ontology_name)

query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?object
WHERE {
  # Find all predicates used in triples
  ?subject ?predicate ?object .
  
  # Only get predicates that are object properties and in URI reference format
  FILTER(isURI(?object))
  
  # Exclude RDF type triples
  FILTER(?predicate != rdf:type)
}
ORDER BY ?object
"""

list_uri = [str(object.get("object")) for object in graph.query(query)]
# Build SPARQL query with FILTER IN clause for specific URIs
uri_filter = "(" + " || ".join([f"?object = <{uri}>" for uri in list_uri]) + ")"
query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?object ?label ?type
WHERE {{
  ?object rdfs:label ?label .
  ?object rdf:type ?type .
  FILTER {uri_filter}
}}
ORDER BY ?object
"""

from rdflib import URIRef, RDFS, Literal, RDF, OWL

results = services.triple_store_service.query(query)
data = []
for row in results:
    data_dict = {}
    for key in row.labels:
        data_dict[key] = str(row[key]) if row[key] else None
    data.append(data_dict)
    graph.add((URIRef(row.get("object")), RDF.type, URIRef(row.get("type"))))
    graph.add((URIRef(row.get("object")), RDF.type, OWL.NamedIndividual))
    graph.add((URIRef(row.get("object")), RDFS.label, Literal(row.get("label"))))

print(data)
