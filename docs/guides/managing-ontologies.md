# Managing Ontologies

This guide explains how to manage ontologies in the ABI framework - creating, extending, querying, and maintaining the knowledge representation system that forms the semantic foundation of your application.

## Prerequisites

Before working with ontologies, you should have:

- A working ABI installation
- Understanding of the [ABI architecture](../concepts/architecture.md)
- Familiarity with the [ontology concept](../concepts/ontology.md)
- Basic knowledge of RDF, RDFS, and SPARQL
- Experience with [pipelines](../concepts/pipelines.md) that populate the ontology

## Ontology Management Overview

The ABI ontology system consists of these key components:

1. **Ontology Schema**: Defines the structure, classes, and relationships
2. **Ontology Store**: Persists and manages ontology data
3. **Query Interface**: Enables retrieving information from the ontology
4. **Graph Builder**: Helps construct semantic graphs programmatically

## Steps to Manage Ontologies

### 1. Define Ontology Schema

Start by defining your ontology schema in Turtle format:

```turtle
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix abi: <http://example.org/abi#> .

# Classes
abi:Organization a rdfs:Class ;
    rdfs:label "Organization" ;
    rdfs:comment "An organization such as a company, NGO, institution, etc." .

abi:Person a rdfs:Class ;
    rdfs:label "Person" ;
    rdfs:comment "An individual person." .

abi:Document a rdfs:Class ;
    rdfs:label "Document" ;
    rdfs:comment "A document or file of any type." .

abi:Project a rdfs:Class ;
    rdfs:label "Project" ;
    rdfs:comment "A business project with defined scope and timeline." .

# Properties
abi:name a rdf:Property ;
    rdfs:label "name" ;
    rdfs:comment "The name of an entity" ;
    rdfs:domain owl:Thing ;
    rdfs:range xsd:string .

abi:description a rdf:Property ;
    rdfs:label "description" ;
    rdfs:comment "A description of an entity" ;
    rdfs:domain owl:Thing ;
    rdfs:range xsd:string .

abi:startDate a rdf:Property ;
    rdfs:label "start date" ;
    rdfs:comment "The start date of an entity" ;
    rdfs:domain abi:Project ;
    rdfs:range xsd:dateTime .

abi:endDate a rdf:Property ;
    rdfs:label "end date" ;
    rdfs:comment "The end date of an entity" ;
    rdfs:domain abi:Project ;
    rdfs:range xsd:dateTime .

# Relationship properties
abi:hasEmployee a rdf:Property ;
    rdfs:label "has employee" ;
    rdfs:comment "Relates an organization to its employees" ;
    rdfs:domain abi:Organization ;
    rdfs:range abi:Person .

abi:worksFor a rdf:Property ;
    rdfs:label "works for" ;
    rdfs:comment "Relates a person to their employer organization" ;
    rdfs:domain abi:Person ;
    rdfs:range abi:Organization ;
    owl:inverseOf abi:hasEmployee .

abi:manages a rdf:Property ;
    rdfs:label "manages" ;
    rdfs:comment "Relates a person to a project they manage" ;
    rdfs:domain abi:Person ;
    rdfs:range abi:Project .

abi:worksOn a rdf:Property ;
    rdfs:label "works on" ;
    rdfs:comment "Relates a person to a project they work on" ;
    rdfs:domain abi:Person ;
    rdfs:range abi:Project .

abi:partOf a rdf:Property ;
    rdfs:label "part of" ;
    rdfs:comment "Relates a project to an organization" ;
    rdfs:domain abi:Project ;
    rdfs:range abi:Organization .

abi:author a rdf:Property ;
    rdfs:label "author" ;
    rdfs:comment "Relates a document to its author" ;
    rdfs:domain abi:Document ;
    rdfs:range abi:Person .

abi:relatedTo a rdf:Property ;
    rdfs:label "related to" ;
    rdfs:comment "Relates a document to a project" ;
    rdfs:domain abi:Document ;
    rdfs:range abi:Project .
```

### 2. Create an Ontology Store

Use the `OntologyStoreService` to create and manage ontology stores:

```python
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from rdflib import Graph

def create_ontology_store():
    """Create and initialize an ontology store."""
    
    # Initialize the ontology store service
    ontology_store = OntologyStoreService()
    
    # Create a new store
    store_name = "business_ontology"
    ontology_store.create_store(store_name)
    
    # Load the schema into the store
    schema_path = "path/to/schema.ttl"
    schema_graph = Graph()
    schema_graph.parse(schema_path, format="turtle")
    
    # Insert the schema into the store
    ontology_store.insert(store_name, schema_graph)
    
    print(f"Created ontology store '{store_name}' and loaded schema")
    
    return ontology_store, store_name
```

### 3. Build and Populate Graphs

Use the `ABIGraph` utility to build semantic graphs programmatically:

```python
from abi.utils.Graph import ABIGraph
from datetime import datetime

def populate_sample_data(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Populate the ontology store with sample data."""
    
    # Create a new graph
    graph = ABIGraph()
    
    # Create Organization entity
    acme_uri = graph.create_entity(
        "Organization", 
        {
            "id": "org-001",
            "name": "Acme Corporation",
            "description": "A leading technology company"
        }
    )
    
    # Create Person entities
    john_uri = graph.create_entity(
        "Person", 
        {
            "id": "person-001",
            "name": "John Smith",
            "email": "john.smith@acme.com",
            "title": "Software Engineer"
        }
    )
    
    jane_uri = graph.create_entity(
        "Person", 
        {
            "id": "person-002",
            "name": "Jane Doe",
            "email": "jane.doe@acme.com",
            "title": "Project Manager"
        }
    )
    
    # Create Project entity
    project_uri = graph.create_entity(
        "Project", 
        {
            "id": "project-001",
            "name": "Knowledge Graph Implementation",
            "description": "Implementing a company-wide knowledge graph",
            "startDate": datetime(2023, 1, 15).isoformat(),
            "endDate": datetime(2023, 6, 30).isoformat()
        }
    )
    
    # Create Document entity
    doc_uri = graph.create_entity(
        "Document", 
        {
            "id": "doc-001",
            "name": "Project Specification",
            "description": "Detailed specifications for the knowledge graph project",
            "createdDate": datetime(2023, 1, 20).isoformat(),
            "format": "PDF"
        }
    )
    
    # Create relationships
    graph.create_relationship(john_uri, "worksFor", acme_uri)
    graph.create_relationship(jane_uri, "worksFor", acme_uri)
    graph.create_relationship(jane_uri, "manages", project_uri)
    graph.create_relationship(john_uri, "worksOn", project_uri)
    graph.create_relationship(project_uri, "partOf", acme_uri)
    graph.create_relationship(jane_uri, "author", doc_uri)
    graph.create_relationship(doc_uri, "relatedTo", project_uri)
    
    # Insert the graph into the ontology store
    ontology_store.insert(store_name, graph.get_graph())
    
    print(f"Populated '{store_name}' with sample data")
```

### 4. Query the Ontology

Use SPARQL to query the ontology:

```python
def query_ontology(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Run various queries against the ontology."""
    
    print("Running sample queries:")
    
    # Find all organizations
    print("\n1. All organizations:")
    orgs_query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?org ?name
        WHERE {
            ?org a abi:Organization ;
                 abi:name ?name .
        }
    """
    results = ontology_store.query(store_name, orgs_query)
    for result in results:
        print(f"  - {result['name']} ({result['org']})")
    
    # Find projects and their managers
    print("\n2. Projects and their managers:")
    projects_query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?project_name ?manager_name
        WHERE {
            ?project a abi:Project ;
                    abi:name ?project_name .
            ?manager abi:manages ?project ;
                    abi:name ?manager_name .
        }
    """
    results = ontology_store.query(store_name, projects_query)
    for result in results:
        print(f"  - Project: {result['project_name']}, Manager: {result['manager_name']}")
    
    # Find documents related to projects
    print("\n3. Documents and related projects:")
    docs_query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?doc_name ?project_name ?author_name
        WHERE {
            ?doc a abi:Document ;
                abi:name ?doc_name ;
                abi:relatedTo ?project .
            ?project abi:name ?project_name .
            ?author abi:author ?doc ;
                  abi:name ?author_name .
        }
    """
    results = ontology_store.query(store_name, docs_query)
    for result in results:
        print(f"  - Document: {result['doc_name']}")
        print(f"    Project: {result['project_name']}")
        print(f"    Author: {result['author_name']}")
```

### 5. Update Ontology Data

Update existing data in the ontology:

```python
def update_ontology_data(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Update data in the ontology."""
    
    # Update using a SPARQL UPDATE query
    update_query = """
        PREFIX abi: <http://example.org/abi#>
        
        DELETE {
            ?project abi:endDate ?old_date .
        }
        INSERT {
            ?project abi:endDate "2023-08-15T00:00:00" .
            ?project abi:status "Extended" .
        }
        WHERE {
            ?project a abi:Project ;
                    abi:name "Knowledge Graph Implementation" ;
                    abi:endDate ?old_date .
        }
    """
    
    ontology_store.update(store_name, update_query)
    print("Updated project end date and added status")
    
    # Alternatively, update using graph operations
    graph = ABIGraph()
    
    # Find the entity to update
    query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?project
        WHERE {
            ?project a abi:Project ;
                    abi:name "Knowledge Graph Implementation" .
        }
    """
    results = ontology_store.query(store_name, query)
    
    if results:
        project_uri = results[0]['project']
        
        # Update properties
        graph.add_property(project_uri, "budget", "150000")
        graph.add_property(project_uri, "priority", "High")
        
        # Insert the update
        ontology_store.insert(store_name, graph.get_graph())
        print("Added budget and priority to project")
```

### 6. Extend the Ontology Schema

Extend the existing ontology schema with new classes and properties:

```python
def extend_ontology_schema(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Extend the ontology schema with new classes and properties."""
    
    # Create a new graph for the extension
    extension_ttl = """
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix abi: <http://example.org/abi#> .

        # New Classes
        abi:Task a rdfs:Class ;
            rdfs:label "Task" ;
            rdfs:comment "A specific task within a project." .

        abi:Skill a rdfs:Class ;
            rdfs:label "Skill" ;
            rdfs:comment "A professional skill or competency." .

        # New Properties
        abi:priority a rdf:Property ;
            rdfs:label "priority" ;
            rdfs:comment "The priority level of an entity" ;
            rdfs:domain owl:Thing ;
            rdfs:range xsd:string .

        abi:dueDate a rdf:Property ;
            rdfs:label "due date" ;
            rdfs:comment "The due date of a task" ;
            rdfs:domain abi:Task ;
            rdfs:range xsd:dateTime .

        abi:status a rdf:Property ;
            rdfs:label "status" ;
            rdfs:comment "The current status of an entity" ;
            rdfs:domain owl:Thing ;
            rdfs:range xsd:string .

        # New Relationship Properties
        abi:assignedTo a rdf:Property ;
            rdfs:label "assigned to" ;
            rdfs:comment "Relates a task to the person it is assigned to" ;
            rdfs:domain abi:Task ;
            rdfs:range abi:Person .

        abi:partOfProject a rdf:Property ;
            rdfs:label "part of project" ;
            rdfs:comment "Relates a task to its parent project" ;
            rdfs:domain abi:Task ;
            rdfs:range abi:Project .

        abi:hasSkill a rdf:Property ;
            rdfs:label "has skill" ;
            rdfs:comment "Relates a person to a skill they possess" ;
            rdfs:domain abi:Person ;
            rdfs:range abi:Skill .

        abi:requiresSkill a rdf:Property ;
            rdfs:label "requires skill" ;
            rdfs:comment "Relates a task to a required skill" ;
            rdfs:domain abi:Task ;
            rdfs:range abi:Skill .
    """
    
    # Parse the extension
    extension_graph = Graph()
    extension_graph.parse(data=extension_ttl, format="turtle")
    
    # Add the extension to the ontology
    ontology_store.insert(store_name, extension_graph)
    
    print("Extended ontology schema with Task and Skill classes and related properties")
    
    # Now add some instance data using the new schema elements
    graph = ABIGraph()
    
    # Create skill entities
    python_uri = graph.create_entity(
        "Skill", 
        {
            "id": "skill-001",
            "name": "Python Programming",
            "level": "Advanced"
        }
    )
    
    rdf_uri = graph.create_entity(
        "Skill", 
        {
            "id": "skill-002",
            "name": "RDF & SPARQL",
            "level": "Intermediate"
        }
    )
    
    # Find existing entities (person and project)
    query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?john ?jane ?project
        WHERE {
            ?john a abi:Person ;
                 abi:name "John Smith" .
            ?jane a abi:Person ;
                 abi:name "Jane Doe" .
            ?project a abi:Project ;
                    abi:name "Knowledge Graph Implementation" .
        }
    """
    results = ontology_store.query(store_name, query)
    
    if results:
        john_uri = results[0]['john']
        jane_uri = results[0]['jane']
        project_uri = results[0]['project']
        
        # Create task entities
        task1_uri = graph.create_entity(
            "Task", 
            {
                "id": "task-001",
                "name": "Design Data Model",
                "description": "Create the RDF data model for the knowledge graph",
                "status": "Completed",
                "priority": "High",
                "dueDate": datetime(2023, 2, 15).isoformat()
            }
        )
        
        task2_uri = graph.create_entity(
            "Task", 
            {
                "id": "task-002",
                "name": "Implement Graph Database",
                "description": "Set up and configure the graph database",
                "status": "In Progress",
                "priority": "High",
                "dueDate": datetime(2023, 3, 30).isoformat()
            }
        )
        
        # Create relationships
        graph.create_relationship(task1_uri, "assignedTo", jane_uri)
        graph.create_relationship(task2_uri, "assignedTo", john_uri)
        graph.create_relationship(task1_uri, "partOfProject", project_uri)
        graph.create_relationship(task2_uri, "partOfProject", project_uri)
        graph.create_relationship(john_uri, "hasSkill", python_uri)
        graph.create_relationship(jane_uri, "hasSkill", rdf_uri)
        graph.create_relationship(task1_uri, "requiresSkill", rdf_uri)
        graph.create_relationship(task2_uri, "requiresSkill", python_uri)
        
        # Insert the new data
        ontology_store.insert(store_name, graph.get_graph())
        print("Added tasks and skills data to the ontology")
```

### 7. Execute Advanced Queries

Execute advanced SPARQL queries for complex data retrieval:

```python
def run_advanced_queries(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Run advanced SPARQL queries against the ontology."""
    
    print("\nRunning advanced queries:")
    
    # Find tasks assigned to people with matching skills
    print("\n1. Tasks assigned to people with matching required skills:")
    matching_skills_query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?person_name ?task_name ?skill_name
        WHERE {
            ?task a abi:Task ;
                 abi:name ?task_name ;
                 abi:assignedTo ?person ;
                 abi:requiresSkill ?skill .
            
            ?person a abi:Person ;
                   abi:name ?person_name ;
                   abi:hasSkill ?skill .
                   
            ?skill a abi:Skill ;
                  abi:name ?skill_name .
        }
    """
    results = ontology_store.query(store_name, matching_skills_query)
    for result in results:
        print(f"  - Person: {result['person_name']}")
        print(f"    Task: {result['task_name']}")
        print(f"    Skill: {result['skill_name']}")
    
    # Find project status with task completion metrics
    print("\n2. Project status with task completion metrics:")
    project_status_query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?project_name ?task_count ?completed_count 
               ((?completed_count/?task_count) AS ?completion_rate)
        WHERE {
            ?project a abi:Project ;
                    abi:name ?project_name .
            
            # Count all tasks
            {
                SELECT ?project (COUNT(?task) AS ?task_count)
                WHERE {
                    ?task a abi:Task ;
                         abi:partOfProject ?project .
                }
                GROUP BY ?project
            }
            
            # Count completed tasks
            {
                SELECT ?project (COUNT(?task) AS ?completed_count)
                WHERE {
                    ?task a abi:Task ;
                         abi:partOfProject ?project ;
                         abi:status "Completed" .
                }
                GROUP BY ?project
            }
        }
    """
    results = ontology_store.query(store_name, project_status_query)
    for result in results:
        completion_rate = float(result['completion_rate']) * 100
        print(f"  - Project: {result['project_name']}")
        print(f"    Tasks: {result['task_count']}")
        print(f"    Completed: {result['completed_count']}")
        print(f"    Completion Rate: {completion_rate:.1f}%")
    
    # Find skill distribution across the organization
    print("\n3. Skill distribution across the organization:")
    skill_distribution_query = """
        PREFIX abi: <http://example.org/abi#>
        SELECT ?skill_name (COUNT(?person) AS ?people_count)
        WHERE {
            ?skill a abi:Skill ;
                  abi:name ?skill_name .
            
            ?person a abi:Person ;
                   abi:hasSkill ?skill .
        }
        GROUP BY ?skill_name
        ORDER BY DESC(?people_count)
    """
    results = ontology_store.query(store_name, skill_distribution_query)
    for result in results:
        print(f"  - Skill: {result['skill_name']}, Count: {result['people_count']}")
```

### 8. Export and Import Ontology Data

Export and import ontology data for backup or migration:

```python
def export_import_ontology(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Demonstrate exporting and importing ontology data."""
    
    # Export the entire ontology to a file
    export_path = f"{store_name}_export.ttl"
    
    # Get the entire graph
    full_graph = ontology_store.get_graph(store_name)
    
    # Serialize to Turtle format
    with open(export_path, 'w') as f:
        f.write(full_graph.serialize(format="turtle"))
    
    print(f"Exported ontology to {export_path}")
    
    # Import into a new store
    new_store_name = f"{store_name}_imported"
    ontology_store.create_store(new_store_name)
    
    # Import from the file
    import_graph = Graph()
    import_graph.parse(export_path, format="turtle")
    
    ontology_store.insert(new_store_name, import_graph)
    
    print(f"Imported ontology to new store: {new_store_name}")
    
    # Verify the import by counting triples
    original_count = len(ontology_store.get_graph(store_name))
    imported_count = len(ontology_store.get_graph(new_store_name))
    
    print(f"Original store: {original_count} triples")
    print(f"Imported store: {imported_count} triples")
```

## API Reference for Ontology Management

### OntologyStoreService API

```python
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from rdflib import Graph, URIRef

# Create an instance
store_service = OntologyStoreService()

# Create a store
store_service.create_store("my_store")

# List available stores
stores = store_service.list_stores()
print(f"Available stores: {stores}")

# Insert data
graph = Graph()
# ... add data to graph ...
store_service.insert("my_store", graph)

# Get the entire graph
full_graph = store_service.get_graph("my_store")

# Execute a SPARQL query
query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
results = store_service.query("my_store", query)

# Execute a SPARQL update
update_query = """
    DELETE { ?s ?p 'old_value' }
    INSERT { ?s ?p 'new_value' }
    WHERE { ?s ?p 'old_value' }
"""
store_service.update("my_store", update_query)

# Delete a store
store_service.delete_store("my_store")
```

### ABIGraph API

```python
from abi.utils.Graph import ABIGraph
from rdflib import URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, XSD

# Create a graph
graph = ABIGraph()

# Create an entity
person_uri = graph.create_entity(
    "Person",
    {
        "id": "person-123",
        "name": "Alice Smith",
        "email": "alice@example.com"
    }
)

# Add a property to an entity
graph.add_property(person_uri, "age", 30)
graph.add_property(person_uri, "bio", "Software developer with 5 years experience")

# Create a relationship between entities
org_uri = graph.create_entity("Organization", {"name": "Example Corp"})
graph.create_relationship(person_uri, "worksFor", org_uri)

# Find entities by type and properties
people = graph.find_entities("Person", {"name": "Alice Smith"})

# Get the underlying rdflib Graph
rdflib_graph = graph.get_graph()

# Count triples
triple_count = len(rdflib_graph)
print(f"Graph contains {triple_count} triples")

# Serialize to different formats
ttl_data = rdflib_graph.serialize(format="turtle")
json_data = rdflib_graph.serialize(format="json-ld")
```

## Best Practices

### Ontology Design

- **Use Clear Naming Conventions**: Adopt consistent naming patterns for classes and properties
- **Create Balanced Hierarchies**: Avoid deep inheritance trees, aim for 2-3 levels
- **Define Domains and Ranges**: Specify the expected types for properties
- **Use Inverse Relationships**: Define inverse relationships to enable bidirectional navigation
- **Document Everything**: Add labels and comments to all classes and properties

### Querying and Performance

- **Start Simple**: Begin with simple queries and build up to more complex ones
- **Use Appropriate Indexes**: Configure indexes for commonly queried patterns
- **Limit Results**: Use LIMIT in SPARQL queries to avoid large result sets
- **Use Named Graphs**: Organize data into named graphs for better management
- **Monitor Query Performance**: Track slow queries and optimize them

### Data Management

- **Validate Data**: Verify data conforms to schema before insertion
- **Use Transactions**: Wrap related changes in transactions
- **Implement Versioning**: Track changes to ontology data over time
- **Regular Backups**: Export and backup ontology data regularly
- **Incremental Updates**: Prefer incremental updates over bulk operations

### Integration with Pipelines

- **Modular Data Loading**: Design pipelines to load specific data segments
- **Data Provenance**: Track the source of data in the ontology
- **Error Handling**: Implement robust error handling in pipelines
- **Validation Steps**: Include validation steps in pipelines
- **Logging**: Log all operations for audit and debugging

## Advanced Ontology Features

### 1. Inference Rules

Add inference rules to derive new knowledge:

```python
def add_inference_rules(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Add inference rules to the ontology."""
    
    # Define inference rules in Turtle
    rules_ttl = """
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix abi: <http://example.org/abi#> .
        
        # Rule: If a person manages a project, they work on it too
        abi:manages rdfs:subPropertyOf abi:worksOn .
        
        # Rule: If a project is part of an organization, and a person works on the project,
        # then the person works for that organization
        abi:projectWorkerRule a owl:ObjectProperty ;
            rdfs:comment "Rule to infer that project workers work for the organization" ;
            owl:propertyChainAxiom (abi:worksOn abi:partOf) .
    """
    
    # Parse the rules
    rules_graph = Graph()
    rules_graph.parse(data=rules_ttl, format="turtle")
    
    # Add rules to the ontology
    ontology_store.insert(store_name, rules_graph)
    
    print("Added inference rules to the ontology")
    
    # Query with inference enabled
    inference_query = """
        PREFIX abi: <http://example.org/abi#>
        
        SELECT ?person_name ?project_name ?org_name
        WHERE {
            # This will use the inference rules
            ?person abi:worksOn ?project ;
                   abi:name ?person_name .
                   
            ?project abi:name ?project_name ;
                    abi:partOf ?org .
                    
            ?org abi:name ?org_name .
        }
    """
    
    results = ontology_store.query(store_name, inference_query, inference=True)
    
    print("\nResults with inference enabled:")
    for result in results:
        print(f"  - Person: {result['person_name']}")
        print(f"    Works on: {result['project_name']}")
        print(f"    For organization: {result['org_name']}")
```

### 2. Ontology Validation

Implement validation of ontology data:

```python
def validate_ontology(ontology_store: IOntologyStoreService, store_name: str) -> None:
    """Validate ontology data against schema constraints."""
    
    # Define validation rules (SHACL shapes)
    shapes_ttl = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix abi: <http://example.org/abi#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        # Shape for Person entities
        abi:PersonShape a sh:NodeShape ;
            sh:targetClass abi:Person ;
            sh:property [
                sh:path abi:name ;
                sh:datatype xsd:string ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
            ] ;
            sh:property [
                sh:path abi:email ;
                sh:datatype xsd:string ;
                sh:minCount 1 ;
                sh:pattern "^[\\w.%+-]+@[\\w.-]+\\.[a-zA-Z]{2,}$" ;
            ] ;
            sh:property [
                sh:path abi:worksFor ;
                sh:class abi:Organization ;
                sh:minCount 1 ;
            ] .
            
        # Shape for Project entities
        abi:ProjectShape a sh:NodeShape ;
            sh:targetClass abi:Project ;
            sh:property [
                sh:path abi:name ;
                sh:datatype xsd:string ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
            ] ;
            sh:property [
                sh:path abi:startDate ;
                sh:datatype xsd:dateTime ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
            ] ;
            sh:property [
                sh:path abi:endDate ;
                sh:datatype xsd:dateTime ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
            ] ;
            sh:property [
                sh:path abi:partOf ;
                sh:class abi:Organization ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
            ] .
    """
    
    # Parse the shapes
    from pyshacl import validate
    
    # Get the data graph
    data_graph = ontology_store.get_graph(store_name)
    
    # Create the shapes graph
    shapes_graph = Graph()
    shapes_graph.parse(data=shapes_ttl, format="turtle")
    
    # Validate the data
    conforms, results_graph, results_text = validate(
        data_graph, 
        shacl_graph=shapes_graph,
        inference='rdfs'
    )
    
    if conforms:
        print("✅ Ontology data conforms to all validation rules")
    else:
        print("❌ Validation errors found:")
        print(results_text)
    
    # Create a validation report
    report_path = f"{store_name}_validation_report.txt"
    with open(report_path, 'w') as f:
        f.write(results_text)
    
    print(f"Validation report saved to {report_path}")
```

### 3. Federated Queries

Execute federated queries across multiple ontology stores:

```python
def federated_query(
    ontology_store: IOntologyStoreService, 
    store_name1: str, 
    store_name2: str
) -> None:
    """Execute a federated query across multiple ontology stores."""
    
    # Create a federated query
    federated_query = f"""
        PREFIX abi: <http://example.org/abi#>
        
        SELECT ?person_name ?project_name ?skill_name
        WHERE {{
            SERVICE <{store_name1}> {{
                ?person a abi:Person ;
                       abi:name ?person_name ;
                       abi:worksOn ?project .
                       
                ?project a abi:Project ;
                        abi:name ?project_name .
            }}
            
            SERVICE <{store_name2}> {{
                ?person a abi:Person ;
                       abi:name ?person_name ;
                       abi:hasSkill ?skill .
                       
                ?skill a abi:Skill ;
                      abi:name ?skill_name .
            }}
        }}
    """
    
    # Execute the federated query
    results = ontology_store.federated_query(federated_query)
    
    print("\nFederated query results:")
    for result in results:
        print(f"  - Person: {result['person_name']}")
        print(f"    Project: {result['project_name']}")
        print(f"    Skill: {result['skill_name']}")
```

## Next Steps

- Explore [Developing Pipelines](developing-pipelines.md) to automate ontology data loading
- Learn about [Writing Workflows](writing-workflows.md) to build processes that use ontology data
- Check out [Creating Assistants](creating-assistants.md) to provide natural language interfaces to ontology data 