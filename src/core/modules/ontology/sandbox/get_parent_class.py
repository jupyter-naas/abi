from rdflib import Graph, URIRef, RDFS

graph = Graph()
graph.parse("src/core/modules/ontology/ontologies/top-level/bfo-core.ttl", format="turtle")

class_uri = "http://purl.obolibrary.org/obo/BFO_0000030"

# Get the parent classes of the given class
parent_classes = graph.objects(URIRef(class_uri), RDFS.subClassOf)
for parent_class in parent_classes:
    print(parent_class)