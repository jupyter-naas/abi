# Triple Store Service

[Source Code](../../../lib/abi/services/triple_store)

## Overview

The Triple Store Service provides a unified interface for working with RDF (Resource Description Framework) data across different storage backends. It abstracts away the underlying storage implementation through adapters, allowing seamless switching between different storage solutions.

The service currently supports the following adapters:

- **Filesystem Adapter**: Used in local development to store RDF triples in the file system
- **Naas Adapter**: Uses Object Storage Service to store RDF triples in cloud storage

This abstraction allows applications to work with semantic data in a consistent way, regardless of whether they're running in development or production environments. The service provides core operations like:

- Inserting triples into the store
- Removing triples from the store
- Querying the store using SPARQL
- Working with subject-specific graphs
- Loading and managing RDF/OWL schemas
- Event subscriptions for ontology changes

The storage backend used is determined by the environment configuration, defaulting to local filesystem storage in development and using cloud storage in production environments.

## Usage

### Default initialization

The Triple Store Service is typically initialized through the application's service manager. The initialization differs between development and production environments:

```python
from src import services

# Access the triple store service
triple_store = services.triple_store_service
```

You can check the loading of the service in [services.py](../../../src/services.py)

#### Development Environment

In development mode (when `ENV=dev` environment variable is set), the service automatically initializes with the Filesystem adapter:

```python
# Development initialization (happens automatically)
triple_store_service = TripleStoreFactory.TripleStoreServiceFilesystem(config.triple_store_path)
```

#### Production Environment

In production, the service uses the Naas adapter with credentials from your configuration:

```python
# Production initialization (happens automatically)
triple_store_service = TripleStoreFactory.TripleStoreServiceNaas(
    naas_api_key=secret.get('NAAS_API_KEY'),
    workspace_id=config.workspace_id,
    storage_name=config.storage_name
)
```

This initialization is handled automatically when the application starts, allowing you to use the triple store service directly without manual setup.

### Factories

The Triple Store Service provides factory methods to create service instances based on your needs:

```python
from lib.abi.services.triple_store.TripleStoreFactory import TripleStoreFactory

# Create a filesystem-based triple store service
triple_store = TripleStoreFactory.TripleStoreServiceFilesystem("/path/to/triple_store")

# Create a Naas-based triple store service
triple_store = TripleStoreFactory.TripleStoreServiceNaas(
    naas_api_key="YOUR_NAAS_API_KEY",
    workspace_id="your-workspace-id",
    storage_name="your-storage-name",
    base_prefix="ontologies"  # Optional, defaults to "ontologies"
)
```

Each factory method returns an instance of `TripleStoreService` that provides a unified interface for RDF operations regardless of the underlying storage backend.

## API Reference

### `TripleStoreService`

The main service class implementing the `ITripleStoreService` interface. It provides a unified API for interacting with different triple store backends through adapters.

#### Methods

##### `insert(triples: Graph) -> None`

Inserts triples from the provided RDF graph into the store.

- **Parameters**:
  - `triples`: RDFlib Graph containing triples to insert
- **Returns**: None

##### `remove(triples: Graph) -> None`

Removes triples from the provided graph from the store.

- **Parameters**:
  - `triples`: RDFlib Graph containing triples to remove
- **Returns**: None

##### `get() -> Graph`

Gets the complete RDF graph from the triple store.

- **Returns**: RDFlib Graph containing all stored triples

##### `query(query: str) -> Graph`

Executes a SPARQL query against the triple store.

- **Parameters**:
  - `query`: SPARQL query string to execute
- **Returns**: RDFlib Graph containing query results

##### `query_view(view: str, query: str) -> Graph`

Executes a SPARQL query against a specific view of the triple store.

- **Parameters**:
  - `view`: Name of the view to query
  - `query`: SPARQL query string to execute
- **Returns**: RDFlib Graph containing query results
- **Raises**: `ViewNotFoundError` if the view does not exist

##### `get_subject_graph(subject: str) -> Graph`

Gets the RDF graph containing all triples for a specific subject.

- **Parameters**:
  - `subject`: Subject URI to retrieve triples for
- **Returns**: RDFlib Graph containing all triples for the specified subject
- **Raises**: `SubjectNotFoundError` if no triples exist with the specified subject

##### `load_schema(filepath: str) -> None`

Loads an RDF/OWL schema file into the triple store.

- **Parameters**:
  - `filepath`: Path to the RDF/OWL schema file to load
- **Returns**: None

##### `get_schema_graph() -> Graph`

Gets the RDF graph containing just the schema/ontology triples.

- **Returns**: RDFlib Graph containing only the schema/ontology triples

##### `subscribe(topic: tuple, event_type: OntologyEvent, callback: Callable, background: bool = False) -> str`

Subscribes to events for a specific topic pattern.

- **Parameters**:
  - `topic`: A (subject, predicate, object) tuple specifying the pattern to match. Each element can be None to match any value in that position.
  - `event_type`: Type of event to subscribe to (INSERT or DELETE)
  - `callback`: Function to call when matching events occur
  - `background`: Whether the callback should be executed in background (default: False)
- **Returns**: A unique subscription ID that can be used to unsubscribe later

##### `unsubscribe(subscription_id: str) -> None`

Unsubscribes from events using a subscription ID.

- **Parameters**:
  - `subscription_id`: The subscription ID returned from a previous subscribe() call
- **Returns**: None
- **Raises**: `SubscriptionNotFoundError` if no subscription exists with the provided ID

### Storage Adapters

The service supports multiple storage backends through adapters:

#### Filesystem Adapter (`TripleStoreService__SecondaryAdaptor__Filesystem`)

Adapter for local file system storage of RDF triples.

- **Initialization**: `TripleStoreFactory.TripleStoreServiceFilesystem(store_path: str)`

#### Naas Adapter (`TripleStoreService__SecondaryAdaptor__NaasStorage`)

Adapter for using Naas-managed cloud storage for RDF triples.

- **Initialization**:
  ```python
  TripleStoreFactory.TripleStoreServiceNaas(
      naas_api_key: str,
      workspace_id: str,
      storage_name: str,
      base_prefix: str = "ontologies"
  )
  ```

### Events and Subscriptions

The Triple Store Service provides an event system for reacting to changes in the RDF data:

```python
from lib.abi.services.triple_store.TripleStorePorts import OntologyEvent

# Subscribe to all triple insertions with any predicate for a specific subject
subscription_id = triple_store.subscribe(
    topic=("http://example.org/subject1", None, None),
    event_type=OntologyEvent.INSERT,
    callback=lambda event, triple: print(f"Triple added: {triple}")
)

# Subscribe to all triple deletions with rdf:type predicate
subscription_id = triple_store.subscribe(
    topic=(None, RDF.type, None),
    event_type=OntologyEvent.DELETE,
    callback=lambda event, triple: print(f"Triple deleted: {triple}")
)

# Run callback in background for heavy processing
subscription_id = triple_store.subscribe(
    topic=(None, None, None),
    event_type=OntologyEvent.INSERT,
    callback=process_triple_in_background,
    background=True
)

# Unsubscribe when no longer needed
triple_store.unsubscribe(subscription_id)
```

### Exceptions

All adapters may throw these exceptions when operations fail:

- `SubjectNotFoundError`: Raised when trying to access a subject that doesn't exist
- `SubscriptionNotFoundError`: Raised when trying to unsubscribe with an invalid subscription ID
- `ViewNotFoundError`: Raised when trying to query a view that doesn't exist

### Usage Examples

```python
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS
from src import services

# Access the triple store service
triple_store = services.triple_store_service

# Create a graph with triples
g = Graph()
EX = Namespace("http://example.org/")
g.bind("ex", EX)

# Add some triples
g.add((EX.Person, RDF.type, RDFS.Class))
g.add((EX.name, RDF.type, RDF.Property))
g.add((EX.name, RDFS.domain, EX.Person))
g.add((EX.alice, RDF.type, EX.Person))
g.add((EX.alice, EX.name, Literal("Alice")))

# Insert triples into the store
triple_store.insert(g)

# Get all triples
all_triples = triple_store.get()

# Query for people
query = """
    SELECT ?person ?name
    WHERE {
        ?person a ex:Person .
        ?person ex:name ?name .
    }
"""
result = triple_store.query(query)

# Get triples for a specific subject
alice_graph = triple_store.get_subject_graph("http://example.org/alice")

# Remove a triple
remove_g = Graph()
remove_g.add((EX.alice, EX.name, Literal("Alice")))
triple_store.remove(remove_g)

# Load a schema from file
triple_store.load_schema("path/to/schema.ttl")
```

## How to create a new secondary adapter

Creating a new secondary adapter allows you to extend the Triple Store Service to work with additional storage backends. Here's a guide on how to create a new adapter.

### Steps to Create a New Adapter

1. **Create a new adapter class** that implements the `ITripleStorePort` interface
2. **Implement the required methods** defined in the interface
3. **Add a factory method** to `TripleStoreFactory` to create instances of your adapter
4. **Register your adapter** with the application if necessary

### Example: Creating an In-Memory Adapter

Here's a simplified example implementation of an in-memory adapter:

```python
from lib.abi.services.triple_store.TripleStorePorts import ITripleStorePort, OntologyEvent, Exceptions
from rdflib import Graph
from typing import Tuple

class TripleStoreService__SecondaryAdaptor__InMemory(ITripleStorePort):
    """In-memory implementation of the Triple Store adapter."""
    
    def __init__(self):
        """Initialize in-memory adapter."""
        self.__graph = Graph()
        
    def insert(self, triples: Graph):
        """Insert triples into the in-memory store."""
        self.__graph += triples
        
    def remove(self, triples: Graph):
        """Remove triples from the in-memory store."""
        self.__graph -= triples
        
    def get(self) -> Graph:
        """Get all triples from the in-memory store."""
        return self.__graph
        
    def get_subject_graph(self, subject: str) -> Graph:
        """Get all triples for a specific subject."""
        subject_graph = Graph()
        
        for s, p, o in self.__graph.triples((subject, None, None)):
            subject_graph.add((s, p, o))
            
        if len(subject_graph) == 0:
            raise Exceptions.SubjectNotFoundError(f"Subject {subject} not found")
            
        return subject_graph
        
    def query(self, query: str) -> Graph:
        """Execute a SPARQL query against the in-memory store."""
        return self.__graph.query(query)
        
    def query_view(self, view: str, query: str) -> Graph:
        """Query a specific view of the in-memory store."""
        # In this simple implementation, views are not supported
        raise Exceptions.ViewNotFoundError(f"View {view} not found in in-memory store")
        
    def handle_view_event(self, view: Tuple[str, str, str], event: OntologyEvent, triple: Tuple[str, str, str]):
        """Handle view events (not implemented for in-memory store)."""
        pass
```

### Add a Factory Method

To make your adapter available through the factory pattern, add a new method to the `TripleStoreFactory` class:

```python
# In lib/abi/services/triple_store/TripleStoreFactory.py

@staticmethod
def TripleStoreServiceInMemory() -> TripleStoreService:
    """Create a Triple Store Service using in-memory storage.
    
    Returns:
        TripleStoreService: Configured service instance using in-memory storage
    """
    from lib.abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__InMemory import TripleStoreService__SecondaryAdaptor__InMemory
    return TripleStoreService(TripleStoreService__SecondaryAdaptor__InMemory())
```

### Usage Example

You can now use your in-memory adapter in your application:

```python
from lib.abi.services.triple_store.TripleStoreFactory import TripleStoreFactory

# Create an in-memory triple store service
triple_store = TripleStoreFactory.TripleStoreServiceInMemory()

# Use the service with the same interface
triple_store.insert(my_graph)
results = triple_store.query(my_query)
```

### Key Considerations When Creating a New Adapter

1. **Performance**: Consider optimizing for your specific storage backend, especially for large RDF datasets
2. **Concurrency**: Ensure your adapter properly handles concurrent access if needed
3. **Namespaces**: Preserve namespace bindings when storing and retrieving RDF data
4. **Testing**: Create comprehensive tests for your adapter to ensure it behaves consistently
5. **Views**: Implement view support if your storage backend can benefit from it
6. **Schema Management**: Handle schema loading and versioning appropriately

By following these steps, you can extend the Triple Store Service to work with any storage backend that can store RDF data.