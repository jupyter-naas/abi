import pytest
import os
import tempfile
from rdflib import Graph, URIRef, Literal
from lib.abi.services.triple_store.TripleStoreFactory import TripleStoreFactory
from lib.abi.services.triple_store.TripleStorePorts import OntologyEvent
@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for testing storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def triple_store_service(temp_storage_dir):
    """Create a TripleStoreService instance with filesystem storage."""
    return TripleStoreFactory.TripleStoreServiceFilesystem(temp_storage_dir)

def test_insert_and_get(triple_store_service):
    """Test inserting and retrieving triples."""
    # Create a test graph
    graph = Graph()
    subject = URIRef("http://example.org/subject")
    predicate = URIRef("http://example.org/predicate")
    object = Literal("test object")
    graph.add((subject, predicate, object))
    
    # Insert the triples
    triple_store_service.insert(graph)
    
    # Retrieve and verify
    retrieved_graph = triple_store_service.get()
    assert len(retrieved_graph) == 1
    assert (subject, predicate, object) in retrieved_graph

def test_remove(triple_store_service):
    """Test removing triples."""
    # Create and insert a test graph
    graph = Graph()
    subject = URIRef("http://example.org/subject")
    predicate = URIRef("http://example.org/predicate")
    object = Literal("test object")
    graph.add((subject, predicate, object))
    triple_store_service.insert(graph)
    
    # Remove the triples
    triple_store_service.remove(graph)
    
    # Verify removal
    retrieved_graph = triple_store_service.get()
    assert len(retrieved_graph) == 0

def test_query(triple_store_service):
    """Test SPARQL query functionality."""
    # Create and insert test data
    graph = Graph()
    subject = URIRef("http://example.org/subject")
    predicate = URIRef("http://example.org/predicate")
    object = Literal("test object")
    graph.add((subject, predicate, object))
    triple_store_service.insert(graph)
    
    # Query the data
    query = """
    SELECT ?s ?p ?o
    WHERE {
        ?s ?p ?o .
    }
    """
    results = triple_store_service.query(query)
    
    # Verify query results
    assert len(results) == 1
    for row in results:
        assert str(row[0]) == str(subject)
        assert str(row[1]) == str(predicate)
        assert str(row[2]) == str(object)

def test_event_subscription(triple_store_service):
    """Test event subscription functionality."""
    events = []
    
    def event_callback(event_type, triple):
        events.append((event_type, triple))
    
    # Subscribe to all events
    subscription_id = triple_store_service.subscribe(
        (None, None, None),
        OntologyEvent.INSERT,
        event_callback
    )
    
    # Create and insert test data
    graph = Graph()
    subject = URIRef("http://example.org/subject")
    predicate = URIRef("http://example.org/predicate")
    object = Literal("test object")
    graph.add((subject, predicate, object))
    triple_store_service.insert(graph)
    
    # Verify event was triggered
    assert len(events) == 1
    assert events[0][0] == OntologyEvent.INSERT
    assert events[0][1] == (subject, predicate, object)
    
    # Unsubscribe and verify no more events
    triple_store_service.unsubscribe(subscription_id)
    events.clear()
    triple_store_service.insert(graph)
    assert len(events) == 0 