# Ontology API

The Ontology API provides interfaces for managing, querying, and updating the ABI knowledge graph. This API enables interaction with the semantic data layer that serves as the foundation for integrating disparate data sources and providing context for AI assistants.

## REST API

### Ontology Stores

#### Create Ontology Store

Creates a new ontology store with the specified configuration.

```
POST /api/v1/ontology/stores
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "name": "sales_knowledge",
  "description": "Sales domain knowledge graph",
  "type": "rdf",
  "configuration": {
    "storage_type": "persistent",
    "reasoning": "rdfs",
    "default_format": "turtle"
  },
  "metadata": {
    "department": "sales",
    "owner": "data-team",
    "version": "1.0"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "ont_123456789",
    "name": "sales_knowledge",
    "description": "Sales domain knowledge graph",
    "type": "rdf",
    "configuration": {
      "storage_type": "persistent",
      "reasoning": "rdfs",
      "default_format": "turtle"
    },
    "metadata": {
      "department": "sales",
      "owner": "data-team",
      "version": "1.0"
    },
    "status": "active",
    "stats": {
      "triples": 0,
      "entities": 0,
      "classes": 0,
      "properties": 0
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-01T12:00:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Get Ontology Store

Returns details of a specific ontology store.

```
GET /api/v1/ontology/stores/{store_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "ont_123456789",
    "name": "sales_knowledge",
    "description": "Sales domain knowledge graph",
    "type": "rdf",
    "configuration": {
      "storage_type": "persistent",
      "reasoning": "rdfs",
      "default_format": "turtle"
    },
    "metadata": {
      "department": "sales",
      "owner": "data-team",
      "version": "1.0"
    },
    "status": "active",
    "stats": {
      "triples": 15687,
      "entities": 3245,
      "classes": 28,
      "properties": 45,
      "disk_usage_mb": 8.4,
      "last_modified": "2023-05-10T15:30:22Z"
    },
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-10T15:30:22Z",
    "created_by": "usr_987654321"
  }
}
```

#### List Ontology Stores

Returns a list of ontology stores with pagination.

```
GET /api/v1/ontology/stores
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
page=1
page_size=10
sort_by=created_at
sort_order=desc
status=active
department=sales
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "ont_123456789",
        "name": "sales_knowledge",
        "description": "Sales domain knowledge graph",
        "type": "rdf",
        "status": "active",
        "metadata": {
          "department": "sales",
          "owner": "data-team",
          "version": "1.0"
        },
        "stats": {
          "triples": 15687,
          "entities": 3245
        },
        "created_at": "2023-05-01T12:00:00Z",
        "updated_at": "2023-05-10T15:30:22Z"
      },
      {
        "id": "ont_987654321",
        "name": "product_knowledge",
        "description": "Product domain knowledge graph",
        "type": "rdf",
        "status": "active",
        "metadata": {
          "department": "product",
          "owner": "data-team",
          "version": "1.2"
        },
        "stats": {
          "triples": 25482,
          "entities": 6721
        },
        "created_at": "2023-04-15T10:00:00Z",
        "updated_at": "2023-05-09T11:45:17Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 2,
      "total_pages": 1
    }
  }
}
```

#### Update Ontology Store

Updates an existing ontology store.

```
PUT /api/v1/ontology/stores/{store_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "description": "Comprehensive sales domain knowledge graph",
  "configuration": {
    "reasoning": "owl",
    "default_format": "turtle"
  },
  "metadata": {
    "department": "sales",
    "owner": "data-team",
    "version": "1.1"
  }
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "ont_123456789",
    "name": "sales_knowledge",
    "description": "Comprehensive sales domain knowledge graph",
    "type": "rdf",
    "configuration": {
      "storage_type": "persistent",
      "reasoning": "owl",
      "default_format": "turtle"
    },
    "metadata": {
      "department": "sales",
      "owner": "data-team",
      "version": "1.1"
    },
    "status": "active",
    "created_at": "2023-05-01T12:00:00Z",
    "updated_at": "2023-05-11T09:30:00Z",
    "created_by": "usr_987654321"
  }
}
```

#### Delete Ontology Store

Deletes an ontology store.

```
DELETE /api/v1/ontology/stores/{store_id}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "ont_123456789",
    "deleted": true
  }
}
```

#### Clear Ontology Store

Removes all data from an ontology store but keeps the store itself.

```
POST /api/v1/ontology/stores/{store_id}/clear
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "id": "ont_123456789",
    "cleared": true,
    "stats": {
      "triples_removed": 15687
    },
    "updated_at": "2023-05-11T14:25:00Z"
  }
}
```

### Graph Management

#### Insert RDF Data

Inserts RDF data into an ontology store.

```
POST /api/v1/ontology/stores/{store_id}/insert
```

**Headers:**

```
Authorization: Bearer {access_token}
Content-Type: text/turtle
```

**Request Body:**

```turtle
@prefix ex: <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Company1 rdf:type ex:Company ;
    rdfs:label "Acme Corporation" ;
    ex:industry "Technology" ;
    ex:foundedYear "1985"^^xsd:integer ;
    ex:numberOfEmployees "5000"^^xsd:integer .

ex:Product1 rdf:type ex:Product ;
    rdfs:label "Widget Pro" ;
    ex:manufacturer ex:Company1 ;
    ex:price "99.99"^^xsd:decimal ;
    ex:currency "USD" .
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "store_id": "ont_123456789",
    "triples_added": 12,
    "updated_at": "2023-05-11T15:00:00Z"
  }
}
```

#### Insert RDF Data (JSON Format)

Inserts RDF data in JSON-LD format into an ontology store.

```
POST /api/v1/ontology/stores/{store_id}/insert
```

**Headers:**

```
Authorization: Bearer {access_token}
Content-Type: application/ld+json
```

**Request Body:**

```json
{
  "@context": {
    "ex": "http://example.org/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#"
  },
  "@graph": [
    {
      "@id": "ex:Company1",
      "@type": "ex:Company",
      "rdfs:label": "Acme Corporation",
      "ex:industry": "Technology",
      "ex:foundedYear": {
        "@value": "1985",
        "@type": "xsd:integer"
      },
      "ex:numberOfEmployees": {
        "@value": "5000",
        "@type": "xsd:integer"
      }
    },
    {
      "@id": "ex:Product1",
      "@type": "ex:Product",
      "rdfs:label": "Widget Pro",
      "ex:manufacturer": {
        "@id": "ex:Company1"
      },
      "ex:price": {
        "@value": "99.99",
        "@type": "xsd:decimal"
      },
      "ex:currency": "USD"
    }
  ]
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "store_id": "ont_123456789",
    "triples_added": 12,
    "updated_at": "2023-05-11T15:05:00Z"
  }
}
```

#### Delete RDF Data

Deletes specific RDF data from an ontology store.

```
POST /api/v1/ontology/stores/{store_id}/delete
```

**Headers:**

```
Authorization: Bearer {access_token}
Content-Type: text/turtle
```

**Request Body:**

```turtle
@prefix ex: <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

ex:Product1 rdf:type ex:Product .
ex:Product1 ?p ?o .
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "store_id": "ont_123456789",
    "triples_removed": 5,
    "updated_at": "2023-05-11T15:10:00Z"
  }
}
```

#### Delete Entity

Deletes all triples related to a specific entity.

```
DELETE /api/v1/ontology/stores/{store_id}/entities/{entity_uri}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "store_id": "ont_123456789",
    "entity_uri": "http://example.org/Product1",
    "triples_removed": 5,
    "updated_at": "2023-05-11T15:15:00Z"
  }
}
```

### Querying

#### SPARQL Query

Executes a SPARQL query against an ontology store.

```
POST /api/v1/ontology/stores/{store_id}/query
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "query": "SELECT ?company ?name ?industry WHERE { ?company a <http://example.org/Company> ; <http://www.w3.org/2000/01/rdf-schema#label> ?name ; <http://example.org/industry> ?industry . }",
  "format": "json"
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "head": {
      "vars": [ "company", "name", "industry" ]
    },
    "results": {
      "bindings": [
        {
          "company": {
            "type": "uri",
            "value": "http://example.org/Company1"
          },
          "name": {
            "type": "literal",
            "value": "Acme Corporation"
          },
          "industry": {
            "type": "literal",
            "value": "Technology"
          }
        },
        {
          "company": {
            "type": "uri",
            "value": "http://example.org/Company2"
          },
          "name": {
            "type": "literal",
            "value": "XYZ Inc"
          },
          "industry": {
            "type": "literal",
            "value": "Manufacturing"
          }
        }
      ]
    }
  }
}
```

#### Graph Export

Exports the entire graph or a subset in the specified format.

```
GET /api/v1/ontology/stores/{store_id}/export
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
format=turtle
```

**Response:**

```
@prefix ex: <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Company1 rdf:type ex:Company ;
    rdfs:label "Acme Corporation" ;
    ex:industry "Technology" ;
    ex:foundedYear "1985"^^xsd:integer ;
    ex:numberOfEmployees "5000"^^xsd:integer .

ex:Product1 rdf:type ex:Product ;
    rdfs:label "Widget Pro" ;
    ex:manufacturer ex:Company1 ;
    ex:price "99.99"^^xsd:decimal ;
    ex:currency "USD" .

# ... more triples ...
```

#### Entity Lookup

Retrieves information about a specific entity.

```
GET /api/v1/ontology/stores/{store_id}/entities/{entity_uri}
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
format=json
include_inferred=true
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "uri": "http://example.org/Company1",
    "types": ["http://example.org/Company"],
    "labels": ["Acme Corporation"],
    "properties": {
      "http://example.org/industry": ["Technology"],
      "http://example.org/foundedYear": [{"value": "1985", "datatype": "http://www.w3.org/2001/XMLSchema#integer"}],
      "http://example.org/numberOfEmployees": [{"value": "5000", "datatype": "http://www.w3.org/2001/XMLSchema#integer"}]
    },
    "outgoing_relations": {
      "http://example.org/hasProduct": ["http://example.org/Product1", "http://example.org/Product2"]
    },
    "incoming_relations": {
      "http://example.org/manufacturer": ["http://example.org/Product1", "http://example.org/Product2"]
    }
  }
}
```

### Schema Management

#### Get Ontology Schema

Retrieves the schema (classes and properties) defined in the ontology.

```
GET /api/v1/ontology/stores/{store_id}/schema
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

```
format=json
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "classes": [
      {
        "uri": "http://example.org/Company",
        "label": "Company",
        "description": "An organization engaged in commercial, industrial, or professional activities",
        "properties": [
          "http://example.org/industry",
          "http://example.org/foundedYear",
          "http://example.org/numberOfEmployees",
          "http://example.org/hasProduct"
        ],
        "subClassOf": []
      },
      {
        "uri": "http://example.org/Product",
        "label": "Product",
        "description": "A good manufactured or refined for sale",
        "properties": [
          "http://example.org/manufacturer",
          "http://example.org/price",
          "http://example.org/currency"
        ],
        "subClassOf": []
      }
    ],
    "properties": [
      {
        "uri": "http://example.org/industry",
        "label": "industry",
        "description": "The industry a company operates in",
        "domain": ["http://example.org/Company"],
        "range": ["http://www.w3.org/2001/XMLSchema#string"]
      },
      {
        "uri": "http://example.org/foundedYear",
        "label": "founded year",
        "description": "The year the company was founded",
        "domain": ["http://example.org/Company"],
        "range": ["http://www.w3.org/2001/XMLSchema#integer"]
      },
      {
        "uri": "http://example.org/manufacturer",
        "label": "manufacturer",
        "description": "The company that manufactures the product",
        "domain": ["http://example.org/Product"],
        "range": ["http://example.org/Company"]
      }
    ]
  }
}
```

#### Upload Schema

Uploads a new schema definition to the ontology store.

```
POST /api/v1/ontology/stores/{store_id}/schema
```

**Headers:**

```
Authorization: Bearer {access_token}
Content-Type: text/turtle
```

**Request Body:**

```turtle
@prefix ex: <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:Company rdf:type owl:Class ;
    rdfs:label "Company" ;
    rdfs:comment "An organization engaged in commercial, industrial, or professional activities" .

ex:Product rdf:type owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A good manufactured or refined for sale" .

ex:industry rdf:type owl:DatatypeProperty ;
    rdfs:label "industry" ;
    rdfs:comment "The industry a company operates in" ;
    rdfs:domain ex:Company ;
    rdfs:range xsd:string .

ex:foundedYear rdf:type owl:DatatypeProperty ;
    rdfs:label "founded year" ;
    rdfs:comment "The year the company was founded" ;
    rdfs:domain ex:Company ;
    rdfs:range xsd:integer .

ex:manufacturer rdf:type owl:ObjectProperty ;
    rdfs:label "manufacturer" ;
    rdfs:comment "The company that manufactures the product" ;
    rdfs:domain ex:Product ;
    rdfs:range ex:Company .
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "store_id": "ont_123456789",
    "triples_added": 25,
    "classes_added": 2,
    "properties_added": 3,
    "updated_at": "2023-05-11T16:00:00Z"
  }
}
```

### Natural Language Interface

#### Natural Language Query

Executes a natural language query against an ontology store.

```
POST /api/v1/ontology/stores/{store_id}/nl-query
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "query": "Show me all technology companies with more than 1000 employees",
  "format": "json",
  "limit": 10
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "query_interpretation": {
      "sparql": "SELECT ?company ?name ?employees WHERE { ?company a <http://example.org/Company> ; <http://www.w3.org/2000/01/rdf-schema#label> ?name ; <http://example.org/industry> 'Technology' ; <http://example.org/numberOfEmployees> ?employees . FILTER (?employees > 1000) } LIMIT 10",
      "confidence": 0.92
    },
    "results": [
      {
        "company": "http://example.org/Company1",
        "name": "Acme Corporation",
        "employees": 5000
      },
      {
        "company": "http://example.org/Company3",
        "name": "TechGiant Inc",
        "employees": 12000
      }
    ],
    "metadata": {
      "count": 2,
      "limit": 10,
      "execution_time_ms": 45
    }
  }
}
```

#### Relationship Exploration

Finds paths or relationships between entities.

```
POST /api/v1/ontology/stores/{store_id}/explore
```

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "source": "http://example.org/Company1",
  "target": "http://example.org/Person5",
  "max_path_length": 3,
  "include_metadata": true
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "paths": [
      {
        "length": 2,
        "path": [
          {
            "entity": "http://example.org/Company1",
            "label": "Acme Corporation",
            "types": ["http://example.org/Company"]
          },
          {
            "relation": "http://example.org/employs",
            "label": "employs"
          },
          {
            "entity": "http://example.org/Person5",
            "label": "Jane Smith",
            "types": ["http://example.org/Person"]
          }
        ]
      },
      {
        "length": 3,
        "path": [
          {
            "entity": "http://example.org/Company1",
            "label": "Acme Corporation",
            "types": ["http://example.org/Company"]
          },
          {
            "relation": "http://example.org/manufactures",
            "label": "manufactures"
          },
          {
            "entity": "http://example.org/Product2",
            "label": "Gadget X",
            "types": ["http://example.org/Product"]
          },
          {
            "relation": "http://example.org/designedBy",
            "label": "designed by"
          },
          {
            "entity": "http://example.org/Person5",
            "label": "Jane Smith",
            "types": ["http://example.org/Person"]
          }
        ]
      }
    ],
    "metadata": {
      "source_label": "Acme Corporation",
      "target_label": "Jane Smith",
      "paths_found": 2,
      "execution_time_ms": 78
    }
  }
}
```

## Python API

### Ontology Store Management

```python
from abi.ontology import OntologyStoreService

# Initialize the ontology store service
ontology_service = OntologyStoreService()

# Create a new ontology store
store = ontology_service.create_store(
    name="sales_knowledge",
    description="Sales domain knowledge graph",
    configuration={
        "storage_type": "persistent",
        "reasoning": "rdfs",
        "default_format": "turtle"
    },
    metadata={
        "department": "sales",
        "owner": "data-team",
        "version": "1.0"
    }
)

print(f"Created ontology store with ID: {store.id}")

# Get store by ID
store = ontology_service.get_store("ont_123456789")

# List stores
stores = ontology_service.list_stores(
    department="sales",
    page=1,
    page_size=10
)

for s in stores.items:
    print(f"{s.id}: {s.name} - Triples: {s.stats.triples}")

# Update a store
store.description = "Comprehensive sales domain knowledge graph"
store.configuration["reasoning"] = "owl"
store.metadata["version"] = "1.1"

updated_store = ontology_service.update_store(store)

# Clear a store
ontology_service.clear_store("ont_123456789")

# Delete a store
ontology_service.delete_store("ont_123456789")
```

### Working with RDF Data

```python
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS
from rdflib.namespace import XSD
from abi.ontology import OntologyStoreService

# Initialize the ontology store service
ontology_service = OntologyStoreService()

# Create a graph with some data
g = Graph()
ex = Namespace("http://example.org/")

# Define a company
company = URIRef(ex["Company1"])
g.add((company, RDF.type, ex.Company))
g.add((company, RDFS.label, Literal("Acme Corporation")))
g.add((company, ex.industry, Literal("Technology")))
g.add((company, ex.foundedYear, Literal(1985, datatype=XSD.integer)))
g.add((company, ex.numberOfEmployees, Literal(5000, datatype=XSD.integer)))

# Define a product
product = URIRef(ex["Product1"])
g.add((product, RDF.type, ex.Product))
g.add((product, RDFS.label, Literal("Widget Pro")))
g.add((product, ex.manufacturer, company))
g.add((product, ex.price, Literal("99.99", datatype=XSD.decimal)))
g.add((product, ex.currency, Literal("USD")))

# Insert data into a store
ontology_service.insert("ont_123456789", g)

# Delete specific triples
delete_g = Graph()
delete_g.add((product, RDF.type, ex.Product))
ontology_service.delete("ont_123456789", delete_g)

# Delete an entity
ontology_service.delete_entity("ont_123456789", str(product))
```

### Querying

```python
from abi.ontology import OntologyStoreService
from rdflib.plugins.sparql import prepareQuery

# Initialize the ontology store service
ontology_service = OntologyStoreService()

# Simple SPARQL query
query = """
    SELECT ?company ?name ?industry 
    WHERE { 
        ?company a <http://example.org/Company> ; 
                <http://www.w3.org/2000/01/rdf-schema#label> ?name ; 
                <http://example.org/industry> ?industry . 
    }
"""

results = ontology_service.query("ont_123456789", query)

# Process the results
for row in results:
    print(f"Company: {row['name']} - Industry: {row['industry']}")

# Parametrized query
query_template = prepareQuery("""
    SELECT ?company ?name ?employees 
    WHERE { 
        ?company a <http://example.org/Company> ; 
                <http://www.w3.org/2000/01/rdf-schema#label> ?name ; 
                <http://example.org/industry> ?industry ; 
                <http://example.org/numberOfEmployees> ?employees . 
        FILTER (?employees > ?min_employees) 
    }
""")

params = {
    "industry": Literal("Technology"),
    "min_employees": Literal(1000)
}

results = ontology_service.query("ont_123456789", query_template, params)

# Export a graph
full_graph = ontology_service.export("ont_123456789", format="turtle")

# Look up an entity
entity_data = ontology_service.get_entity(
    "ont_123456789", 
    "http://example.org/Company1", 
    include_inferred=True
)

print(f"Entity types: {entity_data['types']}")
print(f"Entity labels: {entity_data['labels']}")
```

### Natural Language Interface

```python
from abi.ontology import OntologyNLInterface

# Initialize the natural language interface
nl_interface = OntologyNLInterface("ont_123456789")

# Execute natural language query
results = nl_interface.query(
    "Show me all technology companies with more than 1000 employees",
    limit=10
)

print(f"SPARQL interpretation: {results.query_interpretation.sparql}")
print(f"Confidence: {results.query_interpretation.confidence}")

for item in results.results:
    print(f"Company: {item['name']} - Employees: {item['employees']}")

# Explore relationships
paths = nl_interface.explore_relationships(
    source="http://example.org/Company1",
    target="http://example.org/Person5",
    max_path_length=3
)

for path in paths.paths:
    print(f"Path length: {path.length}")
    path_str = " -> ".join([node['label'] if 'label' in node else node['relation'] for node in path.path])
    print(f"Path: {path_str}")
```

### Schema Management

```python
from abi.ontology import OntologySchemaManager
from rdflib import Graph, URIRef, Literal, Namespace, BNode, RDF, RDFS, OWL
from rdflib.namespace import XSD

# Initialize the schema manager
schema_manager = OntologySchemaManager("ont_123456789")

# Get the current schema
schema = schema_manager.get_schema()

for cls in schema.classes:
    print(f"Class: {cls.label} ({cls.uri})")
    print(f"  Properties: {', '.join([p for p in cls.properties])}")

for prop in schema.properties:
    print(f"Property: {prop.label} ({prop.uri})")
    print(f"  Domain: {', '.join([d for d in prop.domain])}")
    print(f"  Range: {', '.join([r for r in prop.range])}")

# Create a new schema
g = Graph()
ex = Namespace("http://example.org/")
g.bind("ex", ex)
g.bind("owl", OWL)
g.bind("rdfs", RDFS)
g.bind("xsd", XSD)

# Define classes
g.add((ex.Employee, RDF.type, OWL.Class))
g.add((ex.Employee, RDFS.label, Literal("Employee")))
g.add((ex.Employee, RDFS.comment, Literal("A person employed by a company")))

g.add((ex.Department, RDF.type, OWL.Class))
g.add((ex.Department, RDFS.label, Literal("Department")))
g.add((ex.Department, RDFS.comment, Literal("A division of a company")))

# Define properties
g.add((ex.worksIn, RDF.type, OWL.ObjectProperty))
g.add((ex.worksIn, RDFS.label, Literal("works in")))
g.add((ex.worksIn, RDFS.comment, Literal("The department an employee works in")))
g.add((ex.worksIn, RDFS.domain, ex.Employee))
g.add((ex.worksIn, RDFS.range, ex.Department))

g.add((ex.salary, RDF.type, OWL.DatatypeProperty))
g.add((ex.salary, RDFS.label, Literal("salary")))
g.add((ex.salary, RDFS.comment, Literal("The annual salary of an employee")))
g.add((ex.salary, RDFS.domain, ex.Employee))
g.add((ex.salary, RDFS.range, XSD.decimal))

# Upload the schema
schema_manager.upload_schema(g)
```

## Supported RDF Formats

| Format | Content Type | Description |
|--------|--------------|-------------|
| turtle | text/turtle | Terse RDF Triple Language (TTL) |
| rdf+xml | application/rdf+xml | RDF/XML format |
| n3 | text/n3 | Notation3 (N3) format |
| nt | application/n-triples | N-Triples format |
| json-ld | application/ld+json | JSON-LD format |
| nquads | application/n-quads | N-Quads format |
| trig | application/trig | TriG format |

## Ontology Store Configuration

### Storage Types

| Storage Type | Description |
|--------------|-------------|
| persistent | Data is stored persistently on disk |
| in-memory | Data is stored in memory (faster but lost on restart) |
| hybrid | Combination of in-memory and persistent storage |

### Reasoning Levels

| Reasoning Level | Description |
|-----------------|-------------|
| none | No reasoning/inference (raw triples only) |
| rdfs | Basic RDFS reasoning (subclass, subproperty, domain, range) |
| owl | OWL reasoning (more complex inferences) |
| custom | Custom rule-based reasoning |

## Error Handling

Common errors when working with the Ontology API:

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | INVALID_STORE_CONFIG | Invalid ontology store configuration |
| 400 | INVALID_RDF_DATA | Invalid RDF data format |
| 400 | INVALID_SPARQL_QUERY | Invalid SPARQL query syntax |
| 404 | STORE_NOT_FOUND | Ontology store not found |
| 404 | ENTITY_NOT_FOUND | Entity not found in the ontology store |
| 409 | STORE_ALREADY_EXISTS | A store with this name already exists |
| 422 | VALIDATION_ERROR | Validation error in request parameters |
| 500 | QUERY_EXECUTION_ERROR | Error executing the SPARQL query |
| 500 | REASONING_ERROR | Error during reasoning/inference |

## Best Practices

1. **Ontology Design**:
   - Use standard vocabularies where possible (schema.org, FOAF, Dublin Core)
   - Create clear class hierarchies with meaningful inheritance
   - Ensure properties have well-defined domains and ranges
   - Document classes and properties with labels and comments

2. **Data Management**:
   - Batch inserts for better performance
   - Use appropriate unique identifiers for entities
   - Maintain consistency in data representations
   - Consider denormalization for frequently queried patterns

3. **Query Optimization**:
   - Use specific patterns rather than wildcard queries
   - Limit result size for large data sets
   - Use the appropriate reasoning level for your needs
   - Create indexes for frequently queried patterns

4. **Integration**:
   - Use pipelines to maintain data freshness
   - Consider data validation before insertion
   - Implement data synchronization strategies
   - Use proper error handling for integration points

5. **Performance**:
   - Monitor store size and growth
   - Implement caching for common queries
   - Consider partitioning for very large ontologies
   - Use the appropriate storage type for your use case

## Next Steps

- Explore the [Assistants API](assistants.md) to create interfaces that leverage the ontology
- Learn about [Pipelines API](pipelines.md) to automate data loading into the ontology
- Check the [Workflows API](workflows.md) to create business processes using ontology data 