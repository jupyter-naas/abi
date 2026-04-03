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


class HairColor(RDFEntity):
    """
    Hair Color
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000026"
    _name: ClassVar[str] = "Hair Color"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EyeColor(RDFEntity):
    """
    Eye Color
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000044"
    _name: ClassVar[str] = "Eye Color"
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
    bFO_0000197: Optional[Annotated[List[Union[Iris, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class BodilyComponent(RDFEntity):
    """
    Bodily Component
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000084"
    _name: ClassVar[str] = "Bodily Component"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SkinType(RDFEntity):
    """
    Skin Type is classified according to a reference system such as the Fitzpatrick scale: https://en.wikipedia.org/wiki/Fitzpatrick_scale
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000102"
    _name: ClassVar[str] = "Skin Type"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CivilianRole(RDFEntity):
    """
    Civilian Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000173"
    _name: ClassVar[str] = "Civilian Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OrganizationMemberRole(RDFEntity):
    """
    Organization Member Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000175"
    _name: ClassVar[str] = "Organization Member Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Affordance(RDFEntity):
    """
    Affordance
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000177"
    _name: ClassVar[str] = "Affordance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AuthorityRole(RDFEntity):
    """
    Authority Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000187"
    _name: ClassVar[str] = "Authority Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000207(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000207"
    _name: ClassVar[str] = "Ont00000207"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GroupOfAgents(RDFEntity):
    """
    Group of Agents
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000300"
    _name: ClassVar[str] = "Group of Agents"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Disease(RDFEntity):
    """
    Disease
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000318"
    _name: ClassVar[str] = "Disease"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Disability(RDFEntity):
    """
    Disability
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000377"
    _name: ClassVar[str] = "Disability"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AllegianceRole(RDFEntity):
    """
    Allegiance Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000392"
    _name: ClassVar[str] = "Allegiance Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000472(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000472"
    _name: ClassVar[str] = "Ont00000472"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CommercialRole(RDFEntity):
    """
    Commercial Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000485"
    _name: ClassVar[str] = "Commercial Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ont00000487(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000487"
    _name: ClassVar[str] = "Ont00000487"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ContractorRole(RDFEntity):
    """
    Contractor Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000506"
    _name: ClassVar[str] = "Contractor Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Organism(RDFEntity):
    """
    Organism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000551"
    _name: ClassVar[str] = "Organism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InterpersonalRelationshipRole(RDFEntity):
    """
    Interpersonal Relationship Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000599"
    _name: ClassVar[str] = "Interpersonal Relationship Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FinancialValue(RDFEntity):
    """
    Financial Value
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000608"
    _name: ClassVar[str] = "Financial Value"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ethnicity(RDFEntity):
    """
    Ethnicity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000780"
    _name: ClassVar[str] = "Ethnicity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeopoliticalPowerRole(RDFEntity):
    """
    Geopolitical Power Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000898"
    _name: ClassVar[str] = "Geopolitical Power Role"
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
        Annotated[List[Union[Organization, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PermanentResidentRole(RDFEntity):
    """
    Permanent Resident Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000917"
    _name: ClassVar[str] = "Permanent Resident Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
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


class OccupationRole(RDFEntity):
    """
    Occupation Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000984"
    _name: ClassVar[str] = "Occupation Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CitizenRole(RDFEntity):
    """
    Citizen Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000987"
    _name: ClassVar[str] = "Citizen Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OperatorRole(RDFEntity):
    """
    Operator Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001006"
    _name: ClassVar[str] = "Operator Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Agent(RDFEntity):
    """
    Agent
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001017"
    _name: ClassVar[str] = "Agent"
    _property_uris: ClassVar[dict] = {
        "accessory_in": "https://www.commoncoreontologies.org/ont00001852",
        "accomplice_in": "https://www.commoncoreontologies.org/ont00001895",
        "agent_in": "https://www.commoncoreontologies.org/ont00001787",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_affiliate": "https://www.commoncoreontologies.org/ont00001977",
        "has_capability": "https://www.commoncoreontologies.org/ont00001954",
        "has_interest_in": "https://www.commoncoreontologies.org/ont00001984",
        "is_affiliated_with": "https://www.commoncoreontologies.org/ont00001939",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "receives": "https://www.commoncoreontologies.org/ont00001978",
        "sends": "https://www.commoncoreontologies.org/ont00001993",
        "uses": "https://www.commoncoreontologies.org/ont00001813",
    }
    _object_properties: ClassVar[set[str]] = {
        "accessory_in",
        "accomplice_in",
        "agent_in",
        "has_affiliate",
        "has_capability",
        "has_interest_in",
        "is_affiliated_with",
        "receives",
        "sends",
        "uses",
    }

    # Data properties
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
    accessory_in: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x is_accessory_in y iff x is an instance of Agent and y is an instance of Process such that x assists another instance of Agent z in the commission of y, and x was not located at the location of y when y occurred, and x is not an agent_in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    accomplice_in: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="Agent x is accomplice_in Process y iff x assists in the commission of y, is located at the location of y, but is not agent_in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    agent_in: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x agent_in y iff y is an instance of Process and x is an instance of Agent, such that x is causally active in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_affiliate: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(description="x has affiliate y iff y is affiliated with x."),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_capability: Optional[
        Annotated[
            List[Union[AgentCapability, URIRef, str]],
            Field(
                description="x has_capability y iff x is an instance of Agent and y is an instance of Agent Capability, such that x bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_interest_in: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="A relation between an Agent and some Process where the Agent has an interest in that Process."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_affiliated_with: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="x is_affiliated_with y iff x and y are instances of Agent, such that they have any kind of social or business relationship."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    receives: Optional[
        Annotated[
            List[Union[Ont00000402, URIRef, str]],
            Field(
                description="x receives y iff x is an instance of Agent and y is an instance of Act Of Communication, such that x is the recipient and decoder of the InformationContentEntity intended for communication in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    sends: Optional[
        Annotated[
            List[Union[Ont00000402, URIRef, str]],
            Field(
                description="x sends y iff x is an instance of Agent and y is an instance of Act Of Communication, such that x is the initiator and encoder of the InformationContentEntity intended for communication in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    uses: Optional[
        Annotated[
            List[Union[BFO_0000040, URIRef, str]],
            Field(
                description="x uses y iff x is an instance of an Agent and y is an instance of a Material Entity, such that both x and y participate in some instance of a Process wherein x attempts to accomplish a goal by manipulating, deploying, or leveraging some attribute of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class BiologicalSex(RDFEntity):
    """
    Biological Sex
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001033"
    _name: ClassVar[str] = "Biological Sex"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
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


class AgentCapability(RDFEntity):
    """
    Agent Capability
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001379"
    _name: ClassVar[str] = "Agent Capability"
    _property_uris: ClassVar[dict] = {
        "capability_of": "https://www.commoncoreontologies.org/ont00001889",
        "capability_of_aggregate": "https://www.commoncoreontologies.org/ont00001880",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "capability_of",
        "capability_of_aggregate",
    }

    # Data properties
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
    capability_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="x capability_of y iff y is an instance of Agent and x is an instance of Agent Capability, such that x inheres in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    capability_of_aggregate: Optional[
        Annotated[
            List[Union[BFO_0000027, URIRef, str]],
            Field(
                description="x capability_of_aggregate y iff y is an instance of Object Aggregate and x is an instance of Agent Capability, such that x inheres in aggregate y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ScalpHair(BodilyComponent, RDFEntity):
    """
    Scalp Hair
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000058"
    _name: ClassVar[str] = "Scalp Hair"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Skill(AgentCapability, RDFEntity):
    """
    Skill
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000089"
    _name: ClassVar[str] = "Skill"
    _property_uris: ClassVar[dict] = {
        "capability_of": "https://www.commoncoreontologies.org/ont00001889",
        "capability_of_aggregate": "https://www.commoncoreontologies.org/ont00001880",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "capability_of",
        "capability_of_aggregate",
    }

    # Data properties
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
    capability_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="x capability_of y iff y is an instance of Agent and x is an instance of Agent Capability, such that x inheres in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    capability_of_aggregate: Optional[
        Annotated[
            List[Union[BFO_0000027, URIRef, str]],
            Field(
                description="x capability_of_aggregate y iff y is an instance of Object Aggregate and x is an instance of Agent Capability, such that x inheres in aggregate y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Tattoo(BodilyComponent, RDFEntity):
    """
    Tattoo
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000129"
    _name: ClassVar[str] = "Tattoo"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FacialHair(BodilyComponent, RDFEntity):
    """
    Facial Hair
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000157"
    _name: ClassVar[str] = "Facial Hair"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EnemyRole(AllegianceRole, RDFEntity):
    """
    Enemy Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000279"
    _name: ClassVar[str] = "Enemy Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Iris(BodilyComponent, RDFEntity):
    """
    Iris
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000404"
    _name: ClassVar[str] = "Iris"
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
    bFO_0000176: Optional[Annotated[List[Union[Eye, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Objective(Ont00000965, RDFEntity):
    """
    Objective
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000476"
    _name: ClassVar[str] = "Objective"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NeutralRole(AllegianceRole, RDFEntity):
    """
    Neutral Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000486"
    _name: ClassVar[str] = "Neutral Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Eye(BodilyComponent, RDFEntity):
    """
    Eye
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000500"
    _name: ClassVar[str] = "Eye"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Animal(Organism, RDFEntity):
    """
    Animal
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000562"
    _name: ClassVar[str] = "Animal"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OperationalArea(Ont00000487, RDFEntity):
    """
    This is a general term that applies to both military and civilian activities, such as the Geospatial Region within which a company conducts its business.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000567"
    _name: ClassVar[str] = "Operational Area"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OrganizationCapability(AgentCapability, RDFEntity):
    """
    Organization Capability
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000568"
    _name: ClassVar[str] = "Organization Capability"
    _property_uris: ClassVar[dict] = {
        "capability_of": "https://www.commoncoreontologies.org/ont00001889",
        "capability_of_aggregate": "https://www.commoncoreontologies.org/ont00001880",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "capability_of",
        "capability_of_aggregate",
    }

    # Data properties
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
    capability_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="x capability_of y iff y is an instance of Agent and x is an instance of Agent Capability, such that x inheres in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    capability_of_aggregate: Optional[
        Annotated[
            List[Union[BFO_0000027, URIRef, str]],
            Field(
                description="x capability_of_aggregate y iff y is an instance of Object Aggregate and x is an instance of Agent Capability, such that x inheres in aggregate y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Scalp(BodilyComponent, RDFEntity):
    """
    Scalp
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000576"
    _name: ClassVar[str] = "Scalp"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AllyRole(AllegianceRole, RDFEntity):
    """
    Ally Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000587"
    _name: ClassVar[str] = "Ally Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Religion(Ont00000958, RDFEntity):
    """
    Religion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000616"
    _name: ClassVar[str] = "Religion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaterialTerritoryOfAGovernmentDomain(Ont00001341, RDFEntity):
    """
    Material Territory of a Government Domain
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000662"
    _name: ClassVar[str] = "Material Territory of a Government Domain"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GovernmentDomainBorder(Ont00000207, RDFEntity):
    """
    Government Domain Border
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000685"
    _name: ClassVar[str] = "Government Domain Border"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Ideology(Ont00000958, RDFEntity):
    """
    Ideology
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000696"
    _name: ClassVar[str] = "Ideology"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Plant(Organism, RDFEntity):
    """
    Plant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000871"
    _name: ClassVar[str] = "Plant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GroupOfPersons(GroupOfAgents, RDFEntity):
    """
    Group of Persons
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000914"
    _name: ClassVar[str] = "Group of Persons"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Plan(Ont00000965, RDFEntity):
    """
    Plan
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000974"
    _name: ClassVar[str] = "Plan"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Objective, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Scar(BodilyComponent, RDFEntity):
    """
    Scar
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000986"
    _name: ClassVar[str] = "Scar"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InternationalCommunity(GroupOfAgents, RDFEntity):
    """
    International Community
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001062"
    _name: ClassVar[str] = "International Community"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FinancialValueOfProperty(FinancialValue, RDFEntity):
    """
    Financial Value of Property
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001073"
    _name: ClassVar[str] = "Financial Value of Property"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DivisionOfDelimitingDomain(Ont00000472, RDFEntity):
    """
    Instances of this class are not proper Delimiting Domains, but in some cases may have an organization that exercises some control over the region, such as the homeowners' association for a neighborhood.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001114"
    _name: ClassVar[str] = "Division of Delimiting Domain"
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
        Annotated[List[Union[DelimitingDomain, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SetOfEyes(BodilyComponent, RDFEntity):
    """
    Set of Eyes
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001125"
    _name: ClassVar[str] = "Set of Eyes"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Eye, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Organization(GroupOfAgents, RDFEntity):
    """
    Members of organizations are either Organizations themselves or individual Persons. Members can bear specific Organization Member Roles that are determined in the organization rules. The organization rules also determine how decisions are made on behalf of the Organization by the organization members.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001180"
    _name: ClassVar[str] = "Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SocialNetwork(GroupOfAgents, RDFEntity):
    """
    Social Network
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001183"
    _name: ClassVar[str] = "Social Network"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DelimitingDomain(Ont00000472, RDFEntity):
    """
    Delimiting Domain
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001203"
    _name: ClassVar[str] = "Delimiting Domain"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FemaleSex(BiologicalSex, RDFEntity):
    """
    Female Sex
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001212"
    _name: ClassVar[str] = "Female Sex"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GroupOfOrganizations(GroupOfAgents, RDFEntity):
    """
    Group of Organizations
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001239"
    _name: ClassVar[str] = "Group of Organizations"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[
        Annotated[List[Union[Organization, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ProcessRegulation(Ont00000965, RDFEntity):
    """
    Process Regulation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001324"
    _name: ClassVar[str] = "Process Regulation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "permits": "https://www.commoncoreontologies.org/ont00001910",
        "prohibits": "https://www.commoncoreontologies.org/ont00001800",
        "requires": "https://www.commoncoreontologies.org/ont00001974",
    }
    _object_properties: ClassVar[set[str]] = {"permits", "prohibits", "requires"}

    # Data properties
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
    permits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x permits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that y may occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prohibits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x prohibits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must not occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    requires: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x requires y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaleSex(BiologicalSex, RDFEntity):
    """
    Male Sex
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001363"
    _name: ClassVar[str] = "Male Sex"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncorporatedOrganization(Organization, RDFEntity):
    """
    Incorporated Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000010"
    _name: ClassVar[str] = "Incorporated Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Populace(GroupOfPersons, RDFEntity):
    """
    Populace
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000141"
    _name: ClassVar[str] = "Populace"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class GeopoliticalOrganization(Organization, RDFEntity):
    """
    Geopolitical Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000176"
    _name: ClassVar[str] = "Geopolitical Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LanguageSkill(Skill, RDFEntity):
    """
    Language Skill
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000181"
    _name: ClassVar[str] = "Language Skill"
    _property_uris: ClassVar[dict] = {
        "capability_of": "https://www.commoncoreontologies.org/ont00001889",
        "capability_of_aggregate": "https://www.commoncoreontologies.org/ont00001880",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "capability_of",
        "capability_of_aggregate",
    }

    # Data properties
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
    capability_of: Optional[
        Annotated[
            List[Union[Agent, URIRef, str]],
            Field(
                description="x capability_of y iff y is an instance of Agent and x is an instance of Agent Capability, such that x inheres in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    capability_of_aggregate: Optional[
        Annotated[
            List[Union[BFO_0000027, URIRef, str]],
            Field(
                description="x capability_of_aggregate y iff y is an instance of Object Aggregate and x is an instance of Agent Capability, such that x inheres in aggregate y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArmedForce(Organization, RDFEntity):
    """
    Armed Force
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000274"
    _name: ClassVar[str] = "Armed Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GovernmentOrganization(Organization, RDFEntity):
    """
    Government Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000408"
    _name: ClassVar[str] = "Government Organization"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000176",
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    bFO_0000176: Optional[Annotated[List[Union[Government, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CommercialOrganization(Organization, RDFEntity):
    """
    Commercial Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000443"
    _name: ClassVar[str] = "Commercial Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EthnicGroup(GroupOfPersons, RDFEntity):
    """
    Ethnic Group
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000507"
    _name: ClassVar[str] = "Ethnic Group"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001907": "https://www.commoncoreontologies.org/ont00001907",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178", "ont00001907"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]
    ont00001907: Optional[Annotated[List[Union[Ethnicity, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ServiceProvider(Organization, RDFEntity):
    """
    Service Provider
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000509"
    _name: ClassVar[str] = "Service Provider"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ProcessProhibition(ProcessRegulation, RDFEntity):
    """
    Process Prohibition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000553"
    _name: ClassVar[str] = "Process Prohibition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "permits": "https://www.commoncoreontologies.org/ont00001910",
        "prohibits": "https://www.commoncoreontologies.org/ont00001800",
        "requires": "https://www.commoncoreontologies.org/ont00001974",
    }
    _object_properties: ClassVar[set[str]] = {"permits", "prohibits", "requires"}

    # Data properties
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
    permits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x permits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that y may occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prohibits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x prohibits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must not occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    requires: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x requires y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EducationalOrganization(Organization, RDFEntity):
    """
    Educational Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000564"
    _name: ClassVar[str] = "Educational Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaterialTerritoryOfACountry(MaterialTerritoryOfAGovernmentDomain, RDFEntity):
    """
    Material Territory of a Country
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000631"
    _name: ClassVar[str] = "Material Territory of a Country"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActionPermission(ProcessRegulation, RDFEntity):
    """
    Action Permission
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000751"
    _name: ClassVar[str] = "Action Permission"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "permits": "https://www.commoncoreontologies.org/ont00001910",
        "prohibits": "https://www.commoncoreontologies.org/ont00001800",
        "requires": "https://www.commoncoreontologies.org/ont00001974",
    }
    _object_properties: ClassVar[set[str]] = {"permits", "prohibits", "requires"}

    # Data properties
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
    permits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x permits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that y may occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prohibits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x prohibits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must not occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    requires: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x requires y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Family(GroupOfPersons, RDFEntity):
    """
    Family
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000837"
    _name: ClassVar[str] = "Family"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class PoliticalOrientation(Ideology, RDFEntity):
    """
    Political Orientation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000976"
    _name: ClassVar[str] = "Political Orientation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GovernmentDomain(DelimitingDomain, RDFEntity):
    """
    Government Domain
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001152"
    _name: ClassVar[str] = "Government Domain"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ProcessRequirement(ProcessRegulation, RDFEntity):
    """
    Process Requirement
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001224"
    _name: ClassVar[str] = "Process Requirement"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "permits": "https://www.commoncoreontologies.org/ont00001910",
        "prohibits": "https://www.commoncoreontologies.org/ont00001800",
        "requires": "https://www.commoncoreontologies.org/ont00001974",
    }
    _object_properties: ClassVar[set[str]] = {"permits", "prohibits", "requires"}

    # Data properties
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
    permits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x permits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that y may occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prohibits: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x prohibits y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must not occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    requires: Optional[
        Annotated[
            List[Union[BFO_0000015, URIRef, str]],
            Field(
                description="x requires y at t iff: x is an instance of Process Regulation at time t, and y is an instance of Process at time t, and x prescribes that some y must occur."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Person(Animal, RDFEntity):
    """
    Person
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001262"
    _name: ClassVar[str] = "Person"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_familial_relationship_to": "https://www.commoncoreontologies.org/ont00001865",
        "is_parent_of": "https://www.commoncoreontologies.org/ont00001995",
        "is_supervised_by": "https://www.commoncoreontologies.org/ont00001798",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "supervises": "https://www.commoncoreontologies.org/ont00001943",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_familial_relationship_to",
        "is_parent_of",
        "is_supervised_by",
        "supervises",
    }

    # Data properties
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
    has_familial_relationship_to: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="A relationship between persons by virtue of ancestry or legal union."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_parent_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_parent_of y is a familial relationship between an instance of Person x and a different instance of Person y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_supervised_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_supervised_by y iff x and y are both instances of Person and y supervises x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    supervises: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x supervises y iff x and y are both instances of Person and x directs, manages, or oversees y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Crew(GroupOfPersons, RDFEntity):
    """
    Crew
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001284"
    _name: ClassVar[str] = "Crew"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class CivilOrganization(Organization, RDFEntity):
    """
    Civil Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001302"
    _name: ClassVar[str] = "Civil Organization"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Government(Organization, RDFEntity):
    """
    Government
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001335"
    _name: ClassVar[str] = "Government"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FirstOrderAdministrativeRegion(GovernmentDomain, RDFEntity):
    """
    First-Order Administrative Region
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000126"
    _name: ClassVar[str] = "First-Order Administrative Region"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176", "delimits"}

    # Data properties
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
        Annotated[List[Union[DomainOfACountry, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ThirdOrderAdministrativeRegion(GovernmentDomain, RDFEntity):
    """
    Third-Order Administrative Region
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000134"
    _name: ClassVar[str] = "Third-Order Administrative Region"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176", "delimits"}

    # Data properties
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
        Annotated[List[Union[SecondOrderAdministrativeRegion, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DomainOfACountry(GovernmentDomain, RDFEntity):
    """
    Domain of a Country
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000139"
    _name: ClassVar[str] = "Domain of a Country"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NuclearFamily(Family, RDFEntity):
    """
    Nuclear Family
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000383"
    _name: ClassVar[str] = "Nuclear Family"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000178"}

    # Data properties
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
    bFO_0000178: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Citizen(Person, RDFEntity):
    """
    Citizen
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000388"
    _name: ClassVar[str] = "Citizen"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_familial_relationship_to": "https://www.commoncoreontologies.org/ont00001865",
        "is_parent_of": "https://www.commoncoreontologies.org/ont00001995",
        "is_supervised_by": "https://www.commoncoreontologies.org/ont00001798",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "supervises": "https://www.commoncoreontologies.org/ont00001943",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_familial_relationship_to",
        "is_parent_of",
        "is_supervised_by",
        "supervises",
    }

    # Data properties
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
    has_familial_relationship_to: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="A relationship between persons by virtue of ancestry or legal union."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_parent_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_parent_of y is a familial relationship between an instance of Person x and a different instance of Person y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_supervised_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_supervised_by y iff x and y are both instances of Person and y supervises x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    supervises: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x supervises y iff x and y are both instances of Person and x directs, manages, or oversees y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SecondOrderAdministrativeRegion(GovernmentDomain, RDFEntity):
    """
    Second-Order Administrative Region
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000405"
    _name: ClassVar[str] = "Second-Order Administrative Region"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176", "delimits"}

    # Data properties
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
        Annotated[List[Union[FirstOrderAdministrativeRegion, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MilitaryPersonnelForce(ArmedForce, RDFEntity):
    """
    Military Personnel Force
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000426"
    _name: ClassVar[str] = "Military Personnel Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LocalAdministrativeRegion(GovernmentDomain, RDFEntity):
    """
    Local Administrative Region
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000460"
    _name: ClassVar[str] = "Local Administrative Region"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FourthOrderAdministrativeRegion(GovernmentDomain, RDFEntity):
    """
    Fourth-Order Administrative Region
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000473"
    _name: ClassVar[str] = "Fourth-Order Administrative Region"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176", "delimits"}

    # Data properties
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
        Annotated[List[Union[ThirdOrderAdministrativeRegion, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GovernmentOfACountry(Government, RDFEntity):
    """
    Government of a Country
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000532"
    _name: ClassVar[str] = "Government of a Country"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PermanentResident(Person, RDFEntity):
    """
    Permanent Resident
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000645"
    _name: ClassVar[str] = "Permanent Resident"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_familial_relationship_to": "https://www.commoncoreontologies.org/ont00001865",
        "is_parent_of": "https://www.commoncoreontologies.org/ont00001995",
        "is_supervised_by": "https://www.commoncoreontologies.org/ont00001798",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "supervises": "https://www.commoncoreontologies.org/ont00001943",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_familial_relationship_to",
        "is_parent_of",
        "is_supervised_by",
        "supervises",
    }

    # Data properties
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
    has_familial_relationship_to: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="A relationship between persons by virtue of ancestry or legal union."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_parent_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_parent_of y is a familial relationship between an instance of Person x and a different instance of Person y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_supervised_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_supervised_by y iff x and y are both instances of Person and y supervises x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    supervises: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x supervises y iff x and y are both instances of Person and x directs, manages, or oversees y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OrganizationMember(Person, RDFEntity):
    """
    Organization Member
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000647"
    _name: ClassVar[str] = "Organization Member"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_familial_relationship_to": "https://www.commoncoreontologies.org/ont00001865",
        "is_affiliated_with": "https://www.commoncoreontologies.org/ont00001939",
        "is_parent_of": "https://www.commoncoreontologies.org/ont00001995",
        "is_supervised_by": "https://www.commoncoreontologies.org/ont00001798",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "supervises": "https://www.commoncoreontologies.org/ont00001943",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_familial_relationship_to",
        "is_affiliated_with",
        "is_parent_of",
        "is_supervised_by",
        "supervises",
    }

    # Data properties
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
    has_familial_relationship_to: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="A relationship between persons by virtue of ancestry or legal union."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_affiliated_with: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_affiliated_with y iff x and y are instances of Agent, such that they have any kind of social or business relationship."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_parent_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_parent_of y is a familial relationship between an instance of Person x and a different instance of Person y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_supervised_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_supervised_by y iff x and y are both instances of Person and y supervises x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    supervises: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x supervises y iff x and y are both instances of Person and x directs, manages, or oversees y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NeutralPerson(Person, RDFEntity):
    """
    Neutral Person
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000666"
    _name: ClassVar[str] = "Neutral Person"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_familial_relationship_to": "https://www.commoncoreontologies.org/ont00001865",
        "is_parent_of": "https://www.commoncoreontologies.org/ont00001995",
        "is_supervised_by": "https://www.commoncoreontologies.org/ont00001798",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "supervises": "https://www.commoncoreontologies.org/ont00001943",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_familial_relationship_to",
        "is_parent_of",
        "is_supervised_by",
        "supervises",
    }

    # Data properties
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
    has_familial_relationship_to: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="A relationship between persons by virtue of ancestry or legal union."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_parent_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_parent_of y is a familial relationship between an instance of Person x and a different instance of Person y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_supervised_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_supervised_by y iff x and y are both instances of Person and y supervises x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    supervises: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x supervises y iff x and y are both instances of Person and x directs, manages, or oversees y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EnemyPerson(Person, RDFEntity):
    """
    Enemy Person
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000697"
    _name: ClassVar[str] = "Enemy Person"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_familial_relationship_to": "https://www.commoncoreontologies.org/ont00001865",
        "is_parent_of": "https://www.commoncoreontologies.org/ont00001995",
        "is_supervised_by": "https://www.commoncoreontologies.org/ont00001798",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "supervises": "https://www.commoncoreontologies.org/ont00001943",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_familial_relationship_to",
        "is_parent_of",
        "is_supervised_by",
        "supervises",
    }

    # Data properties
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
    has_familial_relationship_to: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="A relationship between persons by virtue of ancestry or legal union."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_parent_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_parent_of y is a familial relationship between an instance of Person x and a different instance of Person y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_supervised_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_supervised_by y iff x and y are both instances of Person and y supervises x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    supervises: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x supervises y iff x and y are both instances of Person and x directs, manages, or oversees y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class AlliedPerson(Person, RDFEntity):
    """
    Allied Person
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000860"
    _name: ClassVar[str] = "Allied Person"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_familial_relationship_to": "https://www.commoncoreontologies.org/ont00001865",
        "is_parent_of": "https://www.commoncoreontologies.org/ont00001995",
        "is_supervised_by": "https://www.commoncoreontologies.org/ont00001798",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "supervises": "https://www.commoncoreontologies.org/ont00001943",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_familial_relationship_to",
        "is_parent_of",
        "is_supervised_by",
        "supervises",
    }

    # Data properties
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
    has_familial_relationship_to: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="A relationship between persons by virtue of ancestry or legal union."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_parent_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_parent_of y is a familial relationship between an instance of Person x and a different instance of Person y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_supervised_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x is_supervised_by y iff x and y are both instances of Person and y supervises x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    supervises: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="x supervises y iff x and y are both instances of Person and x directs, manages, or oversees y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class County(GovernmentDomain, RDFEntity):
    """
    County
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001164"
    _name: ClassVar[str] = "County"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ParamilitaryForce(ArmedForce, RDFEntity):
    """
    Paramilitary Force
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001312"
    _name: ClassVar[str] = "Paramilitary Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Province(FirstOrderAdministrativeRegion, RDFEntity):
    """
    Province
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000046"
    _name: ClassVar[str] = "Province"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176", "delimits"}

    # Data properties
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
        Annotated[List[Union[DomainOfACountry, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Town(LocalAdministrativeRegion, RDFEntity):
    """
    Town
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000071"
    _name: ClassVar[str] = "Town"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Village(LocalAdministrativeRegion, RDFEntity):
    """
    Village
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000718"
    _name: ClassVar[str] = "Village"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class City(LocalAdministrativeRegion, RDFEntity):
    """
    City
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000887"
    _name: ClassVar[str] = "City"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"delimits"}

    # Data properties
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
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ConstituentState(FirstOrderAdministrativeRegion, RDFEntity):
    """
    Constituent State
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000934"
    _name: ClassVar[str] = "Constituent State"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "delimits": "https://www.commoncoreontologies.org/ont00001864",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176", "delimits"}

    # Data properties
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
        Annotated[List[Union[DomainOfACountry, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    delimits: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x delimits y iff x is an instance of Delimiting Domain and y is an instance of Organization and y can legally operate only within x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CarrierAirWing(MilitaryPersonnelForce, RDFEntity):
    """
    Carrier Air Wing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001276"
    _name: ClassVar[str] = "Carrier Air Wing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_subsidiary": "https://www.commoncoreontologies.org/ont00001794",
        "is_delimited_by": "https://www.commoncoreontologies.org/ont00001859",
        "is_organizational_context_of": "https://www.commoncoreontologies.org/ont00001846",
        "is_subsidiary_of": "https://www.commoncoreontologies.org/ont00001815",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_subsidiary",
        "is_delimited_by",
        "is_organizational_context_of",
        "is_subsidiary_of",
    }

    # Data properties
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
    has_subsidiary: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x has_subsidiary y iff x and y are both instances of Organization and y is_subsidiary_of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_delimited_by: Optional[
        Annotated[
            List[Union[DelimitingDomain, URIRef, str]],
            Field(
                description="x is_delimited_by y iff x is an instance of Organization and y is an instance of Delimiting Domain and y delimits x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_organizational_context_of: Optional[
        Annotated[
            List[Union[BFO_0000023, URIRef, str]],
            Field(
                description="x is_organizational_context_of y iff x is an instance of an Organization and y is an instance of a Role and z is an instance of a Person, such that z's affiliation with x is a prerequisite for z bearing y, or x ascribes y to the bearer of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_subsidiary_of: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="x is_subsidiary_of y iff x and y are both instances of Organization and y controls x by having the capacity to determine the outcome of decisions about the financial and operating policies of x. "
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


# Rebuild models to resolve forward references
HairColor.model_rebuild()
EyeColor.model_rebuild()
BodilyComponent.model_rebuild()
SkinType.model_rebuild()
CivilianRole.model_rebuild()
OrganizationMemberRole.model_rebuild()
Affordance.model_rebuild()
AuthorityRole.model_rebuild()
Ont00000207.model_rebuild()
GroupOfAgents.model_rebuild()
Disease.model_rebuild()
Disability.model_rebuild()
AllegianceRole.model_rebuild()
Ont00000472.model_rebuild()
CommercialRole.model_rebuild()
Ont00000487.model_rebuild()
ContractorRole.model_rebuild()
Organism.model_rebuild()
InterpersonalRelationshipRole.model_rebuild()
FinancialValue.model_rebuild()
Ethnicity.model_rebuild()
GeopoliticalPowerRole.model_rebuild()
PermanentResidentRole.model_rebuild()
Ont00000958.model_rebuild()
Ont00000965.model_rebuild()
OccupationRole.model_rebuild()
CitizenRole.model_rebuild()
OperatorRole.model_rebuild()
Agent.model_rebuild()
BiologicalSex.model_rebuild()
Ont00001341.model_rebuild()
AgentCapability.model_rebuild()
ScalpHair.model_rebuild()
Skill.model_rebuild()
Tattoo.model_rebuild()
FacialHair.model_rebuild()
EnemyRole.model_rebuild()
Iris.model_rebuild()
Objective.model_rebuild()
NeutralRole.model_rebuild()
Eye.model_rebuild()
Animal.model_rebuild()
OperationalArea.model_rebuild()
OrganizationCapability.model_rebuild()
Scalp.model_rebuild()
AllyRole.model_rebuild()
Religion.model_rebuild()
MaterialTerritoryOfAGovernmentDomain.model_rebuild()
GovernmentDomainBorder.model_rebuild()
Ideology.model_rebuild()
Plant.model_rebuild()
GroupOfPersons.model_rebuild()
Plan.model_rebuild()
Scar.model_rebuild()
InternationalCommunity.model_rebuild()
FinancialValueOfProperty.model_rebuild()
DivisionOfDelimitingDomain.model_rebuild()
SetOfEyes.model_rebuild()
Organization.model_rebuild()
SocialNetwork.model_rebuild()
DelimitingDomain.model_rebuild()
FemaleSex.model_rebuild()
GroupOfOrganizations.model_rebuild()
ProcessRegulation.model_rebuild()
MaleSex.model_rebuild()
IncorporatedOrganization.model_rebuild()
Populace.model_rebuild()
GeopoliticalOrganization.model_rebuild()
LanguageSkill.model_rebuild()
ArmedForce.model_rebuild()
GovernmentOrganization.model_rebuild()
CommercialOrganization.model_rebuild()
EthnicGroup.model_rebuild()
ServiceProvider.model_rebuild()
ProcessProhibition.model_rebuild()
EducationalOrganization.model_rebuild()
MaterialTerritoryOfACountry.model_rebuild()
ActionPermission.model_rebuild()
Family.model_rebuild()
PoliticalOrientation.model_rebuild()
GovernmentDomain.model_rebuild()
ProcessRequirement.model_rebuild()
Person.model_rebuild()
Crew.model_rebuild()
CivilOrganization.model_rebuild()
Government.model_rebuild()
FirstOrderAdministrativeRegion.model_rebuild()
ThirdOrderAdministrativeRegion.model_rebuild()
DomainOfACountry.model_rebuild()
NuclearFamily.model_rebuild()
Citizen.model_rebuild()
SecondOrderAdministrativeRegion.model_rebuild()
MilitaryPersonnelForce.model_rebuild()
LocalAdministrativeRegion.model_rebuild()
FourthOrderAdministrativeRegion.model_rebuild()
GovernmentOfACountry.model_rebuild()
PermanentResident.model_rebuild()
OrganizationMember.model_rebuild()
NeutralPerson.model_rebuild()
EnemyPerson.model_rebuild()
AlliedPerson.model_rebuild()
County.model_rebuild()
ParamilitaryForce.model_rebuild()
Province.model_rebuild()
Town.model_rebuild()
Village.model_rebuild()
City.model_rebuild()
ConstituentState.model_rebuild()
CarrierAirWing.model_rebuild()
