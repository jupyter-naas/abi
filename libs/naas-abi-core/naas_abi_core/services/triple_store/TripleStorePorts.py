from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Dict, List, Tuple

import rdflib
from rdflib import Graph, URIRef


class Exceptions:
    class SubjectNotFoundError(Exception):
        pass

    class SubscriptionNotFoundError(Exception):
        pass

    class ViewNotFoundError(Exception):
        pass


class OntologyEvent(Enum):
    INSERT = "INSERT"
    DELETE = "DELETE"


class ITripleStorePort(ABC):
    @abstractmethod
    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        pass

    @abstractmethod
    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        pass

    @abstractmethod
    def get(self) -> Graph:
        pass

    @abstractmethod
    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        pass

    @abstractmethod
    def query(self, query: str) -> rdflib.query.Result:
        pass

    @abstractmethod
    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        pass

    @abstractmethod
    def get_subject_graph(self, subject: URIRef) -> Graph:
        pass


class ITripleStoreService(ABC):
    __ontology_adaptor: ITripleStorePort

    __event_listeners: Dict[
        tuple, Dict[OntologyEvent, List[tuple[str, Callable, bool]]]
    ]

    __views: List[Tuple[URIRef | None, URIRef | None, URIRef | None]]

    @abstractmethod
    def subscribe(
        self,
        topic: tuple[URIRef | None, URIRef | None, URIRef | None],
        callback: Callable[[bytes], None],
        event_type: OntologyEvent | None = None,
        graph_name: URIRef | str | None = "*",
    ) -> None:
        """
        Register a callback function to receive notifications for triple store events matching the given
        subject-predicate-object (SPO) pattern.

        This subscription method allows users to listen for INSERT and/or DELETE events—indicated by
        `event_type`—emitted when triples in the store match the specified SPO pattern. Each
        element of the `topic` tuple can be a URIRef to filter on that subject, predicate, or object.
        Specifying None in any position acts as a wildcard, matching any value for that component.

        The provided callback will be invoked with the serialized triple event (as bytes) for
        each matching occurrence.

        Args:
            topic (tuple[URIRef | None, URIRef | None, URIRef | None]):
                The subject, predicate, object pattern to match. Use None for any element to match all.
            callback (Callable[[bytes], None]):
                Function that is called with serialized triple event bytes when a match occurs.
            event_type (OntologyEvent | None, optional):
                Restrict matches to INSERT, DELETE, or receive both event types if None. Defaults to None.

        Returns:
            str: A unique subscription ID that can later be used to unsubscribe.

        Example:
            >>> def print_triple(triple: bytes):
            ...     print(triple)
            >>> subscription_id = triple_store_service.subscribe(
            ...     (None, RDF.type, None), print_triple, OntologyEvent.INSERT)
        """
        pass

    # @abstractmethod
    # def unsubscribe(self, subscription_id: str):
    #     """Unsubscribe from events using a subscription ID.

    #     This method removes a subscription based on its ID, stopping any further callbacks
    #     for that subscription.

    #     Args:
    #         subscription_id (str): The subscription ID returned from a previous subscribe() call

    #     Raises:
    #         SubscriptionNotFoundError: If no subscription exists with the provided ID

    #     Returns:
    #         None
    #     """
    #     pass

    @abstractmethod
    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        """Insert triples from the provided graph into the store.

        This method takes a graph of triples and inserts them into the triple store. The triples
        are partitioned and stored by subject to enable efficient subject-based querying.

        Args:
            triples (Graph): The RDF graph containing triples to insert
            graph_name (URIRef | None): Named graph URI target. None means default graph.

        Returns:
            None
        """
        pass

    @abstractmethod
    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        """Remove triples from the provided graph from the store.

        This method takes a graph of triples and removes them from the triple store. The triples
        are matched against existing triples and removed where matches are found.

        Args:
            triples (Graph): The RDF graph containing triples to remove
            graph_name (URIRef | None): Named graph URI target. None means default graph.

        Returns:
            None
        """
        pass

    @abstractmethod
    def get(self) -> Graph:
        """Get the complete RDF graph from the triple store.

        This method retrieves and returns the full RDF graph containing all triples
        stored in the triple store.

        Returns:
            Graph: The complete RDF graph containing all stored triples
        """
        pass

    @abstractmethod
    def query(self, query: str) -> rdflib.query.Result:
        """Execute a SPARQL query against the triple store.

        This method executes the provided SPARQL query string against all triples in the store
        and returns the results as a new RDF graph.

        Args:
            query (str): The SPARQL query string to execute against the triple store

        Returns:
            Graph: A new RDF graph containing the query results

        Example:
            >>> store.query("SELECT ?s WHERE { ?s a owl:Class }")
        """
        pass

    @abstractmethod
    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        pass

    @abstractmethod
    def get_subject_graph(self, subject: str) -> Graph:
        """Get the RDF graph containing all triples for a specific subject.

        This method retrieves and returns an RDFlib Graph containing all triples
        that have the specified subject.

        Args:
            subject (str): The subject to retrieve triples for

        Returns:
            Graph: An RDFlib Graph containing all triples for the specified subject

        Raises:
            SubjectNotFoundError: If no triples exist with the specified subject
        """
        pass

    @abstractmethod
    def load_schema(self, filepath: str):
        """Load an RDF/OWL schema file into the triple store.

        This method takes a file path string pointing to an RDF/OWL schema file,
        loads it into an RDFlib Graph, and inserts all schema triples into the triple store.
        The schema defines the ontology structure including classes, properties and restrictions.

        Args:
            filepath (str): Path to the RDF/OWL schema file to load

        Returns:
            None

        Example:
            >>> store.load_schema("path/to/schema.ttl")
        """
        pass

    @abstractmethod
    def get_schema_graph(self) -> Graph:
        """Get the RDF graph containing just the schema/ontology triples.

        This method returns an RDFlib Graph containing only the schema/ontology triples
        that define classes, properties, and other structural elements. It excludes
        instance data triples.

        Returns:
            Graph: An RDF graph containing only the schema/ontology triples

        Example:
            >>> schema = store.get_schema_graph()
        """
        pass
