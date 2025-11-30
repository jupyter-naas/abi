import uuid

import pytest
import requests
from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import Oxigraph
from rdflib import RDF, BNode, Graph, Literal, URIRef

# class TestOxigraph:
#     """Test suite for the Oxigraph triple store adapter."""

#     @pytest.fixture
#     def mock_oxigraph_url(self):
#         """Mock Oxigraph URL for testing."""
#         return "http://localhost:7878"

#     @pytest.fixture
#     def sample_graph(self):
#         """Create a sample RDF graph for testing."""
#         g = Graph()
#         g.bind("ex", "http://example.org/")

#         subject = URIRef("http://example.org/alice")
#         g.add((subject, RDF.type, URIRef("http://example.org/Person")))
#         g.add((subject, URIRef("http://example.org/name"), Literal("Alice")))
#         g.add((subject, URIRef("http://example.org/age"), Literal(30)))

#         return g

#     @pytest.fixture
#     def mock_successful_response(self):
#         """Mock successful HTTP response for SELECT queries."""
#         response = Mock()
#         response.status_code = 200
#         response.headers = {"Content-Type": "application/sparql-results+json"}
#         response_text = """{
#             "head": {"vars": ["s", "p", "o"]},
#             "results": {
#                 "bindings": [{
#                     "s": {"type": "uri", "value": "http://example.org/alice"},
#                     "p": {"type": "uri", "value": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"},
#                     "o": {"type": "uri", "value": "http://example.org/Person"}
#                 }]
#             }
#         }"""
#         response.text = response_text
#         response.content = response_text.encode('utf-8')
#         response.raise_for_status = Mock()
#         return response

#     @pytest.fixture
#     def mock_turtle_response(self):
#         """Mock Turtle response for CONSTRUCT queries."""
#         response = Mock()
#         response.status_code = 200
#         response.headers = {"Content-Type": "text/turtle"}
#         response.text = """@prefix ex: <http://example.org/> .
# ex:alice a ex:Person ."""
#         response.raise_for_status = Mock()
#         return response

#     def test_init_default_parameters(self):
#         """Test Oxigraph initialization with default parameters."""
#         with patch('requests.get') as mock_get:
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             adapter = Oxigraph()

#             assert adapter.oxigraph_url == "http://localhost:7878"
#             assert adapter.query_endpoint == "http://localhost:7878/query"
#             assert adapter.update_endpoint == "http://localhost:7878/update"
#             assert adapter.store_endpoint == "http://localhost:7878/store"
#             assert adapter.timeout == 60

#     def test_init_custom_parameters(self, mock_oxigraph_url):
#         """Test Oxigraph initialization with custom parameters."""
#         with patch('requests.get') as mock_get:
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             custom_url = "http://oxigraph.example.com:8080"
#             adapter = Oxigraph(
#                 oxigraph_url=custom_url,
#                 timeout=30
#             )

#             assert adapter.oxigraph_url == custom_url
#             assert adapter.query_endpoint == f"{custom_url}/query"
#             assert adapter.timeout == 30

#     def test_connection_test_success(self, mock_oxigraph_url):
#         """Test successful connection test during initialization."""
#         with patch('requests.get') as mock_get:
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             Oxigraph(mock_oxigraph_url)

#             # Verify connection test was performed
#             mock_get.assert_called_once()
#             call_args = mock_get.call_args
#             assert call_args[0][0] == f"{mock_oxigraph_url}/query"
#             assert "query" in call_args[1]["params"]

#     def test_connection_test_failure(self, mock_oxigraph_url):
#         """Test connection failure during initialization."""
#         with patch('requests.get') as mock_get:
#             mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

#             with pytest.raises(requests.exceptions.ConnectionError):
#                 Oxigraph(mock_oxigraph_url)

#     def test_insert_success(self, mock_oxigraph_url, sample_graph):
#         """Test successful triple insertion."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_post.return_value.raise_for_status = Mock()

#             adapter = Oxigraph(mock_oxigraph_url)
#             adapter.insert(sample_graph)

#             # Verify the POST call was made correctly
#             assert mock_post.call_count == 1
#             call_args = mock_post.call_args
#             assert call_args[0][0] == adapter.update_endpoint
#             assert call_args[1]["headers"]["Content-Type"] == "application/sparql-update"
#             assert "INSERT DATA" in call_args[1]["data"]
#             assert "alice" in call_args[1]["data"]  # Check that our sample data is there

#     def test_remove_success(self, mock_oxigraph_url, sample_graph):
#         """Test successful triple removal."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_post.return_value.raise_for_status = Mock()

#             adapter = Oxigraph(mock_oxigraph_url)
#             adapter.remove(sample_graph)

#             # Verify the POST call was made correctly
#             assert mock_post.call_count == 1
#             call_args = mock_post.call_args
#             assert call_args[0][0] == adapter.update_endpoint
#             assert call_args[1]["headers"]["Content-Type"] == "application/sparql-update"
#             assert "DELETE DATA" in call_args[1]["data"]
#             assert "alice" in call_args[1]["data"]

#     def test_get_success(self, mock_oxigraph_url, mock_turtle_response):
#         """Test successful retrieval of all triples."""
#         with patch('requests.get') as mock_get:

#             # First call for connection test, second for get
#             mock_get.side_effect = [
#                 Mock(status_code=200, raise_for_status=Mock()),  # Connection test
#                 mock_turtle_response  # Get response
#             ]

#             adapter = Oxigraph(mock_oxigraph_url)
#             result = adapter.get()

#             assert isinstance(result, Graph)
#             # The mock response contains one triple
#             assert len(result) > 0

#     def test_query_select_success(self, mock_oxigraph_url, mock_successful_response):
#         """Test successful SELECT query execution."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_post.return_value = mock_successful_response

#             adapter = Oxigraph(mock_oxigraph_url)
#             query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
#             result = adapter.query(query)

#             # Verify the query was executed correctly
#             call_args = mock_post.call_args
#             assert call_args[0][0] == adapter.query_endpoint
#             assert call_args[1]["data"] == query
#             assert "sparql-results" in call_args[1]["headers"]["Accept"]

#             # Verify we can iterate results
#             result_list = list(result)
#             assert len(result_list) == 1

#     def test_query_construct_success(self, mock_oxigraph_url, mock_turtle_response):
#         """Test successful CONSTRUCT query execution."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_turtle_response.headers = {"Content-Type": "application/n-triples"}
#             mock_turtle_response.text = "<http://example.org/alice> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Person> .\n"
#             mock_post.return_value = mock_turtle_response

#             adapter = Oxigraph(mock_oxigraph_url)
#             query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
#             result = adapter.query(query)

#             # For CONSTRUCT queries, result should be a Graph
#             assert isinstance(result, Graph)

#     def test_query_update_success(self, mock_oxigraph_url):
#         """Test successful UPDATE query execution."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             update_response = Mock()
#             update_response.status_code = 200
#             update_response.headers = {"Content-Type": "text/plain"}
#             update_response.raise_for_status = Mock()
#             mock_post.return_value = update_response

#             adapter = Oxigraph(mock_oxigraph_url)
#             query = "INSERT DATA { <http://example.org/test> <http://example.org/prop> 'value' }"
#             adapter.query(query)

#             # Verify the update was executed correctly
#             call_args = mock_post.call_args
#             assert call_args[0][0] == adapter.update_endpoint
#             assert call_args[1]["data"] == query

#     def test_get_subject_graph_success(self, mock_oxigraph_url, mock_turtle_response):
#         """Test successful subject graph retrieval."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_turtle_response.headers = {"Content-Type": "application/n-triples"}
#             mock_turtle_response.text = "<http://example.org/alice> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Person> .\n"
#             mock_post.return_value = mock_turtle_response

#             adapter = Oxigraph(mock_oxigraph_url)
#             subject = URIRef("http://example.org/alice")
#             result = adapter.get_subject_graph(subject)

#             assert isinstance(result, Graph)
#             # Verify the query was constructed correctly
#             call_args = mock_post.call_args
#             assert str(subject) in call_args[1]["data"]
#             assert "CONSTRUCT" in call_args[1]["data"]

#     def test_query_view_delegates_to_query(self, mock_oxigraph_url):
#         """Test that query_view delegates to query method."""
#         with patch('requests.get') as mock_get:
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             adapter = Oxigraph(mock_oxigraph_url)

#             # Mock the query method
#             adapter.query = Mock(return_value="mocked_result")

#             query = "SELECT ?s WHERE { ?s ?p ?o }"
#             result = adapter.query_view("some_view", query)

#             # Verify query was called with the same query string
#             adapter.query.assert_called_once_with(query)
#             assert result == "mocked_result"

#     def test_handle_view_event_no_op(self, mock_oxigraph_url):
#         """Test that handle_view_event is a no-op."""
#         with patch('requests.get') as mock_get:
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             adapter = Oxigraph(mock_oxigraph_url)

#             # This should not raise any exception
#             adapter.handle_view_event(
#                 view=(None, None, None),
#                 event=OntologyEvent.INSERT,
#                 triple=(URIRef("http://example.org/s"), URIRef("http://example.org/p"), URIRef("http://example.org/o"))
#             )

#     def test_insert_http_error(self, mock_oxigraph_url, sample_graph):
#         """Test that HTTP errors are properly raised during insert."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")

#             adapter = Oxigraph(mock_oxigraph_url)

#             with pytest.raises(requests.exceptions.HTTPError):
#                 adapter.insert(sample_graph)

#     def test_query_timeout_error(self, mock_oxigraph_url):
#         """Test that timeout errors are properly handled."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

#             adapter = Oxigraph(mock_oxigraph_url)

#             with pytest.raises(requests.exceptions.Timeout):
#                 adapter.query("SELECT ?s WHERE { ?s ?p ?o }")

#     def test_query_unexpected_content_type(self, mock_oxigraph_url):
#         """Test handling of unexpected content types in query responses."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             unexpected_response = Mock()
#             unexpected_response.status_code = 200
#             unexpected_response.headers = {"Content-Type": "text/html"}
#             unexpected_response.raise_for_status = Mock()
#             mock_post.return_value = unexpected_response

#             adapter = Oxigraph(mock_oxigraph_url)

#             with pytest.raises(ValueError, match="Unexpected content type"):
#                 adapter.query("SELECT ?s WHERE { ?s ?p ?o }")

#     def test_insert_empty_graph(self, mock_oxigraph_url):
#         """Test that inserting an empty graph is handled gracefully."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             adapter = Oxigraph(mock_oxigraph_url)
#             empty_graph = Graph()

#             # Insert empty graph - should not make HTTP request
#             adapter.insert(empty_graph)

#             # Verify no POST requests were made for empty graph
#             mock_post.assert_not_called()

#     def test_remove_empty_graph(self, mock_oxigraph_url):
#         """Test that removing from an empty graph works correctly."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_post.return_value.raise_for_status = Mock()

#             adapter = Oxigraph(mock_oxigraph_url)
#             empty_graph = Graph()

#             # Remove empty graph - should still work
#             adapter.remove(empty_graph)

#             # Verify POST was called (empty DELETE DATA query is still valid)
#             assert mock_post.call_count == 1
#             call_args = mock_post.call_args
#             assert "DELETE DATA" in call_args[1]["data"]

#     def test_query_ask_query(self, mock_oxigraph_url):
#         """Test ASK query handling."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             ask_response = Mock()
#             ask_response.status_code = 200
#             ask_response.headers = {"Content-Type": "application/sparql-results+json"}
#             ask_response.text = """{
#                 "head": {},
#                 "boolean": true
#             }"""
#             ask_response.raise_for_status = Mock()
#             mock_post.return_value = ask_response

#             adapter = Oxigraph(mock_oxigraph_url)
#             query = "ASK WHERE { ?s ?p ?o }"
#             result = adapter.query(query)

#             # ASK queries return results but with different structure
#             result_list = list(result)
#             # For ASK queries, the result structure is different but should still be iterable
#             assert isinstance(result_list, list)

#     def test_query_with_different_datatypes(self, mock_oxigraph_url):
#         """Test query results with different RDF datatypes."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             # Mock response with various datatypes
#             response = Mock()
#             response.status_code = 200
#             response.headers = {"Content-Type": "application/sparql-results+json"}
#             response.text = """{
#                 "head": {"vars": ["uri", "integer", "string", "date"]},
#                 "results": {
#                     "bindings": [{
#                         "uri": {"type": "uri", "value": "http://example.org/test"},
#                         "integer": {"type": "literal", "value": "42", "datatype": "http://www.w3.org/2001/XMLSchema#integer"},
#                         "string": {"type": "literal", "value": "test string"},
#                         "date": {"type": "literal", "value": "2023-01-01", "datatype": "http://www.w3.org/2001/XMLSchema#date"}
#                     }]
#                 }
#             }"""
#             response.raise_for_status = Mock()
#             mock_post.return_value = response

#             adapter = Oxigraph(mock_oxigraph_url)
#             result = adapter.query("SELECT ?uri ?integer ?string ?date WHERE { ?s ?p ?o }")

#             rows = list(result)
#             assert len(rows) == 1
#             row = rows[0]

#             # Test that different datatypes are handled correctly
#             assert str(row.uri) == "http://example.org/test"
#             assert isinstance(row.integer, Literal)
#             assert int(row.integer) == 42
#             assert str(row.string) == "test string"

#     def test_get_subject_graph_empty_result(self, mock_oxigraph_url):
#         """Test get_subject_graph when no triples are found for the subject."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             # Mock empty CONSTRUCT result
#             empty_response = Mock()
#             empty_response.status_code = 200
#             empty_response.headers = {"Content-Type": "application/n-triples"}
#             empty_response.text = ""  # Empty N-Triples
#             empty_response.raise_for_status = Mock()
#             mock_post.return_value = empty_response

#             adapter = Oxigraph(mock_oxigraph_url)
#             subject = URIRef("http://example.org/nonexistent")
#             result = adapter.get_subject_graph(subject)

#             assert isinstance(result, Graph)
#             assert len(result) == 0

#     def test_query_with_bnode(self, mock_oxigraph_url):
#         """Test query results containing blank nodes."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             bnode_response = Mock()
#             bnode_response.status_code = 200
#             bnode_response.headers = {"Content-Type": "application/sparql-results+json"}
#             bnode_response.text = """{
#                 "head": {"vars": ["s", "p", "o"]},
#                 "results": {
#                     "bindings": [{
#                         "s": {"type": "bnode", "value": "_:b1"},
#                         "p": {"type": "uri", "value": "http://example.org/property"},
#                         "o": {"type": "literal", "value": "test value"}
#                     }]
#                 }
#             }"""
#             bnode_response.raise_for_status = Mock()
#             mock_post.return_value = bnode_response

#             adapter = Oxigraph(mock_oxigraph_url)
#             result = adapter.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o }")

#             rows = list(result)
#             assert len(rows) == 1
#             row = rows[0]

#             # Verify blank node is properly handled
#             from rdflib.term import BNode
#             assert isinstance(row.s, BNode)

#     def test_connection_test_with_custom_timeout(self):
#         """Test connection test with custom timeout."""
#         with patch('requests.get') as mock_get:
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()

#             adapter = Oxigraph("http://localhost:7878", timeout=30)

#             assert adapter.timeout == 30
#             # Verify connection test was called with correct timeout
#             mock_get.assert_called_once()
#             assert mock_get.call_args[1]['timeout'] == 30

#     def test_main_script_functionality(self):
#         """Test the main script functionality for basic operations."""
#         with patch('requests.get') as mock_get, \
#              patch('requests.post') as mock_post:

#             # Setup HTTP mocks
#             mock_get.return_value.status_code = 200
#             mock_get.return_value.raise_for_status = Mock()
#             mock_post.return_value.raise_for_status = Mock()

#             # Test with explicit parameters
#             adapter = Oxigraph(
#                 oxigraph_url="http://localhost:7878"
#             )

#             # Test that the main functionality can be called without errors
#             assert adapter.oxigraph_url == "http://localhost:7878"


class TestOxigraphIntegration:
    """Integration tests for Oxigraph (require running Oxigraph instance)."""

    @pytest.fixture
    def oxigraph_adapter(self):
        """Create an Oxigraph adapter for integration testing."""
        return Oxigraph(oxigraph_url="http://localhost:7878")

    @pytest.fixture
    def integration_graph(self):
        """Create a test graph for integration testing."""
        g = Graph()
        g.bind("test", "http://test.example.org/")

        subject = URIRef("http://test.example.org/integration_test")
        g.add((subject, RDF.type, URIRef("http://test.example.org/TestEntity")))
        g.add(
            (
                subject,
                URIRef("http://test.example.org/testProperty"),
                Literal("integration_value"),
            )
        )

        return g

    def generate_graph(
        self, num_triples: int, base_uri: str = "http://test.example.org/"
    ):
        """Create a large test graph for integration testing."""
        g = Graph()
        g.bind("test", base_uri)

        for i in range(num_triples):
            subject = URIRef(f"{base_uri}/entity{i}")
            g.add((subject, RDF.type, URIRef(f"{base_uri}/TestEntity")))

        return g

    def test_large_graph_insert(self, oxigraph_adapter):
        """Test inserting a large graph into Oxigraph."""
        try:
            base_uri = f"http://test.example.org/{uuid.uuid4()}"
            large_graph = self.generate_graph(100001, base_uri)
            oxigraph_adapter.insert(large_graph)

            # Verify the data was inserted
            count_query = (
                f"SELECT (COUNT(*) as ?count) WHERE {{ ?s a <{base_uri}/TestEntity> }}"
            )
            result = list(oxigraph_adapter.query(count_query))
            assert len(result) == 1

            print(result)

            # Access count using Variable object
            from rdflib.term import Variable

            count_var = Variable("count")
            assert int(result[0][count_var]) == 100001

            # Cleanup
            oxigraph_adapter.remove(large_graph)
        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping large graph test")

    def test_insert_and_query_workflow(self, oxigraph_adapter, integration_graph):
        """Test basic insert and query workflow."""
        try:
            # Insert test data
            oxigraph_adapter.insert(integration_graph)

            # Query for the data
            query = """
            SELECT ?s ?p ?o WHERE {
                ?s <http://test.example.org/testProperty> ?o
            }
            """
            results = list(oxigraph_adapter.query(query))
            assert len(results) == 1
            assert str(results[0].o) == "integration_value"

            # Cleanup
            oxigraph_adapter.remove(integration_graph)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping integration test")

    def test_construct_query(self, oxigraph_adapter, integration_graph):
        """Test CONSTRUCT query returns a graph."""
        try:
            oxigraph_adapter.insert(integration_graph)

            query = """
            CONSTRUCT { ?s ?p ?o }
            WHERE { 
                ?s <http://test.example.org/testProperty> ?o .
                ?s ?p ?o
            }
            """
            result = oxigraph_adapter.query(query)

            assert isinstance(result, Graph)
            assert len(result) > 0

            # Cleanup
            oxigraph_adapter.remove(integration_graph)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping construct test")

    def test_ask_query(self, oxigraph_adapter, integration_graph):
        """Test ASK query."""
        try:
            oxigraph_adapter.insert(integration_graph)

            # Ask if data exists
            ask_query = """
            ASK WHERE {
                ?s <http://test.example.org/testProperty> "integration_value"
            }
            """
            result = list(oxigraph_adapter.query(ask_query))
            assert result is not None

            # Cleanup
            oxigraph_adapter.remove(integration_graph)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping ASK test")

    def test_get_subject_graph(self, oxigraph_adapter, integration_graph):
        """Test retrieving all triples for a specific subject."""
        try:
            oxigraph_adapter.insert(integration_graph)

            subject = URIRef("http://test.example.org/integration_test")
            subject_graph = oxigraph_adapter.get_subject_graph(subject)

            assert isinstance(subject_graph, Graph)
            assert len(subject_graph) == 2  # type and testProperty

            # Cleanup
            oxigraph_adapter.remove(integration_graph)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping subject graph test")

    def test_filter_query(self, oxigraph_adapter):
        """Test SPARQL FILTER clause."""
        try:
            # Create test data with numbers - use unique URI path
            g = Graph()
            g.bind("test", "http://test.example.org/filter/")

            for i in range(10):
                subject = URIRef(f"http://test.example.org/filter/number{i}")
                g.add(
                    (subject, RDF.type, URIRef("http://test.example.org/filter/Number"))
                )
                g.add(
                    (
                        subject,
                        URIRef("http://test.example.org/filter/value"),
                        Literal(i),
                    )
                )

            oxigraph_adapter.insert(g)

            # Query with FILTER - use specific URI
            query = """
            SELECT ?s ?value WHERE {
                ?s <http://test.example.org/filter/value> ?value .
                FILTER(?value > 5)
            }
            ORDER BY ?value
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 4  # values 6, 7, 8, 9
            from rdflib.term import Variable

            value_var = Variable("value")
            assert int(results[0][value_var]) == 6
            assert int(results[-1][value_var]) == 9

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping FILTER test")

    def test_optional_clause(self, oxigraph_adapter):
        """Test SPARQL OPTIONAL clause."""
        try:
            g = Graph()
            g.bind("test", "http://test.example.org/")

            # Create entities with and without optional properties
            for i in range(5):
                subject = URIRef(f"http://test.example.org/entity{i}")
                g.add((subject, RDF.type, URIRef("http://test.example.org/Entity")))
                g.add((subject, URIRef("http://test.example.org/id"), Literal(i)))

                # Only add optional property for even numbers
                if i % 2 == 0:
                    g.add(
                        (
                            subject,
                            URIRef("http://test.example.org/optional"),
                            Literal(f"value{i}"),
                        )
                    )

            oxigraph_adapter.insert(g)

            query = """
            SELECT ?s ?id ?optional WHERE {
                ?s <http://test.example.org/id> ?id .
                OPTIONAL { ?s <http://test.example.org/optional> ?optional }
            }
            ORDER BY ?id
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 5
            # Check that optional values are present for even IDs
            for row in results:
                if int(row.id) % 2 == 0:
                    assert row.optional is not None
                else:
                    assert row.optional is None

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping OPTIONAL test")

    def test_union_clause(self, oxigraph_adapter):
        """Test SPARQL UNION clause."""
        try:
            g = Graph()
            g.bind("test", "http://test.example.org/")

            # Create different types of entities
            person = URIRef("http://test.example.org/person1")
            g.add((person, RDF.type, URIRef("http://test.example.org/Person")))
            g.add((person, URIRef("http://test.example.org/name"), Literal("Alice")))

            org = URIRef("http://test.example.org/org1")
            g.add((org, RDF.type, URIRef("http://test.example.org/Organization")))
            g.add((org, URIRef("http://test.example.org/title"), Literal("ACME Corp")))

            oxigraph_adapter.insert(g)

            query = """
            SELECT ?entity ?label WHERE {
                {
                    ?entity a <http://test.example.org/Person> .
                    ?entity <http://test.example.org/name> ?label .
                }
                UNION
                {
                    ?entity a <http://test.example.org/Organization> .
                    ?entity <http://test.example.org/title> ?label .
                }
            }
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 2
            labels = [str(row.label) for row in results]
            assert "Alice" in labels
            assert "ACME Corp" in labels

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping UNION test")

    def test_aggregation_functions(self, oxigraph_adapter):
        """Test SPARQL aggregation functions (COUNT, SUM, AVG, MIN, MAX)."""
        try:
            from rdflib.term import Variable

            g = Graph()
            g.bind("test", "http://test.example.org/agg/")

            values = [10, 20, 30, 40, 50]
            for i, val in enumerate(values):
                subject = URIRef(f"http://test.example.org/agg/item{i}")
                g.add(
                    (subject, URIRef("http://test.example.org/agg/value"), Literal(val))
                )

            oxigraph_adapter.insert(g)

            # Test COUNT, SUM, AVG, MIN, MAX
            query = """
            SELECT 
                (COUNT(?value) as ?count)
                (SUM(?value) as ?sum)
                (AVG(?value) as ?avg)
                (MIN(?value) as ?min)
                (MAX(?value) as ?max)
            WHERE {
                ?s <http://test.example.org/agg/value> ?value .
            }
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 1
            row = results[0]
            count_var = Variable("count")
            sum_var = Variable("sum")
            avg_var = Variable("avg")
            min_var = Variable("min")
            max_var = Variable("max")

            assert int(row[count_var]) == 5
            assert int(row[sum_var]) == 150
            assert int(row[avg_var]) == 30
            assert int(row[min_var]) == 10
            assert int(row[max_var]) == 50

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping aggregation test")

    def test_group_by_having(self, oxigraph_adapter):
        """Test SPARQL GROUP BY and HAVING clauses."""
        try:
            from rdflib.term import Variable

            g = Graph()
            g.bind("test", "http://test.example.org/groupby/")

            # Create categories with items
            categories = ["A", "B", "C"]
            for cat in categories:
                for i in range(3 if cat == "A" else 2 if cat == "B" else 1):
                    subject = URIRef(f"http://test.example.org/groupby/{cat}/item{i}")
                    g.add(
                        (
                            subject,
                            URIRef("http://test.example.org/groupby/category"),
                            Literal(cat),
                        )
                    )

            oxigraph_adapter.insert(g)

            query = """
            SELECT ?category (COUNT(?item) as ?count)
            WHERE {
                ?item <http://test.example.org/groupby/category> ?category .
            }
            GROUP BY ?category
            HAVING (COUNT(?item) > 1)
            ORDER BY DESC(?count)
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 2  # Only A and B have more than 1 item
            category_var = Variable("category")
            count_var = Variable("count")

            assert str(results[0][category_var]) == "A"
            assert int(results[0][count_var]) == 3
            assert str(results[1][category_var]) == "B"
            assert int(results[1][count_var]) == 2

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping GROUP BY test")

    def test_blank_nodes_are_filtered(self, oxigraph_adapter):
        """Test that blank nodes are filtered out during insert."""
        try:
            domain = uuid.uuid4()
            g = Graph()

            # Create a structure with blank nodes
            person = URIRef(f"http://{domain}/bnode/person1")
            address = BNode()

            g.add((person, RDF.type, URIRef(f"http://{domain}/bnode/Person")))
            g.add((person, URIRef(f"http://{domain}/bnode/hasAddress"), address))
            g.add(
                (
                    address,
                    URIRef(f"http://{domain}/bnode/street"),
                    Literal("123 Main St"),
                )
            )

            # Insert graph with blank nodes
            oxigraph_adapter.insert(g)

            # Query should only find the person type, not the address relationship
            query = f"""
            SELECT ?s ?p ?o WHERE {{
                ?s ?p ?o .
                FILTER(STRSTARTS(STR(?s), "http://{domain}/"))
            }}
            """
            results = list(oxigraph_adapter.query(query))

            # Should only have 1 triple (person rdf:type Person)
            # The blank node triples should have been filtered out
            assert len(results) == 1

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running")

    def test_special_characters_in_literals(self, oxigraph_adapter):
        """Test handling of special characters in literals."""
        try:
            g = Graph()
            g.bind("test", "http://test.example.org/")

            subject = URIRef("http://test.example.org/special")

            # Test various special characters
            special_strings = [
                'String with "quotes"',
                "String with 'apostrophes'",
                "String with\nnewlines",
                "String with\ttabs",
                "Unicode: 你好世界 🌍",
                "Emoji: 😀 👍 🎉",
                "Special chars: @#$%^&*()",
                "Backslash: \\test\\path",
            ]

            for i, text in enumerate(special_strings):
                g.add(
                    (subject, URIRef(f"http://test.example.org/prop{i}"), Literal(text))
                )

            oxigraph_adapter.insert(g)

            # Query back and verify
            query = """
            SELECT ?p ?o WHERE {
                <http://test.example.org/special> ?p ?o .
            }
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == len(special_strings)

            retrieved_values = [str(row.o) for row in results]
            for original in special_strings:
                assert original in retrieved_values

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping special characters test")

    def test_different_datatypes(self, oxigraph_adapter):
        """Test handling of different RDF datatypes."""
        try:
            from rdflib.namespace import XSD

            g = Graph()
            g.bind("test", "http://test.example.org/")

            subject = URIRef("http://test.example.org/datatypes")

            # Add different datatype literals
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/integer"),
                    Literal(42, datatype=XSD.integer),
                )
            )
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/float"),
                    Literal(3.14, datatype=XSD.float),
                )
            )
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/boolean"),
                    Literal(True, datatype=XSD.boolean),
                )
            )
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/date"),
                    Literal("2024-01-01", datatype=XSD.date),
                )
            )
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/string"),
                    Literal("test string", datatype=XSD.string),
                )
            )

            oxigraph_adapter.insert(g)

            # Query and verify datatypes are preserved
            query = """
            SELECT ?p ?o WHERE {
                <http://test.example.org/datatypes> ?p ?o .
            }
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 5

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping datatypes test")

    def test_language_tags(self, oxigraph_adapter):
        """Test handling of language-tagged literals."""
        try:
            g = Graph()
            g.bind("test", "http://test.example.org/")

            subject = URIRef("http://test.example.org/multilingual")

            # Add same property with different language tags
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/label"),
                    Literal("Hello", lang="en"),
                )
            )
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/label"),
                    Literal("Bonjour", lang="fr"),
                )
            )
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/label"),
                    Literal("Hola", lang="es"),
                )
            )
            g.add(
                (
                    subject,
                    URIRef("http://test.example.org/label"),
                    Literal("你好", lang="zh"),
                )
            )

            oxigraph_adapter.insert(g)

            # Query with language filter
            query = """
            SELECT ?label WHERE {
                <http://test.example.org/multilingual> <http://test.example.org/label> ?label .
                FILTER(LANG(?label) = "fr")
            }
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 1
            assert str(results[0].label) == "Bonjour"

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping language tags test")

    def test_property_paths(self, oxigraph_adapter):
        """Test SPARQL property paths."""
        try:
            g = Graph()
            g.bind("test", "http://test.example.org/")

            # Create a chain: A -> B -> C -> D
            for i in range(3):
                subject = URIRef(f"http://test.example.org/node{i}")
                obj = URIRef(f"http://test.example.org/node{i + 1}")
                g.add((subject, URIRef("http://test.example.org/next"), obj))

            oxigraph_adapter.insert(g)

            # Test property path with +
            query = """
            SELECT ?end WHERE {
                <http://test.example.org/node0> <http://test.example.org/next>+ ?end .
            }
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 3  # node1, node2, node3

            # Cleanup
            oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping property paths test")

    def test_describe_query(self, oxigraph_adapter, integration_graph):
        """Test DESCRIBE query."""
        try:
            oxigraph_adapter.insert(integration_graph)

            query = """
            DESCRIBE <http://test.example.org/integration_test>
            """
            result = oxigraph_adapter.query(query)

            assert isinstance(result, Graph)
            assert len(result) > 0

            # Cleanup
            oxigraph_adapter.remove(integration_graph)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping DESCRIBE test")

    def test_empty_graph_operations(self, oxigraph_adapter):
        """Test operations with empty graphs."""
        try:
            empty_graph = Graph()

            # Insert empty graph should not fail
            oxigraph_adapter.insert(empty_graph)

            # Remove empty graph should not fail
            oxigraph_adapter.remove(empty_graph)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping empty graph test")

    def test_update_operations(self, oxigraph_adapter):
        """Test SPARQL UPDATE operations."""
        try:
            g = Graph()
            g.bind("test", "http://test.example.org/")

            subject = URIRef("http://test.example.org/updatetest")
            g.add(
                (subject, URIRef("http://test.example.org/value"), Literal("initial"))
            )

            oxigraph_adapter.insert(g)

            # Update using SPARQL DELETE/INSERT
            update_query = """
            DELETE { <http://test.example.org/updatetest> <http://test.example.org/value> ?old }
            INSERT { <http://test.example.org/updatetest> <http://test.example.org/value> "updated" }
            WHERE { <http://test.example.org/updatetest> <http://test.example.org/value> ?old }
            """
            oxigraph_adapter.query(update_query)

            # Query to verify update
            query = """
            SELECT ?value WHERE {
                <http://test.example.org/updatetest> <http://test.example.org/value> ?value .
            }
            """
            results = list(oxigraph_adapter.query(query))

            assert len(results) == 1
            assert str(results[0].value) == "updated"

            # Cleanup - remove all
            cleanup_graph = Graph()
            cleanup_graph.add(
                (subject, URIRef("http://test.example.org/value"), Literal("updated"))
            )
            oxigraph_adapter.remove(cleanup_graph)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping UPDATE test")

    def test_batch_insertions(self, oxigraph_adapter):
        """Test multiple batch insertions."""
        try:
            from rdflib.term import Variable

            graphs = []

            # Create multiple graphs - use unique URI
            for batch in range(5):
                g = Graph()
                g.bind("test", "http://test.example.org/batches/")

                for i in range(100):
                    subject = URIRef(
                        f"http://test.example.org/batches/batch{batch}/item{i}"
                    )
                    g.add(
                        (
                            subject,
                            RDF.type,
                            URIRef("http://test.example.org/batches/Item"),
                        )
                    )
                    g.add(
                        (
                            subject,
                            URIRef("http://test.example.org/batches/batch"),
                            Literal(batch),
                        )
                    )

                graphs.append(g)
                oxigraph_adapter.insert(g)

            # Verify total count
            count_query = """
            SELECT (COUNT(*) as ?count) WHERE {
                ?s a <http://test.example.org/batches/Item> .
            }
            """
            results = list(oxigraph_adapter.query(count_query))
            count_var = Variable("count")
            assert int(results[0][count_var]) == 500  # 5 batches * 100 items

            # Cleanup
            for g in graphs:
                oxigraph_adapter.remove(g)

        except requests.exceptions.ConnectionError:
            pytest.skip("Oxigraph is not running - skipping batch insertions test")

    # @pytest.mark.integration
    # def test_full_workflow(self, oxigraph_adapter, integration_graph):
    #     """Test complete workflow: insert, query, get subject, remove."""
    #     try:
    #         # Insert test data
    #         oxigraph_adapter.insert(integration_graph)

    #         # Query for the data
    #         query = """
    #         SELECT ?s ?p ?o WHERE {
    #             ?s <http://test.example.org/testProperty> ?o
    #         }
    #         """
    #         results = list(oxigraph_adapter.query(query))
    #         assert len(results) == 1

    #         # Get subject graph
    #         subject = URIRef("http://test.example.org/integration_test")
    #         subject_graph = oxigraph_adapter.get_subject_graph(subject)
    #         assert len(subject_graph) == 2  # type and testProperty

    #         # Remove the data
    #         oxigraph_adapter.remove(integration_graph)

    #         # Verify removal
    #         results_after_remove = list(oxigraph_adapter.query(query))
    #         assert len(results_after_remove) == 0

    #     except requests.exceptions.ConnectionError:
    #         pytest.skip("Oxigraph is not running - skipping integration test")

    # @pytest.mark.integration
    # def test_large_dataset_performance(self, oxigraph_adapter):
    #     """Test performance with larger datasets."""
    #     try:
    #         # Create a larger test dataset
    #         large_graph = Graph()
    #         large_graph.bind("perf", "http://performance.test.org/")

    #         # Add 1000 triples
    #         for i in range(1000):
    #             subject = URIRef(f"http://performance.test.org/entity{i}")
    #             large_graph.add((subject, RDF.type, URIRef("http://performance.test.org/Entity")))
    #             large_graph.add((subject, URIRef("http://performance.test.org/id"), Literal(i)))

    #         # Measure insert time
    #         start_time = time.time()
    #         oxigraph_adapter.insert(large_graph)
    #         insert_time = time.time() - start_time

    #         # Insert should complete in reasonable time (Oxigraph is fast!)
    #         assert insert_time < 5.0, f"Insert took too long: {insert_time}s"

    #         # Test query performance
    #         start_time = time.time()
    #         results = list(oxigraph_adapter.query("SELECT ?s WHERE { ?s a <http://performance.test.org/Entity> }"))
    #         query_time = time.time() - start_time

    #         assert len(results) == 1000
    #         assert query_time < 2.0, f"Query took too long: {query_time}s"

    #         # Test COUNT query performance
    #         start_time = time.time()
    #         count_results = list(oxigraph_adapter.query("SELECT (COUNT(*) as ?count) WHERE { ?s a <http://performance.test.org/Entity> }"))
    #         count_time = time.time() - start_time

    #         assert len(count_results) == 1
    #         assert int(count_results[0].count) == 1000
    #         assert count_time < 1.0, f"Count query took too long: {count_time}s"

    #         # Clean up
    #         oxigraph_adapter.remove(large_graph)

    #     except requests.exceptions.ConnectionError:
    #         pytest.skip("Oxigraph is not running - skipping performance test")

    # @pytest.mark.integration
    # def test_concurrent_operations(self, oxigraph_adapter):
    #     """Test concurrent insert and query operations."""
    #     try:
    #         import concurrent.futures

    #         def insert_data(thread_id):
    #             """Insert data in a separate thread."""
    #             graph = Graph()
    #             for i in range(100):
    #                 subject = URIRef(f"http://concurrent.test.org/thread{thread_id}/entity{i}")
    #                 graph.add((subject, RDF.type, URIRef("http://concurrent.test.org/Entity")))
    #                 graph.add((subject, URIRef("http://concurrent.test.org/threadId"), Literal(thread_id)))
    #             oxigraph_adapter.insert(graph)
    #             return thread_id

    #         # Run multiple insert operations concurrently
    #         with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    #             futures = [executor.submit(insert_data, i) for i in range(3)]
    #             results = [future.result() for future in concurrent.futures.as_completed(futures)]

    #         assert len(results) == 3

    #         # Verify all data was inserted correctly
    #         total_results = list(oxigraph_adapter.query(
    #             "SELECT ?s WHERE { ?s a <http://concurrent.test.org/Entity> }"
    #         ))
    #         assert len(total_results) == 300  # 3 threads × 100 entities each

    #         # Clean up
    #         cleanup_graph = Graph()
    #         for result in total_results:
    #             subject_graph = oxigraph_adapter.get_subject_graph(result.s)
    #             cleanup_graph += subject_graph
    #         oxigraph_adapter.remove(cleanup_graph)

    #     except requests.exceptions.ConnectionError:
    #         pytest.skip("Oxigraph is not running - skipping concurrent test")

    # @pytest.mark.integration
    # def test_complex_sparql_queries(self, oxigraph_adapter):
    #     """Test complex SPARQL queries with various features."""
    #     try:
    #         # Setup test data
    #         test_graph = Graph()
    #         test_graph.bind("test", "http://complex.test.org/")

    #         # Create hierarchical data
    #         for i in range(5):
    #             person = URIRef(f"http://complex.test.org/person{i}")
    #             test_graph.add((person, RDF.type, URIRef("http://complex.test.org/Person")))
    #             test_graph.add((person, URIRef("http://complex.test.org/name"), Literal(f"Person {i}")))
    #             test_graph.add((person, URIRef("http://complex.test.org/age"), Literal(20 + i)))

    #             if i > 0:
    #                 friend = URIRef(f"http://complex.test.org/person{i-1}")
    #                 test_graph.add((person, URIRef("http://complex.test.org/knows"), friend))

    #         oxigraph_adapter.insert(test_graph)

    #         # Test FILTER query
    #         filter_results = list(oxigraph_adapter.query("""
    #             PREFIX test: <http://complex.test.org/>
    #             SELECT ?person ?age WHERE {
    #                 ?person a test:Person ;
    #                         test:age ?age .
    #                 FILTER(?age > 22)
    #             }
    #             ORDER BY ?age
    #         """))

    #         assert len(filter_results) == 2  # persons with age > 22

    #         # Test OPTIONAL query
    #         optional_results = list(oxigraph_adapter.query("""
    #             PREFIX test: <http://complex.test.org/>
    #             SELECT ?person ?name ?friend WHERE {
    #                 ?person a test:Person ;
    #                         test:name ?name .
    #                 OPTIONAL { ?person test:knows ?friend }
    #             }
    #             ORDER BY ?name
    #         """))

    #         assert len(optional_results) == 5  # All persons

    #         # Test GROUP BY and COUNT
    #         group_results = list(oxigraph_adapter.query("""
    #             PREFIX test: <http://complex.test.org/>
    #             SELECT (COUNT(?friend) as ?friendCount) WHERE {
    #                 ?person a test:Person .
    #                 OPTIONAL { ?person test:knows ?friend }
    #             }
    #         """))

    #         assert len(group_results) == 1
    #         assert int(group_results[0].friendCount) == 4  # Total friendship connections

    #         # Clean up
    #         oxigraph_adapter.remove(test_graph)

    #     except requests.exceptions.ConnectionError:
    #         pytest.skip("Oxigraph is not running - skipping complex query test")


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"])
