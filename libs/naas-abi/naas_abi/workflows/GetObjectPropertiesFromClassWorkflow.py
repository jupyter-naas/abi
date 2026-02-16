from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

import pydash
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field
from rdflib import OWL, RDF, RDFS, Graph, URIRef

# Ontology operators mapping
ONTOLOGY_OPERATORS = {"unionOf": "or", "intersectionOf": "and", "complementOf": "not"}


@dataclass
class GetObjectPropertiesFromClassWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GetObjectPropertiesFromClassWorkflow.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
        ontology_file_path (str): Path to the ontology file
    """

    triple_store: ITripleStoreService
    ontology_file_path: Optional[str] = None


class GetObjectPropertiesFromClassWorkflowParameters(WorkflowParameters):
    """Parameters for GetObjectPropertiesFromClassWorkflow execution.

    Attributes:
        class_uri (str): URI of the class to get object properties for
    """

    class_uri: Annotated[
        str,
        Field(
            ...,
            description="URI of the class to get object properties for",
            pattern="^http.*",
        ),
    ]


class GetObjectPropertiesFromClassWorkflow(Workflow):
    """Workflow for getting object properties of a given class from ontology."""

    __configuration: GetObjectPropertiesFromClassWorkflowConfiguration

    def __init__(
        self, configuration: GetObjectPropertiesFromClassWorkflowConfiguration
    ):
        super().__init__(configuration)
        self.__configuration = configuration
        self.graph = Graph()
        if self.__configuration.ontology_file_path:
            self.graph.parse(self.__configuration.ontology_file_path, format="turtle")
        else:
            self.graph = self.__configuration.triple_store.get_schema_graph()
        self.operators = ONTOLOGY_OPERATORS
        self._ = pydash

        # Initialize data structures like in generate_docs
        self.onto_tuples: dict = {}
        self.onto_classes: dict = {}
        self.onto: dict = {}

        # Create basic mapping for common properties
        self.mapping: dict = {
            "http://www.w3.org/2000/01/rdf-schema#label": "label",
            "http://www.w3.org/2000/01/rdf-schema#domain": "domain",
            "http://www.w3.org/2000/01/rdf-schema#range": "range",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "type",
            "http://www.w3.org/2000/01/rdf-schema#subClassOf": "subclassOf",
            "http://www.w3.org/2002/07/owl#unionOf": "unionOf",
            "http://www.w3.org/2002/07/owl#intersectionOf": "intersectionOf",
            "http://www.w3.org/2002/07/owl#complementOf": "complementOf",
        }

        # Load triples into onto_tuples structure
        self._load_triples()

        # Load classes
        self._load_classes()

    def _load_triples(self):
        """Load SPO triples into onto_tuples dictionary structure."""
        for s, p, o in self.graph:
            self._handle_onto_tuples(s, p, o)

            # Keep only the predicates that are in the mapping.
            if str(p) not in self.mapping:
                continue

            # If the subject is not in the onto dictionary, we create a new dict for it.
            if str(s) not in self.onto:
                self.onto[str(s)] = {"__id": str(s)}

            # If the predicate is not in the onto dict, we create a new list for it.
            if self.mapping[str(p)] not in self.onto[str(s)]:
                self.onto[str(s)][self.mapping[str(p)]] = []

            # We append the object to the list of the predicate.
            self.onto[str(s)][self.mapping[str(p)]].append(str(o))

    def _handle_onto_tuples(self, s, p, o):
        """Load SPO in onto_tuples dictionary."""
        if str(s) not in self.onto_tuples:
            self.onto_tuples[str(s)] = []
        self.onto_tuples[str(s)].append((p, o))

    def _load_classes(self):
        """Load classes from the ontology."""
        # Filter the classes from the ontology.
        _onto_classes = self._.filter_(
            self.onto,
            lambda x: (
                "http://www.w3.org/2002/07/owl#Class" in x["type"]
                if "type" in x
                else None
            ),
        )

        # Remove subclassOf that are restrictions to keep it simple for now.
        for cls in _onto_classes:
            cls["subclassOf"] = self._.filter_(
                cls.get("subclassOf", []), lambda x: True if "http" in x else False
            )

        # Rebuild dictionary with __id as the key
        self.onto_classes = {e["__id"]: e for e in _onto_classes}

    def _get_first_rest(self, tpl):
        """Get the values from unionOf, intersectionOf and complementOf."""
        first = None
        rest = None
        for i in tpl:
            a, b = i

            if str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#first":
                first = str(b)

            if (
                str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"
                and str(b) != "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"
            ):
                rest = str(b)
        return first, rest

    def get_linked_classes(self, cls_id, rel_type=None):
        """Recursive function to build a tree of classes based on unionOf, intersectionOf and complementOf."""
        # Handle None case
        if cls_id is None:
            return []

        # If it's a leaf we return a dict with the class id and the operator.
        if "http" in cls_id:
            if rel_type is not None and rel_type in self.operators:
                return {self.operators[rel_type]: [cls_id]}
            return [cls_id]

        # If it's a class, we want to go over the unionOf, intersectionOf and complementOf.
        if cls_id in self.onto_classes:
            cls = self.onto_classes[cls_id]
            res = (
                [
                    self.get_linked_classes(e, "unionOf")
                    for e in self._.get(cls, "unionOf", [])
                ]
                + [
                    self.get_linked_classes(e, "intersectionOf")
                    for e in self._.get(cls, "intersectionOf", [])
                ]
                + [
                    self.get_linked_classes(e, "complementOf")
                    for e in self._.get(cls, "complementOf", [])
                ]
            )
            return res
        else:
            # If it's not a class, then we will have a 'first' and a 'rest' to handle.
            first, rest = self._get_first_rest(self.onto_tuples[cls_id])

            # We grab the operator based on the rel_type.
            operator = self.operators[rel_type]

            # We get the left/first value.
            left = self.get_linked_classes(first, rel_type)
            if rest:
                # We get the right/rest value.
                right = self.get_linked_classes(rest, rel_type)

                if operator in right and operator in left:
                    if (
                        operator in right
                        and type(right[operator]) is dict
                        and operator in right[operator]
                        and type(right[operator][operator]) is list
                    ):
                        right[operator] = right[operator][operator]

                    return {operator: self._.flatten([left[operator], right[operator]])}
                else:
                    return {operator: self._.flatten([left, right])}
            else:
                return {operator: left}

    # We map the ranges and domains to the classes by calling get_linked_classes.
    def map_ranges_domains(self, x):
        if "domain" in x:
            x["domain"] = self._.map_(
                x["domain"],
                lambda x: (
                    x
                    if (x is not None and "http" in x)
                    else (
                        self.get_linked_classes(x)[0]
                        if self.get_linked_classes(x)
                        else None
                    )
                ),
            )
        if "range" in x:
            x["range"] = self._.map_(
                x["range"],
                lambda x: (
                    x
                    if (x is not None and "http" in x)
                    else (
                        self.get_linked_classes(x)[0]
                        if self.get_linked_classes(x)
                        else None
                    )
                ),
            )
        return x

    def is_class(self, uri):
        """Check if the given URI is a class in the ontology."""
        uri_ref = URIRef(uri)
        # Check if it's declared as an OWL Class
        print(self.graph.serialize(format="turtle"))
        return (uri_ref, RDF.type, OWL.Class) in self.graph

    def _class_matches_domain(self, class_uri, domains):
        """Check if class_uri matches any of the domains (including complex expressions)."""
        for domain in domains:
            if isinstance(domain, str) and domain == class_uri:
                return True
            elif isinstance(domain, dict):
                # Handle complex expressions
                if "or" in domain and class_uri in domain["or"]:
                    return True
                if "and" in domain and class_uri in domain["and"]:
                    return True
        return False

    def _process_ranges(self, ranges):
        """Process ranges with sophisticated logic to handle complex expressions."""
        processed_ranges = []

        def _get_labeled_uri(uri):
            """Get label for a URI."""
            range_uri = URIRef(uri)
            range_label = self.graph.value(range_uri, RDFS.label)
            return {"uri": uri, "label": str(range_label) if range_label else None}

        def _process_range_item(range_item):
            """Process range item recursively."""
            if isinstance(range_item, str):
                return _get_labeled_uri(range_item)
            elif isinstance(range_item, dict):
                processed_dict = {}
                for key, value in range_item.items():
                    if key in ["or", "and", "not"]:
                        if isinstance(value, list):
                            processed_dict[key] = [
                                _process_range_item(item) for item in value
                            ]
                        else:
                            processed_dict[key] = _process_range_item(value)
                return processed_dict
            return range_item

        for range_item in ranges:
            processed_range = _process_range_item(range_item)
            processed_ranges.append(processed_range)

        return processed_ranges

    def get_object_properties_from_class(
        self, parameters: GetObjectPropertiesFromClassWorkflowParameters
    ) -> dict:
        """Get all object properties for a given class using sophisticated logic."""
        # First, validate that the URI is actually a class
        if not self.is_class(parameters.class_uri):
            raise ValueError(
                f"URI {parameters.class_uri} is not a class in the ontology"
            )

        class_uri = URIRef(parameters.class_uri)

        object_properties: list[dict] = []

        # Query for object properties with domain class_uri or union containing it
        for s, p, o in self.graph.triples((None, RDF.type, OWL.ObjectProperty)):
            property_data = {
                "object_property_uri": str(s),
                "object_property_label": str(self.graph.value(s, RDFS.label) or ""),
                "domain": [],
                "range": [],
            }

            # Collect all domains
            property_data["domain"] = [
                str(domain_uri) for domain_uri in self.graph.objects(s, RDFS.domain)
            ]

            # Collect all ranges
            property_data["range"] = [
                str(range_uri) for range_uri in self.graph.objects(s, RDFS.range)
            ]

            # Apply sophisticated mapping logic from generate_docs
            property_data = self.map_ranges_domains(property_data)

            # Check if class_uri is in the domain
            if self._class_matches_domain(str(class_uri), property_data["domain"]):
                # Process ranges with sophisticated logic
                processed_ranges = self._process_ranges(property_data["range"])

                object_properties.append(
                    {
                        "object_property_uri": str(s),
                        "object_property_label": property_data["object_property_label"],
                        "ranges": processed_ranges,
                    }
                )

        return {
            "class_uri": parameters.class_uri,
            "object_properties": object_properties,
        }

    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[BaseTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="get_object_properties_from_class",
                description="Get all object properties for a given class from the ontology.",
                func=lambda **kwargs: self.get_object_properties_from_class(
                    GetObjectPropertiesFromClassWorkflowParameters(**kwargs)
                ),
                args_schema=GetObjectPropertiesFromClassWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None


if __name__ == "__main__":
    from naas_abi_core import logger
    from naas_abi import ABIModule
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi"])

    workflow = GetObjectPropertiesFromClassWorkflow(
        GetObjectPropertiesFromClassWorkflowConfiguration(
            triple_store=ABIModule.get_instance().engine.services.triple_store
        )
    )
    class_uri = "http://purl.obolibrary.org/obo/BFO_0000015"
    result = workflow.get_object_properties_from_class(
        GetObjectPropertiesFromClassWorkflowParameters(class_uri=class_uri)
    )
    logger.info(result)
