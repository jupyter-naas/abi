"""
AWS Neptune Triple Store Adapter

This module provides adapters for connecting to AWS Neptune graph database instances,
enabling high-performance RDF triple storage and SPARQL querying capabilities for
semantic data applications.

Features:
- Direct connection to AWS Neptune instances
- SSH tunnel support for VPC-deployed Neptune instances
- AWS IAM authentication with SigV4 signing
- Named graph support and management
- Full SPARQL query and update operations
- RDFLib integration for seamless graph operations

Classes:
    AWSNeptune: Basic Neptune adapter for direct connections
    AWSNeptuneSSHTunnel: Neptune adapter with SSH tunnel support for VPC deployments

Example:
    Basic Neptune connection:

    >>> neptune = AWSNeptune(
    ...     aws_region_name="us-east-1",
    ...     aws_access_key_id="AKIA...",
    ...     aws_secret_access_key="...",
    ...     db_instance_identifier="my-neptune-instance"
    ... )
    >>>
    >>> # Insert RDF triples
    >>> graph = Graph()
    >>> graph.add((URIRef("http://example.org/person1"),
    ...           RDF.type,
    ...           URIRef("http://example.org/Person")))
    >>> neptune.insert(graph)
    >>>
    >>> # Query the data
    >>> results = neptune.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o }")

    SSH tunnel connection for VPC-deployed Neptune:

    >>> neptune_ssh = AWSNeptuneSSHTunnel(
    ...     aws_region_name="us-east-1",
    ...     aws_access_key_id="AKIA...",
    ...     aws_secret_access_key="...",
    ...     db_instance_identifier="my-vpc-neptune-instance",
    ...     bastion_host="bastion.example.com",
    ...     bastion_port=22,
    ...     bastion_user="ubuntu",
    ...     bastion_private_key="-----BEGIN RSA PRIVATE KEY-----\\n..."
    ... )

Dependencies:
    - boto3: AWS SDK for Python
    - botocore: Core AWS functionality
    - requests: HTTP client for SPARQL endpoints
    - rdflib: RDF graph processing
    - paramiko: SSH client (for tunnel support)
    - sshtunnel: SSH tunnel management (for tunnel support)

Author: Maxime Jublou <maxime@naas.ai>
License: MIT
"""

from abi.services.triple_store.TripleStoreService import ITripleStorePort

import boto3
import botocore
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from rdflib import Graph, URIRef
from abi.services.triple_store.TripleStorePorts import OntologyEvent
from io import StringIO
import rdflib
from typing import Tuple, Any, overload, TYPE_CHECKING
import tempfile
import socket

# Import SSH dependencies only when needed for type checking
if TYPE_CHECKING:
    from sshtunnel import SSHTunnelForwarder

from rdflib.plugins.sparql.results.xmlresults import XMLResultParser
from rdflib.plugins.sparql.results.rdfresults import RDFResultParser
from rdflib.query import ResultParser
from rdflib.query import ResultRow
from rdflib.term import Identifier
from rdflib.namespace import _NAMESPACE_PREFIXES_RDFLIB, _NAMESPACE_PREFIXES_CORE

from SPARQLWrapper import SPARQLWrapper

from enum import Enum

ORIGINAL_GETADDRINFO = socket.getaddrinfo

NEPTUNE_DEFAULT_GRAPH_NAME: URIRef = URIRef(
    "http://aws.amazon.com/neptune/vocab/v01/DefaultNamedGraph"
)


class QueryType(Enum):
    """SPARQL query types supported by Neptune."""

    INSERT_DATA = "INSERT DATA"
    DELETE_DATA = "DELETE DATA"


class QueryMode(Enum):
    """SPARQL operation modes for Neptune endpoint."""

    QUERY = "query"
    UPDATE = "update"


class AWSNeptune(ITripleStorePort):
    """
    AWS Neptune Triple Store Adapter

    This adapter provides a connection to AWS Neptune graph database instances,
    enabling storage and querying of RDF triples using SPARQL. It implements
    the ITripleStorePort interface for seamless integration with the triple
    store service.

    The adapter handles:
    - AWS IAM authentication with SigV4 signing
    - Automatic Neptune endpoint discovery
    - SPARQL query and update operations
    - Named graph management
    - RDFLib Graph integration

    Attributes:
        aws_region_name (str): AWS region where Neptune instance is deployed
        aws_access_key_id (str): AWS access key for authentication
        aws_secret_access_key (str): AWS secret key for authentication
        db_instance_identifier (str): Neptune database instance identifier
        neptune_sparql_endpoint (str): Auto-discovered Neptune SPARQL endpoint
        neptune_port (int): Neptune instance port
        neptune_sparql_url (str): Full SPARQL endpoint URL
        default_graph_name (URIRef): Default named graph for operations

    Example:
        >>> neptune = AWSNeptune(
        ...     aws_region_name="us-east-1",
        ...     aws_access_key_id="AKIA1234567890EXAMPLE",
        ...     aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ...     db_instance_identifier="my-neptune-db"
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
        >>> neptune.insert(g)
        >>>
        >>> # Query the data
        >>> result = neptune.query('''
        ...     SELECT ?person ?name WHERE {
        ...         ?person a <http://example.org/Person> .
        ...         ?person <http://example.org/name> ?name .
        ...     }
        ... ''')
        >>> for row in result:
        ...     print(f"Person: {row.person}, Name: {row.name}")
        >>>
        >>> # Get all triples for a specific subject
        >>> alice_graph = neptune.get_subject_graph(URIRef("http://example.org/alice"))
        >>> print(f"Alice has {len(alice_graph)} triples")
    """

    aws_region_name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    db_instance_identifier: str

    bastion_host: str
    bastion_port: int
    bastion_user: str

    neptune_sparql_endpoint: str
    neptune_port: int
    neptune_sparql_url: str

    credentials: botocore.credentials.Credentials

    # SSH tunnel to the Bastion host
    tunnel: 'SSHTunnelForwarder'

    default_graph_name: URIRef

    def __init__(
        self,
        aws_region_name: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        db_instance_identifier: str,
        default_graph_name: URIRef = NEPTUNE_DEFAULT_GRAPH_NAME,
    ):
        """
        Initialize AWS Neptune adapter.

        This constructor establishes a connection to the specified Neptune instance
        by discovering the endpoint through AWS APIs and setting up authentication.

        Args:
            aws_region_name (str): AWS region name (e.g., 'us-east-1', 'eu-west-1')
            aws_access_key_id (str): AWS access key ID for authentication
            aws_secret_access_key (str): AWS secret access key for authentication
            db_instance_identifier (str): Neptune database instance identifier
            default_graph_name (URIRef, optional): Default named graph URI.
                Defaults to Neptune's default graph.

        Raises:
            AssertionError: If any required parameter is not a string
            botocore.exceptions.ClientError: If AWS credentials are invalid or
                Neptune instance cannot be found
            botocore.exceptions.NoCredentialsError: If AWS credentials are missing

        Example:
            >>> neptune = AWSNeptune(
            ...     aws_region_name="us-east-1",
            ...     aws_access_key_id="AKIA1234567890EXAMPLE",
            ...     aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            ...     db_instance_identifier="my-neptune-cluster"
            ... )
        """
        assert isinstance(aws_region_name, str)
        assert isinstance(aws_access_key_id, str)
        assert isinstance(aws_secret_access_key, str)
        assert isinstance(db_instance_identifier, str)

        self.aws_region_name = aws_region_name

        self.session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region_name,
        )

        self.db_instance_identifier = db_instance_identifier

        self.client = self.session.client("neptune", region_name=self.aws_region_name)

        cluster_endpoints = self.client.describe_db_instances(
            DBInstanceIdentifier=self.db_instance_identifier
        )["DBInstances"]
        self.neptune_sparql_endpoint = cluster_endpoints[0]["Endpoint"]["Address"]

        self.neptune_port = cluster_endpoints[0]["Endpoint"]["Port"]

        self.credentials = self.session.get_credentials()

        self.neptune_sparql_url = (
            f"https://{self.neptune_sparql_endpoint}:{self.neptune_port}/sparql"
        )

        self.default_graph_name = default_graph_name

    def __get_signed_headers(
        self,
        method: str,
        url: str,
        data: Any | None = None,
        params: Any | None = None,
        headers: Any | None = None,
    ):
        """
        Generate AWS SigV4 signed headers for Neptune authentication.

        This method creates the necessary authentication headers for making
        requests to AWS Neptune using AWS Identity and Access Management (IAM)
        credentials and the SigV4 signing process.

        Args:
            method (str): HTTP method (e.g., 'GET', 'POST')
            url (str): The target URL for the request
            data (Any, optional): Request body data
            params (Any, optional): URL parameters
            headers (Any, optional): Additional headers to include

        Returns:
            dict: Dictionary containing signed headers for AWS authentication

        Note:
            This is an internal method used by submit_query() and should not
            be called directly by users of the adapter.
        """
        request = AWSRequest(
            method=method, url=url, data=data, params=params, headers=headers
        )
        SigV4Auth(
            self.credentials, "neptune-db", region_name=self.aws_region_name
        ).add_auth(request)
        return request.headers

    def submit_query(self, data: Any, timeout: int = 60) -> requests.Response:
        """
        Submit a SPARQL query or update to the Neptune endpoint.

        This method handles the low-level communication with Neptune, including
        authentication, proper headers, and error handling.

        Args:
            data (Any): Query data containing either 'query' or 'update' key
                with the SPARQL statement as the value
            timeout (int, optional): Request timeout in seconds. Defaults to 60.

        Returns:
            requests.Response: HTTP response from Neptune endpoint

        Raises:
            requests.exceptions.HTTPError: If the HTTP request fails
            requests.exceptions.Timeout: If the request times out
            requests.exceptions.ConnectionError: If connection fails

        Example:
            >>> # This is typically called internally by other methods
            >>> response = neptune.submit_query({'query': 'SELECT ?s ?p ?o WHERE { ?s ?p ?o }'})
            >>> print(response.status_code)  # Should be 200 for success
        """
        headers = {}
        headers["Accept"] = "application/sparql-results+xml"
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        headers = self.__get_signed_headers(
            "POST",
            self.neptune_sparql_url,
            data=data,
            headers=headers,
        )

        response = requests.post(
            self.neptune_sparql_url,
            headers=headers,
            timeout=timeout,
            verify=True,
            data=data,
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(response.text)
            raise e

        return response

    @overload
    def insert(self, triples: Graph, graph_name: URIRef): ...
    @overload
    def insert(self, triples: Graph): ...

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        """
        Insert RDF triples into Neptune.

        This method converts an RDFLib Graph into SPARQL INSERT DATA statements
        and executes them against Neptune. The triples are inserted into the
        specified named graph or the default graph if none is provided.

        Args:
            triples (Graph): RDFLib Graph containing triples to insert
            graph_name (URIRef, optional): Named graph URI to insert into.
                If None, uses the default graph.

        Returns:
            requests.Response: HTTP response from Neptune

        Raises:
            requests.exceptions.HTTPError: If the insert operation fails

        Example:
            >>> from rdflib import Graph, URIRef, RDF, Literal
            >>> g = Graph()
            >>> g.add((URIRef("http://example.org/alice"),
            ...        RDF.type,
            ...        URIRef("http://example.org/Person")))
            >>> g.add((URIRef("http://example.org/alice"),
            ...        URIRef("http://example.org/name"),
            ...        Literal("Alice")))
            >>>
            >>> # Insert into default graph
            >>> neptune.insert(g)
            >>>
            >>> # Insert into specific named graph
            >>> custom_graph = URIRef("http://example.org/graph/people")
            >>> neptune.insert(g, custom_graph)
        """
        if graph_name is None:
            graph_name = self.default_graph_name

        query = self.graph_to_query(triples, QueryType.INSERT_DATA, graph_name)

        response = self.submit_query({QueryMode.UPDATE.value: query})
        return response

    @overload
    def remove(self, triples: Graph, graph_name: URIRef): ...
    @overload
    def remove(self, triples: Graph): ...

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        """
        Remove RDF triples from Neptune.

        This method converts an RDFLib Graph into SPARQL DELETE DATA statements
        and executes them against Neptune. Only exact matching triples will be
        removed from the specified named graph.

        Args:
            triples (Graph): RDFLib Graph containing triples to remove
            graph_name (URIRef, optional): Named graph URI to remove from.
                If None, uses the default graph.

        Returns:
            requests.Response: HTTP response from Neptune

        Raises:
            requests.exceptions.HTTPError: If the remove operation fails

        Example:
            >>> from rdflib import Graph, URIRef, RDF, Literal
            >>> g = Graph()
            >>> g.add((URIRef("http://example.org/alice"),
            ...        URIRef("http://example.org/name"),
            ...        Literal("Alice")))
            >>>
            >>> # Remove from default graph
            >>> neptune.remove(g)
            >>>
            >>> # Remove from specific named graph
            >>> custom_graph = URIRef("http://example.org/graph/people")
            >>> neptune.remove(g, custom_graph)
        """
        if graph_name is None:
            graph_name = self.default_graph_name
        query = self.graph_to_query(triples, QueryType.DELETE_DATA, graph_name)
        response = self.submit_query({"update": query})
        return response

    def get(self) -> Graph:
        """
        Retrieve all triples from Neptune as an RDFLib Graph.

        This method executes a SPARQL SELECT query to fetch all triples
        from Neptune and constructs an RDFLib Graph from the results.

        Warning:
            This operation can be expensive for large datasets as it retrieves
            ALL triples from the database. Consider using query() with specific
            patterns for better performance on large graphs.

        Returns:
            Graph: RDFLib Graph containing all triples from Neptune

        Raises:
            requests.exceptions.HTTPError: If the query fails

        Example:
            >>> # Get all triples (use carefully with large datasets)
            >>> all_triples = neptune.get()
            >>> print(f"Total triples: {len(all_triples)}")
            >>>
            >>> # Iterate through triples
            >>> for subject, predicate, obj in all_triples:
            ...     print(f"{subject} {predicate} {obj}")
        """
        response = self.submit_query(
            {QueryMode.QUERY.value: "select ?s ?p ?o where {?s ?p ?o}"}
        )
        result = XMLResultParser().parse(StringIO(response.text))

        graph = Graph()
        for row in result:
            assert isinstance(row, ResultRow)

            s: Identifier | None = row.get("s")
            p: Identifier | None = row.get("p")
            o: Identifier | None = row.get("o")

            assert s is not None and p is not None and o is not None
            

            graph.add((s, p, o))

        return graph

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        """
        Handle ontology change events for views.

        This method is called when ontology events occur that match registered
        view patterns. Currently, this is a no-op implementation that can be
        extended for custom event handling.

        Args:
            view (Tuple[URIRef | None, URIRef | None, URIRef | None]):
                View pattern (subject, predicate, object) where None matches any
            event (OntologyEvent): Type of event (INSERT or DELETE)
            triple (Tuple[URIRef | None, URIRef | None, URIRef | None]):
                The actual triple that triggered the event

        Note:
            This method is part of the ITripleStorePort interface but is
            currently not implemented for Neptune. Override this method
            in a subclass if you need custom event handling.
        """
        pass

    def query(
        self, query: str, query_mode: QueryMode = QueryMode.QUERY
    ) -> rdflib.query.Result:
        """
        Execute a SPARQL query against Neptune.

        This method submits SPARQL queries (SELECT, CONSTRUCT, ASK, DESCRIBE)
        or updates (INSERT, DELETE, UPDATE) to Neptune and returns the results.

        Args:
            query (str): SPARQL query string
            query_mode (QueryMode, optional): Whether this is a query or update
                operation. Defaults to QueryMode.QUERY.

        Returns:
            rdflib.query.Result: Query results that can be iterated over

        Raises:
            requests.exceptions.HTTPError: If the query fails
            Exception: If result parsing fails

        Example:
            >>> # SELECT query
            >>> result = neptune.query('''
            ...     SELECT ?person ?name WHERE {
            ...         ?person a <http://example.org/Person> .
            ...         ?person <http://example.org/name> ?name .
            ...     }
            ... ''')
            >>> for row in result:
            ...     print(f"Person: {row.person}, Name: {row.name}")
            >>>
            >>> # CONSTRUCT query
            >>> result = neptune.query('''
            ...     CONSTRUCT { ?s ?p ?o }
            ...     WHERE { ?s a <http://example.org/Person> . ?s ?p ?o }
            ... ''')
            >>> print(f"Constructed graph has {len(result)} triples")
            >>>
            >>> # UPDATE operation
            >>> neptune.query('''
            ...     INSERT DATA {
            ...         <http://example.org/bob> a <http://example.org/Person> .
            ...         <http://example.org/bob> <http://example.org/name> "Bob" .
            ...     }
            ... ''', QueryMode.UPDATE)
        """
        response = self.submit_query({query_mode.value: query})
        
        # Detect if SELECT, ASK or CONSTRUCT, DESCRIBE
        sparql = SPARQLWrapper(self.neptune_sparql_url)
        sparql.setQuery(query)
    
        
        parser : ResultParser | None = None
        
        if sparql.queryType in ["SELECT", "ASK"]:
            parser = XMLResultParser()
        elif sparql.queryType in ["CONSTRUCT", "DESCRIBE"]:
            parser = RDFResultParser()
        else:
            raise ValueError(f"Unsupported query type: {sparql.queryType}")
        
        try:
            result = parser.parse(StringIO(response.text))
            return result
        except Exception as e:
            print(response.text)
            raise e

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
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

        Example:
            >>> result = neptune.query_view("people_view", '''
            ...     SELECT ?person WHERE { ?person a <http://example.org/Person> }
            ... ''')
        """
        return self.query(query)

    def get_subject_graph(self, subject: URIRef) -> Graph:
        """
        Get all triples for a specific subject as an RDFLib Graph.

        This method retrieves all triples where the given URI is the subject
        and returns them as an RDFLib Graph object.

        Args:
            subject (URIRef): The subject URI to get triples for

        Returns:
            Graph: RDFLib Graph containing all triples for the subject

        Example:
            >>> alice_uri = URIRef("http://example.org/alice")
            >>> alice_graph = neptune.get_subject_graph(alice_uri)
            >>> print(f"Alice has {len(alice_graph)} properties")
            >>>
            >>> # Print all properties of Alice
            >>> for _, predicate, obj in alice_graph:
            ...     print(f"Alice {predicate} {obj}")
        """
        res = self.query(f"SELECT ?s ?p ?o WHERE  {{ <{str(subject)}> ?p ?o }}")

        graph = Graph()
        for row in res:
            assert isinstance(row, ResultRow)
            assert len(row) == 3
            _, p, o = row
            graph.add((subject, p, o))

        return graph

    def graph_to_query(
        self, graph: Graph, query_type: QueryType, graph_name: URIRef
    ) -> str:
        """
        Convert an RDFLib graph to a SPARQL INSERT/DELETE statement.

        This method takes an RDFLib Graph and converts it into a properly
        formatted SPARQL statement that can be executed against Neptune.
        It handles namespace prefixes and converts triples to N3 format.

        Args:
            graph (Graph): The RDFLib graph to convert
            query_type (QueryType): Whether to generate INSERT DATA or DELETE DATA
            graph_name (URIRef): Named graph to target for the operation

        Returns:
            str: A SPARQL INSERT/DELETE statement ready for execution

        Example:
            >>> from rdflib import Graph, URIRef, RDF, Literal
            >>> g = Graph()
            >>> g.add((URIRef("http://example.org/alice"),
            ...        RDF.type,
            ...        URIRef("http://example.org/Person")))
            >>>
            >>> query = neptune.graph_to_query(
            ...     g,
            ...     QueryType.INSERT_DATA,
            ...     URIRef("http://example.org/mygraph")
            ... )
            >>> print(query)
            INSERT DATA { GRAPH <http://example.org/mygraph> {
            <http://example.org/alice> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Person> .
            }}
        """
        # Get all namespaces from the graph
        namespaces = []
        for prefix, namespace in graph.namespaces():
            if (
                prefix in _NAMESPACE_PREFIXES_RDFLIB
                or prefix in _NAMESPACE_PREFIXES_CORE
            ):
                continue
            namespaces.append(f"PREFIX {prefix}: <{namespace}>")

        # Build the INSERT DATA statement
        triples = []
        for s, p, o in graph:
            # Skip if any term is a blank node
            if isinstance(s, rdflib.BNode) or isinstance(p, rdflib.BNode) or isinstance(o, rdflib.BNode):
                continue
            # Convert each term to N3 format
            s_str = s.n3()
            p_str = p.n3()
            o_str = o.n3()
            triples.append(f"{s_str} {p_str} {o_str} .")

        # Combine everything into a SPARQL query
        query = "\n".join(namespaces)
        query += f"\n\n{query_type.value} {{ GRAPH <{str(graph_name)}> {{\n"
        query += "\n".join(triples)
        query += "\n}}"

        return query

    # Graph management

    def create_graph(self, graph_name: URIRef):
        """
        Create a new named graph in Neptune.

        This method creates a new named graph with the specified URI. The graph
        will be empty after creation and ready to receive triples.

        Args:
            graph_name (URIRef): URI of the named graph to create

        Raises:
            AssertionError: If graph_name is None or not a URIRef
            requests.exceptions.HTTPError: If the graph creation fails

        Example:
            >>> my_graph = URIRef("http://example.org/graphs/people")
            >>> neptune.create_graph(my_graph)
            >>> print("Graph created successfully")
        """
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)

        result = self.submit_query(
            {QueryMode.UPDATE.value: f"CREATE GRAPH <{str(graph_name)}>"}
        )
        print(result.text)

    def clear_graph(self, graph_name: URIRef = NEPTUNE_DEFAULT_GRAPH_NAME):
        """
        Remove all triples from a named graph.

        This method deletes all triples from the specified graph but keeps
        the graph itself. The graph will be empty after this operation.

        Args:
            graph_name (URIRef, optional): URI of the named graph to clear.
                Defaults to Neptune's default graph.

        Raises:
            AssertionError: If graph_name is None or not a URIRef
            requests.exceptions.HTTPError: If the clear operation fails

        Warning:
            This operation cannot be undone. All data in the specified graph
            will be permanently deleted.

        Example:
            >>> # Clear the default graph
            >>> neptune.clear_graph()
            >>>
            >>> # Clear a specific named graph
            >>> my_graph = URIRef("http://example.org/graphs/people")
            >>> neptune.clear_graph(my_graph)
            >>> print("Graph cleared successfully")
        """
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)

        self.submit_query({QueryMode.UPDATE.value: f"CLEAR GRAPH <{str(graph_name)}>"})

    def drop_graph(self, graph_name: URIRef):
        """
        Delete a named graph and all its triples from Neptune.

        This method completely removes the specified graph and all triples
        it contains. The graph will no longer exist after this operation.

        Args:
            graph_name (URIRef): URI of the named graph to drop

        Raises:
            AssertionError: If graph_name is None or not a URIRef
            requests.exceptions.HTTPError: If the drop operation fails

        Warning:
            This operation cannot be undone. The graph and all its data
            will be permanently deleted.

        Example:
            >>> my_graph = URIRef("http://example.org/graphs/temporary")
            >>> neptune.drop_graph(my_graph)
            >>> print("Graph dropped successfully")
        """
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)

        self.submit_query({QueryMode.UPDATE.value: f"DROP GRAPH <{str(graph_name)}>"})

    def copy_graph(self, source_graph_name: URIRef, target_graph_name: URIRef):
        """
        Copy all triples from one named graph to another.

        This method copies all triples from the source graph to the target graph.
        If the target graph already exists, its contents will be replaced.
        The source graph remains unchanged.

        Args:
            source_graph_name (URIRef): URI of the source graph to copy from
            target_graph_name (URIRef): URI of the target graph to copy to

        Raises:
            AssertionError: If either graph name is None or not a URIRef
            requests.exceptions.HTTPError: If the copy operation fails

        Warning:
            If the target graph already exists, its contents will be completely
            replaced by the contents of the source graph.

        Example:
            >>> source = URIRef("http://example.org/graphs/original")
            >>> backup = URIRef("http://example.org/graphs/backup")
            >>> neptune.copy_graph(source, backup)
            >>> print("Graph copied successfully")
        """
        assert source_graph_name is not None
        assert isinstance(source_graph_name, URIRef)
        assert target_graph_name is not None
        assert isinstance(target_graph_name, URIRef)

        self.submit_query(
            {
                QueryMode.UPDATE.value: f"COPY GRAPH <{str(source_graph_name)}> TO <{str(target_graph_name)}>"
            }
        )

    def add_graph_to_graph(self, source_graph_name: URIRef, target_graph_name: URIRef):
        """
        Add all triples from one named graph to another.

        This method adds all triples from the source graph to the target graph.
        Unlike copy_graph(), this operation preserves existing triples in the
        target graph and adds new ones from the source graph.

        Args:
            source_graph_name (URIRef): URI of the source graph to add from
            target_graph_name (URIRef): URI of the target graph to add to

        Raises:
            AssertionError: If either graph name is None or not a URIRef
            requests.exceptions.HTTPError: If the add operation fails

        Note:
            This operation merges graphs rather than replacing. Existing triples
            in the target graph are preserved, and new triples from the source
            graph are added.

        Example:
            >>> people_graph = URIRef("http://example.org/graphs/people")
            >>> all_data = URIRef("http://example.org/graphs/complete")
            >>> neptune.add_graph_to_graph(people_graph, all_data)
            >>> print("Graph content added successfully")
        """
        assert source_graph_name is not None
        assert isinstance(source_graph_name, URIRef)
        assert target_graph_name is not None
        assert isinstance(target_graph_name, URIRef)

        self.submit_query(
            {
                QueryMode.UPDATE.value: f"ADD GRAPH <{str(source_graph_name)}> TO <{str(target_graph_name)}>"
            }
        )


class AWSNeptuneSSHTunnel(AWSNeptune):
    """
    AWS Neptune Triple Store Adapter with SSH Tunnel Support

    This adapter extends AWSNeptune to provide secure access to Neptune instances
    deployed in private VPCs through SSH tunneling via a bastion host. It's ideal
    for production environments where Neptune is not directly accessible from
    the internet.

    The adapter establishes an SSH tunnel from your local machine through a bastion
    host to the Neptune instance, then routes all SPARQL requests through this tunnel.
    This provides secure access while maintaining all the functionality of the base
    AWSNeptune adapter.

    Features:
    - All AWSNeptune functionality via SSH tunnel
    - Secure access to VPC-deployed Neptune instances
    - SSH key-based authentication to bastion host
    - Automatic port forwarding and connection management
    - Socket address monkey-patching for transparent operation

    Architecture:
        Your Application → SSH Tunnel → Bastion Host → VPC → Neptune Instance

    Attributes:
        bastion_host (str): Hostname or IP of the bastion host
        bastion_port (int): SSH port on the bastion host (typically 22)
        bastion_user (str): SSH username for bastion host connection
        bastion_private_key (str): SSH private key content for authentication
        tunnel (SSHTunnelForwarder): Active SSH tunnel instance

    Example:
        >>> # SSH tunnel connection to VPC-deployed Neptune
        >>> neptune_ssh = AWSNeptuneSSHTunnel(
        ...     aws_region_name="us-east-1",
        ...     aws_access_key_id="AKIA1234567890EXAMPLE",
        ...     aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ...     db_instance_identifier="my-vpc-neptune-cluster",
        ...     bastion_host="bastion.mycompany.com",
        ...     bastion_port=22,
        ...     bastion_user="ubuntu",
        ...     bastion_private_key='''-----BEGIN RSA PRIVATE KEY-----
        ... MIIEpAIBAAKCAQEA2...
        ... ...private key content...
        ... -----END RSA PRIVATE KEY-----'''
        ... )
        >>>
        >>> # Use exactly like regular AWSNeptune - tunnel is transparent
        >>> from rdflib import Graph, URIRef, RDF, Literal
        >>> g = Graph()
        >>> g.add((URIRef("http://example.org/alice"),
        ...        RDF.type,
        ...        URIRef("http://example.org/Person")))
        >>> neptune_ssh.insert(g)
        >>>
        >>> # Query through the tunnel
        >>> result = neptune_ssh.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o }")
        >>> print(f"Found {len(list(result))} triples")

    Security Notes:
        - Always use SSH key authentication instead of passwords
        - Ensure your bastion host is properly secured and monitored
        - Consider using temporary SSH keys for enhanced security
        - The private key is temporarily written to disk during tunnel creation
    """

    def __init__(
        self,
        aws_region_name: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        db_instance_identifier: str,
        bastion_host: str,
        bastion_port: int,
        bastion_user: str,
        bastion_private_key: str,
        default_graph_name: URIRef = NEPTUNE_DEFAULT_GRAPH_NAME,
    ):
        """
        Initialize AWS Neptune adapter with SSH tunnel support.

        This constructor first initializes the base AWSNeptune adapter to discover
        the Neptune endpoint, then establishes an SSH tunnel through the specified
        bastion host to enable secure access to VPC-deployed Neptune instances.

        Args:
            aws_region_name (str): AWS region name (e.g., 'us-east-1')
            aws_access_key_id (str): AWS access key ID for Neptune authentication
            aws_secret_access_key (str): AWS secret key for Neptune authentication
            db_instance_identifier (str): Neptune database instance identifier
            bastion_host (str): Hostname or IP address of the bastion host
            bastion_port (int): SSH port on the bastion host (typically 22)
            bastion_user (str): SSH username for bastion host authentication
            bastion_private_key (str): Complete SSH private key content as a string
            default_graph_name (URIRef, optional): Default named graph URI

        Raises:
            AssertionError: If any parameter has incorrect type
            paramiko.AuthenticationException: If SSH authentication fails
            paramiko.SSHException: If SSH connection fails
            socket.gaierror: If bastion host cannot be resolved
            TimeoutError: If SSH connection times out

        Example:
            >>> # Load private key from file
            >>> with open('/path/to/ssh/key.pem', 'r') as f:
            ...     private_key = f.read()
            >>>
            >>> neptune_ssh = AWSNeptuneSSHTunnel(
            ...     aws_region_name="us-east-1",
            ...     aws_access_key_id="AKIA1234567890EXAMPLE",
            ...     aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            ...     db_instance_identifier="my-vpc-neptune",
            ...     bastion_host="bastion.mycompany.com",
            ...     bastion_port=22,
            ...     bastion_user="ec2-user",
            ...     bastion_private_key=private_key
            ... )
        """
        super().__init__(
            aws_region_name=aws_region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            db_instance_identifier=db_instance_identifier,
            default_graph_name=default_graph_name,
        )

        assert isinstance(bastion_host, str)
        assert isinstance(bastion_port, int)
        assert isinstance(bastion_user, str)
        assert isinstance(bastion_private_key, str)

        # Import SSH dependencies when actually needed
        try:
            import paramiko
        except ImportError as e:
            raise ImportError(
                "SSH tunnel support requires optional dependencies. "
                "Install them with: pip install 'abi[ssh]' or install paramiko and sshtunnel separately"
            ) from e
            
        self.bastion_host = bastion_host
        self.bastion_port = bastion_port
        self.bastion_user = bastion_user
        self.bastion_private_key = bastion_private_key

        self.bastion_client = paramiko.SSHClient()
        self.bastion_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # self.bastion_client.connect(self.bastion_host, port=self.bastion_port, username=self.bastion_user, pkey=paramiko.RSAKey.from_private_key(StringIO(self.bastion_private_key)))
        self.tunnel = self.__create_ssh_tunnel()

        # We patch the neptune_sparql_url to use the tunnel.
        self.neptune_sparql_url = f"https://{self.neptune_sparql_endpoint}:{self.tunnel.local_bind_port}/sparql"

    def __monkey_patch_getaddrinfo(self):
        """
        Monkey patch socket.getaddrinfo to redirect Neptune endpoint to localhost.

        This method modifies the global socket.getaddrinfo function to intercept
        DNS resolution requests for the Neptune endpoint and redirect them to
        localhost (127.0.0.1). This is necessary because:

        1. The SSH tunnel creates a local port that forwards to Neptune
        2. HTTPS requests need to connect to localhost to use the tunnel
        3. The original Neptune endpoint hostname needs to be preserved for SSL

        The patching ensures that when the HTTP client tries to connect to the
        Neptune endpoint, it actually connects to the local tunnel port instead.

        Note:
            This is an internal method that modifies global socket behavior.
            It should only be called once during tunnel setup.

        Warning:
            This method modifies global socket behavior and could affect other
            network operations in the same process. Use with caution in multi-
            threaded or complex applications.
        """
        assert self.neptune_sparql_endpoint is not None

        def new_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            if host == self.neptune_sparql_endpoint:
                return ORIGINAL_GETADDRINFO("127.0.0.1", port, family, type, proto, flags)
            else:
                return ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)

        socket.getaddrinfo = new_getaddrinfo

    def __create_ssh_tunnel(self):
        """
        Create and start an SSH tunnel to the Neptune database.

        This method establishes an SSH tunnel from a local port through the
        bastion host to the Neptune database endpoint. The tunnel enables
        secure access to VPC-deployed Neptune instances that are not directly
        accessible from the internet.

        The process involves:
        1. Writing the SSH private key to a temporary file
        2. Creating an SSHTunnelForwarder instance
        3. Connecting to the bastion host using SSH key authentication
        4. Forwarding traffic from a local port to Neptune's port
        5. Starting the tunnel and applying network patches

        Returns:
            SSHTunnelForwarder: An active SSH tunnel instance that forwards
                traffic from localhost to Neptune through the bastion host

        Raises:
            paramiko.AuthenticationException: If SSH key authentication fails
            paramiko.SSHException: If SSH connection to bastion fails
            socket.gaierror: If bastion host DNS resolution fails
            OSError: If temporary file creation fails

        Note:
            The SSH private key is temporarily written to disk during tunnel
            creation for security reasons (paramiko requirement). The temporary
            file is automatically cleaned up.

        Example:
            >>> # This method is called automatically during __init__
            >>> # Manual usage (not recommended):
            >>> tunnel = neptune_ssh._AWSNeptuneSSHTunnel__create_ssh_tunnel()
            >>> print(f"Tunnel running on local port: {tunnel.local_bind_port}")
        """
        from sshtunnel import SSHTunnelForwarder
        
        assert self.neptune_sparql_endpoint is not None
        assert self.neptune_port is not None

        # Write pkey to tmpfile
        with tempfile.NamedTemporaryFile(delete=True) as tmpfile:
            tmpfile.write(self.bastion_private_key.encode("utf-8"))
            tmpfile.flush()
            tmpfile.name

            tunnel = SSHTunnelForwarder(
                (self.bastion_host, self.bastion_port),
                ssh_username=self.bastion_user,
                ssh_pkey=tmpfile.name,
                remote_bind_address=(
                    socket.gethostbyname(self.neptune_sparql_endpoint),
                    self.neptune_port,
                ),
            )

            tunnel.start()

            self.__monkey_patch_getaddrinfo()

            return tunnel


if __name__ == "__main__":
    """
    Example usage and interactive testing for AWS Neptune adapters.
    
    This section provides examples of how to use both AWSNeptune and AWSNeptuneSSHTunnel
    adapters, and includes an interactive SPARQL console for testing.
    
    Environment Variables Required:
        AWS_REGION: AWS region (e.g., 'us-east-1')
        AWS_ACCESS_KEY_ID: AWS access key for authentication
        AWS_SECRET_ACCESS_KEY: AWS secret access key
        AWS_NEPTUNE_DB_CLUSTER_IDENTIFIER: Neptune database instance identifier
        
    For SSH Tunnel (AWSNeptuneSSHTunnel):
        AWS_BASTION_HOST: Bastion host hostname or IP
        AWS_BASTION_PORT: SSH port (typically 22)
        AWS_BASTION_USER: SSH username
        AWS_BASTION_PRIVATE_KEY: SSH private key content
        
    Usage Examples:
        # Direct connection (for publicly accessible Neptune)
        python AWSNeptune.py
        
        # SSH tunnel connection (for VPC-deployed Neptune)
        # Ensure all environment variables are set first
        python AWSNeptune.py
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    try:
        # Try SSH tunnel connection if bastion host is configured
        neptune: AWSNeptune
        if os.getenv("AWS_BASTION_HOST"):
            print("Initializing Neptune adapter with SSH tunnel...")
            neptune = AWSNeptuneSSHTunnel(
                aws_region_name=os.environ["AWS_REGION"],
                aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                db_instance_identifier=os.environ["AWS_NEPTUNE_DB_CLUSTER_IDENTIFIER"],
                bastion_host=os.environ["AWS_BASTION_HOST"],
                bastion_port=int(os.environ["AWS_BASTION_PORT"]),
                bastion_user=os.environ["AWS_BASTION_USER"],
                bastion_private_key=os.environ["AWS_BASTION_PRIVATE_KEY"],
            )
            print("✓ SSH tunnel established successfully")
        else:
            print("Initializing Neptune adapter with direct connection...")
            neptune = AWSNeptune(
                aws_region_name=os.environ["AWS_REGION"],
                aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                db_instance_identifier=os.environ["AWS_NEPTUNE_DB_CLUSTER_IDENTIFIER"],
            )
            print("✓ Direct connection established successfully")

        print(f"Connected to Neptune endpoint: {neptune.neptune_sparql_endpoint}")
        print("\nAvailable commands:")
        print("  SELECT/ASK/CONSTRUCT queries - executed as QUERY")
        print("  INSERT/DELETE/UPDATE statements - executed as UPDATE")
        print("  create graph <uri> - create a new named graph")
        print("  clear graph <uri> - clear all triples from a graph")
        print("  list graphs - show all named graphs")
        print("  exit - quit the console")
        print("\nEntering interactive SPARQL console...")
        print("=" * 50)

        while True:
            query = input("SPARQL> ").strip()

            if query.lower() == "exit":
                print("Goodbye!")
                break
            elif query.startswith("create graph "):
                try:
                    graph_uri = query.split(" ", 2)[2]
                    graph_name = URIRef(graph_uri)
                    neptune.create_graph(graph_name)
                    print(f"✓ Graph {graph_uri} created successfully")
                except Exception as e:
                    print(f"✗ Error creating graph: {e}")
            elif query.startswith("clear graph "):
                try:
                    graph_uri = query.split(" ", 2)[2]
                    graph_name = URIRef(graph_uri)
                    neptune.clear_graph(graph_name)
                    print(f"✓ Graph {graph_uri} cleared successfully")
                except Exception as e:
                    print(f"✗ Error clearing graph: {e}")
            elif query.lower().startswith("list graphs"):
                try:
                    result = neptune.query(
                        "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"
                    )
                    graphs = []
                    for row in result:
                        if isinstance(row, ResultRow) and hasattr(row, "g"):
                            graphs.append(str(row.g))
                    if graphs:
                        print("Named graphs:")
                        for graph in graphs:
                            print(f"  - {graph}")
                    else:
                        print("No named graphs found")
                except Exception as e:
                    print(f"✗ Error listing graphs: {e}")
            elif query:
                try:
                    # Determine query mode based on query type
                    query_mode = QueryMode.QUERY
                    if any(
                        query.upper().strip().startswith(cmd)
                        for cmd in [
                            "INSERT",
                            "DELETE",
                            "CREATE",
                            "DROP",
                            "CLEAR",
                            "COPY",
                            "ADD",
                        ]
                    ):
                        query_mode = QueryMode.UPDATE

                    result = neptune.query(query, query_mode)

                    if query_mode == QueryMode.UPDATE:
                        print("✓ Update executed successfully")
                    else:
                        # Format and display query results
                        result_list = list(result)
                        if result_list:
                            print(f"Results ({len(result_list)} rows):")
                            for i, row in enumerate(result_list):
                                if i >= 10:  # Limit display to first 10 rows
                                    print(f"... and {len(result_list) - 10} more rows")
                                    break
                                print(f"  {row}")
                        else:
                            print("No results returned")
                except Exception as e:
                    print(f"✗ Query error: {e}")

    except KeyError as e:
        print(f"✗ Missing required environment variable: {e}")
        print("Please set all required environment variables and try again.")
    except Exception as e:
        print(f"✗ Connection error: {e}")
        print("Please check your AWS credentials and Neptune configuration.")
