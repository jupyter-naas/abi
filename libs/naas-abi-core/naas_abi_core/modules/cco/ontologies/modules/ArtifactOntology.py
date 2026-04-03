from __future__ import annotations
from typing import Annotated, Any, ClassVar, List, Optional, Union
from pydantic import BaseModel, Field
import uuid
import datetime
import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"
    _uri: str = ""
    _object_properties: ClassVar[set[str]] = set()

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    def __init__(self, **kwargs):
        uri = kwargs.pop("_uri", None)
        super().__init__(**kwargs)
        if uri is not None:
            self._uri = uri
        elif not self._uri:
            self._uri = f"{self._namespace}{uuid.uuid4()}"

    @classmethod
    def set_namespace(cls, namespace: str):
        """Set the namespace for generating URIs"""
        cls._namespace = namespace

    def rdf(
        self, subject_uri: str | None = None, visited: set[str] | None = None
    ) -> Graph:
        """Generate RDF triples for this instance

        Args:
            subject_uri: Optional URI to use as subject (defaults to self._uri)
            visited: Set of URIs that have already been processed (for cycle detection)
        """
        # Initialize visited set if not provided
        if visited is None:
            visited = set()

        g = Graph()
        g.bind("cco", CCO)
        g.bind("bfo", BFO)
        g.bind("abi", ABI)
        g.bind("rdfs", RDFS)
        g.bind("rdf", RDF)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)

        # Check if we've already processed this entity (cycle detection)
        if subject_uri in visited:
            # Already processed, just return empty graph to avoid infinite recursion
            # The relationship triple will be added by the caller
            return g

        # Mark this entity as visited before processing
        visited.add(subject_uri)

        # Add class type
        if hasattr(self, "_class_uri"):
            g.add((subject, RDF.type, URIRef(self._class_uri)))

        # Add owl:NamedIndividual type
        g.add((subject, RDF.type, OWL.NamedIndividual))

        # Add label if it exists
        if hasattr(self, "label"):
            g.add((subject, RDFS.label, Literal(self.label)))

        object_props: set[str] = getattr(self, "_object_properties", set())

        # Add properties
        if hasattr(self, "_property_uris"):
            for prop_name, prop_uri in self._property_uris.items():
                is_object_prop = prop_name in object_props
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, "rdf") and hasattr(item, "_uri"):
                                # Check if this entity was already visited to prevent cycles
                                if item._uri not in visited:
                                    # Add triples from related object
                                    g += item.rdf(visited=visited)
                                # Always add the triple, even if already visited
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            elif is_object_prop and isinstance(item, (str, URIRef)):
                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, "rdf") and hasattr(prop_value, "_uri"):
                        # Check if this entity was already visited to prevent cycles
                        if prop_value._uri not in visited:
                            # Add triples from related object
                            g += prop_value.rdf(visited=visited)
                        # Always add the triple, even if already visited
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    elif is_object_prop and isinstance(prop_value, (str, URIRef)):
                        g.add((subject, URIRef(prop_uri), URIRef(str(prop_value))))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))

        return g


class SystemRole(RDFEntity):
    """
    System Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000038"
    _name: ClassVar[str] = "System Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000170(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000170"
    _name: ClassVar[str] = "Ont00000170"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000205(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000205"
    _name: ClassVar[str] = "Ont00000205"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000253(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000253"
    _name: ClassVar[str] = "Ont00000253"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArtifactFunction(RDFEntity):
    """
    Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000323"
    _name: ClassVar[str] = "Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Payload(RDFEntity):
    """
    Depending on the nature of the Flight or Mission, the Payload of a Vehicle may include cargo, passengers, flight crew, munitions, scientific instruments or experiments, or other equipment. Extra fuel, when optionally carried, is also considered part of the payload.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000556"
    _name: ClassVar[str] = "Payload"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArtifactLocation(RDFEntity):
    """
    Artifact Location
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000591"
    _name: ClassVar[str] = "Artifact Location"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InfrastructureElement(RDFEntity):
    """
    Infrastructure Element
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000627"
    _name: ClassVar[str] = "Infrastructure Element"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000686(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000686"
    _name: ClassVar[str] = "Ont00000686"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Resource(RDFEntity):
    """
    This class is designed to group continuants according to a very broad criterion and is not intended to be used as a parent class for entities that can be more specifically represented under another class. Hence, Natural Resource may be an appropriate subtype but Money, Oil, and Gold Mine are not.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000740"
    _name: ClassVar[str] = "Resource"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ComponentRole(RDFEntity):
    """
    Component Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000758"
    _name: ClassVar[str] = "Component Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArtifactHistory(RDFEntity):
    """
    Artifact History
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000856"
    _name: ClassVar[str] = "Artifact History"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InfrastructureSystem(RDFEntity):
    """
    Infrastructure System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000870"
    _name: ClassVar[str] = "Infrastructure System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PartRole(RDFEntity):
    """
    Part Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000929"
    _name: ClassVar[str] = "Part Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000958(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000958"
    _name: ClassVar[str] = "Ont00000958"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000965(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000965"
    _name: ClassVar[str] = "Ont00000965"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialArtifact(RDFEntity):
    """
    Material Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000995"
    _name: ClassVar[str] = "Material Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InfrastructureRole(RDFEntity):
    """
    The disposition will typically be a function of an artifact, which is often designed to be part of some Infrastructure system. But not always. In some cases an entity may be repurposed to be an element of some Infrastructure. In those cases it is a capability of that entity that supports the functioning of the system.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001141"
    _name: ClassVar[str] = "Infrastructure Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ReactionMass(RDFEntity):
    """
    Reaction Mass
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001168"
    _name: ClassVar[str] = "Reaction Mass"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00001341(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001341"
    _name: ClassVar[str] = "Ont00001341"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CoolingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Cooling Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000002"
    _name: ClassVar[str] = "Cooling Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Container(MaterialArtifact, RDFEntity):
    """
    Container
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000020"
    _name: ClassVar[str] = "Container"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SensorPlatform(MaterialArtifact, RDFEntity):
    """
    Sensor Platform
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000021"
    _name: ClassVar[str] = "Sensor Platform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SensorDeploymentArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Sensor Deployment Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000023"
    _name: ClassVar[str] = "Sensor Deployment Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ControlSurface(MaterialArtifact, RDFEntity):
    """
    Control Surface
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000095"
    _name: ClassVar[str] = "Control Surface"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PropulsionSystem(MaterialArtifact, RDFEntity):
    """
    Propulsion System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000096"
    _name: ClassVar[str] = "Propulsion System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectricalArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Electrical Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000098"
    _name: ClassVar[str] = "Electrical Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class VehicleCompartment(MaterialArtifact, RDFEntity):
    """
    Vehicle Compartment
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000103"
    _name: ClassVar[str] = "Vehicle Compartment"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VentilationControlArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Ventilation Control Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000113"
    _name: ClassVar[str] = "Ventilation Control Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class InformationProcessingArtifact(MaterialArtifact, RDFEntity):
    """
    Information Processing Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000117"
    _name: ClassVar[str] = "Information Processing Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArtifactFunctionSpecification(Ont00000965, RDFEntity):
    """
    Artifact Function Specification
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000118"
    _name: ClassVar[str] = "Artifact Function Specification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VehicleTrackPoint(Ont00000170, RDFEntity):
    """
    Vehicle Track Point
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000122"
    _name: ClassVar[str] = "Vehicle Track Point"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001944": "https://www.commoncoreontologies.org/ont00001944",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001944"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    ont00001944: Optional[
        Annotated[List[Union[URIRef, VehicleTrack, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PowerTransformer(MaterialArtifact, RDFEntity):
    """
    Power Transformer
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000130"
    _name: ClassVar[str] = "Power Transformer"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OpticalInstrument(MaterialArtifact, RDFEntity):
    """
    Optical Instruments are typically constructed for the purpose of being used to aid in vision or the analysis of light.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000136"
    _name: ClassVar[str] = "Optical Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FragranceArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Fragrance Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000183"
    _name: ClassVar[str] = "Fragrance Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Facility(MaterialArtifact, RDFEntity):
    """
    Facility
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000192"
    _name: ClassVar[str] = "Facility"
    _property_uris: ClassVar[dict] = {
        "bFO_0000171": "http://purl.obolibrary.org/obo/BFO_0000171",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000171"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000171: Optional[Annotated[List[Union[Ont00001341, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class FrictionReductionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Friction Reduction Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000206"
    _name: ClassVar[str] = "Friction Reduction Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Engine(MaterialArtifact, RDFEntity):
    """
    Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000210"
    _name: ClassVar[str] = "Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LightingSystem(MaterialArtifact, RDFEntity):
    """
    Lighting System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000236"
    _name: ClassVar[str] = "Lighting System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Propeller(MaterialArtifact, RDFEntity):
    """
    Propeller
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000238"
    _name: ClassVar[str] = "Propeller"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HeatSink(MaterialArtifact, RDFEntity):
    """
    Heat Sink
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000243"
    _name: ClassVar[str] = "Heat Sink"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Shaft(MaterialArtifact, RDFEntity):
    """
    A Shaft is usually used to connect other components of a drive train that cannot be connected directly either because of the distance between them or the need to allow for relative movement between those components.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000249"
    _name: ClassVar[str] = "Shaft"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TransportationArtifact(MaterialArtifact, RDFEntity):
    """
    Transportation Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000254"
    _name: ClassVar[str] = "Transportation Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FluidControlArtifact(MaterialArtifact, RDFEntity):
    """
    Fluid Control Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000256"
    _name: ClassVar[str] = "Fluid Control Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CommunicationInterferenceArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Communication Interference Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000273"
    _name: ClassVar[str] = "Communication Interference Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PowerSource(MaterialArtifact, RDFEntity):
    """
    Power Source
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000288"
    _name: ClassVar[str] = "Power Source"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArtifactIdentifier(Ont00000686, RDFEntity):
    """
    Artifact Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000292"
    _name: ClassVar[str] = "Artifact Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArtifactDesign(Ont00000965, RDFEntity):
    """
    Artifact Design
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000319"
    _name: ClassVar[str] = "Artifact Design"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001942": "https://www.commoncoreontologies.org/ont00001942",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001942"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    ont00001942: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TransportationInfrastructure(InfrastructureSystem, RDFEntity):
    """
    Transportation Infrastructure
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000328"
    _name: ClassVar[str] = "Transportation Infrastructure"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Brake(MaterialArtifact, RDFEntity):
    """
    Brake
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000342"
    _name: ClassVar[str] = "Brake"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CommunicationInstrument(MaterialArtifact, RDFEntity):
    """
    Communication Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000346"
    _name: ClassVar[str] = "Communication Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Filter(MaterialArtifact, RDFEntity):
    """
    Filter
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000348"
    _name: ClassVar[str] = "Filter"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ResearchArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Research Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000353"
    _name: ClassVar[str] = "Research Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PowerTransformerRectifierUnit(MaterialArtifact, RDFEntity):
    """
    Power Transformer Rectifier Unit
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000372"
    _name: ClassVar[str] = "Power Transformer Rectifier Unit"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CombustionChamber(MaterialArtifact, RDFEntity):
    """
    Combustion Chamber
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000397"
    _name: ClassVar[str] = "Combustion Chamber"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DiffractionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Diffraction Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000403"
    _name: ClassVar[str] = "Diffraction Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CommunicationReceptionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Communication Reception Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000422"
    _name: ClassVar[str] = "Communication Reception Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EnhancingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Enhancing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000437"
    _name: ClassVar[str] = "Enhancing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Weapon(MaterialArtifact, RDFEntity):
    """
    Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000445"
    _name: ClassVar[str] = "Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MotionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Motion Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000448"
    _name: ClassVar[str] = "Motion Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CollimationArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Collimation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000451"
    _name: ClassVar[str] = "Collimation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TimekeepingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Timekeeping Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000452"
    _name: ClassVar[str] = "Timekeeping Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EnvironmentControlSystem(MaterialArtifact, RDFEntity):
    """
    Controlling air quality typically involves temperature control, oxygen replenishment, and removal of moisture, odor, smoke, heat, dust, airborne bacteria, carbon dioxide, and other undesired gases or particulates.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000453"
    _name: ClassVar[str] = "Environment Control System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Coupling(MaterialArtifact, RDFEntity):
    """
    Coupling
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000458"
    _name: ClassVar[str] = "Coupling"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OrientationControlArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Orientation Control Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000466"
    _name: ClassVar[str] = "Orientation Control Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LifeSupportArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Life Support Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000480"
    _name: ClassVar[str] = "Life Support Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Tripod(MaterialArtifact, RDFEntity):
    """
    Tripod
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000488"
    _name: ClassVar[str] = "Tripod"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DetonatingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Detonating Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000491"
    _name: ClassVar[str] = "Detonating Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OpticalProcessingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Optical Processing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000504"
    _name: ClassVar[str] = "Optical Processing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FinancialInstrument(MaterialArtifact, RDFEntity):
    """
    Financial Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000537"
    _name: ClassVar[str] = "Financial Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Dam(MaterialArtifact, RDFEntity):
    """
    Dam
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000561"
    _name: ClassVar[str] = "Dam"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class QualitySpecification(Ont00000965, RDFEntity):
    """
    Quality Specification
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000575"
    _name: ClassVar[str] = "Quality Specification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PowerRectifier(MaterialArtifact, RDFEntity):
    """
    Power Rectifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000577"
    _name: ClassVar[str] = "Power Rectifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Tool(MaterialArtifact, RDFEntity):
    """
    Tool
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000581"
    _name: ClassVar[str] = "Tool"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ImagingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000601"
    _name: ClassVar[str] = "Imaging Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NavigationArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Navigation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000603"
    _name: ClassVar[str] = "Navigation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ImpactShieldingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Impact Shielding Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000623"
    _name: ClassVar[str] = "Impact Shielding Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DeceptionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Deception Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000629"
    _name: ClassVar[str] = "Deception Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RefractionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Refraction Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000635"
    _name: ClassVar[str] = "Refraction Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ContainingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Containing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000651"
    _name: ClassVar[str] = "Containing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Decoy(MaterialArtifact, RDFEntity):
    """
    Decoy
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000652"
    _name: ClassVar[str] = "Decoy"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PowerTransmissionArtifact(MaterialArtifact, RDFEntity):
    """
    Power Transmission Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000663"
    _name: ClassVar[str] = "Power Transmission Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CleaningArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Cleaning Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000665"
    _name: ClassVar[str] = "Cleaning Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class BatteryTerminal(MaterialArtifact, RDFEntity):
    """
    Battery Terminal
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000668"
    _name: ClassVar[str] = "Battery Terminal"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AttitudeControlArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Attitude Control Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000679"
    _name: ClassVar[str] = "Attitude Control Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SwitchArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Switch Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000689"
    _name: ClassVar[str] = "Switch Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TerminalBoard(MaterialArtifact, RDFEntity):
    """
    Terminal Board
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000706"
    _name: ClassVar[str] = "Terminal Board"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Vehicle(MaterialArtifact, RDFEntity):
    """
    Vehicle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000713"
    _name: ClassVar[str] = "Vehicle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CounterfeitInstrument(MaterialArtifact, RDFEntity):
    """
    Counterfeit Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000719"
    _name: ClassVar[str] = "Counterfeit Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CommunicationArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Communication Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000727"
    _name: ClassVar[str] = "Communication Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class HydraulicPowerTransferUnit(MaterialArtifact, RDFEntity):
    """
    Hydraulic Power Transfer Unit
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000730"
    _name: ClassVar[str] = "Hydraulic Power Transfer Unit"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Transducer(MaterialArtifact, RDFEntity):
    """
    Transducer
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000736"
    _name: ClassVar[str] = "Transducer"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IgnitionSystem(MaterialArtifact, RDFEntity):
    """
    Ignition System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000742"
    _name: ClassVar[str] = "Ignition System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LubricationSystem(MaterialArtifact, RDFEntity):
    """
    A Lubrication System typical consists of a reservoir, pump, heat exchanger, filter, regulator, valves, sensors, pipes, and hoses. In some cases it also includes the passageways and openings within the artifact it is designed to lubricate. For example, the oil holes in a bearing and crankshaft.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000767"
    _name: ClassVar[str] = "Lubrication System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ImagingInstrument(MaterialArtifact, RDFEntity):
    """
    Imaging Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000771"
    _name: ClassVar[str] = "Imaging Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SignalDetectionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Signal Detection Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000776"
    _name: ClassVar[str] = "Signal Detection Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ControlSystem(MaterialArtifact, RDFEntity):
    """
    Control System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000781"
    _name: ClassVar[str] = "Control System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ChemicalReactionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Chemical Reaction Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000791"
    _name: ClassVar[str] = "Chemical Reaction Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class InformationBearingArtifact(MaterialArtifact, RDFEntity):
    """
    This class continues to use the word ‘bearing’ in its rdfs:label for legacy reasons. It should be understood that all instances of this class are carriers of information content entities and only, strictly speaking, a bearer of their concretizations.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000798"
    _name: ClassVar[str] = "Information Bearing Artifact"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00000958, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SubmersibleArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Submersible Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000809"
    _name: ClassVar[str] = "Submersible Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioWaveConversionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Radio Wave Conversion Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000811"
    _name: ClassVar[str] = "Radio Wave Conversion Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class InformationMediumArtifact(MaterialArtifact, RDFEntity):
    """
    An empty notebook, when manufactured, is a medium but not yet a carrier of information content. However, a book, in the sense of a novel or collection of philosophical essays or poems, depends necessarily on it carrying some information content. Thus, there are no empty books. Likewise, there are no empty databases, only portions of digital storage that have not yet been configured to carry some information content according to a database software application.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000893"
    _name: ClassVar[str] = "Information Medium Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VehicleTrack(Ont00000205, RDFEntity):
    """
    Vehicle Track
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000904"
    _name: ClassVar[str] = "Vehicle Track"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001855": "https://www.commoncoreontologies.org/ont00001855",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001855"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    ont00001855: Optional[
        Annotated[List[Union[URIRef, VehicleTrackPoint, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ComputingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Computing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000932"
    _name: ClassVar[str] = "Computing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class InhibitingMotionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Inhibiting Motion Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000937"
    _name: ClassVar[str] = "Inhibiting Motion Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TelecommunicationInfrastructure(InfrastructureSystem, RDFEntity):
    """
    Telecommunication Infrastructure
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000954"
    _name: ClassVar[str] = "Telecommunication Infrastructure"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HeatingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Heating Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001013"
    _name: ClassVar[str] = "Heating Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CommunicationSystem(MaterialArtifact, RDFEntity):
    """
    Communication System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001036"
    _name: ClassVar[str] = "Communication System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EquipmentMount(MaterialArtifact, RDFEntity):
    """
    Equipment Mount
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001042"
    _name: ClassVar[str] = "Equipment Mount"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NuclearRadiationDetectionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Nuclear Radiation Detection Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001044"
    _name: ClassVar[str] = "Nuclear Radiation Detection Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FuelSystem(MaterialArtifact, RDFEntity):
    """
    Fuel System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001060"
    _name: ClassVar[str] = "Fuel System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Laser(MaterialArtifact, RDFEntity):
    """
    Laser
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001067"
    _name: ClassVar[str] = "Laser"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FluidControlArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Fluid Control Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001070"
    _name: ClassVar[str] = "Fluid Control Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PayloadCapacity(ArtifactFunction, RDFEntity):
    """
    Payload Capacity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001071"
    _name: ClassVar[str] = "Payload Capacity"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[URIRef, Vehicle, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class PortionOfProcessedMaterial(MaterialArtifact, RDFEntity):
    """
    Portion of Processed Material
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001084"
    _name: ClassVar[str] = "Portion of Processed Material"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ReflectionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Reflection Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001085"
    _name: ClassVar[str] = "Reflection Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MeasurementArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001100"
    _name: ClassVar[str] = "Measurement Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArtifactModelName(Ont00000686, RDFEntity):
    """
    Artifact Model Name
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001103"
    _name: ClassVar[str] = "Artifact Model Name"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VehicleFrame(MaterialArtifact, RDFEntity):
    """
    Vehicle Frame
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001134"
    _name: ClassVar[str] = "Vehicle Frame"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Flywheel(MaterialArtifact, RDFEntity):
    """
    Flywheel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001140"
    _name: ClassVar[str] = "Flywheel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DamagingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Damaging Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001153"
    _name: ClassVar[str] = "Damaging Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CommunicationRelayArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Communication Relay Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001169"
    _name: ClassVar[str] = "Communication Relay Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectromagneticShieldingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Electromagnetic Shielding Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001174"
    _name: ClassVar[str] = "Electromagnetic Shielding Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NavigationSystem(MaterialArtifact, RDFEntity):
    """
    Navigation System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001187"
    _name: ClassVar[str] = "Navigation System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StructuralSupportArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Structural Support Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001200"
    _name: ClassVar[str] = "Structural Support Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LiftingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Lifting Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001211"
    _name: ClassVar[str] = "Lifting Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SignalProcessingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Signal Processing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001218"
    _name: ClassVar[str] = "Signal Processing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SensorArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Sensor Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001241"
    _name: ClassVar[str] = "Sensor Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FuelArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Fuel Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001253"
    _name: ClassVar[str] = "Fuel Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ServiceArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Service Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001301"
    _name: ClassVar[str] = "Service Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ObservationArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Observation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001306"
    _name: ClassVar[str] = "Observation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CoveringArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Covering Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001310"
    _name: ClassVar[str] = "Covering Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArticleOfClothing(MaterialArtifact, RDFEntity):
    """
    Article of Clothing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001313"
    _name: ClassVar[str] = "Article of Clothing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BearingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Bearing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001323"
    _name: ClassVar[str] = "Bearing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CircuitBreaker(MaterialArtifact, RDFEntity):
    """
    Circuit Breaker
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001343"
    _name: ClassVar[str] = "Circuit Breaker"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LegalInstrument(MaterialArtifact, RDFEntity):
    """
    Legal Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001346"
    _name: ClassVar[str] = "Legal Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ThermalControlArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Thermal Control Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001350"
    _name: ClassVar[str] = "Thermal Control Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class HealingArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Healing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001361"
    _name: ClassVar[str] = "Healing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PoweringArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Powering Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001366"
    _name: ClassVar[str] = "Powering Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MachineBearing(MaterialArtifact, RDFEntity):
    """
    Machine Bearing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001370"
    _name: ClassVar[str] = "Machine Bearing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectromagneticInductionArtifactFunction(ArtifactFunction, RDFEntity):
    """
    Electromagnetic Induction Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001371"
    _name: ClassVar[str] = "Electromagnetic Induction Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MedicalArtifact(MaterialArtifact, RDFEntity):
    """
    Medical Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001381"
    _name: ClassVar[str] = "Medical Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FilterFunction(ArtifactFunction, RDFEntity):
    """
    Although its basic function remains the same, a Filter can be used in 2 different ways:
    (1) to allow only the desired entities to pass through (e.g. removing dirt from engine oil); or
    (2) to allow everything except the desired entities to pass through (e.g. panning for gold).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001999"
    _name: ClassVar[str] = "Filter Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PropulsionControlSystem(ControlSystem, RDFEntity):
    """
    Propulsion Control System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000012"
    _name: ClassVar[str] = "Propulsion Control System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TitleDocument(LegalInstrument, RDFEntity):
    """
    Title Document
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000018"
    _name: ClassVar[str] = "Title Document"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioCommunicationReceptionArtifactFunction(
    CommunicationReceptionArtifactFunction, RDFEntity
):
    """
    Radio Communication Reception Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000022"
    _name: ClassVar[str] = "Radio Communication Reception Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NuclearReactor(PowerSource, RDFEntity):
    """
    Nuclear Reactor
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000030"
    _name: ClassVar[str] = "Nuclear Reactor"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ConveyanceArtifactFunction(MotionArtifactFunction, RDFEntity):
    """
    Conveyance Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000034"
    _name: ClassVar[str] = "Conveyance Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class WasteManagementArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Waste Management Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000036"
    _name: ClassVar[str] = "Waste Management Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ReactionEngine(Engine, RDFEntity):
    """
    Reaction Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000056"
    _name: ClassVar[str] = "Reaction Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FrequencyMeasurementArtifactFunction(MeasurementArtifactFunction, RDFEntity):
    """
    Frequency Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000062"
    _name: ClassVar[str] = "Frequency Measurement Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MilitaryArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Military Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000066"
    _name: ClassVar[str] = "Military Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class WiredCommunicationArtifactFunction(CommunicationArtifactFunction, RDFEntity):
    """
    Wired Communication Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000076"
    _name: ClassVar[str] = "Wired Communication Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CuttingWeapon(Weapon, RDFEntity):
    """
    Cutting Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000081"
    _name: ClassVar[str] = "Cutting Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BidirectionalTransducer(Transducer, RDFEntity):
    """
    Bidirectional Transducer
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000092"
    _name: ClassVar[str] = "Bidirectional Transducer"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AirInlet(FluidControlArtifact, RDFEntity):
    """
    Air Inlet
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000111"
    _name: ClassVar[str] = "Air Inlet"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Pump(FluidControlArtifact, RDFEntity):
    """
    Pump
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000116"
    _name: ClassVar[str] = "Pump"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RecordingDevice(InformationProcessingArtifact, RDFEntity):
    """
    Recording Device
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000132"
    _name: ClassVar[str] = "Recording Device"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CargoCabin(VehicleCompartment, RDFEntity):
    """
    Cargo Cabin
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000143"
    _name: ClassVar[str] = "Cargo Cabin"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncendiaryWeapon(Weapon, RDFEntity):
    """
    Incendiary Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000145"
    _name: ClassVar[str] = "Incendiary Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeneratorControlUnit(ControlSystem, RDFEntity):
    """
    Generator Control Unit
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000153"
    _name: ClassVar[str] = "Generator Control Unit"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfATimekeepingInstrument(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Timekeeping Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000159"
    _name: ClassVar[str] = "Material Copy of a Timekeeping Instrument"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00000958, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ManualTool(Tool, RDFEntity):
    """
    Manual Tool
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000160"
    _name: ClassVar[str] = "Manual Tool"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfACertificate(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Certificate
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000189"
    _name: ClassVar[str] = "Material Copy of a Certificate"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002002, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Camera(ImagingInstrument, RDFEntity):
    """
    Camera
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000199"
    _name: ClassVar[str] = "Camera"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ChemicalWeapon(Weapon, RDFEntity):
    """
    Chemical Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000212"
    _name: ClassVar[str] = "Chemical Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DiffractionGrating(OpticalInstrument, RDFEntity):
    """
    Diffraction Grating
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000230"
    _name: ClassVar[str] = "Diffraction Grating"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FragmentationArtifactFunction(DamagingArtifactFunction, RDFEntity):
    """
    Fragmentation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000244"
    _name: ClassVar[str] = "Fragmentation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Nozzle(FluidControlArtifact, RDFEntity):
    """
    Nozzle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000252"
    _name: ClassVar[str] = "Nozzle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HydraulicFluidReservoir(Container, RDFEntity):
    """
    Hydraulic Fluid Reservoir
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000264"
    _name: ClassVar[str] = "Hydraulic Fluid Reservoir"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HearingAid(MedicalArtifact, RDFEntity):
    """
    Hearing Aid
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000266"
    _name: ClassVar[str] = "Hearing Aid"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CatalystArtifactFunction(ChemicalReactionArtifactFunction, RDFEntity):
    """
    Catalyst Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000267"
    _name: ClassVar[str] = "Catalyst Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NuclearWeapon(Weapon, RDFEntity):
    """
    Nuclear Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000277"
    _name: ClassVar[str] = "Nuclear Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CounterfeitFinancialInstrument(CounterfeitInstrument, RDFEntity):
    """
    Counterfeit Financial Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000282"
    _name: ClassVar[str] = "Counterfeit Financial Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InertialNavigationSystem(NavigationSystem, RDFEntity):
    """
    Inertial Navigation System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000287"
    _name: ClassVar[str] = "Inertial Navigation System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadarImagingArtifactFunction(ImagingArtifactFunction, RDFEntity):
    """
    Radar Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000289"
    _name: ClassVar[str] = "Radar Imaging Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class VehicleTransmission(PowerTransmissionArtifact, RDFEntity):
    """
    Vehicle Transmission
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000301"
    _name: ClassVar[str] = "Vehicle Transmission"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IntercommunicationSystem(CommunicationSystem, RDFEntity):
    """
    Intercommunication System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000303"
    _name: ClassVar[str] = "Intercommunication System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Microscope(ImagingInstrument, RDFEntity):
    """
    Microscope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000304"
    _name: ClassVar[str] = "Microscope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Hinge(MachineBearing, RDFEntity):
    """
    Hinge
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000306"
    _name: ClassVar[str] = "Hinge"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfFood(PortionOfProcessedMaterial, RDFEntity):
    """
    Portion of Food
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000307"
    _name: ClassVar[str] = "Portion of Food"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HealthcareArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Healthcare Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000309"
    _name: ClassVar[str] = "Healthcare Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FiltrationArtifactFunction(FilterFunction, RDFEntity):
    """
    Filtration Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000311"
    _name: ClassVar[str] = "Filtration Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectronicSignalProcessingArtifactFunction(
    SignalProcessingArtifactFunction, RDFEntity
):
    """
    Electronic Signal Processing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000317"
    _name: ClassVar[str] = "Electronic Signal Processing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ResidentialArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Residential Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000321"
    _name: ClassVar[str] = "Residential Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Fan(FluidControlArtifact, RDFEntity):
    """
    Fan
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000338"
    _name: ClassVar[str] = "Fan"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CoolingSystem(EnvironmentControlSystem, RDFEntity):
    """
    Cooling System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000350"
    _name: ClassVar[str] = "Cooling System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectricalResistanceArtifactFunction(ElectricalArtifactFunction, RDFEntity):
    """
    Electrical Resistance Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000407"
    _name: ClassVar[str] = "Electrical Resistance Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SparkIgnitionSystem(IgnitionSystem, RDFEntity):
    """
    Spark Ignition System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000409"
    _name: ClassVar[str] = "Spark Ignition System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SpeedMeasurementArtifactFunction(MeasurementArtifactFunction, RDFEntity):
    """
    Speed Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000411"
    _name: ClassVar[str] = "Speed Measurement Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OxidizerArtifactFunction(ChemicalReactionArtifactFunction, RDFEntity):
    """
    Oxidizer Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000412"
    _name: ClassVar[str] = "Oxidizer Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Computer(InformationProcessingArtifact, RDFEntity):
    """
    Computer
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000420"
    _name: ClassVar[str] = "Computer"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Watercraft(Vehicle, RDFEntity):
    """
    Watercraft
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000440"
    _name: ClassVar[str] = "Watercraft"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CompressionIgnitionSystem(IgnitionSystem, RDFEntity):
    """
    Compression Ignition System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000454"
    _name: ClassVar[str] = "Compression Ignition System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfMaterial(PortionOfProcessedMaterial, RDFEntity):
    """
    Portion of Material
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000457"
    _name: ClassVar[str] = "Portion of Material"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfCash(FinancialInstrument, RDFEntity):
    """
    Portion of Cash
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000475"
    _name: ClassVar[str] = "Portion of Cash"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ResearchAndDevelopmentArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Research and Development Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000481"
    _name: ClassVar[str] = "Research and Development Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioCommunicationInterferenceArtifactFunction(
    CommunicationInterferenceArtifactFunction, RDFEntity
):
    """
    Radio Communication Interference Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000495"
    _name: ClassVar[str] = "Radio Communication Interference Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PneumaticPowerSource(PowerSource, RDFEntity):
    """
    Pneumatic Power Source
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000516"
    _name: ClassVar[str] = "Pneumatic Power Source"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CuttingArtifactFunction(DamagingArtifactFunction, RDFEntity):
    """
    Cutting Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000534"
    _name: ClassVar[str] = "Cutting Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Telescope(ImagingInstrument, RDFEntity):
    """
    Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000547"
    _name: ClassVar[str] = "Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WaterTransportationArtifact(TransportationArtifact, RDFEntity):
    """
    Water Transportation Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000549"
    _name: ClassVar[str] = "Water Transportation Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ExplosiveWeapon(Weapon, RDFEntity):
    """
    Explosive Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000552"
    _name: ClassVar[str] = "Explosive Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Sensor(Transducer, RDFEntity):
    """
    Sensor
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000569"
    _name: ClassVar[str] = "Sensor"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ControllablePitchPropeller(Propeller, RDFEntity):
    """
    Controllable Pitch Propeller
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000586"
    _name: ClassVar[str] = "Controllable Pitch Propeller"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAInstrumentDisplayPanel(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Instrument Display Panel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000597"
    _name: ClassVar[str] = "Material Copy of a Instrument Display Panel"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00000958, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Valve(FluidControlArtifact, RDFEntity):
    """
    Valve
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000598"
    _name: ClassVar[str] = "Valve"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LegalArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Legal Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000600"
    _name: ClassVar[str] = "Legal Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GroundVehicle(Vehicle, RDFEntity):
    """
    Ground Vehicle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000618"
    _name: ClassVar[str] = "Ground Vehicle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NozzleThroat(FluidControlArtifact, RDFEntity):
    """
    Nozzle Throat
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000625"
    _name: ClassVar[str] = "Nozzle Throat"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HeatEngine(Engine, RDFEntity):
    """
    Heat Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000638"
    _name: ClassVar[str] = "Heat Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadiologicalWeapon(Weapon, RDFEntity):
    """
    Radiological Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000656"
    _name: ClassVar[str] = "Radiological Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DistanceMeasurementArtifactFunction(MeasurementArtifactFunction, RDFEntity):
    """
    Distance Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000657"
    _name: ClassVar[str] = "Distance Measurement Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GovernmentArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Government Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000661"
    _name: ClassVar[str] = "Government Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class VoltageRegulatingArtifactFunction(ElectricalArtifactFunction, RDFEntity):
    """
    Voltage Regulating Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000678"
    _name: ClassVar[str] = "Voltage Regulating Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ExternalNavigationLightingSystem(LightingSystem, RDFEntity):
    """
    External Navigation Lighting System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000681"
    _name: ClassVar[str] = "External Navigation Lighting System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Mirror(OpticalInstrument, RDFEntity):
    """
    Mirror
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000682"
    _name: ClassVar[str] = "Mirror"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelecommunicationInstrument(CommunicationInstrument, RDFEntity):
    """
    Telecommunication Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000690"
    _name: ClassVar[str] = "Telecommunication Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FuelTank(Container, RDFEntity):
    """
    Fuel Tank
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000691"
    _name: ClassVar[str] = "Fuel Tank"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MassSpecification(QualitySpecification, RDFEntity):
    """
    Mass Specification
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000693"
    _name: ClassVar[str] = "Mass Specification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NozzleMouth(FluidControlArtifact, RDFEntity):
    """
    Nozzle Mouth
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000694"
    _name: ClassVar[str] = "Nozzle Mouth"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAnImage(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of an Image
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000702"
    _name: ClassVar[str] = "Material Copy of an Image"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002004, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Prosthesis(MedicalArtifact, RDFEntity):
    """
    Prosthesis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000715"
    _name: ClassVar[str] = "Prosthesis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CryogenicStorageDewar(Container, RDFEntity):
    """
    Cryogenic Storage Dewar
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000720"
    _name: ClassVar[str] = "Cryogenic Storage Dewar"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VehicleControlSystem(ControlSystem, RDFEntity):
    """
    Vehicle Control System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000723"
    _name: ClassVar[str] = "Vehicle Control System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfADatabase(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Database
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000756"
    _name: ClassVar[str] = "Material Copy of a Database"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002006, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OpticalFocusingArtifactFunction(OpticalProcessingArtifactFunction, RDFEntity):
    """
    Optical Focusing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000764"
    _name: ClassVar[str] = "Optical Focusing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FuelVentilationSystem(FluidControlArtifact, RDFEntity):
    """
    Fuel Ventilation System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000793"
    _name: ClassVar[str] = "Fuel Ventilation System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectricalConductionArtifactFunction(ElectricalArtifactFunction, RDFEntity):
    """
    Electrical Conduction Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000795"
    _name: ClassVar[str] = "Electrical Conduction Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfAList(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a List
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000799"
    _name: ClassVar[str] = "Material Copy of a List"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002007, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Prism(OpticalInstrument, RDFEntity):
    """
    Prism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000804"
    _name: ClassVar[str] = "Prism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PowerTool(Tool, RDFEntity):
    """
    Power Tool
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000806"
    _name: ClassVar[str] = "Power Tool"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ReactantArtifactFunction(ChemicalReactionArtifactFunction, RDFEntity):
    """
    Reactant Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000808"
    _name: ClassVar[str] = "Reactant Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TelecommunicationNetworkLine(CommunicationInstrument, RDFEntity):
    """
    Telecommunication Network Line
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000825"
    _name: ClassVar[str] = "Telecommunication Network Line"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ExplosiveArtifactFunction(DamagingArtifactFunction, RDFEntity):
    """
    Explosive Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000841"
    _name: ClassVar[str] = "Explosive Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class HeatingSystem(EnvironmentControlSystem, RDFEntity):
    """
    Heating System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000849"
    _name: ClassVar[str] = "Heating System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PublicSafetyArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Public Safety Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000864"
    _name: ClassVar[str] = "Public Safety Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfAVideo(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Video
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000874"
    _name: ClassVar[str] = "Material Copy of a Video"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002009, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ReligiousArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Religious Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000880"
    _name: ClassVar[str] = "Religious Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class WiredCommunicationReceptionArtifactFunction(
    CommunicationReceptionArtifactFunction, RDFEntity
):
    """
    Wired Communication Reception Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000886"
    _name: ClassVar[str] = "Wired Communication Reception Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioCommunicationRelayArtifactFunction(
    CommunicationRelayArtifactFunction, RDFEntity
):
    """
    Radio Communication Relay Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000900"
    _name: ClassVar[str] = "Radio Communication Relay Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioCommunicationInstrument(CommunicationInstrument, RDFEntity):
    """
    Radio Communication Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000903"
    _name: ClassVar[str] = "Radio Communication Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelecommunicationNetworkNode(CommunicationInstrument, RDFEntity):
    """
    Telecommunication Network Node
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000918"
    _name: ClassVar[str] = "Telecommunication Network Node"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000176: Optional[
        Annotated[List[Union[TelecommunicationNetwork, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PartsList(QualitySpecification, RDFEntity):
    """
    Parts List
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000919"
    _name: ClassVar[str] = "Parts List"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FinancialArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Financial Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000938"
    _name: ClassVar[str] = "Financial Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ThermalImagingArtifactFunction(ImagingArtifactFunction, RDFEntity):
    """
    Thermal Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000944"
    _name: ClassVar[str] = "Thermal Imaging Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TemperatureMeasurementArtifactFunction(MeasurementArtifactFunction, RDFEntity):
    """
    Temperature Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000947"
    _name: ClassVar[str] = "Temperature Measurement Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectricMotor(Engine, RDFEntity):
    """
    Electric Motor
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000952"
    _name: ClassVar[str] = "Electric Motor"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CurrentConversionArtifactFunction(ElectricalArtifactFunction, RDFEntity):
    """
    Current Conversion Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000961"
    _name: ClassVar[str] = "Current Conversion Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FuelTransferSystem(FluidControlArtifact, RDFEntity):
    """
    Fuel Transfer System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000963"
    _name: ClassVar[str] = "Fuel Transfer System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfWasteMaterial(PortionOfProcessedMaterial, RDFEntity):
    """
    Portion of Waste Material
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000980"
    _name: ClassVar[str] = "Portion of Waste Material"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ThermalInsulationArtifactFunction(ThermalControlArtifactFunction, RDFEntity):
    """
    Thermal Insulation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000985"
    _name: ClassVar[str] = "Thermal Insulation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectricalPowerProductionArtifactFunction(ElectricalArtifactFunction, RDFEntity):
    """
    Electrical Power Production Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000994"
    _name: ClassVar[str] = "Electrical Power Production Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TelecommunicationNetwork(CommunicationSystem, RDFEntity):
    """
    Telecommunication Network
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000998"
    _name: ClassVar[str] = "Telecommunication Network"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAMessage(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001002"
    _name: ClassVar[str] = "Material Copy of a Message"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002010, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class BiologicalWeapon(Weapon, RDFEntity):
    """
    Biological Weapon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001008"
    _name: ClassVar[str] = "Biological Weapon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TrimTab(ControlSurface, RDFEntity):
    """
    Trim Tab
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001027"
    _name: ClassVar[str] = "Trim Tab"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Aircraft(Vehicle, RDFEntity):
    """
    Aircraft
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001043"
    _name: ClassVar[str] = "Aircraft"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArtifactModel(ArtifactDesign, RDFEntity):
    """
    Artifact Model
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001045"
    _name: ClassVar[str] = "Artifact Model"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001942": "https://www.commoncoreontologies.org/ont00001942",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001942"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    ont00001942: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectricalPowerSource(PowerSource, RDFEntity):
    """
    Electrical Power Source
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001049"
    _name: ClassVar[str] = "Electrical Power Source"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ProjectileLauncher(Weapon, RDFEntity):
    """
    Projectile Launcher
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001051"
    _name: ClassVar[str] = "Projectile Launcher"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfABarcode(InformationBearingArtifact, RDFEntity):
    """
    For information on types of barcodes, see: https://www.scandit.com/types-barcodes-choosing-right-barcode/
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001064"
    _name: ClassVar[str] = "Material Copy of a Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002014, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OrientationObservationArtifactFunction(ObservationArtifactFunction, RDFEntity):
    """
    Orientation Observation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001087"
    _name: ClassVar[str] = "Orientation Observation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectricalPowerStorageArtifactFunction(ElectricalArtifactFunction, RDFEntity):
    """
    Electrical Power Storage Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001092"
    _name: ClassVar[str] = "Electrical Power Storage Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PoisonArtifactFunction(DamagingArtifactFunction, RDFEntity):
    """
    Poison Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001123"
    _name: ClassVar[str] = "Poison Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PressurizationControlArtifactFunction(
    VentilationControlArtifactFunction, RDFEntity
):
    """
    Pressurization Control Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001129"
    _name: ClassVar[str] = "Pressurization Control Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Spacecraft(Vehicle, RDFEntity):
    """
    Spacecraft
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001139"
    _name: ClassVar[str] = "Spacecraft"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectromagneticCommunicationArtifactFunction(
    CommunicationArtifactFunction, RDFEntity
):
    """
    Electromagnetic Communication Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001148"
    _name: ClassVar[str] = "Electromagnetic Communication Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PortionOfAmmunition(Weapon, RDFEntity):
    """
    Portion of Ammunition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001150"
    _name: ClassVar[str] = "Portion of Ammunition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfPaper(InformationMediumArtifact, RDFEntity):
    """
    Portion of Paper
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001151"
    _name: ClassVar[str] = "Portion of Paper"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FullMotionVideoImagingArtifactFunction(ImagingArtifactFunction, RDFEntity):
    """
    Full Motion Video Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001155"
    _name: ClassVar[str] = "Full Motion Video Imaging Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfAInformationLine(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Information Line
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001156"
    _name: ClassVar[str] = "Material Copy of a Information Line"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002037, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class HydraulicPowerSource(PowerSource, RDFEntity):
    """
    Hydraulic Power Source
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001157"
    _name: ClassVar[str] = "Hydraulic Power Source"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Bond(FinancialInstrument, RDFEntity):
    """
    Bond
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001159"
    _name: ClassVar[str] = "Bond"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SolventArtifactFunction(ChemicalReactionArtifactFunction, RDFEntity):
    """
    Solvent Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001160"
    _name: ClassVar[str] = "Solvent Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CounterfeitLegalInstrument(CounterfeitInstrument, RDFEntity):
    """
    Counterfeit Legal Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001161"
    _name: ClassVar[str] = "Counterfeit Legal Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DigitalStorageDevice(InformationMediumArtifact, RDFEntity):
    """
    Digital Storage Device
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001179"
    _name: ClassVar[str] = "Digital Storage Device"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Rocket(Vehicle, RDFEntity):
    """
    Rocket
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001185"
    _name: ClassVar[str] = "Rocket"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OpticalLens(OpticalInstrument, RDFEntity):
    """
    Optical Lens
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001207"
    _name: ClassVar[str] = "Optical Lens"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RetailArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Retail Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001210"
    _name: ClassVar[str] = "Retail Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Periscope(OpticalInstrument, RDFEntity):
    """
    Periscope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001216"
    _name: ClassVar[str] = "Periscope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PhysicallyPoweredEngine(Engine, RDFEntity):
    """
    Physically Powered Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001221"
    _name: ClassVar[str] = "Physically Powered Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CrushingArtifactFunction(DamagingArtifactFunction, RDFEntity):
    """
    Crushing Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001233"
    _name: ClassVar[str] = "Crushing Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NeutralizationArtifactFunction(ChemicalReactionArtifactFunction, RDFEntity):
    """
    Neutralization Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001234"
    _name: ClassVar[str] = "Neutralization Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Actuator(Transducer, RDFEntity):
    """
    Actuator
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001242"
    _name: ClassVar[str] = "Actuator"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfADocumentField(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Document Field
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001243"
    _name: ClassVar[str] = "Material Copy of a Document Field"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002038, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CabinPressurizationControlSystem(EnvironmentControlSystem, RDFEntity):
    """
    Cabin Pressurization Control System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001249"
    _name: ClassVar[str] = "Cabin Pressurization Control System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InteriorLightingSystem(LightingSystem, RDFEntity):
    """
    Interior Lighting System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001250"
    _name: ClassVar[str] = "Interior Lighting System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PropulsionArtifactFunction(MotionArtifactFunction, RDFEntity):
    """
    Propulsion Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001252"
    _name: ClassVar[str] = "Propulsion Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PublicAddressSystem(CommunicationSystem, RDFEntity):
    """
    Public Address System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001265"
    _name: ClassVar[str] = "Public Address System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WiredCommunicationRelayArtifactFunction(
    CommunicationRelayArtifactFunction, RDFEntity
):
    """
    Wired Communication Relay Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001271"
    _name: ClassVar[str] = "Wired Communication Relay Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SensorModalityFunction(SensorArtifactFunction, RDFEntity):
    """
    Sensor Modality Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001273"
    _name: ClassVar[str] = "Sensor Modality Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[Annotated[List[Union[Sensor, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Stock(FinancialInstrument, RDFEntity):
    """
    Stock
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001278"
    _name: ClassVar[str] = "Stock"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EmulsifierArtifactFunction(ChemicalReactionArtifactFunction, RDFEntity):
    """
    Emulsifier Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001281"
    _name: ClassVar[str] = "Emulsifier Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfADocument(InformationBearingArtifact, RDFEntity):
    """
    Material Copy of a Document
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001298"
    _name: ClassVar[str] = "Material Copy of a Document"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002039, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PositionObservationArtifactFunction(ObservationArtifactFunction, RDFEntity):
    """
    Position Observation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001303"
    _name: ClassVar[str] = "Position Observation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DimensionSpecification(QualitySpecification, RDFEntity):
    """
    Dimension Specification
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001304"
    _name: ClassVar[str] = "Dimension Specification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Gimbal(EquipmentMount, RDFEntity):
    """
    Gimbal
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001316"
    _name: ClassVar[str] = "Gimbal"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LandTransportationArtifact(TransportationArtifact, RDFEntity):
    """
    Land Transportation Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001326"
    _name: ClassVar[str] = "Land Transportation Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EducationArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Education Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001329"
    _name: ClassVar[str] = "Education Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SpeedArtifactFunction(MotionArtifactFunction, RDFEntity):
    """
    Speed Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001353"
    _name: ClassVar[str] = "Speed Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MotionObservationArtifactFunction(ObservationArtifactFunction, RDFEntity):
    """
    Motion Observation Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001368"
    _name: ClassVar[str] = "Motion Observation Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FertilizerArtifactFunction(EnhancingArtifactFunction, RDFEntity):
    """
    Fertilizer Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001372"
    _name: ClassVar[str] = "Fertilizer Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class HospitalityArtifactFunction(ServiceArtifactFunction, RDFEntity):
    """
    Hospitality Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001378"
    _name: ClassVar[str] = "Hospitality Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DeflectingPrism(Prism, RDFEntity):
    """
    Deflecting Prism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000001"
    _name: ClassVar[str] = "Deflecting Prism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PowerInvertingArtifactFunction(CurrentConversionArtifactFunction, RDFEntity):
    """
    Power Inverting Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000019"
    _name: ClassVar[str] = "Power Inverting Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectronicStock(Stock, RDFEntity):
    """
    Electronic Stock
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000025"
    _name: ClassVar[str] = "Electronic Stock"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DispersivePrism(Prism, RDFEntity):
    """
    Dispersive Prism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000028"
    _name: ClassVar[str] = "Dispersive Prism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FlowControlValve(Valve, RDFEntity):
    """
    Flow Control Valves are often more complex than a simple Valve and typically include an Actuator that is capable of automatically adjusting the state of the valve in response to signals from a connected Sensor or Controller.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000047"
    _name: ClassVar[str] = "Flow Control Valve"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Banknote(PortionOfCash, RDFEntity):
    """
    Banknote
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000049"
    _name: ClassVar[str] = "Banknote"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VeryHighFrequencyCommunicationInstrument(RadioCommunicationInstrument, RDFEntity):
    """
    Very High Frequency Communication Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000050"
    _name: ClassVar[str] = "Very High Frequency Communication Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GroundMotorVehicle(GroundVehicle, RDFEntity):
    """
    Ground Motor Vehicle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000053"
    _name: ClassVar[str] = "Ground Motor Vehicle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelephoneLine(TelecommunicationNetworkLine, RDFEntity):
    """
    Telephone Line
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000059"
    _name: ClassVar[str] = "Telephone Line"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfABook(MaterialCopyOfADocument, RDFEntity):
    """
    Material Copy of a Book
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000064"
    _name: ClassVar[str] = "Material Copy of a Book"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002040, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfATranscript(MaterialCopyOfADocument, RDFEntity):
    """
    Material Copy of a Transcript
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000069"
    _name: ClassVar[str] = "Material Copy of a Transcript"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002041, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OpticalMicroscope(Microscope, RDFEntity):
    """
    Optical Microscope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000075"
    _name: ClassVar[str] = "Optical Microscope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AutopilotSystem(VehicleControlSystem, RDFEntity):
    """
    Autopilot System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000086"
    _name: ClassVar[str] = "Autopilot System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Firearm(ProjectileLauncher, RDFEntity):
    """
    Firearm
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000088"
    _name: ClassVar[str] = "Firearm"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InfraredTelescope(Telescope, RDFEntity):
    """
    Infrared Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000090"
    _name: ClassVar[str] = "Infrared Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfCoolant(PortionOfMaterial, RDFEntity):
    """
    Portion of Coolant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000091"
    _name: ClassVar[str] = "Portion of Coolant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PreferredStock(Stock, RDFEntity):
    """
    Preferred Stock
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000093"
    _name: ClassVar[str] = "Preferred Stock"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ComplexOpticalLens(OpticalLens, RDFEntity):
    """
    Complex Optical Lens
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000097"
    _name: ClassVar[str] = "Complex Optical Lens"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelephoneNetwork(TelecommunicationNetwork, RDFEntity):
    """
    Telephone Network
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000152"
    _name: ClassVar[str] = "Telephone Network"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectricalConnectorArtifactFunction(
    ElectricalConductionArtifactFunction, RDFEntity
):
    """
    Electrical Connector Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000162"
    _name: ClassVar[str] = "Electrical Connector Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class UltravioletTelescope(Telescope, RDFEntity):
    """
    Ultraviolet Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000174"
    _name: ClassVar[str] = "Ultraviolet Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Arrow(PortionOfAmmunition, RDFEntity):
    """
    Arrow
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000178"
    _name: ClassVar[str] = "Arrow"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MinimumSpeedArtifactFunction(SpeedArtifactFunction, RDFEntity):
    """
    Minimum Speed Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000190"
    _name: ClassVar[str] = "Minimum Speed Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectricalContactArtifactFunction(
    ElectricalConductionArtifactFunction, RDFEntity
):
    """
    Electrical Contact Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000194"
    _name: ClassVar[str] = "Electrical Contact Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MovingTargetIndicationArtifactFunction(RadarImagingArtifactFunction, RDFEntity):
    """
    Moving Target Indication Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000214"
    _name: ClassVar[str] = "Moving Target Indication Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioTelescope(Telescope, RDFEntity):
    """
    A Radio Telescope consists of a specialized Antenna and a Radio Receiver and is typically used to receive radio waves from sources in outer space.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000215"
    _name: ClassVar[str] = "Radio Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Shell(PortionOfAmmunition, RDFEntity):
    """
    Shell
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000216"
    _name: ClassVar[str] = "Shell"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TorpedoTube(ProjectileLauncher, RDFEntity):
    """
    Torpedo Tube
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000231"
    _name: ClassVar[str] = "Torpedo Tube"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StockCertificate(Stock, RDFEntity):
    """
    Stock Certificate
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000233"
    _name: ClassVar[str] = "Stock Certificate"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfATwoDimensionalBarcode(MaterialCopyOfABarcode, RDFEntity):
    """
    Material Copy of a Two-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000241"
    _name: ClassVar[str] = "Material Copy of a Two-Dimensional Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002015, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Road(LandTransportationArtifact, RDFEntity):
    """
    Road
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000247"
    _name: ClassVar[str] = "Road"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfCryogenicMaterial(PortionOfMaterial, RDFEntity):
    """
    Portion of Cryogenic Material
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000255"
    _name: ClassVar[str] = "Portion of Cryogenic Material"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAOneDimensionalBarcode(MaterialCopyOfABarcode, RDFEntity):
    """
    Material Copy of a One-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000258"
    _name: ClassVar[str] = "Material Copy of a One-Dimensional Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002020, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Cannon(ProjectileLauncher, RDFEntity):
    """
    Cannon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000268"
    _name: ClassVar[str] = "Cannon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioTransmitter(RadioCommunicationInstrument, RDFEntity):
    """
    Radio Transmitter
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000269"
    _name: ClassVar[str] = "Radio Transmitter"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ProstheticLeg(Prosthesis, RDFEntity):
    """
    Prosthetic Leg
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000299"
    _name: ClassVar[str] = "Prosthetic Leg"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AlternatingCurrentPowerSource(ElectricalPowerSource, RDFEntity):
    """
    Alternating Current Power Source
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000302"
    _name: ClassVar[str] = "Alternating Current Power Source"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Grenade(ExplosiveWeapon, RDFEntity):
    """
    Grenade
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000310"
    _name: ClassVar[str] = "Grenade"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelecommunicationSwitchingNode(TelecommunicationNetworkNode, RDFEntity):
    """
    Telecommunication Switching Node
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000315"
    _name: ClassVar[str] = "Telecommunication Switching Node"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000176: Optional[
        Annotated[List[Union[TelecommunicationNetwork, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioTransponder(RadioCommunicationInstrument, RDFEntity):
    """
    Radio Transponder
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000325"
    _name: ClassVar[str] = "Radio Transponder"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Interphone(IntercommunicationSystem, RDFEntity):
    """
    Interphone
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000334"
    _name: ClassVar[str] = "Interphone"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ProstheticArm(Prosthesis, RDFEntity):
    """
    Prosthetic Arm
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000341"
    _name: ClassVar[str] = "Prosthetic Arm"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SurfactantArtifactFunction(EmulsifierArtifactFunction, RDFEntity):
    """
    Surfactant Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000344"
    _name: ClassVar[str] = "Surfactant Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectronicBond(Bond, RDFEntity):
    """
    Electronic Bond
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000347"
    _name: ClassVar[str] = "Electronic Bond"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SatelliteArtifact(Spacecraft, RDFEntity):
    """
    Satellite Artifact
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000352"
    _name: ClassVar[str] = "Satellite Artifact"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WirelessTelecommunicationNetwork(TelecommunicationNetwork, RDFEntity):
    """
    Wireless Telecommunication Network
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000363"
    _name: ClassVar[str] = "Wireless Telecommunication Network"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PneumaticMotor(PhysicallyPoweredEngine, RDFEntity):
    """
    Pneumatic Motor
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000364"
    _name: ClassVar[str] = "Pneumatic Motor"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfGalliumArsenide(PortionOfMaterial, RDFEntity):
    """
    Portion of Gallium Arsenide
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000376"
    _name: ClassVar[str] = "Portion of Gallium Arsenide"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfASpreadsheet(MaterialCopyOfADocument, RDFEntity):
    """
    Material Copy of a Spreadsheet
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000382"
    _name: ClassVar[str] = "Material Copy of a Spreadsheet"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002042, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ElectronMicroscope(Microscope, RDFEntity):
    """
    Electron Microscope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000413"
    _name: ClassVar[str] = "Electron Microscope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ProstheticHand(Prosthesis, RDFEntity):
    """
    Prosthetic Hand
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000417"
    _name: ClassVar[str] = "Prosthetic Hand"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RailwayJunction(LandTransportationArtifact, RDFEntity):
    """
    Railway Junction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000428"
    _name: ClassVar[str] = "Railway Junction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SimpleOpticalLens(OpticalLens, RDFEntity):
    """
    Simple Optical Lens
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000434"
    _name: ClassVar[str] = "Simple Optical Lens"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class XrayMicroscope(Microscope, RDFEntity):
    """
    X-ray Microscope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000436"
    _name: ClassVar[str] = "X-ray Microscope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Railway(LandTransportationArtifact, RDFEntity):
    """
    Railway
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000456"
    _name: ClassVar[str] = "Railway"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAAcademicDegree(MaterialCopyOfACertificate, RDFEntity):
    """
    Material Copy of a Academic Degree
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000470"
    _name: ClassVar[str] = "Material Copy of a Academic Degree"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002003, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FuelCell(ElectricalPowerSource, RDFEntity):
    """
    Fuel Cell
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000477"
    _name: ClassVar[str] = "Fuel Cell"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SyntheticApertureRadarImagingArtifactFunction(
    RadarImagingArtifactFunction, RDFEntity
):
    """
    Synthetic Aperture Radar Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000482"
    _name: ClassVar[str] = "Synthetic Aperture Radar Imaging Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfACodeList(MaterialCopyOfAList, RDFEntity):
    """
    Material Copy of a Code List
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000493"
    _name: ClassVar[str] = "Material Copy of a Code List"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002008, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class AirConditioningUnit(CoolingSystem, RDFEntity):
    """
    Air Conditioning Unit
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000524"
    _name: ClassVar[str] = "Air Conditioning Unit"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GammarayTelescope(Telescope, RDFEntity):
    """
    Gamma-ray Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000526"
    _name: ClassVar[str] = "Gamma-ray Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class JetEngine(ReactionEngine, RDFEntity):
    """
    Some (most) jet engines utilize turbines, but some do not. Most rocket engines do not utilize turbines, but some do.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000533"
    _name: ClassVar[str] = "Jet Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BondCertificate(Bond, RDFEntity):
    """
    Bond Certificate
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000536"
    _name: ClassVar[str] = "Bond Certificate"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ArticleOfSolidWaste(PortionOfWasteMaterial, RDFEntity):
    """
    Article of Solid Waste
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000571"
    _name: ClassVar[str] = "Article of Solid Waste"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfPropellant(PortionOfMaterial, RDFEntity):
    """
    Portion of Propellant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000593"
    _name: ClassVar[str] = "Portion of Propellant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InfraredCamera(Camera, RDFEntity):
    """
    Infrared Camera
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000617"
    _name: ClassVar[str] = "Infrared Camera"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAReport(MaterialCopyOfADocument, RDFEntity):
    """
    Material Copy of a Report
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000624"
    _name: ClassVar[str] = "Material Copy of a Report"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002043, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfAEmailMessage(MaterialCopyOfAMessage, RDFEntity):
    """
    Material Copy of a Email Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000640"
    _name: ClassVar[str] = "Material Copy of a Email Message"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002012, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MissileLauncher(ProjectileLauncher, RDFEntity):
    """
    Missile Launcher
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000658"
    _name: ClassVar[str] = "Missile Launcher"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ProstheticFoot(Prosthesis, RDFEntity):
    """
    Prosthetic Foot
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000673"
    _name: ClassVar[str] = "Prosthetic Foot"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ConvergentDivergentNozzle(Nozzle, RDFEntity):
    """
    By increasing the Exhaust Velocity of the gas, the Nozzle increases the Thrust generated.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000698"
    _name: ClassVar[str] = "Convergent-Divergent Nozzle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ComputerNetwork(TelecommunicationNetwork, RDFEntity):
    """
    Computer Network
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000700"
    _name: ClassVar[str] = "Computer Network"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfASystemClock(MaterialCopyOfATimekeepingInstrument, RDFEntity):
    """
    Material Copy of a System Clock
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000703"
    _name: ClassVar[str] = "Material Copy of a System Clock"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00000958, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Tunnel(LandTransportationArtifact, RDFEntity):
    """
    Tunnel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000704"
    _name: ClassVar[str] = "Tunnel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectricBattery(ElectricalPowerSource, RDFEntity):
    """
    Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000716"
    _name: ClassVar[str] = "Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PolarizingPrism(Prism, RDFEntity):
    """
    Polarizing Prism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000721"
    _name: ClassVar[str] = "Polarizing Prism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LandMine(ExplosiveWeapon, RDFEntity):
    """
    Land Mine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000734"
    _name: ClassVar[str] = "Land Mine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAChart(MaterialCopyOfAnImage, RDFEntity):
    """
    Material Copy of a Chart
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000743"
    _name: ClassVar[str] = "Material Copy of a Chart"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002005, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CombustionEngine(HeatEngine, RDFEntity):
    """
    Combustion Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000746"
    _name: ClassVar[str] = "Combustion Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Canal(WaterTransportationArtifact, RDFEntity):
    """
    Canal
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000747"
    _name: ClassVar[str] = "Canal"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Bullet(PortionOfAmmunition, RDFEntity):
    """
    Bullet
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000748"
    _name: ClassVar[str] = "Bullet"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VideoCamera(Camera, RDFEntity):
    """
    Video Camera
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000774"
    _name: ClassVar[str] = "Video Camera"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HydraulicMotor(PhysicallyPoweredEngine, RDFEntity):
    """
    Hydraulic Motor
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000777"
    _name: ClassVar[str] = "Hydraulic Motor"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DirectCurrentPowerSource(ElectricalPowerSource, RDFEntity):
    """
    Direct Current Power Source
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000790"
    _name: ClassVar[str] = "Direct Current Power Source"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RailTransportVehicle(GroundVehicle, RDFEntity):
    """
    Rail Transport Vehicle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000796"
    _name: ClassVar[str] = "Rail Transport Vehicle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfNuclearFuel(PortionOfMaterial, RDFEntity):
    """
    Portion of Nuclear Fuel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000813"
    _name: ClassVar[str] = "Portion of Nuclear Fuel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OpticalCommunicationArtifactFunction(
    ElectromagneticCommunicationArtifactFunction, RDFEntity
):
    """
    Optical Communication Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000823"
    _name: ClassVar[str] = "Optical Communication Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PesticideArtifactFunction(PoisonArtifactFunction, RDFEntity):
    """
    Pesticide Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000828"
    _name: ClassVar[str] = "Pesticide Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PortionOfFuel(PortionOfMaterial, RDFEntity):
    """
    Portion of Fuel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000838"
    _name: ClassVar[str] = "Portion of Fuel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Bicycle(GroundVehicle, RDFEntity):
    """
    Bicycle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000840"
    _name: ClassVar[str] = "Bicycle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SolarPanel(ElectricalPowerSource, RDFEntity):
    """
    Solar Panel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000843"
    _name: ClassVar[str] = "Solar Panel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UltraHighFrequencyCommunicationInstrument(
    RadioCommunicationInstrument, RDFEntity
):
    """
    Ultra High Frequency Communication Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000857"
    _name: ClassVar[str] = "Ultra High Frequency Communication Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ImprovisedExplosiveDevice(ExplosiveWeapon, RDFEntity):
    """
    Improvised Explosive Device
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000858"
    _name: ClassVar[str] = "Improvised Explosive Device"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OpticalCamera(Camera, RDFEntity):
    """
    Optical Camera
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000869"
    _name: ClassVar[str] = "Optical Camera"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BrakeControlSystem(VehicleControlSystem, RDFEntity):
    """
    Brake Control System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000877"
    _name: ClassVar[str] = "Brake Control System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HighFrequencyCommunicationInstrument(RadioCommunicationInstrument, RDFEntity):
    """
    High Frequency Communication Instrument
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000888"
    _name: ClassVar[str] = "High Frequency Communication Instrument"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfOxidizer(PortionOfMaterial, RDFEntity):
    """
    Oxidizers are essential participants in many processes including combustion and rusting. Hence, a portion of oxidizer must always be present along with a portion of fuel in order for combustion to occur.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000897"
    _name: ClassVar[str] = "Portion of Oxidizer"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EmailBox(TelecommunicationInstrument, RDFEntity):
    """
    Email Box
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000906"
    _name: ClassVar[str] = "Email Box"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Telephone(TelecommunicationInstrument, RDFEntity):
    """
    Telephone
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000907"
    _name: ClassVar[str] = "Telephone"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EmergencyACDCPowerSource(ElectricalPowerSource, RDFEntity):
    """
    Emergency AC/DC Power Source
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000909"
    _name: ClassVar[str] = "Emergency AC/DC Power Source"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class XrayTelescope(Telescope, RDFEntity):
    """
    X-ray Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000945"
    _name: ClassVar[str] = "X-ray Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ReflectivePrism(Prism, RDFEntity):
    """
    Reflective Prism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000988"
    _name: ClassVar[str] = "Reflective Prism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PowerRectifyingArtifactFunction(CurrentConversionArtifactFunction, RDFEntity):
    """
    Power Rectifying Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000993"
    _name: ClassVar[str] = "Power Rectifying Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SprayNozzle(Nozzle, RDFEntity):
    """
    Spray Nozzle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001000"
    _name: ClassVar[str] = "Spray Nozzle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Cartridge(PortionOfAmmunition, RDFEntity):
    """
    Cartridge
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001003"
    _name: ClassVar[str] = "Cartridge"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OpticalTelescope(Telescope, RDFEntity):
    """
    Optical Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001009"
    _name: ClassVar[str] = "Optical Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EquipmentCoolingSystem(CoolingSystem, RDFEntity):
    """
    Equipment Cooling System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001018"
    _name: ClassVar[str] = "Equipment Cooling System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SteeringControlSystem(VehicleControlSystem, RDFEntity):
    """
    Steering Control System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001019"
    _name: ClassVar[str] = "Steering Control System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectricGenerator(ElectricalPowerSource, RDFEntity):
    """
    Electric Generator
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001025"
    _name: ClassVar[str] = "Electric Generator"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UnguidedRocket(PortionOfAmmunition, RDFEntity):
    """
    Unguided Rocket
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001029"
    _name: ClassVar[str] = "Unguided Rocket"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfANotificationMessage(MaterialCopyOfAMessage, RDFEntity):
    """
    Material Copy of a Notification Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001046"
    _name: ClassVar[str] = "Material Copy of a Notification Message"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002013, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class AirBreathingCombustionEngine(ReactionEngine, RDFEntity):
    """
    Air-Breathing Combustion Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001083"
    _name: ClassVar[str] = "Air-Breathing Combustion Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RoadJunction(LandTransportationArtifact, RDFEntity):
    """
    Road Junction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001086"
    _name: ClassVar[str] = "Road Junction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Coin(PortionOfCash, RDFEntity):
    """
    Coin
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001093"
    _name: ClassVar[str] = "Coin"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CommonStock(Stock, RDFEntity):
    """
    Common Stock
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001097"
    _name: ClassVar[str] = "Common Stock"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Bridge(LandTransportationArtifact, RDFEntity):
    """
    Bridge
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001099"
    _name: ClassVar[str] = "Bridge"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PropellingNozzle(Nozzle, RDFEntity):
    """
    Propelling Nozzle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001117"
    _name: ClassVar[str] = "Propelling Nozzle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAFormDocument(MaterialCopyOfADocument, RDFEntity):
    """
    Material Copy of a Form Document
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001119"
    _name: ClassVar[str] = "Material Copy of a Form Document"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002044, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PrecisionGuidedMissile(PortionOfAmmunition, RDFEntity):
    """
    Precision-Guided Missile
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001124"
    _name: ClassVar[str] = "Precision-Guided Missile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioReceiver(RadioCommunicationInstrument, RDFEntity):
    """
    Radio Receiver
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001145"
    _name: ClassVar[str] = "Radio Receiver"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RocketLauncher(ProjectileLauncher, RDFEntity):
    """
    Rocket Launcher
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001173"
    _name: ClassVar[str] = "Rocket Launcher"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RailwayCrossing(LandTransportationArtifact, RDFEntity):
    """
    Railway Crossing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001178"
    _name: ClassVar[str] = "Railway Crossing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TripleInertialNavigationSystem(InertialNavigationSystem, RDFEntity):
    """
    Triple Inertial Navigation System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001181"
    _name: ClassVar[str] = "Triple Inertial Navigation System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Denture(Prosthesis, RDFEntity):
    """
    Denture
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001188"
    _name: ClassVar[str] = "Denture"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioAntenna(BidirectionalTransducer, RDFEntity):
    """
    Radio Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001192"
    _name: ClassVar[str] = "Radio Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Trail(LandTransportationArtifact, RDFEntity):
    """
    Trail
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001201"
    _name: ClassVar[str] = "Trail"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SolarPanelSystem(ElectricalPowerSource, RDFEntity):
    """
    Solar Panel System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001222"
    _name: ClassVar[str] = "Solar Panel System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAJournalArticle(MaterialCopyOfADocument, RDFEntity):
    """
    Material Copy of a Journal Article
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001228"
    _name: ClassVar[str] = "Material Copy of a Journal Article"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002045, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioCommunicationArtifactFunction(
    ElectromagneticCommunicationArtifactFunction, RDFEntity
):
    """
    Radio Communication Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001240"
    _name: ClassVar[str] = "Radio Communication Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TelecommunicationEndpoint(TelecommunicationNetworkNode, RDFEntity):
    """
    Telecommunication Endpoint
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001247"
    _name: ClassVar[str] = "Telecommunication Endpoint"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000176: Optional[
        Annotated[List[Union[TelecommunicationNetwork, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArtificialEye(Prosthesis, RDFEntity):
    """
    Artificial Eye
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001248"
    _name: ClassVar[str] = "Artificial Eye"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NominalSpeedArtifactFunction(SpeedArtifactFunction, RDFEntity):
    """
    Nominal Speed Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001275"
    _name: ClassVar[str] = "Nominal Speed Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class HydraulicValve(Valve, RDFEntity):
    """
    Hydraulic Valve
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001282"
    _name: ClassVar[str] = "Hydraulic Valve"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RoundShot(PortionOfAmmunition, RDFEntity):
    """
    Round Shot
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001288"
    _name: ClassVar[str] = "Round Shot"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioTransceiver(RadioCommunicationInstrument, RDFEntity):
    """
    Radio Transceiver
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001320"
    _name: ClassVar[str] = "Radio Transceiver"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaximumSpeedArtifactFunction(SpeedArtifactFunction, RDFEntity):
    """
    Maximum Speed Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001365"
    _name: ClassVar[str] = "Maximum Speed Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Bow(ProjectileLauncher, RDFEntity):
    """
    Bow
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001373"
    _name: ClassVar[str] = "Bow"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectronicCash(PortionOfCash, RDFEntity):
    """
    Electronic Cash
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001382"
    _name: ClassVar[str] = "Electronic Cash"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAAztecCode(MaterialCopyOfATwoDimensionalBarcode, RDFEntity):
    """
    Material Copy of a Aztec Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000014"
    _name: ClassVar[str] = "Material Copy of a Aztec Code"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002016, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PortionOfSolidFuel(PortionOfFuel, RDFEntity):
    """
    Portion of Solid Fuel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000039"
    _name: ClassVar[str] = "Portion of Solid Fuel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfSolidPropellant(PortionOfPropellant, RDFEntity):
    """
    Portion of Solid Propellant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000043"
    _name: ClassVar[str] = "Portion of Solid Propellant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MobileTelephone(Telephone, RDFEntity):
    """
    Mobile Telephone
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000057"
    _name: ClassVar[str] = "Mobile Telephone"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfLiquidOxygen(PortionOfCryogenicMaterial, RDFEntity):
    """
    Portion of Liquid Oxygen
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000101"
    _name: ClassVar[str] = "Portion of Liquid Oxygen"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfLiquidHydrogen(PortionOfCryogenicMaterial, RDFEntity):
    """
    Portion of Liquid Hydrogen
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000128"
    _name: ClassVar[str] = "Portion of Liquid Hydrogen"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FlightTransponder(RadioTransponder, RDFEntity):
    """
    Flight Transponder
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000147"
    _name: ClassVar[str] = "Flight Transponder"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HandGun(Firearm, RDFEntity):
    """
    Hand Gun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000156"
    _name: ClassVar[str] = "Hand Gun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LargeScaleRocketLauncher(RocketLauncher, RDFEntity):
    """
    Large-Scale Rocket Launcher
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000167"
    _name: ClassVar[str] = "Large-Scale Rocket Launcher"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DetergentArtifactFunction(SurfactantArtifactFunction, RDFEntity):
    """
    Detergent Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000171"
    _name: ClassVar[str] = "Detergent Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TelephoneSubscriberLine(TelephoneLine, RDFEntity):
    """
    Telephone Subscriber Line
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000193"
    _name: ClassVar[str] = "Telephone Subscriber Line"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ReflectingOpticalTelescope(OpticalTelescope, RDFEntity):
    """
    Reflecting Optical Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000219"
    _name: ClassVar[str] = "Reflecting Optical Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfADataMatrixCode(MaterialCopyOfATwoDimensionalBarcode, RDFEntity):
    """
    Material Copy of a Data Matrix Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000242"
    _name: ClassVar[str] = "Material Copy of a Data Matrix Code"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002017, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Torpedo(PrecisionGuidedMissile, RDFEntity):
    """
    Torpedo
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000280"
    _name: ClassVar[str] = "Torpedo"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EmergencyLocatorTransmitter(RadioTransmitter, RDFEntity):
    """
    Emergency Locator Transmitter
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000285"
    _name: ClassVar[str] = "Emergency Locator Transmitter"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AirBreathingJetEngine(JetEngine, RDFEntity):
    """
    Air-Breathing Jet Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000294"
    _name: ClassVar[str] = "Air-Breathing Jet Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ShoulderFiredRocketLauncher(RocketLauncher, RDFEntity):
    """
    Shoulder-Fired Rocket Launcher
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000298"
    _name: ClassVar[str] = "Shoulder-Fired Rocket Launcher"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfLiquidHelium(PortionOfCryogenicMaterial, RDFEntity):
    """
    Portion of Liquid Helium
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000316"
    _name: ClassVar[str] = "Portion of Liquid Helium"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAUPCBarcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a UPC Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000326"
    _name: ClassVar[str] = "Material Copy of a UPC Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002034, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RocketPropelledGrenade(UnguidedRocket, RDFEntity):
    """
    Rocket-Propelled Grenade
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000337"
    _name: ClassVar[str] = "Rocket-Propelled Grenade"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Mortar(Cannon, RDFEntity):
    """
    Mortar
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000340"
    _name: ClassVar[str] = "Mortar"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RefractingOpticalTelescope(OpticalTelescope, RDFEntity):
    """
    Refracting Optical Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000355"
    _name: ClassVar[str] = "Refracting Optical Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RocketEngine(JetEngine, RDFEntity):
    """
    Most rocket engines are also Internal Combustion Engines, however non-combusting forms also exist. For example, an untied balloon full of air that is released and allowed to zoom around the room may be both a Rocket Engine and a Physically Powered Engine.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000362"
    _name: ClassVar[str] = "Rocket Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InternalCombustionEngine(CombustionEngine, RDFEntity):
    """
    Internal Combustion Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000394"
    _name: ClassVar[str] = "Internal Combustion Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AntiMicrobialArtifactFunction(PesticideArtifactFunction, RDFEntity):
    """
    Anti-Microbial Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000415"
    _name: ClassVar[str] = "Anti-Microbial Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArmoredFightingVehicle(GroundMotorVehicle, RDFEntity):
    """
    Armored Fighting Vehicle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000427"
    _name: ClassVar[str] = "Armored Fighting Vehicle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfACodabarBarcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a Codabar Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000429"
    _name: ClassVar[str] = "Material Copy of a Codabar Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002021, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ExternalCombustionEngine(CombustionEngine, RDFEntity):
    """
    External Combustion Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000431"
    _name: ClassVar[str] = "External Combustion Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAWarningMessage(MaterialCopyOfANotificationMessage, RDFEntity):
    """
    Material Copy of a Warning Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000471"
    _name: ClassVar[str] = "Material Copy of a Warning Message"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002011, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class WireAntenna(RadioAntenna, RDFEntity):
    """
    Wire Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000499"
    _name: ClassVar[str] = "Wire Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAQRCode(MaterialCopyOfATwoDimensionalBarcode, RDFEntity):
    """
    Material Copy of a QR Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000559"
    _name: ClassVar[str] = "Material Copy of a QR Code"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002018, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfACode93Barcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a Code 93 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000582"
    _name: ClassVar[str] = "Material Copy of a Code 93 Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002022, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfAITFBarcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a ITF Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000602"
    _name: ClassVar[str] = "Material Copy of a ITF Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002023, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Truck(GroundMotorVehicle, RDFEntity):
    """
    Trucks vary greatly in their size and power -- ranging from small ultra-light trucks to enormous heavy trucks. Trucks also vary greatly in their configurations -- ranging from very basic flatbeds or box trucks to highly specialized cargo carriers. Trucks may also be configured to mount specialized equipment, such as in the case of fire trucks, concrete mixers, and suction excavators.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000606"
    _name: ClassVar[str] = "Truck"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfGaseousPropellant(PortionOfPropellant, RDFEntity):
    """
    Portion of Gaseous Propellant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000637"
    _name: ClassVar[str] = "Portion of Gaseous Propellant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Highway(Road, RDFEntity):
    """
    Highway
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000646"
    _name: ClassVar[str] = "Highway"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GroundMovingTargetIndicationArtifactFunction(
    MovingTargetIndicationArtifactFunction, RDFEntity
):
    """
    Ground Moving Target Indication Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000650"
    _name: ClassVar[str] = "Ground Moving Target Indication Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class WireReceiver(RadioReceiver, RDFEntity):
    """
    Wire Receiver
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000701"
    _name: ClassVar[str] = "Wire Receiver"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VisualProsthesis(ArtificialEye, RDFEntity):
    """
    Visual Prosthesis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000709"
    _name: ClassVar[str] = "Visual Prosthesis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HornAntenna(RadioAntenna, RDFEntity):
    """
    Horn Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000714"
    _name: ClassVar[str] = "Horn Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ParabolicAntenna(RadioAntenna, RDFEntity):
    """
    Parabolic Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000724"
    _name: ClassVar[str] = "Parabolic Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SubmillimeterWavelengthRadioTelescope(RadioTelescope, RDFEntity):
    """
    The submillimeter waveband is between the far-infrared and microwave wavebands and is typically taken to have a wavelength of between a few hundred micrometers and a millimeter.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000728"
    _name: ClassVar[str] = "Submillimeter Wavelength Radio Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Locomotive(RailTransportVehicle, RDFEntity):
    """
    Locomotive
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000775"
    _name: ClassVar[str] = "Locomotive"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioRepeater(RadioTransceiver, RDFEntity):
    """
    Radio Repeater
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000785"
    _name: ClassVar[str] = "Radio Repeater"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CatadioptricOpticalTelescope(OpticalTelescope, RDFEntity):
    """
    Catadioptric Optical Telescope
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000792"
    _name: ClassVar[str] = "Catadioptric Optical Telescope"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfLiquidNitrogen(PortionOfCryogenicMaterial, RDFEntity):
    """
    Portion of Liquid Nitrogen
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000816"
    _name: ClassVar[str] = "Portion of Liquid Nitrogen"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HerbicideArtifactFunction(PesticideArtifactFunction, RDFEntity):
    """
    Herbicide Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000831"
    _name: ClassVar[str] = "Herbicide Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MountedGun(Firearm, RDFEntity):
    """
    Mounted Gun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000848"
    _name: ClassVar[str] = "Mounted Gun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RocketPod(RocketLauncher, RDFEntity):
    """
    Rocket Pod
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000868"
    _name: ClassVar[str] = "Rocket Pod"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IdentificationFriendOrFoeTransponder(RadioTransponder, RDFEntity):
    """
    Identification Friend or Foe Transponder
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000878"
    _name: ClassVar[str] = "Identification Friend or Foe Transponder"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAMSIPlesseyBarcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a MSI Plessey Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000899"
    _name: ClassVar[str] = "Material Copy of a MSI Plessey Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002024, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TrainCar(RailTransportVehicle, RDFEntity):
    """
    Train Car
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000928"
    _name: ClassVar[str] = "Train Car"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LandlineTelephone(Telephone, RDFEntity):
    """
    Landline Telephone
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000933"
    _name: ClassVar[str] = "Landline Telephone"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OcularProsthesis(ArtificialEye, RDFEntity):
    """
    Ocular Prosthesis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000943"
    _name: ClassVar[str] = "Ocular Prosthesis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HighwayInterchange(RoadJunction, RDFEntity):
    """
    Highway Interchange
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000956"
    _name: ClassVar[str] = "Highway Interchange"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfLiquidPropellant(PortionOfPropellant, RDFEntity):
    """
    Portion of Liquid Propellant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000962"
    _name: ClassVar[str] = "Portion of Liquid Propellant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAEANBarcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a EAN Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000966"
    _name: ClassVar[str] = "Material Copy of a EAN Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002025, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Automobile(GroundMotorVehicle, RDFEntity):
    """
    Automobile
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001011"
    _name: ClassVar[str] = "Automobile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAGS1DataBarBarcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Further variants of GS1 DataBar have not been defined here.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001012"
    _name: ClassVar[str] = "Material Copy of a GS1 DataBar Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002031, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PortionOfGaseousFuel(PortionOfFuel, RDFEntity):
    """
    Portion of Gaseous Fuel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001020"
    _name: ClassVar[str] = "Portion of Gaseous Fuel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Train(RailTransportVehicle, RDFEntity):
    """
    Train
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001030"
    _name: ClassVar[str] = "Train"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FullMotionVideoCamera(VideoCamera, RDFEntity):
    """
    Full Motion Video Camera
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001034"
    _name: ClassVar[str] = "Full Motion Video Camera"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PrimaryCellElectricBattery(ElectricBattery, RDFEntity):
    """
    Primary Cell Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001050"
    _name: ClassVar[str] = "Primary Cell Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Motorcycle(GroundMotorVehicle, RDFEntity):
    """
    Motorcycle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001061"
    _name: ClassVar[str] = "Motorcycle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PatchReceiver(RadioReceiver, RDFEntity):
    """
    Patch Receiver
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001082"
    _name: ClassVar[str] = "Patch Receiver"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CellularTelecommunicationNetwork(WirelessTelecommunicationNetwork, RDFEntity):
    """
    Cellular Telecommunication Network
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001095"
    _name: ClassVar[str] = "Cellular Telecommunication Network"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LongGun(Firearm, RDFEntity):
    """
    Long Gun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001104"
    _name: ClassVar[str] = "Long Gun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SecondaryCellElectricBattery(ElectricBattery, RDFEntity):
    """
    Secondary Cell Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001105"
    _name: ClassVar[str] = "Secondary Cell Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfLiquidFuel(PortionOfFuel, RDFEntity):
    """
    Portion of Liquid Fuel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001135"
    _name: ClassVar[str] = "Portion of Liquid Fuel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfGelatinousPropellant(PortionOfPropellant, RDFEntity):
    """
    Portion of Gelatinous Propellant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001172"
    _name: ClassVar[str] = "Portion of Gelatinous Propellant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Railcar(RailTransportVehicle, RDFEntity):
    """
    In American-English, the term 'Railcar' is often used in a broader sense that is interchangeable with 'Railroad Car'.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001198"
    _name: ClassVar[str] = "Railcar"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DishReceiver(RadioReceiver, RDFEntity):
    """
    Dish Receiver
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001223"
    _name: ClassVar[str] = "Dish Receiver"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAPDF417Code(MaterialCopyOfATwoDimensionalBarcode, RDFEntity):
    """
    Material Copy of a PDF417 Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001245"
    _name: ClassVar[str] = "Material Copy of a PDF417 Code"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002019, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class InsecticideArtifactFunction(PesticideArtifactFunction, RDFEntity):
    """
    Insecticide Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001255"
    _name: ClassVar[str] = "Insecticide Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfACode39Barcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a Code 39 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001260"
    _name: ClassVar[str] = "Material Copy of a Code 39 Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002032, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfACode128Barcode(MaterialCopyOfAOneDimensionalBarcode, RDFEntity):
    """
    Material Copy of a Code 128 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001264"
    _name: ClassVar[str] = "Material Copy of a Code 128 Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002033, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Howitzer(Cannon, RDFEntity):
    """
    Howitzer
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001270"
    _name: ClassVar[str] = "Howitzer"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Bus(GroundMotorVehicle, RDFEntity):
    """
    Bus
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001292"
    _name: ClassVar[str] = "Bus"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WettingAgentArtifactFunction(SurfactantArtifactFunction, RDFEntity):
    """
    Wetting Agent Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001299"
    _name: ClassVar[str] = "Wetting Agent Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PatchAntenna(RadioAntenna, RDFEntity):
    """
    Patch Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001300"
    _name: ClassVar[str] = "Patch Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Shotgun(LongGun, RDFEntity):
    """
    Shotgun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000015"
    _name: ClassVar[str] = "Shotgun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RandomWireAntenna(WireAntenna, RDFEntity):
    """
    Random Wire Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000048"
    _name: ClassVar[str] = "Random Wire Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StirlingEngine(ExternalCombustionEngine, RDFEntity):
    """
    Stirling Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000054"
    _name: ClassVar[str] = "Stirling Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LithiumionElectricBattery(SecondaryCellElectricBattery, RDFEntity):
    """
    Lithium-ion Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000158"
    _name: ClassVar[str] = "Lithium-ion Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Rifle(LongGun, RDFEntity):
    """
    Rifle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000204"
    _name: ClassVar[str] = "Rifle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GasTurbine(InternalCombustionEngine, RDFEntity):
    """
    Gas Turbine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000333"
    _name: ClassVar[str] = "Gas Turbine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAISSNBarcode(MaterialCopyOfAEANBarcode, RDFEntity):
    """
    Material Copy of a ISSN Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000461"
    _name: ClassVar[str] = "Material Copy of a ISSN Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002026, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArmoredPersonnelCarrier(ArmoredFightingVehicle, RDFEntity):
    """
    Armored Personnel Carrier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000467"
    _name: ClassVar[str] = "Armored Personnel Carrier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PulsejetEngine(AirBreathingJetEngine, RDFEntity):
    """
    Pulsejet Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000522"
    _name: ClassVar[str] = "Pulsejet Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DefoliantArtifactFunction(HerbicideArtifactFunction, RDFEntity):
    """
    Defoliant Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000538"
    _name: ClassVar[str] = "Defoliant Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfAJAN13Barcode(MaterialCopyOfAEANBarcode, RDFEntity):
    """
    Material Copy of a JAN-13 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000596"
    _name: ClassVar[str] = "Material Copy of a JAN-13 Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002027, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SteamEngine(ExternalCombustionEngine, RDFEntity):
    """
    Steam Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000634"
    _name: ClassVar[str] = "Steam Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AntiBacterialArtifactFunction(AntiMicrobialArtifactFunction, RDFEntity):
    """
    Anti-Bacterial Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000671"
    _name: ClassVar[str] = "Anti-Bacterial Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TurbofanAirBreathingJetEngine(AirBreathingJetEngine, RDFEntity):
    """
    Turbofan Air-Breathing Jet Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000688"
    _name: ClassVar[str] = "Turbofan Air-Breathing Jet Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SemiautomaticPistol(HandGun, RDFEntity):
    """
    Semi-automatic Pistol
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000711"
    _name: ClassVar[str] = "Semi-automatic Pistol"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FungicideArtifactFunction(AntiMicrobialArtifactFunction, RDFEntity):
    """
    Fungicide Artifact Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000762"
    _name: ClassVar[str] = "Fungicide Artifact Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000197: Optional[
        Annotated[List[Union[MaterialArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CompressionIgnitionEngine(InternalCombustionEngine, RDFEntity):
    """
    Compression Ignition Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000807"
    _name: ClassVar[str] = "Compression Ignition Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LightMachineGun(LongGun, RDFEntity):
    """
    Light Machine Gun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000851"
    _name: ClassVar[str] = "Light Machine Gun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NickelmetalHydrideElectricBattery(SecondaryCellElectricBattery, RDFEntity):
    """
    Nickel-metal Hydride Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000930"
    _name: ClassVar[str] = "Nickel-metal Hydride Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAUPCABarcode(MaterialCopyOfAUPCBarcode, RDFEntity):
    """
    Material Copy of a UPC-A Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000931"
    _name: ClassVar[str] = "Material Copy of a UPC-A Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002035, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialCopyOfAEAN13Barcode(MaterialCopyOfAEANBarcode, RDFEntity):
    """
    Material Copy of a EAN-13 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000972"
    _name: ClassVar[str] = "Material Copy of a EAN-13 Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002028, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RamjetEngine(AirBreathingJetEngine, RDFEntity):
    """
    Ramjet Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000996"
    _name: ClassVar[str] = "Ramjet Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TurbojetAirBreathingJetEngine(AirBreathingJetEngine, RDFEntity):
    """
    Turbojet Air-Breathing Jet Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001005"
    _name: ClassVar[str] = "Turbojet Air-Breathing Jet Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PassengerTrainCar(TrainCar, RDFEntity):
    """
    Passenger Train Car
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001007"
    _name: ClassVar[str] = "Passenger Train Car"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ControlledAccessHighway(Highway, RDFEntity):
    """
    Controlled-Access Highway
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001015"
    _name: ClassVar[str] = "Controlled-Access Highway"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SparkIgnitionEngine(InternalCombustionEngine, RDFEntity):
    """
    Spark Ignition Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001024"
    _name: ClassVar[str] = "Spark Ignition Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NickelCadmiumElectricBattery(SecondaryCellElectricBattery, RDFEntity):
    """
    Nickel Cadmium Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001038"
    _name: ClassVar[str] = "Nickel Cadmium Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HelicalAntenna(WireAntenna, RDFEntity):
    """
    Helical Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001054"
    _name: ClassVar[str] = "Helical Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HeavyMachineGun(MountedGun, RDFEntity):
    """
    Heavy Machine Gun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001077"
    _name: ClassVar[str] = "Heavy Machine Gun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SubmachineGun(LongGun, RDFEntity):
    """
    Submachine Gun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001096"
    _name: ClassVar[str] = "Submachine Gun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ScramjetEngine(AirBreathingJetEngine, RDFEntity):
    """
    Scramjet Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001121"
    _name: ClassVar[str] = "Scramjet Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAEAN8Barcode(MaterialCopyOfAEANBarcode, RDFEntity):
    """
    Material Copy of a EAN-8 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001131"
    _name: ClassVar[str] = "Material Copy of a EAN-8 Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002029, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class BeverageAntenna(WireAntenna, RDFEntity):
    """
    Beverage Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001138"
    _name: ClassVar[str] = "Beverage Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MediumMachineGun(MountedGun, RDFEntity):
    """
    Medium Machine Gun
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001217"
    _name: ClassVar[str] = "Medium Machine Gun"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AlkalineElectricBattery(PrimaryCellElectricBattery, RDFEntity):
    """
    Alkaline Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001229"
    _name: ClassVar[str] = "Alkaline Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RhombicAntenna(WireAntenna, RDFEntity):
    """
    Rhombic Antenna
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001230"
    _name: ClassVar[str] = "Rhombic Antenna"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Revolver(HandGun, RDFEntity):
    """
    Revolver
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001254"
    _name: ClassVar[str] = "Revolver"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAISBNBarcode(MaterialCopyOfAEANBarcode, RDFEntity):
    """
    Material Copy of a ISBN Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001268"
    _name: ClassVar[str] = "Material Copy of a ISBN Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002030, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Tank(ArmoredFightingVehicle, RDFEntity):
    """
    Tank firepower is normally provided by a large-caliber main gun mounted in a rotating turret, which is supported by secondary machine guns. A tank's heavy armour and all-terrain mobility provide protection for both the tank and its crew, allowing it to perform all primary tasks of the armoured troops on the battlefield.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001319"
    _name: ClassVar[str] = "Tank"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LeadAcidElectricBattery(SecondaryCellElectricBattery, RDFEntity):
    """
    Lead Acid Electric Battery
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001321"
    _name: ClassVar[str] = "Lead Acid Electric Battery"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InfantryFightingVehicle(ArmoredFightingVehicle, RDFEntity):
    """
    Infantry Fighting Vehicle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001342"
    _name: ClassVar[str] = "Infantry Fighting Vehicle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FreightTrainCar(TrainCar, RDFEntity):
    """
    Freight Train Car
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001355"
    _name: ClassVar[str] = "Freight Train Car"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialCopyOfAUPCEBarcode(MaterialCopyOfAUPCBarcode, RDFEntity):
    """
    Material Copy of a UPC-E Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001209"
    _name: ClassVar[str] = "Material Copy of a UPC-E Barcode"
    _property_uris: ClassVar[dict] = {
        "bFO_0000101": "http://purl.obolibrary.org/obo/BFO_0000101",
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000101", "bFO_0000176"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000101: Optional[Annotated[List[Union[Ont00002036, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    bFO_0000176: Optional[
        Annotated[List[Union[InformationMediumArtifact, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ReciprocatingSteamEngine(SteamEngine, RDFEntity):
    """
    Reciprocating Steam Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000343"
    _name: ClassVar[str] = "Reciprocating Steam Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TurbineSteamEngine(SteamEngine, RDFEntity):
    """
    Turbine Steam Engine
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000788"
    _name: ClassVar[str] = "Turbine Steam Engine"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SniperRifle(Rifle, RDFEntity):
    """
    Sniper Rifle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000942"
    _name: ClassVar[str] = "Sniper Rifle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AssaultRifle(Rifle, RDFEntity):
    """
    Assault Rifle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000968"
    _name: ClassVar[str] = "Assault Rifle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


# Rebuild models to resolve forward references
SystemRole.model_rebuild()
Ont00000170.model_rebuild()
Ont00000205.model_rebuild()
Ont00000253.model_rebuild()
ArtifactFunction.model_rebuild()
Payload.model_rebuild()
ArtifactLocation.model_rebuild()
InfrastructureElement.model_rebuild()
Ont00000686.model_rebuild()
Resource.model_rebuild()
ComponentRole.model_rebuild()
ArtifactHistory.model_rebuild()
InfrastructureSystem.model_rebuild()
PartRole.model_rebuild()
Ont00000958.model_rebuild()
Ont00000965.model_rebuild()
MaterialArtifact.model_rebuild()
InfrastructureRole.model_rebuild()
ReactionMass.model_rebuild()
Ont00001341.model_rebuild()
CoolingArtifactFunction.model_rebuild()
Container.model_rebuild()
SensorPlatform.model_rebuild()
SensorDeploymentArtifactFunction.model_rebuild()
ControlSurface.model_rebuild()
PropulsionSystem.model_rebuild()
ElectricalArtifactFunction.model_rebuild()
VehicleCompartment.model_rebuild()
VentilationControlArtifactFunction.model_rebuild()
InformationProcessingArtifact.model_rebuild()
ArtifactFunctionSpecification.model_rebuild()
VehicleTrackPoint.model_rebuild()
PowerTransformer.model_rebuild()
OpticalInstrument.model_rebuild()
FragranceArtifactFunction.model_rebuild()
Facility.model_rebuild()
FrictionReductionArtifactFunction.model_rebuild()
Engine.model_rebuild()
LightingSystem.model_rebuild()
Propeller.model_rebuild()
HeatSink.model_rebuild()
Shaft.model_rebuild()
TransportationArtifact.model_rebuild()
FluidControlArtifact.model_rebuild()
CommunicationInterferenceArtifactFunction.model_rebuild()
PowerSource.model_rebuild()
ArtifactIdentifier.model_rebuild()
ArtifactDesign.model_rebuild()
TransportationInfrastructure.model_rebuild()
Brake.model_rebuild()
CommunicationInstrument.model_rebuild()
Filter.model_rebuild()
ResearchArtifactFunction.model_rebuild()
PowerTransformerRectifierUnit.model_rebuild()
CombustionChamber.model_rebuild()
DiffractionArtifactFunction.model_rebuild()
CommunicationReceptionArtifactFunction.model_rebuild()
EnhancingArtifactFunction.model_rebuild()
Weapon.model_rebuild()
MotionArtifactFunction.model_rebuild()
CollimationArtifactFunction.model_rebuild()
TimekeepingArtifactFunction.model_rebuild()
EnvironmentControlSystem.model_rebuild()
Coupling.model_rebuild()
OrientationControlArtifactFunction.model_rebuild()
LifeSupportArtifactFunction.model_rebuild()
Tripod.model_rebuild()
DetonatingArtifactFunction.model_rebuild()
OpticalProcessingArtifactFunction.model_rebuild()
FinancialInstrument.model_rebuild()
Dam.model_rebuild()
QualitySpecification.model_rebuild()
PowerRectifier.model_rebuild()
Tool.model_rebuild()
ImagingArtifactFunction.model_rebuild()
NavigationArtifactFunction.model_rebuild()
ImpactShieldingArtifactFunction.model_rebuild()
DeceptionArtifactFunction.model_rebuild()
RefractionArtifactFunction.model_rebuild()
ContainingArtifactFunction.model_rebuild()
Decoy.model_rebuild()
PowerTransmissionArtifact.model_rebuild()
CleaningArtifactFunction.model_rebuild()
BatteryTerminal.model_rebuild()
AttitudeControlArtifactFunction.model_rebuild()
SwitchArtifactFunction.model_rebuild()
TerminalBoard.model_rebuild()
Vehicle.model_rebuild()
CounterfeitInstrument.model_rebuild()
CommunicationArtifactFunction.model_rebuild()
HydraulicPowerTransferUnit.model_rebuild()
Transducer.model_rebuild()
IgnitionSystem.model_rebuild()
LubricationSystem.model_rebuild()
ImagingInstrument.model_rebuild()
SignalDetectionArtifactFunction.model_rebuild()
ControlSystem.model_rebuild()
ChemicalReactionArtifactFunction.model_rebuild()
InformationBearingArtifact.model_rebuild()
SubmersibleArtifactFunction.model_rebuild()
RadioWaveConversionArtifactFunction.model_rebuild()
InformationMediumArtifact.model_rebuild()
VehicleTrack.model_rebuild()
ComputingArtifactFunction.model_rebuild()
InhibitingMotionArtifactFunction.model_rebuild()
TelecommunicationInfrastructure.model_rebuild()
HeatingArtifactFunction.model_rebuild()
CommunicationSystem.model_rebuild()
EquipmentMount.model_rebuild()
NuclearRadiationDetectionArtifactFunction.model_rebuild()
FuelSystem.model_rebuild()
Laser.model_rebuild()
FluidControlArtifactFunction.model_rebuild()
PayloadCapacity.model_rebuild()
PortionOfProcessedMaterial.model_rebuild()
ReflectionArtifactFunction.model_rebuild()
MeasurementArtifactFunction.model_rebuild()
ArtifactModelName.model_rebuild()
VehicleFrame.model_rebuild()
Flywheel.model_rebuild()
DamagingArtifactFunction.model_rebuild()
CommunicationRelayArtifactFunction.model_rebuild()
ElectromagneticShieldingArtifactFunction.model_rebuild()
NavigationSystem.model_rebuild()
StructuralSupportArtifactFunction.model_rebuild()
LiftingArtifactFunction.model_rebuild()
SignalProcessingArtifactFunction.model_rebuild()
SensorArtifactFunction.model_rebuild()
FuelArtifactFunction.model_rebuild()
ServiceArtifactFunction.model_rebuild()
ObservationArtifactFunction.model_rebuild()
CoveringArtifactFunction.model_rebuild()
ArticleOfClothing.model_rebuild()
BearingArtifactFunction.model_rebuild()
CircuitBreaker.model_rebuild()
LegalInstrument.model_rebuild()
ThermalControlArtifactFunction.model_rebuild()
HealingArtifactFunction.model_rebuild()
PoweringArtifactFunction.model_rebuild()
MachineBearing.model_rebuild()
ElectromagneticInductionArtifactFunction.model_rebuild()
MedicalArtifact.model_rebuild()
FilterFunction.model_rebuild()
PropulsionControlSystem.model_rebuild()
TitleDocument.model_rebuild()
RadioCommunicationReceptionArtifactFunction.model_rebuild()
NuclearReactor.model_rebuild()
ConveyanceArtifactFunction.model_rebuild()
WasteManagementArtifactFunction.model_rebuild()
ReactionEngine.model_rebuild()
FrequencyMeasurementArtifactFunction.model_rebuild()
MilitaryArtifactFunction.model_rebuild()
WiredCommunicationArtifactFunction.model_rebuild()
CuttingWeapon.model_rebuild()
BidirectionalTransducer.model_rebuild()
AirInlet.model_rebuild()
Pump.model_rebuild()
RecordingDevice.model_rebuild()
CargoCabin.model_rebuild()
IncendiaryWeapon.model_rebuild()
GeneratorControlUnit.model_rebuild()
MaterialCopyOfATimekeepingInstrument.model_rebuild()
ManualTool.model_rebuild()
MaterialCopyOfACertificate.model_rebuild()
Camera.model_rebuild()
ChemicalWeapon.model_rebuild()
DiffractionGrating.model_rebuild()
FragmentationArtifactFunction.model_rebuild()
Nozzle.model_rebuild()
HydraulicFluidReservoir.model_rebuild()
HearingAid.model_rebuild()
CatalystArtifactFunction.model_rebuild()
NuclearWeapon.model_rebuild()
CounterfeitFinancialInstrument.model_rebuild()
InertialNavigationSystem.model_rebuild()
RadarImagingArtifactFunction.model_rebuild()
VehicleTransmission.model_rebuild()
IntercommunicationSystem.model_rebuild()
Microscope.model_rebuild()
Hinge.model_rebuild()
PortionOfFood.model_rebuild()
HealthcareArtifactFunction.model_rebuild()
FiltrationArtifactFunction.model_rebuild()
ElectronicSignalProcessingArtifactFunction.model_rebuild()
ResidentialArtifactFunction.model_rebuild()
Fan.model_rebuild()
CoolingSystem.model_rebuild()
ElectricalResistanceArtifactFunction.model_rebuild()
SparkIgnitionSystem.model_rebuild()
SpeedMeasurementArtifactFunction.model_rebuild()
OxidizerArtifactFunction.model_rebuild()
Computer.model_rebuild()
Watercraft.model_rebuild()
CompressionIgnitionSystem.model_rebuild()
PortionOfMaterial.model_rebuild()
PortionOfCash.model_rebuild()
ResearchAndDevelopmentArtifactFunction.model_rebuild()
RadioCommunicationInterferenceArtifactFunction.model_rebuild()
PneumaticPowerSource.model_rebuild()
CuttingArtifactFunction.model_rebuild()
Telescope.model_rebuild()
WaterTransportationArtifact.model_rebuild()
ExplosiveWeapon.model_rebuild()
Sensor.model_rebuild()
ControllablePitchPropeller.model_rebuild()
MaterialCopyOfAInstrumentDisplayPanel.model_rebuild()
Valve.model_rebuild()
LegalArtifactFunction.model_rebuild()
GroundVehicle.model_rebuild()
NozzleThroat.model_rebuild()
HeatEngine.model_rebuild()
RadiologicalWeapon.model_rebuild()
DistanceMeasurementArtifactFunction.model_rebuild()
GovernmentArtifactFunction.model_rebuild()
VoltageRegulatingArtifactFunction.model_rebuild()
ExternalNavigationLightingSystem.model_rebuild()
Mirror.model_rebuild()
TelecommunicationInstrument.model_rebuild()
FuelTank.model_rebuild()
MassSpecification.model_rebuild()
NozzleMouth.model_rebuild()
MaterialCopyOfAnImage.model_rebuild()
Prosthesis.model_rebuild()
CryogenicStorageDewar.model_rebuild()
VehicleControlSystem.model_rebuild()
MaterialCopyOfADatabase.model_rebuild()
OpticalFocusingArtifactFunction.model_rebuild()
FuelVentilationSystem.model_rebuild()
ElectricalConductionArtifactFunction.model_rebuild()
MaterialCopyOfAList.model_rebuild()
Prism.model_rebuild()
PowerTool.model_rebuild()
ReactantArtifactFunction.model_rebuild()
TelecommunicationNetworkLine.model_rebuild()
ExplosiveArtifactFunction.model_rebuild()
HeatingSystem.model_rebuild()
PublicSafetyArtifactFunction.model_rebuild()
MaterialCopyOfAVideo.model_rebuild()
ReligiousArtifactFunction.model_rebuild()
WiredCommunicationReceptionArtifactFunction.model_rebuild()
RadioCommunicationRelayArtifactFunction.model_rebuild()
RadioCommunicationInstrument.model_rebuild()
TelecommunicationNetworkNode.model_rebuild()
PartsList.model_rebuild()
FinancialArtifactFunction.model_rebuild()
ThermalImagingArtifactFunction.model_rebuild()
TemperatureMeasurementArtifactFunction.model_rebuild()
ElectricMotor.model_rebuild()
CurrentConversionArtifactFunction.model_rebuild()
FuelTransferSystem.model_rebuild()
PortionOfWasteMaterial.model_rebuild()
ThermalInsulationArtifactFunction.model_rebuild()
ElectricalPowerProductionArtifactFunction.model_rebuild()
TelecommunicationNetwork.model_rebuild()
MaterialCopyOfAMessage.model_rebuild()
BiologicalWeapon.model_rebuild()
TrimTab.model_rebuild()
Aircraft.model_rebuild()
ArtifactModel.model_rebuild()
ElectricalPowerSource.model_rebuild()
ProjectileLauncher.model_rebuild()
MaterialCopyOfABarcode.model_rebuild()
OrientationObservationArtifactFunction.model_rebuild()
ElectricalPowerStorageArtifactFunction.model_rebuild()
PoisonArtifactFunction.model_rebuild()
PressurizationControlArtifactFunction.model_rebuild()
Spacecraft.model_rebuild()
ElectromagneticCommunicationArtifactFunction.model_rebuild()
PortionOfAmmunition.model_rebuild()
PortionOfPaper.model_rebuild()
FullMotionVideoImagingArtifactFunction.model_rebuild()
MaterialCopyOfAInformationLine.model_rebuild()
HydraulicPowerSource.model_rebuild()
Bond.model_rebuild()
SolventArtifactFunction.model_rebuild()
CounterfeitLegalInstrument.model_rebuild()
DigitalStorageDevice.model_rebuild()
Rocket.model_rebuild()
OpticalLens.model_rebuild()
RetailArtifactFunction.model_rebuild()
Periscope.model_rebuild()
PhysicallyPoweredEngine.model_rebuild()
CrushingArtifactFunction.model_rebuild()
NeutralizationArtifactFunction.model_rebuild()
Actuator.model_rebuild()
MaterialCopyOfADocumentField.model_rebuild()
CabinPressurizationControlSystem.model_rebuild()
InteriorLightingSystem.model_rebuild()
PropulsionArtifactFunction.model_rebuild()
PublicAddressSystem.model_rebuild()
WiredCommunicationRelayArtifactFunction.model_rebuild()
SensorModalityFunction.model_rebuild()
Stock.model_rebuild()
EmulsifierArtifactFunction.model_rebuild()
MaterialCopyOfADocument.model_rebuild()
PositionObservationArtifactFunction.model_rebuild()
DimensionSpecification.model_rebuild()
Gimbal.model_rebuild()
LandTransportationArtifact.model_rebuild()
EducationArtifactFunction.model_rebuild()
SpeedArtifactFunction.model_rebuild()
MotionObservationArtifactFunction.model_rebuild()
FertilizerArtifactFunction.model_rebuild()
HospitalityArtifactFunction.model_rebuild()
DeflectingPrism.model_rebuild()
PowerInvertingArtifactFunction.model_rebuild()
ElectronicStock.model_rebuild()
DispersivePrism.model_rebuild()
FlowControlValve.model_rebuild()
Banknote.model_rebuild()
VeryHighFrequencyCommunicationInstrument.model_rebuild()
GroundMotorVehicle.model_rebuild()
TelephoneLine.model_rebuild()
MaterialCopyOfABook.model_rebuild()
MaterialCopyOfATranscript.model_rebuild()
OpticalMicroscope.model_rebuild()
AutopilotSystem.model_rebuild()
Firearm.model_rebuild()
InfraredTelescope.model_rebuild()
PortionOfCoolant.model_rebuild()
PreferredStock.model_rebuild()
ComplexOpticalLens.model_rebuild()
TelephoneNetwork.model_rebuild()
ElectricalConnectorArtifactFunction.model_rebuild()
UltravioletTelescope.model_rebuild()
Arrow.model_rebuild()
MinimumSpeedArtifactFunction.model_rebuild()
ElectricalContactArtifactFunction.model_rebuild()
MovingTargetIndicationArtifactFunction.model_rebuild()
RadioTelescope.model_rebuild()
Shell.model_rebuild()
TorpedoTube.model_rebuild()
StockCertificate.model_rebuild()
MaterialCopyOfATwoDimensionalBarcode.model_rebuild()
Road.model_rebuild()
PortionOfCryogenicMaterial.model_rebuild()
MaterialCopyOfAOneDimensionalBarcode.model_rebuild()
Cannon.model_rebuild()
RadioTransmitter.model_rebuild()
ProstheticLeg.model_rebuild()
AlternatingCurrentPowerSource.model_rebuild()
Grenade.model_rebuild()
TelecommunicationSwitchingNode.model_rebuild()
RadioTransponder.model_rebuild()
Interphone.model_rebuild()
ProstheticArm.model_rebuild()
SurfactantArtifactFunction.model_rebuild()
ElectronicBond.model_rebuild()
SatelliteArtifact.model_rebuild()
WirelessTelecommunicationNetwork.model_rebuild()
PneumaticMotor.model_rebuild()
PortionOfGalliumArsenide.model_rebuild()
MaterialCopyOfASpreadsheet.model_rebuild()
ElectronMicroscope.model_rebuild()
ProstheticHand.model_rebuild()
RailwayJunction.model_rebuild()
SimpleOpticalLens.model_rebuild()
XrayMicroscope.model_rebuild()
Railway.model_rebuild()
MaterialCopyOfAAcademicDegree.model_rebuild()
FuelCell.model_rebuild()
SyntheticApertureRadarImagingArtifactFunction.model_rebuild()
MaterialCopyOfACodeList.model_rebuild()
AirConditioningUnit.model_rebuild()
GammarayTelescope.model_rebuild()
JetEngine.model_rebuild()
BondCertificate.model_rebuild()
ArticleOfSolidWaste.model_rebuild()
PortionOfPropellant.model_rebuild()
InfraredCamera.model_rebuild()
MaterialCopyOfAReport.model_rebuild()
MaterialCopyOfAEmailMessage.model_rebuild()
MissileLauncher.model_rebuild()
ProstheticFoot.model_rebuild()
ConvergentDivergentNozzle.model_rebuild()
ComputerNetwork.model_rebuild()
MaterialCopyOfASystemClock.model_rebuild()
Tunnel.model_rebuild()
ElectricBattery.model_rebuild()
PolarizingPrism.model_rebuild()
LandMine.model_rebuild()
MaterialCopyOfAChart.model_rebuild()
CombustionEngine.model_rebuild()
Canal.model_rebuild()
Bullet.model_rebuild()
VideoCamera.model_rebuild()
HydraulicMotor.model_rebuild()
DirectCurrentPowerSource.model_rebuild()
RailTransportVehicle.model_rebuild()
PortionOfNuclearFuel.model_rebuild()
OpticalCommunicationArtifactFunction.model_rebuild()
PesticideArtifactFunction.model_rebuild()
PortionOfFuel.model_rebuild()
Bicycle.model_rebuild()
SolarPanel.model_rebuild()
UltraHighFrequencyCommunicationInstrument.model_rebuild()
ImprovisedExplosiveDevice.model_rebuild()
OpticalCamera.model_rebuild()
BrakeControlSystem.model_rebuild()
HighFrequencyCommunicationInstrument.model_rebuild()
PortionOfOxidizer.model_rebuild()
EmailBox.model_rebuild()
Telephone.model_rebuild()
EmergencyACDCPowerSource.model_rebuild()
XrayTelescope.model_rebuild()
ReflectivePrism.model_rebuild()
PowerRectifyingArtifactFunction.model_rebuild()
SprayNozzle.model_rebuild()
Cartridge.model_rebuild()
OpticalTelescope.model_rebuild()
EquipmentCoolingSystem.model_rebuild()
SteeringControlSystem.model_rebuild()
ElectricGenerator.model_rebuild()
UnguidedRocket.model_rebuild()
MaterialCopyOfANotificationMessage.model_rebuild()
AirBreathingCombustionEngine.model_rebuild()
RoadJunction.model_rebuild()
Coin.model_rebuild()
CommonStock.model_rebuild()
Bridge.model_rebuild()
PropellingNozzle.model_rebuild()
MaterialCopyOfAFormDocument.model_rebuild()
PrecisionGuidedMissile.model_rebuild()
RadioReceiver.model_rebuild()
RocketLauncher.model_rebuild()
RailwayCrossing.model_rebuild()
TripleInertialNavigationSystem.model_rebuild()
Denture.model_rebuild()
RadioAntenna.model_rebuild()
Trail.model_rebuild()
SolarPanelSystem.model_rebuild()
MaterialCopyOfAJournalArticle.model_rebuild()
RadioCommunicationArtifactFunction.model_rebuild()
TelecommunicationEndpoint.model_rebuild()
ArtificialEye.model_rebuild()
NominalSpeedArtifactFunction.model_rebuild()
HydraulicValve.model_rebuild()
RoundShot.model_rebuild()
RadioTransceiver.model_rebuild()
MaximumSpeedArtifactFunction.model_rebuild()
Bow.model_rebuild()
ElectronicCash.model_rebuild()
MaterialCopyOfAAztecCode.model_rebuild()
PortionOfSolidFuel.model_rebuild()
PortionOfSolidPropellant.model_rebuild()
MobileTelephone.model_rebuild()
PortionOfLiquidOxygen.model_rebuild()
PortionOfLiquidHydrogen.model_rebuild()
FlightTransponder.model_rebuild()
HandGun.model_rebuild()
LargeScaleRocketLauncher.model_rebuild()
DetergentArtifactFunction.model_rebuild()
TelephoneSubscriberLine.model_rebuild()
ReflectingOpticalTelescope.model_rebuild()
MaterialCopyOfADataMatrixCode.model_rebuild()
Torpedo.model_rebuild()
EmergencyLocatorTransmitter.model_rebuild()
AirBreathingJetEngine.model_rebuild()
ShoulderFiredRocketLauncher.model_rebuild()
PortionOfLiquidHelium.model_rebuild()
MaterialCopyOfAUPCBarcode.model_rebuild()
RocketPropelledGrenade.model_rebuild()
Mortar.model_rebuild()
RefractingOpticalTelescope.model_rebuild()
RocketEngine.model_rebuild()
InternalCombustionEngine.model_rebuild()
AntiMicrobialArtifactFunction.model_rebuild()
ArmoredFightingVehicle.model_rebuild()
MaterialCopyOfACodabarBarcode.model_rebuild()
ExternalCombustionEngine.model_rebuild()
MaterialCopyOfAWarningMessage.model_rebuild()
WireAntenna.model_rebuild()
MaterialCopyOfAQRCode.model_rebuild()
MaterialCopyOfACode93Barcode.model_rebuild()
MaterialCopyOfAITFBarcode.model_rebuild()
Truck.model_rebuild()
PortionOfGaseousPropellant.model_rebuild()
Highway.model_rebuild()
GroundMovingTargetIndicationArtifactFunction.model_rebuild()
WireReceiver.model_rebuild()
VisualProsthesis.model_rebuild()
HornAntenna.model_rebuild()
ParabolicAntenna.model_rebuild()
SubmillimeterWavelengthRadioTelescope.model_rebuild()
Locomotive.model_rebuild()
RadioRepeater.model_rebuild()
CatadioptricOpticalTelescope.model_rebuild()
PortionOfLiquidNitrogen.model_rebuild()
HerbicideArtifactFunction.model_rebuild()
MountedGun.model_rebuild()
RocketPod.model_rebuild()
IdentificationFriendOrFoeTransponder.model_rebuild()
MaterialCopyOfAMSIPlesseyBarcode.model_rebuild()
TrainCar.model_rebuild()
LandlineTelephone.model_rebuild()
OcularProsthesis.model_rebuild()
HighwayInterchange.model_rebuild()
PortionOfLiquidPropellant.model_rebuild()
MaterialCopyOfAEANBarcode.model_rebuild()
Automobile.model_rebuild()
MaterialCopyOfAGS1DataBarBarcode.model_rebuild()
PortionOfGaseousFuel.model_rebuild()
Train.model_rebuild()
FullMotionVideoCamera.model_rebuild()
PrimaryCellElectricBattery.model_rebuild()
Motorcycle.model_rebuild()
PatchReceiver.model_rebuild()
CellularTelecommunicationNetwork.model_rebuild()
LongGun.model_rebuild()
SecondaryCellElectricBattery.model_rebuild()
PortionOfLiquidFuel.model_rebuild()
PortionOfGelatinousPropellant.model_rebuild()
Railcar.model_rebuild()
DishReceiver.model_rebuild()
MaterialCopyOfAPDF417Code.model_rebuild()
InsecticideArtifactFunction.model_rebuild()
MaterialCopyOfACode39Barcode.model_rebuild()
MaterialCopyOfACode128Barcode.model_rebuild()
Howitzer.model_rebuild()
Bus.model_rebuild()
WettingAgentArtifactFunction.model_rebuild()
PatchAntenna.model_rebuild()
Shotgun.model_rebuild()
RandomWireAntenna.model_rebuild()
StirlingEngine.model_rebuild()
LithiumionElectricBattery.model_rebuild()
Rifle.model_rebuild()
GasTurbine.model_rebuild()
MaterialCopyOfAISSNBarcode.model_rebuild()
ArmoredPersonnelCarrier.model_rebuild()
PulsejetEngine.model_rebuild()
DefoliantArtifactFunction.model_rebuild()
MaterialCopyOfAJAN13Barcode.model_rebuild()
SteamEngine.model_rebuild()
AntiBacterialArtifactFunction.model_rebuild()
TurbofanAirBreathingJetEngine.model_rebuild()
SemiautomaticPistol.model_rebuild()
FungicideArtifactFunction.model_rebuild()
CompressionIgnitionEngine.model_rebuild()
LightMachineGun.model_rebuild()
NickelmetalHydrideElectricBattery.model_rebuild()
MaterialCopyOfAUPCABarcode.model_rebuild()
MaterialCopyOfAEAN13Barcode.model_rebuild()
RamjetEngine.model_rebuild()
TurbojetAirBreathingJetEngine.model_rebuild()
PassengerTrainCar.model_rebuild()
ControlledAccessHighway.model_rebuild()
SparkIgnitionEngine.model_rebuild()
NickelCadmiumElectricBattery.model_rebuild()
HelicalAntenna.model_rebuild()
HeavyMachineGun.model_rebuild()
SubmachineGun.model_rebuild()
ScramjetEngine.model_rebuild()
MaterialCopyOfAEAN8Barcode.model_rebuild()
BeverageAntenna.model_rebuild()
MediumMachineGun.model_rebuild()
AlkalineElectricBattery.model_rebuild()
RhombicAntenna.model_rebuild()
Revolver.model_rebuild()
MaterialCopyOfAISBNBarcode.model_rebuild()
Tank.model_rebuild()
LeadAcidElectricBattery.model_rebuild()
InfantryFightingVehicle.model_rebuild()
FreightTrainCar.model_rebuild()
MaterialCopyOfAUPCEBarcode.model_rebuild()
ReciprocatingSteamEngine.model_rebuild()
TurbineSteamEngine.model_rebuild()
SniperRifle.model_rebuild()
AssaultRifle.model_rebuild()
