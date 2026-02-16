from typing import Any, Dict, List, Optional, Set, Union

from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from rdflib import OWL, URIRef
from rdflib.query import ResultRow


class TriplesUtils:
    def __init__(self, triple_store: TripleStoreService):
        self.triple_store = triple_store

    def add_rdf_types_to_metadata(
        self, metadata: Dict[str, Any], rdf_types: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add RDF types to metadata.

        Args:
            rdf_types: The RDF types to add to metadata

        Returns:
            The metadata with RDF types added
        """
        # Add metadata: Get RDF types from subject
        owl_types: List[str] = []
        type_uris: List[str] = []
        type_labels: List[str] = []
        for rdf_type in rdf_types:
            # If the type is from OWL namespace, add its URI to "owl"
            if str(rdf_type["type"]).startswith(str(OWL)):
                # Collect all OWL types
                owl_types.append(str(rdf_type["type"]))
            else:
                # Otherwise accumulate its type and label
                type_uris.append(str(rdf_type["type"]))
                type_labels.append(str(rdf_type["label"]))

        # If any non-OWL types were found, add them as lists
        if type_uris and type_labels:
            metadata["type_uri"] = type_uris
            metadata["type_label"] = type_labels
        if owl_types:
            metadata["owl_type"] = owl_types

        return metadata

    def get_rdf_type_from_subject(self, subject: URIRef | str) -> List[Dict[str, Any]]:
        """Get the RDF type from a given subject.

        Args:
            subject: The subject of the triple

        Returns:
            The RDF type of the subject
        """
        sparql_query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?type ?label
            WHERE {{
                <{str(subject)}> rdf:type ?type .
                ?type rdfs:label ?label .
            }}
        """
        rdf_types: List[Dict] = []
        results = self.triple_store.query(sparql_query)
        for row in results:
            assert isinstance(row, ResultRow)
            rdf_types.append({"type": row.type, "label": row.label})
        return rdf_types

    def is_subclass_of(
        self,
        class_uri: str,
        parent_class: Union[str, List[str]],
        visited: Optional[Set[str]] = None,
    ) -> bool:
        """
        Recursively check if a subject is a subclass of a parent class (or one of multiple parent classes).
        :param subject: The URI of the subject class to check.
        :param parent_class: The URI of the parent class to check against, or a list of parent class URIs (OR logic).
        :param visited: Set of already visited class URIs to avoid cycles.
        :return: True if subject is a subclass of parent_class (or any in the list), False otherwise.
        """
        # Normalize parent_class to a list
        if isinstance(parent_class, str):
            parent_classes = [parent_class]
        else:
            parent_classes = parent_class

        # Initialize visited set if not provided
        if visited is None:
            visited = set()

        # Avoid infinite loops
        if class_uri in visited:
            return False
        visited.add(class_uri)

        # If subject equals any parent, it's a match
        if class_uri in parent_classes:
            return True

        # Query for direct parent classes using rdfs:subClassOf
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?parent
        WHERE {{
            <{class_uri}> rdfs:subClassOf ?parent .
        }}
        """

        results = self.triple_store.query(query)

        # Check each parent class
        for row in results:
            assert isinstance(row, ResultRow)
            parent = str(row["parent"])

            # Recursively check if this parent is a subclass of any target
            if self.is_subclass_of(parent, parent_classes, visited):
                return True

        return False
