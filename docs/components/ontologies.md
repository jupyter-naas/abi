# Ontologies in ABI

## What are Ontologies?

Ontologies in ABI provide a formal representation of knowledge using semantic web technologies. They define:

- **Classes/Concepts**: Categories of entities (e.g., Person, Organization, Event)
- **Properties**: Relationships between entities or attributes of entities
- **Individuals**: Specific instances of classes
- **Rules/Axioms**: Logical constraints that govern relationships

ABI uses RDF (Resource Description Framework) and OWL (Web Ontology Language) to represent ontologies in a machine-readable format.

## Ontology Organization

Ontologies in ABI are organized in a layered approach:

1. **Foundation or Top-Level Ontologies**: Basic concepts like space, time, and objects (e.g., BFO - Basic Formal Ontology)
2. **Mid-Level Ontologies**: Concepts common across domains (e.g., Common Core Ontologies)
3. **Domain Ontologies**: Concepts specific to particular domains (e.g., Finance, Healthcare)
4. **Application Ontologies**: Concepts specific to applications

The `src/core/modules/common/ontologies/` directory contains the core ontologies used across ABI.

## Creating Module Ontologies

When building a module, you can:

1. **Reuse existing ontologies**: Leverage foundation and mid-level ontologies
2. **Extend with domain concepts**: Add domain-specific classes and properties
3. **Create application ontologies**: Define concepts specific to your module

### File Structure

Ontologies can be placed in your module's directory: 

```
src/custom/modules/your_module_name/
└── ontologies/
├── YourDomainOntology.ttl # Domain-level ontology
└── YourApplicationOntology.ttl # Application-specific ontology
```

### Creating an Ontology File

Ontology files use mostly Turtle (.ttl) format:

```t
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix cco: <https://www.commoncoreontologies.org/> .
@prefix abi: <http://ontology.naas.ai/abi/> .
@prefix your: <http://ontology.naas.ai/your_module/> .
# Ontology metadata
<http://ontology.naas.ai/your_module/YourOntology> rdf:type owl:Ontology ;
owl:imports <https://www.commoncoreontologies.org/RelevantOntology> ;
dc:title "Your Ontology" ;
dc:description "Description of your ontology" .
# Classes
your:YourClass rdf:type owl:Class ;
rdfs:label "Your Class"@en ;
rdfs:subClassOf bfo:BFO_0000001 ; # Choose appropriate parent class
skos:definition "Definition of your class" .
# Object Properties
your:hasRelatedEntity rdf:type owl:ObjectProperty ;
rdfs:label "has related entity"@en ;
rdfs:domain your:YourClass ;
rdfs:range your:RelatedClass ;
skos:definition "Relates your class to a related class" .
# Data Properties
your:hasAttribute rdf:type owl:DatatypeProperty ;
rdfs:label "has attribute"@en ;
rdfs:domain your:YourClass ;
rdfs:range xsd:string ;
skos:definition "An attribute of your class" .
# Individuals
your:exampleIndividual rdf:type your:YourClass ;
rdfs:label "Example Individual"@en ;
your:hasAttribute "Example value" .
```

## Ontology Best Practices

1. **Start with existing ontologies**: Avoid reinventing concepts that already exist
2. **Follow upper ontology principles**: Align with foundation ontologies like BFO
3. **Use consistent naming**: Follow the pattern `ClassNamesInPascalCase` and `propertyNamesInCamelCase`
4. **Add documentation**: Include labels, definitions, and examples
5. **Keep it modular**: Separate domain concepts from application-specific ones
6. **Test with reasoners**: Validate your ontology for consistency
7. **Maintain compatibility**: Ensure backward compatibility when updating

## Using Ontologies in Pipelines

Ontologies are primarily used in pipelines to transform data into semantic triples:

```python
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS
Define namespaces
YOUR = Namespace("http://ontology.naas.ai/your_module/")
def transform_to_rdf(data):
graph = Graph()
# Bind namespaces
graph.bind("your", YOUR)
# Create URIs for entities
entity_uri = URIRef(f"{YOUR}entity/{data['id']}")
# Add class assertions
graph.add((entity_uri, RDF.type, YOUR.YourClass))
# Add property assertions
graph.add((entity_uri, YOUR.hasAttribute, Literal(data["attribute"])))
return graph
```

## Querying Ontologies with SPARQL

SPARQL is used to query the ontology store:

```python
def query_entities(ontology_store, store_name):
sparql_query = """
PREFIX your: <http://ontology.naas.ai/your_module/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?entity ?attribute
WHERE {
?entity rdf:type your:YourClass ;
your:hasAttribute ?attribute .
}
"""
return ontology_store.query(store_name=store_name, query=sparql_query)
```

## Related Resources

- [Integrations](./integrations.md) - Connect to external data sources
- [Pipelines](./pipelines.md) - Transform data into ontology triples
- [Workflows](./workflows.md) - Orchestrate semantic data processing