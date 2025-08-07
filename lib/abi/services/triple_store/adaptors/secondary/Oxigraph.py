"""
Oxigraph Triple Store Adapter

This module provides an adapter for connecting to Oxigraph graph database instances,
enabling lightweight, high-performance RDF triple storage and SPARQL querying capabilities.

Features:
- Direct HTTP/REST API connection to Oxigraph
- Full SPARQL 1.1 query and update operations
- Named graph support
- RDFLib integration for seamless graph operations
- Minimal resource footprint, ideal for development and Apple Silicon

Classes:
    Oxigraph: Triple store adapter for Oxigraph instances

Example:
    >>> oxigraph = Oxigraph(
    ...     oxigraph_url="http://localhost:7878"
    ... )
    >>>
    >>> # Insert RDF triples
    >>> graph = Graph()
    >>> graph.add((URIRef("http://example.org/person1"),
    ...           RDF.type,
    ...           URIRef("http://example.org/Person")))
    >>> oxigraph.insert(graph)
    >>>
    >>> # Query the data
    >>> results = oxigraph.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o }")

Author: ABI Project
License: MIT
"""

from abi.services.triple_store.TripleStorePorts import ITripleStorePort, OntologyEvent
from rdflib import Graph, URIRef
import rdflib
from typing import Tuple, Union
import requests
import logging

logger = logging.getLogger(__name__)


class Oxigraph(ITripleStorePort):
    """
    Oxigraph Triple Store Adapter

    This adapter provides a connection to Oxigraph graph database instances,
    enabling storage and querying of RDF triples using SPARQL. It implements
    the ITripleStorePort interface for seamless integration with the triple
    store service.

    The adapter handles:
    - HTTP REST API communication with Oxigraph
    - SPARQL query and update operations
    - RDFLib Graph integration
    - Content negotiation for different RDF formats

    Attributes:
        oxigraph_url (str): Base URL of the Oxigraph instance
        query_endpoint (str): SPARQL query endpoint URL
        update_endpoint (str): SPARQL update endpoint URL
        store_endpoint (str): RDF store endpoint URL
        timeout (int): HTTP request timeout in seconds

    Example:
        >>> oxigraph = Oxigraph(
        ...     oxigraph_url="http://localhost:7878"
        ... )
        >>>
        >>> # Create and insert triples
        >>> from rdflib import Graph, URIRef, RDF, Literal
        >>> g = Graph()
        >>> g.add((URIRef("http://example.org/alice"),
        ...        RDF.type,
        ...        URIRef("http://example.org/Person")))
        >>> g.add((URIRef("http://example.org/alice"),
        ...        URIRef("http://example.org/name"),
        ...        Literal("Alice")))
        >>> oxigraph.insert(g)
        >>>
        >>> # Query the data
        >>> result = oxigraph.query('''
        ...     SELECT ?person ?name WHERE {
        ...         ?person a <http://example.org/Person> .
        ...         ?person <http://example.org/name> ?name .
        ...     }
        ... ''')
        >>> for row in result:
        ...     print(f"Person: {row.person}, Name: {row.name}")
    """

    def __init__(
        self,
        oxigraph_url: str = "http://localhost:7878",
        timeout: int = 60
    ):
        """
        Initialize Oxigraph adapter.

        Args:
            oxigraph_url (str): Base URL of the Oxigraph instance.
                Defaults to "http://localhost:7878"
            timeout (int): Request timeout in seconds. Defaults to 60

        Raises:
            requests.exceptions.ConnectionError: If Oxigraph is not accessible
        """
        self.oxigraph_url = oxigraph_url.rstrip('/')
        self.query_endpoint = f"{self.oxigraph_url}/query"
        self.update_endpoint = f"{self.oxigraph_url}/update"
        self.store_endpoint = f"{self.oxigraph_url}/store"
        self.timeout = timeout
        
        # Test connection
        self._test_connection()
        
        logger.info(f"Oxigraph adapter initialized with endpoint: {self.oxigraph_url}")

    def _test_connection(self):
        """
        Test if Oxigraph is accessible.
        
        Raises:
            requests.exceptions.ConnectionError: If Oxigraph is not accessible
        """
        try:
            response = requests.get(
                self.query_endpoint,
                params={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"},
                timeout=self.timeout
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to connect to Oxigraph at {self.oxigraph_url}: {e}")
            raise

    def insert(self, triples: Graph):
        """
        Insert RDF triples into Oxigraph.

        This method converts an RDFLib Graph into a SPARQL INSERT DATA query
        and sends it to Oxigraph via the update endpoint.

        Args:
            triples (Graph): RDFLib Graph containing triples to insert

        Raises:
            requests.exceptions.HTTPError: If the insert operation fails
            requests.exceptions.Timeout: If the request times out
        """
        if len(triples) == 0:
            return
            
        # Build INSERT DATA query
        insert_query = "INSERT DATA {\n"
        for s, p, o in triples:
            insert_query += f"  {s.n3()} {p.n3()} {o.n3()} .\n"
        insert_query += "}"
        
        response = requests.post(
            self.update_endpoint,
            headers={
                "Content-Type": "application/sparql-update"
            },
            data=insert_query,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        logger.debug(f"Inserted {len(triples)} triples into Oxigraph")

    def remove(self, triples: Graph):
        """
        Remove RDF triples from Oxigraph.

        This method constructs a SPARQL DELETE DATA query from the provided
        graph and executes it against Oxigraph.

        Args:
            triples (Graph): RDFLib Graph containing triples to remove

        Raises:
            requests.exceptions.HTTPError: If the remove operation fails
        """
        # Build DELETE DATA query
        delete_query = "DELETE DATA {\n"
        for s, p, o in triples:
            delete_query += f"  {s.n3()} {p.n3()} {o.n3()} .\n"
        delete_query += "}"
        
        response = requests.post(
            self.update_endpoint,
            headers={
                "Content-Type": "application/sparql-update"
            },
            data=delete_query,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        logger.debug(f"Removed {len(triples)} triples from Oxigraph")

    def get(self) -> Graph:
        """
        Retrieve all triples from Oxigraph as an RDFLib Graph.

        Warning:
            This operation can be expensive for large datasets as it retrieves
            ALL triples from the database. Consider using query() with specific
            patterns for better performance.

        Returns:
            Graph: RDFLib Graph containing all triples from Oxigraph

        Raises:
            requests.exceptions.HTTPError: If the query fails
        """
        response = requests.get(
            self.store_endpoint,
            headers={"Accept": "text/turtle"},
            timeout=self.timeout
        )
        
        response.raise_for_status()
        
        graph = Graph()
        graph.parse(data=response.text, format='turtle')
        return graph

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        """
        Handle ontology change events for views.

        Note:
            This method is part of the ITripleStorePort interface but is
            currently not implemented for Oxigraph. Override this method
            in a subclass if you need custom event handling.

        Args:
            view: View pattern (subject, predicate, object)
            event: Type of event (INSERT or DELETE)
            triple: The actual triple that triggered the event
        """
        pass

    def query(self, query: str) -> rdflib.query.Result:  # type: ignore
        """
        Execute a SPARQL query against Oxigraph.

        This method submits SPARQL queries (SELECT, CONSTRUCT, ASK, DESCRIBE)
        or updates (INSERT, DELETE, UPDATE) to Oxigraph and returns the results.

        Args:
            query (str): SPARQL query string

        Returns:
            rdflib.query.Result: Query results that can be iterated over

        Raises:
            requests.exceptions.HTTPError: If the query fails
            ValueError: If query type cannot be determined

        Example:
            >>> # SELECT query
            >>> result = oxigraph.query('''
            ...     SELECT ?person ?name WHERE {
            ...         ?person a <http://example.org/Person> .
            ...         ?person <http://example.org/name> ?name .
            ...     }
            ... ''')
            >>> for row in result:
            ...     print(f"Person: {row.person}, Name: {row.name}")
        """
        # Determine if this is a query or update
        query_upper = query.strip().upper()
        is_update = any(query_upper.startswith(cmd) for cmd in [
            "INSERT", "DELETE", "CREATE", "DROP", "CLEAR", "LOAD", "COPY", "MOVE", "ADD"
        ])
        
        if is_update:
            # SPARQL Update
            response = requests.post(
                self.update_endpoint,
                headers={
                    "Content-Type": "application/sparql-update"
                },
                data=query,
                timeout=self.timeout
            )
        else:
            # SPARQL Query
            response = requests.post(
                self.query_endpoint,
                headers={
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json,application/n-triples"
                },
                data=query,
                timeout=self.timeout
            )
        
        response.raise_for_status()
        
        if is_update:
            # For updates, return an empty result
            return rdflib.query.Result('SELECT')
        
        # Parse the results based on content type
        content_type = response.headers.get('Content-Type', '')
        
        if 'sparql-results' in content_type:
            # SELECT or ASK query - parse JSON results
            import json
            result_data = json.loads(response.text)
            
            # Create a result wrapper that's compatible with RDFLib's ResultRow
            from rdflib.query import ResultRow
            from rdflib.term import URIRef, Literal, BNode, Variable
            
            # Extract variables
            vars = result_data.get('head', {}).get('vars', [])
            bindings = result_data.get('results', {}).get('bindings', [])
            
            # Convert variable names to Variable objects
            var_objects = [Variable(var) for var in vars]
            
            # Convert bindings to result rows
            results = []
            
            for binding in bindings:
                row_values = {}
                
                for var in vars:
                    var_obj = Variable(var)
                    
                    if var in binding:
                        binding_info = binding[var]
                        value_str = binding_info['value']
                        binding_type = binding_info.get('type', 'literal')
                        
                        # Convert to appropriate RDFLib term
                        value: Union[URIRef, BNode, Literal, None]
                        if binding_type == 'uri':
                            value = URIRef(value_str)
                        elif binding_type == 'bnode':
                            value = BNode(value_str)
                        else:  # literal
                            datatype = binding_info.get('datatype')
                            lang = binding_info.get('xml:lang')
                            
                            if datatype:
                                # Handle numeric datatypes
                                if datatype in ['http://www.w3.org/2001/XMLSchema#integer', 
                                              'http://www.w3.org/2001/XMLSchema#long']:
                                    try:
                                        value = Literal(int(value_str), datatype=URIRef(datatype))
                                    except ValueError:
                                        value = Literal(value_str, datatype=URIRef(datatype))
                                else:
                                    value = Literal(value_str, datatype=URIRef(datatype))
                            elif lang:
                                value = Literal(value_str, lang=lang)
                            else:
                                value = Literal(value_str)
                        
                        row_values[var_obj] = value
                    else:
                        row_values[var_obj] = None  # type: ignore
                
                # Create a ResultRow compatible object
                row = ResultRow(row_values, var_objects)
                results.append(row)
            
            # Return an iterable result
            return iter(results)  # type: ignore
        elif 'n-triples' in content_type or 'turtle' in content_type:
            # CONSTRUCT or DESCRIBE query
            graph = Graph()
            format_type = 'nt' if 'n-triples' in content_type else 'turtle'
            graph.parse(data=response.text, format=format_type)
            return graph  # type: ignore
        else:
            raise ValueError(f"Unexpected content type: {content_type}")

    def query_view(self, view: str, query: str) -> rdflib.query.Result:  # type: ignore
        """
        Execute a SPARQL query against a specific view.

        Note:
            This implementation currently ignores the view parameter and
            executes the query against the entire dataset. Override this
            method if you need view-specific querying behavior.

        Args:
            view (str): View identifier (currently ignored)
            query (str): SPARQL query string

        Returns:
            rdflib.query.Result: Query results
        """
        return self.query(query)

    def get_subject_graph(self, subject: URIRef) -> Graph:
        """
        Get all triples for a specific subject as an RDFLib Graph.

        Args:
            subject (URIRef): The subject URI to get triples for

        Returns:
            Graph: RDFLib Graph containing all triples for the subject

        Example:
            >>> alice_uri = URIRef("http://example.org/alice")
            >>> alice_graph = oxigraph.get_subject_graph(alice_uri)
            >>> print(f"Alice has {len(alice_graph)} properties")
        """
        query = f"""
        CONSTRUCT {{ <{str(subject)}> ?p ?o }}
        WHERE {{ <{str(subject)}> ?p ?o }}
        """
        
        result = self.query(query)
        
        if isinstance(result, Graph):
            return result
        else:
            # If query returns non-graph result, create empty graph
            return Graph()


if __name__ == "__main__":
    """
    Example usage and interactive testing for Oxigraph adapter.
    
    Usage:
        python Oxigraph.py
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Initialize Oxigraph adapter
    oxigraph_url = os.getenv("OXIGRAPH_URL", "http://localhost:7878")
    
    print(f"Connecting to Oxigraph at {oxigraph_url}")
    
    try:
        adapter = Oxigraph(oxigraph_url=oxigraph_url)
        print("✓ Connected successfully")
        
        # Test operations
        print("\nTesting basic operations...")
        
        # Create test data
        test_graph = Graph()
        test_subject = URIRef("http://example.org/test/person1")
        test_graph.add((test_subject, rdflib.RDF.type, URIRef("http://example.org/Person")))
        test_graph.add((test_subject, URIRef("http://example.org/name"), rdflib.Literal("Test Person")))
        
        # Insert
        print("- Inserting test data...")
        adapter.insert(test_graph)
        print("  ✓ Insert successful")
        
        # Query
        print("- Querying data...")
        result = adapter.query("SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }")
        for row in result:  # type: ignore
            print(f"  Total triples: {row.count}")  # type: ignore
        
        # Get subject graph
        print("- Getting subject graph...")
        subject_graph = adapter.get_subject_graph(test_subject)
        print(f"  Subject has {len(subject_graph)} triples")
        
        # Clean up
        print("- Removing test data...")
        adapter.remove(test_graph)
        print("  ✓ Remove successful")
        
        print("\n✓ All tests passed!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("Make sure Oxigraph is running and accessible")