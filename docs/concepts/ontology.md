# Ontology

This document explains the concept of Ontology in the ABI framework, its purpose, implementation, and how it serves as the central knowledge representation system.

## What is the Ontology?

The Ontology in ABI is a formal representation of knowledge as a set of concepts and relationships within a domain. It provides a shared vocabulary and semantic model that allows the system to understand, integrate, and reason about business data from different sources.

## Key Features

- **Semantic Representation**: Represents business entities and relationships in a machine-readable format
- **Knowledge Integration**: Unifies data from multiple sources into a coherent knowledge graph
- **Reasoning Support**: Enables logical inference over the integrated data
- **Query Capability**: Supports complex queries across different domains
- **Extensibility**: Can be extended to cover new domains and concepts
- **Schema Validation**: Ensures data consistency and integrity

## Ontology Architecture

```
┌───────────────────────────────────────────────────────────┐
│                      Ontology System                      │
│                                                           │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │  Ontology     │    │  Triple       │    │  SPARQL   │  │
│  │  Schema       │───►│  Store        │◄───┤  Endpoint │  │
│  │               │    │               │    │           │  │
│  └───────────────┘    └───────────────┘    └───────────┘  │
│                              ▲                  ▲         │
│                              │                  │         │
│                       ┌───────────────┐         │         │
│                       │  Graph        │         │         │
│                       │  Update API   │◄────────┘         │
│                       │               │                   │
│                       └───────────────┘                   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Ontology Components

### Ontology Schema

The schema defines the classes, properties, and relationships that make up the ontology:

```turtle
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix abi: <http://example.org/abi/ontology#> .

# Class definitions
abi:Company a rdfs:Class ;
    rdfs:label "Company" ;
    rdfs:comment "A business organization" .

abi:Person a rdfs:Class ;
    rdfs:label "Person" ;
    rdfs:comment "An individual person" .

abi:Product a rdfs:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A product offered by a company" .

abi:Sale a rdfs:Class ;
    rdfs:label "Sale" ;
    rdfs:comment "A sales transaction" .

# Property definitions
abi:name a rdf:Property ;
    rdfs:label "name" ;
    rdfs:comment "The name of an entity" ;
    rdfs:domain rdfs:Resource ;
    rdfs:range xsd:string .

abi:hasEmployee a rdf:Property ;
    rdfs:label "has employee" ;
    rdfs:comment "Relates a company to its employees" ;
    rdfs:domain abi:Company ;
    rdfs:range abi:Person .

abi:worksFor a rdf:Property ;
    rdfs:label "works for" ;
    rdfs:comment "Relates a person to their employer" ;
    rdfs:domain abi:Person ;
    rdfs:range abi:Company .

abi:manufactures a rdf:Property ;
    rdfs:label "manufactures" ;
    rdfs:comment "Relates a company to products it manufactures" ;
    rdfs:domain abi:Company ;
    rdfs:range abi:Product .

abi:soldBy a rdf:Property ;
    rdfs:label "sold by" ;
    rdfs:comment "Relates a sale to the company that made it" ;
    rdfs:domain abi:Sale ;
    rdfs:range abi:Company .

abi:includes a rdf:Property ;
    rdfs:label "includes" ;
    rdfs:comment "Relates a sale to products sold" ;
    rdfs:domain abi:Sale ;
    rdfs:range abi:Product .

abi:amount a rdf:Property ;
    rdfs:label "amount" ;
    rdfs:comment "The monetary amount of a sale" ;
    rdfs:domain abi:Sale ;
    rdfs:range xsd:decimal .

abi:date a rdf:Property ;
    rdfs:label "date" ;
    rdfs:comment "The date of a sale" ;
    rdfs:domain abi:Sale ;
    rdfs:range xsd:date .
```

### Ontology Store

The ontology store is responsible for storing and retrieving semantic data:

```python
class OntologyStoreService(IOntologyStoreService):
    """Service for managing ontology stores."""
    
    def __init__(self, config: OntologyStoreConfiguration):
        self.__config = config
        self.__stores = {}
        
    def create_store(self, name: str) -> bool:
        """Create a new ontology store.
        
        Args:
            name: Name of the store to create
            
        Returns:
            True if successful, False otherwise
        """
        if name in self.__stores:
            return False
        
        self.__stores[name] = Graph()
        return True
    
    def insert(self, store_name: str, graph: Graph) -> bool:
        """Insert triples into an ontology store.
        
        Args:
            store_name: Name of the store to insert into
            graph: Graph containing triples to insert
            
        Returns:
            True if successful, False otherwise
        """
        if store_name not in self.__stores:
            self.create_store(store_name)
        
        self.__stores[store_name] += graph
        return True
    
    def query(self, store_name: str, query: str) -> List[Dict[str, Any]]:
        """Query an ontology store.
        
        Args:
            store_name: Name of the store to query
            query: SPARQL query string
            
        Returns:
            List of query results as dictionaries
        """
        if store_name not in self.__stores:
            return []
        
        results = self.__stores[store_name].query(query)
        return [
            {str(var): str(value) for var, value in result.items()}
            for result in results
        ]
```

## Graph Building

Creating and manipulating semantic graphs:

```python
# Creating a graph
graph = ABIGraph()

# Adding entities
company_uri = graph.create_entity(
    "Company",
    {
        "name": "Acme Corp",
        "founded": "1985-06-15",
        "industry": "Technology"
    }
)

person_uri = graph.create_entity(
    "Person",
    {
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "role": "CEO"
    }
)

product_uri = graph.create_entity(
    "Product",
    {
        "name": "Widget Pro",
        "sku": "WP-1234",
        "price": "99.99"
    }
)

# Adding relationships
graph.create_relationship(
    company_uri,
    "hasEmployee",
    person_uri
)

graph.create_relationship(
    person_uri,
    "worksFor",
    company_uri
)

graph.create_relationship(
    company_uri,
    "manufactures",
    product_uri
)
```

## SPARQL Queries

Querying the ontology with SPARQL:

```python
# Query all technology companies and their employees
sparql_query = """
    PREFIX abi: <http://example.org/abi/ontology#>
    
    SELECT ?company_name ?person_name ?role
    WHERE {
        ?company a abi:Company ;
                 abi:name ?company_name ;
                 abi:industry "Technology" ;
                 abi:hasEmployee ?person .
        
        ?person a abi:Person ;
                abi:name ?person_name ;
                abi:role ?role .
    }
    ORDER BY ?company_name ?role
"""

results = ontology_store.query("business_data", sparql_query)

# Output results
for result in results:
    print(f"Company: {result['company_name']}")
    print(f"  Employee: {result['person_name']}")
    print(f"  Role: {result['role']}")
```

## Ontology Extensions

The core ontology can be extended with domain-specific concepts:

```turtle
# Marketing domain extension
@prefix mkt: <http://example.org/abi/marketing#> .

mkt:Campaign a rdfs:Class ;
    rdfs:label "Marketing Campaign" ;
    rdfs:comment "A marketing campaign" .

mkt:Audience a rdfs:Class ;
    rdfs:label "Audience" ;
    rdfs:comment "A target audience for marketing" .

mkt:Channel a rdfs:Class ;
    rdfs:label "Channel" ;
    rdfs:comment "A marketing channel" .

mkt:targets a rdf:Property ;
    rdfs:label "targets" ;
    rdfs:comment "Relates a campaign to its target audience" ;
    rdfs:domain mkt:Campaign ;
    rdfs:range mkt:Audience .

mkt:uses a rdf:Property ;
    rdfs:label "uses" ;
    rdfs:comment "Relates a campaign to channels it uses" ;
    rdfs:domain mkt:Campaign ;
    rdfs:range mkt:Channel .
```

## Using the Ontology in ABI

The ontology is used throughout the ABI system:

1. **Pipelines** populate the ontology with data from external systems
2. **Workflows** query and update the ontology as part of business processes
3. **Assistants** use the ontology to answer user queries and provide insights

Example of a workflow using the ontology:

```python
def analyze_sales_trends(self, region: str, period: str) -> Dict:
    """Analyze sales trends for a region and time period.
    
    Args:
        region: The region to analyze
        period: The time period to analyze
        
    Returns:
        Dictionary with sales trend analysis
    """
    # Determine date range
    start_date, end_date = self._calculate_date_range(period)
    
    # Query the ontology for sales data
    sparql_query = f"""
        PREFIX abi: <http://example.org/abi/ontology#>
        
        SELECT ?product_name (SUM(?amount) as ?total_sales) ?date
        WHERE {{
            ?sale a abi:Sale ;
                  abi:region "{region}" ;
                  abi:amount ?amount ;
                  abi:date ?date ;
                  abi:includes ?product .
            
            ?product a abi:Product ;
                    abi:name ?product_name .
            
            FILTER(?date >= "{start_date}"^^xsd:date && ?date <= "{end_date}"^^xsd:date)
        }}
        GROUP BY ?product_name ?date
        ORDER BY ?date ?product_name
    """
    
    results = self.__configuration.ontology_store.query(
        "sales_ontology", 
        sparql_query
    )
    
    # Process and analyze the results
    # ...
    
    return analysis
```

## Next Steps

- Learn about [Managing Ontologies](../guides/managing-ontologies.md)
- Understand how [Pipelines](pipelines.md) populate the ontology
- Explore how [Assistants](assistants.md) use the ontology to answer queries 