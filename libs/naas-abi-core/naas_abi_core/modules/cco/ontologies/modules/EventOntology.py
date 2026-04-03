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


class ProcessProfile(RDFEntity):
    """
    Process Profile
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000144"
    _name: ClassVar[str] = "Process Profile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Change(RDFEntity):
    """
    Change
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000004"
    _name: ClassVar[str] = "Change"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Act(RDFEntity):
    """
    Act
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000005"
    _name: ClassVar[str] = "Act"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NaturalProcess(RDFEntity):
    """
    Natural Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000007"
    _name: ClassVar[str] = "Natural Process"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ProcessEnding(RDFEntity):
    """
    Process Ending
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000083"
    _name: ClassVar[str] = "Process Ending"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MechanicalProcess(RDFEntity):
    """
    Mechanical Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000110"
    _name: ClassVar[str] = "Mechanical Process"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ProcessBeginning(RDFEntity):
    """
    Process Beginning
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000197"
    _name: ClassVar[str] = "Process Beginning"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Target(RDFEntity):
    """
    Although people speak of targeting a process, say, a parade, what in fact are being targeted are the material participants of that process. The disruption or ceasing of the process is the objective of some plan, but not technically a target. Only material things can be targeted for action. Even if some dependent entity is described as being the target, the material thing for which that dependent entity depends is the object of a targeting process.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000544"
    _name: ClassVar[str] = "Target"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Effect(RDFEntity):
    """
    Effect
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000660"
    _name: ClassVar[str] = "Effect"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Stasis(RDFEntity):
    """
    Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000819"
    _name: ClassVar[str] = "Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Cause(RDFEntity):
    """
    Cause
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000978"
    _name: ClassVar[str] = "Cause"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WaveProcess(NaturalProcess, RDFEntity):
    """
    Wave Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000099"
    _name: ClassVar[str] = "Wave Process"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[URIRef, WaveProcessProfile, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class StasisOfSpecificallyDependentContinuant(Stasis, RDFEntity):
    """
    Stasis of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000135"
    _name: ClassVar[str] = "Stasis of Specifically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PlannedAct(Act, RDFEntity):
    """
    Planned Act
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000228"
    _name: ClassVar[str] = "Planned Act"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Combustion(NaturalProcess, RDFEntity):
    """
    Combustion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000272"
    _name: ClassVar[str] = "Combustion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Momentum(ProcessProfile, RDFEntity):
    """
    The SI unit of measure for Momentum is Newton seconds (N s).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000278"
    _name: ClassVar[str] = "Momentum"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PropulsionProcess(NaturalProcess, RDFEntity):
    """
    Propulsion Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000312"
    _name: ClassVar[str] = "Propulsion Process"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfGenericallyDependentContinuant(Stasis, RDFEntity):
    """
    Stasis of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000335"
    _name: ClassVar[str] = "Stasis of Generically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BiographicalLife(Act, RDFEntity):
    """
    Biographical Life
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000418"
    _name: ClassVar[str] = "Biographical Life"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Power(ProcessProfile, RDFEntity):
    """
    Power
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000503"
    _name: ClassVar[str] = "Power"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UnplannedAct(Act, RDFEntity):
    """
    Unplanned Act
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000546"
    _name: ClassVar[str] = "Unplanned Act"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfDependentContinuant(Change, RDFEntity):
    """
    Gain of Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000554"
    _name: ClassVar[str] = "Gain of Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Force(ProcessProfile, RDFEntity):
    """
    Force
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000570"
    _name: ClassVar[str] = "Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IgnitionProcess(NaturalProcess, RDFEntity):
    """
    Ignition Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000594"
    _name: ClassVar[str] = "Ignition Process"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OscillationProcess(Change, RDFEntity):
    """
    Oscillation is often thought of in the sense of motion, e.g., a swinging clock pendulum. However, the repetitive variation in location around a central point is technically a process of vibration, sometimes referred to as mechanical oscillation. Use the term Vibration Motion for those cases.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000644"
    _name: ClassVar[str] = "Oscillation Process"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Acceleration(ProcessProfile, RDFEntity):
    """
    Acceleration
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000712"
    _name: ClassVar[str] = "Acceleration"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[Annotated[List[Union[URIRef, Velocity, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class DecreaseOfDependentContinuant(Change, RDFEntity):
    """
    Decrease of Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000726"
    _name: ClassVar[str] = "Decrease of Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WaveProcessProfile(ProcessProfile, RDFEntity):
    """
    This is a defined class used to group process profiles of Wave Processes. Note that not every relevant process profile can be asserted as a subtype, however, because they (e.g. Frequency and Amplitude) are applicable to other processes as well (e.g. Oscillation Process).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000752"
    _name: ClassVar[str] = "Wave Process Profile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Velocity(ProcessProfile, RDFEntity):
    """
    Velocity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000763"
    _name: ClassVar[str] = "Velocity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WaveProduction(NaturalProcess, RDFEntity):
    """
    Wave Production
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000765"
    _name: ClassVar[str] = "Wave Production"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ImpulsiveForce(ProcessProfile, RDFEntity):
    """
    An Impulse changes the Momentum (and potentially also the direction of Motion) of the object it is applied to and is typically measured in Newton meters.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000772"
    _name: ClassVar[str] = "Impulsive Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Speed(ProcessProfile, RDFEntity):
    """
    An object's speed is the scalar absolute value of it's Velocity.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000830"
    _name: ClassVar[str] = "Speed"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EffectOfLocationChange(Effect, RDFEntity):
    """
    Effect of Location Change
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000855"
    _name: ClassVar[str] = "Effect of Location Change"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001819": "https://www.commoncoreontologies.org/ont00001819",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132", "ont00001819"}

    # Data properties
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
    bFO_0000132: Optional[
        Annotated[List[Union[ActOfLocationChange, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001819: Optional[
        Annotated[List[Union[ActOfLocationChange, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SoundProcessProfile(ProcessProfile, RDFEntity):
    """
    Sound Process Profile
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000862"
    _name: ClassVar[str] = "Sound Process Profile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LossOfDependentContinuant(Change, RDFEntity):
    """
    Loss of Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000876"
    _name: ClassVar[str] = "Loss of Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Amplitude(ProcessProfile, RDFEntity):
    """
    Amplitude
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000910"
    _name: ClassVar[str] = "Amplitude"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Death(NaturalProcess, RDFEntity):
    """
    Death
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000920"
    _name: ClassVar[str] = "Death"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Frequency(ProcessProfile, RDFEntity):
    """
    Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001047"
    _name: ClassVar[str] = "Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfDependentContinuant(Change, RDFEntity):
    """
    Increase of Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001048"
    _name: ClassVar[str] = "Increase of Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioInterference(NaturalProcess, RDFEntity):
    """
    Radio Interference
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001122"
    _name: ClassVar[str] = "Radio Interference"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Motion(NaturalProcess, RDFEntity):
    """
    Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001133"
    _name: ClassVar[str] = "Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Deltav(ProcessProfile, RDFEntity):
    """
    Delta-v is not equivalent to and should not be confused with Acceleration, which is the rate of change of Velocity.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001219"
    _name: ClassVar[str] = "Delta-v"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[Annotated[List[Union[URIRef, Velocity, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Birth(NaturalProcess, RDFEntity):
    """
    Birth
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001237"
    _name: ClassVar[str] = "Birth"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelemetryProcess(MechanicalProcess, RDFEntity):
    """
    Telemetry Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001330"
    _name: ClassVar[str] = "Telemetry Process"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[
            List[Union[ActOfCommunicationByMedia, ActOfMeasuring, URIRef, str]], Field()
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Behavior(Act, RDFEntity):
    """
    Behavior
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001347"
    _name: ClassVar[str] = "Behavior"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SoundFrequency(Frequency, RDFEntity):
    """
    Sound Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000008"
    _name: ClassVar[str] = "Sound Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NominalStasis(StasisOfSpecificallyDependentContinuant, RDFEntity):
    """
    Nominal Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000011"
    _name: ClassVar[str] = "Nominal Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfGenericallyDependentContinuant(GainOfDependentContinuant, RDFEntity):
    """
    Gain of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000013"
    _name: ClassVar[str] = "Gain of Generically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000057"}

    # Data properties
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
    bFO_0000057: Optional[Annotated[List[Union[BFO_0000031, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ActOfObservation(PlannedAct, RDFEntity):
    """
    Act of Observation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000037"
    _name: ClassVar[str] = "Act of Observation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfGenericallyDependentContinuant(
    IncreaseOfDependentContinuant, RDFEntity
):
    """
    Increase of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000107"
    _name: ClassVar[str] = "Increase of Generically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMilitaryForce(PlannedAct, RDFEntity):
    """
    Act of Military Force
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000109"
    _name: ClassVar[str] = "Act of Military Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MaximumPower(Power, RDFEntity):
    """
    Maximum Power
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000138"
    _name: ClassVar[str] = "Maximum Power"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfGovernment(PlannedAct, RDFEntity):
    """
    Act of Government
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000142"
    _name: ClassVar[str] = "Act of Government"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CriminalAct(PlannedAct, RDFEntity):
    """
    Criminal Act
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000165"
    _name: ClassVar[str] = "Criminal Act"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WaveCycle(WaveProcess, RDFEntity):
    """
    Wave Cycle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000166"
    _name: ClassVar[str] = "Wave Cycle"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[URIRef, WaveProcessProfile, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Thrust(Force, RDFEntity):
    """
    More generally, Thrust is the propulsive Force of a Rocket.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000179"
    _name: ClassVar[str] = "Thrust"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfTraining(PlannedAct, RDFEntity):
    """
    Act of Training
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000234"
    _name: ClassVar[str] = "Act of Training"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfRealizableEntity(StasisOfSpecificallyDependentContinuant, RDFEntity):
    """
    Stasis of Realizable Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000246"
    _name: ClassVar[str] = "Stasis of Realizable Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DecreaseOfSpecificallyDependentContinuant(
    DecreaseOfDependentContinuant, RDFEntity
):
    """
    Decrease of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000290"
    _name: ClassVar[str] = "Decrease of Specifically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AngularVelocity(Velocity, RDFEntity):
    """
    Angular Velocity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000296"
    _name: ClassVar[str] = "Angular Velocity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Wavelength(WaveProcessProfile, RDFEntity):
    """
    Assuming a non-dispersive media, the Wavelength will be the inverse of the Frequency.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000313"
    _name: ClassVar[str] = "Wavelength"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMeasuring(PlannedAct, RDFEntity):
    """
    Act of Measuring
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000345"
    _name: ClassVar[str] = "Act of Measuring"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMotion(PlannedAct, RDFEntity):
    """
    Act of Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000357"
    _name: ClassVar[str] = "Act of Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfInformationProcessing(PlannedAct, RDFEntity):
    """
    Act of Information Processing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000366"
    _name: ClassVar[str] = "Act of Information Processing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RotationalMotion(Motion, RDFEntity):
    """
    Rotational Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000368"
    _name: ClassVar[str] = "Rotational Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[List[Union[AngularVelocity, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfPrediction(PlannedAct, RDFEntity):
    """
    An Act of Prediction may involve the use of some or no relevant information. An Act of Prediction that utilizes relevant information may also be (or at least involve) an Act of Estimation. Hence, these two classes are not disjoint. Furthermore, neither class subsumes the other since estimates can be made about existing entities and not all predictions produce measurements (e.g. predicting that it will rain tomorrow).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000371"
    _name: ClassVar[str] = "Act of Prediction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Pressure(Force, RDFEntity):
    """
    Pressure
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000380"
    _name: ClassVar[str] = "Pressure"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfSpecificallyDependentContinuant(GainOfDependentContinuant, RDFEntity):
    """
    Gain of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000395"
    _name: ClassVar[str] = "Gain of Specifically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000057"}

    # Data properties
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
    bFO_0000057: Optional[Annotated[List[Union[BFO_0000020, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ActOfCommunication(PlannedAct, RDFEntity):
    """
    Act of Communication
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000402"
    _name: ClassVar[str] = "Act of Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPlanning(PlannedAct, RDFEntity):
    """
    Act of Planning
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000511"
    _name: ClassVar[str] = "Act of Planning"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TransverseWaveProfile(WaveProcessProfile, RDFEntity):
    """
    Transverse Wave Profile
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000514"
    _name: ClassVar[str] = "Transverse Wave Profile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Loudness(SoundProcessProfile, RDFEntity):
    """
    Loudness
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000523"
    _name: ClassVar[str] = "Loudness"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LossOfGenericallyDependentContinuant(LossOfDependentContinuant, RDFEntity):
    """
    Loss of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000542"
    _name: ClassVar[str] = "Loss of Generically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EnhancedStasis(StasisOfSpecificallyDependentContinuant, RDFEntity):
    """
    Enhanced Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000555"
    _name: ClassVar[str] = "Enhanced Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VisibleLightReflectionProcess(WaveProcess, RDFEntity):
    """
    Visible Light Reflection Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000558"
    _name: ClassVar[str] = "Visible Light Reflection Process"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[URIRef, WaveProcessProfile, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfArtifactEmployment(PlannedAct, RDFEntity):
    """
    Act of Artifact Employment
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000566"
    _name: ClassVar[str] = "Act of Artifact Employment"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SoundProduction(WaveProduction, RDFEntity):
    """
    Sound Production
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000572"
    _name: ClassVar[str] = "Sound Production"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfInhabitancy(PlannedAct, RDFEntity):
    """
    Act of Inhabitancy
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000676"
    _name: ClassVar[str] = "Act of Inhabitancy"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfTargeting(PlannedAct, RDFEntity):
    """
    Act of Targeting
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000741"
    _name: ClassVar[str] = "Act of Targeting"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectromagneticRadiationFrequency(Frequency, RDFEntity):
    """
    Divisions between EM radiation frequencies are fiat and sources vary on where to draw boundaries.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000754"
    _name: ClassVar[str] = "Electromagnetic Radiation Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SurfaceWaveProfile(WaveProcessProfile, RDFEntity):
    """
    Surface Wave Profile
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000760"
    _name: ClassVar[str] = "Surface Wave Profile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TranslationalMotion(Motion, RDFEntity):
    """
    Translational Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000789"
    _name: ClassVar[str] = "Translational Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[Annotated[List[Union[URIRef, Velocity, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class StasisOfQuality(StasisOfSpecificallyDependentContinuant, RDFEntity):
    """
    Stasis of Quality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000850"
    _name: ClassVar[str] = "Stasis of Quality"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LossOfSpecificallyDependentContinuant(LossOfDependentContinuant, RDFEntity):
    """
    Loss of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000865"
    _name: ClassVar[str] = "Loss of Specifically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Married(StasisOfGenericallyDependentContinuant, RDFEntity):
    """
    Married
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000895"
    _name: ClassVar[str] = "Married"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfArtifactProcessing(PlannedAct, RDFEntity):
    """
    Act of Artifact Processing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000908"
    _name: ClassVar[str] = "Act of Artifact Processing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfConsumption(PlannedAct, RDFEntity):
    """
    Act of Consumption
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000949"
    _name: ClassVar[str] = "Act of Consumption"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ElectromagneticWaveProcess(WaveProcess, RDFEntity):
    """
    Electromagnetic Wave Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000951"
    _name: ClassVar[str] = "Electromagnetic Wave Process"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[TransverseWaveProfile, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Pitch(SoundProcessProfile, RDFEntity):
    """
    Pitch
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000953"
    _name: ClassVar[str] = "Pitch"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AngularMomentum(Momentum, RDFEntity):
    """
    Angular Momentum
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000955"
    _name: ClassVar[str] = "Angular Momentum"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MechanicalWaveProcess(WaveProcess, RDFEntity):
    """
    Mechanical Wave Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001028"
    _name: ClassVar[str] = "Mechanical Wave Process"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[URIRef, WaveProcessProfile, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ProperAcceleration(Acceleration, RDFEntity):
    """
    Proper Acceleration
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001112"
    _name: ClassVar[str] = "Proper Acceleration"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[Annotated[List[Union[URIRef, Velocity, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ActOfEntertainment(PlannedAct, RDFEntity):
    """
    Act of Entertainment
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001144"
    _name: ClassVar[str] = "Act of Entertainment"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfViolence(PlannedAct, RDFEntity):
    """
    Act of Violence
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001147"
    _name: ClassVar[str] = "Act of Violence"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfSpecificallyDependentContinuant(
    IncreaseOfDependentContinuant, RDFEntity
):
    """
    Increase of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001214"
    _name: ClassVar[str] = "Increase of Specifically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LongitudinalWaveProfile(WaveProcessProfile, RDFEntity):
    """
    Longitudinal Wave Profile
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001227"
    _name: ClassVar[str] = "Longitudinal Wave Profile"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001857": "https://www.commoncoreontologies.org/ont00001857",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001857"}

    # Data properties
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
    ont00001857: Optional[
        Annotated[List[Union[MechanicalWaveProcess, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfPossession(PlannedAct, RDFEntity):
    """
    In all cases, to possess something, an agent must have an intention to possess it.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001232"
    _name: ClassVar[str] = "Act of Possession"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfIntelligenceGathering(PlannedAct, RDFEntity):
    """
    Act of Intelligence Gathering
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001251"
    _name: ClassVar[str] = "Act of Intelligence Gathering"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VibrationMotion(Motion, RDFEntity):
    """
    Vibration Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001279"
    _name: ClassVar[str] = "Vibration Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Waveform(WaveProcessProfile, RDFEntity):
    """
    Waveform
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001286"
    _name: ClassVar[str] = "Waveform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DamagedStasis(StasisOfSpecificallyDependentContinuant, RDFEntity):
    """
    Damaged Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001289"
    _name: ClassVar[str] = "Damaged Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LegalSystemAct(PlannedAct, RDFEntity):
    """
    Legal System Act
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001314"
    _name: ClassVar[str] = "Legal System Act"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DecreaseOfGenericallyDependentContinuant(
    DecreaseOfDependentContinuant, RDFEntity
):
    """
    For the most part Generically Dependent Continuants do not inhere in their bearers over some continuous scale. The primary exception is religion and this class allows annotation of those cases where an Agent is described as becoming less religious. Other cases would include the decrease of an organization's bearing of some objective.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001322"
    _name: ClassVar[str] = "Decrease of Generically Dependent Continuant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SocialAct(PlannedAct, RDFEntity):
    """
    Social Act
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001327"
    _name: ClassVar[str] = "Social Act"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Timbre(SoundProcessProfile, RDFEntity):
    """
    Timbre
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001338"
    _name: ClassVar[str] = "Timbre"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Torque(Force, RDFEntity):
    """
    Torque
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001376"
    _name: ClassVar[str] = "Torque"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TriangularWaveform(Waveform, RDFEntity):
    """
    Triangular Waveform
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000016"
    _name: ClassVar[str] = "Triangular Waveform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfConstruction(ActOfArtifactProcessing, RDFEntity):
    """
    An Act of Construction typically involves the production of only one or a limited number of goods, such as in the construction of an airport or a community of condominiums.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000051"
    _name: ClassVar[str] = "Act of Construction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfLocationChange(ActOfMotion, RDFEntity):
    """
    Act of Location Change
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000065"
    _name: ClassVar[str] = "Act of Location Change"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfEstimation(ActOfMeasuring, RDFEntity):
    """
    Although the boundary between Act of Estimation and guessing is vague, estimation can be partially distinguished from guessing in that every Act of Estimation has as input some relevant information; whereas an act of guessing can occur sans information (or at least sans pertinent information). For example, if Mr. Green were asked how many blades of grass are in his lawn, he could simply choose a number (i.e. he could guess) or he could estimate the number by counting how many baldes of grass are in 1 square foot of his lawn, measuring the square footage of his lawn, and then multiplying these values to arrive at a number. Hence, many estimates may be loosely considered to be educated guesses.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000078"
    _name: ClassVar[str] = "Act of Estimation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfSocialMovement(SocialAct, RDFEntity):
    """
    Act of Social Movement
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000079"
    _name: ClassVar[str] = "Act of Social Movement"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfDisposition(StasisOfRealizableEntity, RDFEntity):
    """
    Stasis of Disposition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000115"
    _name: ClassVar[str] = "Stasis of Disposition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfExpressiveCommunication(ActOfCommunication, RDFEntity):
    """
    Examples: apologizing, condoling, congratulating, greeting, thanking, accepting (acknowledging an acknowledgment)
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000123"
    _name: ClassVar[str] = "Act of Expressive Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfQuality(IncreaseOfSpecificallyDependentContinuant, RDFEntity):
    """
    Increase of Quality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000131"
    _name: ClassVar[str] = "Increase of Quality"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDirectiveCommunication(ActOfCommunication, RDFEntity):
    """
    Examples: advising, admonishing, asking, begging, dismissing, excusing, forbidding, instructing, ordering, permitting, requesting, requiring, suggesting, urging, warning
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000133"
    _name: ClassVar[str] = "Act of Directive Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ClockwiseRotationalMotion(RotationalMotion, RDFEntity):
    """
    Clockwise Rotational Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000148"
    _name: ClassVar[str] = "Clockwise Rotational Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[List[Union[AngularVelocity, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RadioFrequency(ElectromagneticRadiationFrequency, RDFEntity):
    """
    Radio Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000150"
    _name: ClassVar[str] = "Radio Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfHomicide(ActOfViolence, RDFEntity):
    """
    Act of Homicide
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000191"
    _name: ClassVar[str] = "Act of Homicide"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001803": "https://www.commoncoreontologies.org/ont00001803",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001803"}

    # Data properties
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
    ont00001803: Optional[Annotated[List[Union[Death, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class SoundWavelength(Wavelength, RDFEntity):
    """
    Sound Wavelength
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000209"
    _name: ClassVar[str] = "Sound Wavelength"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LossOfRealizableEntity(LossOfSpecificallyDependentContinuant, RDFEntity):
    """
    Loss of Realizable Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000250"
    _name: ClassVar[str] = "Loss of Realizable Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GammaRayFrequency(ElectromagneticRadiationFrequency, RDFEntity):
    """
    Currently gamma radiation is distinguished from x-rays by their source--either inside or outside of the nucleus--rather than by frequency, energy, and wavelength.
    https://en.wikipedia.org/wiki/Gamma_ray#Naming_conventions_and_overlap_in_terminology
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000261"
    _name: ClassVar[str] = "Gamma Ray Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Election(SocialAct, RDFEntity):
    """
    Election
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000265"
    _name: ClassVar[str] = "Election"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDecoyUse(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Decoy Use
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000291"
    _name: ClassVar[str] = "Act of Decoy Use"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SoundPressure(Pressure, RDFEntity):
    """
    Sound Pressure
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000305"
    _name: ClassVar[str] = "Sound Pressure"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfReconnaissance(ActOfIntelligenceGathering, RDFEntity):
    """
    Act of Reconnaissance
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000320"
    _name: ClassVar[str] = "Act of Reconnaissance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WoundedStasis(DamagedStasis, RDFEntity):
    """
    Wounded Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000360"
    _name: ClassVar[str] = "Wounded Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfRepresentativeCommunication(ActOfCommunication, RDFEntity):
    """
    Examples: affirming, alleging, announcing, answering, attributing, claiming, classifying, concurring, confirming, conjecturing, denying, disagreeing, disclosing, disputing, identifying, informing, insisting, predicting, ranking, reporting, stating, stipulating
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000379"
    _name: ClassVar[str] = "Act of Representative Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RectilinearMotion(TranslationalMotion, RDFEntity):
    """
    Rectilinear Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000384"
    _name: ClassVar[str] = "Rectilinear Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[Annotated[List[Union[URIRef, Velocity, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class TremendouslyHighFrequency(ElectromagneticRadiationFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 1–0.1 mm
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000391"
    _name: ClassVar[str] = "Tremendously High Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FundamentalFrequency(SoundFrequency, RDFEntity):
    """
    Fundamental Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000401"
    _name: ClassVar[str] = "Fundamental Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SquareWaveform(Waveform, RDFEntity):
    """
    Square Waveform
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000414"
    _name: ClassVar[str] = "Square Waveform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StableOrientation(StasisOfQuality, RDFEntity):
    """
    Stable Orientation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000430"
    _name: ClassVar[str] = "Stable Orientation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfAssociation(SocialAct, RDFEntity):
    """
    Act of Association
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000433"
    _name: ClassVar[str] = "Act of Association"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCeremony(SocialAct, RDFEntity):
    """
    Act of Ceremony
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000455"
    _name: ClassVar[str] = "Act of Ceremony"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class XrayFrequency(ElectromagneticRadiationFrequency, RDFEntity):
    """
    X-ray Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000490"
    _name: ClassVar[str] = "X-ray Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfToolUse(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Tool Use
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000513"
    _name: ClassVar[str] = "Act of Tool Use"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfVehicleUse(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Vehicle Use
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000515"
    _name: ClassVar[str] = "Act of Vehicle Use"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCommunicationByMedia(ActOfCommunication, RDFEntity):
    """
    Act of Communication by Media
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000517"
    _name: ClassVar[str] = "Act of Communication by Media"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SonicFrequency(SoundFrequency, RDFEntity):
    """
    Sound waves with frequencies in this range are typically audible to humans.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000530"
    _name: ClassVar[str] = "Sonic Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DecreaseOfQuality(DecreaseOfSpecificallyDependentContinuant, RDFEntity):
    """
    Decrease of Quality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000535"
    _name: ClassVar[str] = "Decrease of Quality"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SineWaveform(Waveform, RDFEntity):
    """
    Sine Waveform
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000580"
    _name: ClassVar[str] = "Sine Waveform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPositionChange(ActOfMotion, RDFEntity):
    """
    An Act of Position Change does not entail a change of location.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000584"
    _name: ClassVar[str] = "Act of Position Change"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SawtoothWaveform(Waveform, RDFEntity):
    """
    Sawtooth Waveform
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000585"
    _name: ClassVar[str] = "Sawtooth Waveform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMassMediaCommunication(ActOfCommunication, RDFEntity):
    """
    Act of Mass Media Communication
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000588"
    _name: ClassVar[str] = "Act of Mass Media Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UltravioletLightFrequency(ElectromagneticRadiationFrequency, RDFEntity):
    """
    Ultraviolet Light Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000610"
    _name: ClassVar[str] = "Ultraviolet Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfRealizableEntity(IncreaseOfSpecificallyDependentContinuant, RDFEntity):
    """
    Increase of Realizable Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000611"
    _name: ClassVar[str] = "Increase of Realizable Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfWeaponUse(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Weapon Use
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000612"
    _name: ClassVar[str] = "Act of Weapon Use"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InverseSawtoothWaveform(Waveform, RDFEntity):
    """
    Inverse Sawtooth Waveform
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000621"
    _name: ClassVar[str] = "Inverse Sawtooth Waveform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfAppraisal(ActOfMeasuring, RDFEntity):
    """
    Note that, while most if not all Acts of Appraisal involve some estimating and many Acts of Estimation involve some appraising (i.e. these classes are not disjoint), neither class subsumes the other. For example, some Acts of Appraisal (e.g. a tax assessor appraising the value of a building) impart a normative element to the measured value while others (e.g. a gustatory appraisal that fresh green beans taste better than canned green beans) involve complete information. Furthermore, many Acts of Estimation (e.g. estimating the height of a tree) are concerned solely with determining a numerical value (as opposed to the nature, value, importance, condition, or quality).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000636"
    _name: ClassVar[str] = "Act of Appraisal"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfRealizableEntity(GainOfSpecificallyDependentContinuant, RDFEntity):
    """
    Gain of Realizable Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000642"
    _name: ClassVar[str] = "Gain of Realizable Entity"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000057"}

    # Data properties
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
    bFO_0000057: Optional[Annotated[List[Union[BFO_0000017, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ActOfTerrorism(ActOfViolence, RDFEntity):
    """
    Act of Terrorism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000654"
    _name: ClassVar[str] = "Act of Terrorism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SoundWaveProcess(MechanicalWaveProcess, RDFEntity):
    """
    Sound Wave Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000675"
    _name: ClassVar[str] = "Sound Wave Process"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[LongitudinalWaveProfile, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfTrainingAcquisition(ActOfTraining, RDFEntity):
    """
    Act of Training Acquisition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000687"
    _name: ClassVar[str] = "Act of Training Acquisition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfSojourn(ActOfInhabitancy, RDFEntity):
    """
    Act of Sojourn
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000739"
    _name: ClassVar[str] = "Act of Sojourn"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CurvilinearMotion(TranslationalMotion, RDFEntity):
    """
    Curvilinear Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000773"
    _name: ClassVar[str] = "Curvilinear Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[Annotated[List[Union[URIRef, Velocity, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ElectromagneticPulse(ElectromagneticWaveProcess, RDFEntity):
    """
    Electromagnetic Pulse
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000812"
    _name: ClassVar[str] = "Electromagnetic Pulse"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[TransverseWaveProfile, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class StasisOfFunction(StasisOfRealizableEntity, RDFEntity):
    """
    Stasis of Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000820"
    _name: ClassVar[str] = "Stasis of Function"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfRole(StasisOfRealizableEntity, RDFEntity):
    """
    Stasis of Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000824"
    _name: ClassVar[str] = "Stasis of Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfFinancialInstrumentUse(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Financial Instrument Use
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000836"
    _name: ClassVar[str] = "Act of Financial Instrument Use"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DecreaseOfRealizableEntity(DecreaseOfSpecificallyDependentContinuant, RDFEntity):
    """
    Decrease of Realizable Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000854"
    _name: ClassVar[str] = "Decrease of Realizable Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPersonalCommunication(ActOfCommunication, RDFEntity):
    """
    Act of Personal Communication
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000875"
    _name: ClassVar[str] = "Act of Personal Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VisibleObservation(ActOfObservation, RDFEntity):
    """
    Visible Observation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000889"
    _name: ClassVar[str] = "Visible Observation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[List[Union[URIRef, VisibleLightReflectionProcess, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfFacilityUse(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Facility Use
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000902"
    _name: ClassVar[str] = "Act of Facility Use"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfLegalInstrumentUse(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Legal Instrument Use
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000935"
    _name: ClassVar[str] = "Act of Legal Instrument Use"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfArtifactModification(ActOfArtifactProcessing, RDFEntity):
    """
    Excluded from this class are instances of role change or role creation such as the introduction of an artifact as a piece of evidence in a trial or the loading of artifacts onto a ship for transport.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000970"
    _name: ClassVar[str] = "Act of Artifact Modification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDeceptiveCommunication(ActOfCommunication, RDFEntity):
    """
    Act of Deceptive Communication
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000971"
    _name: ClassVar[str] = "Act of Deceptive Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPortionOfMaterialConsumption(ActOfArtifactEmployment, RDFEntity):
    """
    Act of Portion of Material Consumption
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000981"
    _name: ClassVar[str] = "Act of Portion of Material Consumption"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ShearWaveProcess(MechanicalWaveProcess, RDFEntity):
    """
    Shear Wave Process
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000983"
    _name: ClassVar[str] = "Shear Wave Process"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[URIRef, WaveProcessProfile, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class VisibleLightFrequency(ElectromagneticRadiationFrequency, RDFEntity):
    """
    Visible light overlaps with near infrared and near ultraviolet.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001056"
    _name: ClassVar[str] = "Visible Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfQuality(GainOfSpecificallyDependentContinuant, RDFEntity):
    """
    Gain of Quality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001068"
    _name: ClassVar[str] = "Gain of Quality"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000057"}

    # Data properties
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
    bFO_0000057: Optional[Annotated[List[Union[BFO_0000019, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ActOfTrainingInstruction(ActOfTraining, RDFEntity):
    """
    Act of Training Instruction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001075"
    _name: ClassVar[str] = "Act of Training Instruction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfEspionage(ActOfIntelligenceGathering, RDFEntity):
    """
    Act of Espionage
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001094"
    _name: ClassVar[str] = "Act of Espionage"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CounterClockwiseRotationalMotion(RotationalMotion, RDFEntity):
    """
    Counter-Clockwise Rotational Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001109"
    _name: ClassVar[str] = "Counter-Clockwise Rotational Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[List[Union[AngularVelocity, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LossOfQuality(LossOfSpecificallyDependentContinuant, RDFEntity):
    """
    Loss of Quality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001127"
    _name: ClassVar[str] = "Loss of Quality"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfResiding(ActOfInhabitancy, RDFEntity):
    """
    Act of Residing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001128"
    _name: ClassVar[str] = "Act of Residing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfMissionCapability(StasisOfRealizableEntity, RDFEntity):
    """
    Stasis of Mission Capability
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001132"
    _name: ClassVar[str] = "Stasis of Mission Capability"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UltrasonicFrequency(SoundFrequency, RDFEntity):
    """
    Ultrasonic Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001136"
    _name: ClassVar[str] = "Ultrasonic Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDataTransformation(ActOfInformationProcessing, RDFEntity):
    """
    Act of Data Transformation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001158"
    _name: ClassVar[str] = "Act of Data Transformation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCommissiveCommunication(ActOfCommunication, RDFEntity):
    """
    Examples: agreeing, betting, guaranteeing, inviting, offering, promising, swearing, volunteering
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001162"
    _name: ClassVar[str] = "Act of Commissive Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SpinningMotion(RotationalMotion, RDFEntity):
    """
    Spinning Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001184"
    _name: ClassVar[str] = "Spinning Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[List[Union[AngularVelocity, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfArtifactAssembly(ActOfArtifactProcessing, RDFEntity):
    """
    Many Acts of Manufacturing and Construction involve one or more Acts of Artifact Assembly, but Acts of Artifact Assembly can also occur in isolation from these activities.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001196"
    _name: ClassVar[str] = "Act of Artifact Assembly"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfArtifactOperationality(StasisOfRealizableEntity, RDFEntity):
    """
    Stasis of Artifact Operationality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001213"
    _name: ClassVar[str] = "Stasis of Artifact Operationality"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfSuicide(ActOfViolence, RDFEntity):
    """
    Act of Suicide
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001236"
    _name: ClassVar[str] = "Act of Suicide"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001803": "https://www.commoncoreontologies.org/ont00001803",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001803"}

    # Data properties
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
    ont00001803: Optional[Annotated[List[Union[Death, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class InfrasonicFrequency(SoundFrequency, RDFEntity):
    """
    Infrasonic Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001274"
    _name: ClassVar[str] = "Infrasonic Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RevolvingMotion(RotationalMotion, RDFEntity):
    """
    Revolving Motion
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001285"
    _name: ClassVar[str] = "Revolving Motion"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[List[Union[AngularVelocity, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfOwnership(ActOfPossession, RDFEntity):
    """
    The relation between the owner and property may be private, collective, or common and the property may be objects, land, real estate, or intellectual property.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001336"
    _name: ClassVar[str] = "Act of Ownership"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InfraredLightFrequency(ElectromagneticRadiationFrequency, RDFEntity):
    """
    Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001337"
    _name: ClassVar[str] = "Infrared Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfManufacturing(ActOfArtifactProcessing, RDFEntity):
    """
    An Act of Manufacturing typically involves the mass production of goods.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001359"
    _name: ClassVar[str] = "Act of Manufacturing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDeclarativeCommunication(ActOfCommunication, RDFEntity):
    """
    Examples: Baptism, Sentencing a person to imprisonment, Pronouncing a couple husband and wife, Declaring war
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001374"
    _name: ClassVar[str] = "Act of Declarative Communication"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UpperMidrangeFrequency(SonicFrequency, RDFEntity):
    """
    Upper Midrange Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000006"
    _name: ClassVar[str] = "Upper Midrange Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfAdvising(ActOfDirectiveCommunication, RDFEntity):
    """
    Act of Advising
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000024"
    _name: ClassVar[str] = "Act of Advising"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Mailing(ActOfCommunicationByMedia, RDFEntity):
    """
    Mailing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000027"
    _name: ClassVar[str] = "Mailing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DecreaseOfRole(DecreaseOfRealizableEntity, RDFEntity):
    """
    Decrease of Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000033"
    _name: ClassVar[str] = "Decrease of Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SoftXrayFrequency(XrayFrequency, RDFEntity):
    """
    Soft X-ray Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000035"
    _name: ClassVar[str] = "Soft X-ray Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfPartiallyMissionCapable(StasisOfMissionCapability, RDFEntity):
    """
    Stasis of Partially Mission Capable
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000100"
    _name: ClassVar[str] = "Stasis of Partially Mission Capable"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EndOfLifeStasis(StasisOfArtifactOperationality, RDFEntity):
    """
    An End of Life Stasis (EoL) is distinguished from a Stasis of Partially Mission Capable or Stasis of Non-Mission Capable in that EoL is more inclusive such that the participating Artifact may be either Partially or Non-Mission Capable. Additionally, EoL applies only to Artifacts and is typically determined in relation to its original mission and designed primary functions. In contrast, an Artifact's level of Mission Capability depends on the requirements of the mission under consideration such that a given Artifact may simultaneously be Fully Mission Capable for mission1, Partially Mission Capable for mission2, and Non-Mission Capable for mission3.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000106"
    _name: ClassVar[str] = "End of Life Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfConductingMassMediaInterview(ActOfMassMediaCommunication, RDFEntity):
    """
    Act of Conducting Mass Media Interview
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000121"
    _name: ClassVar[str] = "Act of Conducting Mass Media Interview"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfFinancialDeposit(ActOfFinancialInstrumentUse, RDFEntity):
    """
    Act of Financial Deposit
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000137"
    _name: ClassVar[str] = "Act of Financial Deposit"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMeeting(ActOfAssociation, RDFEntity):
    """
    Act of Meeting
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000144"
    _name: ClassVar[str] = "Act of Meeting"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InstantMessaging(ActOfCommunicationByMedia, RDFEntity):
    """
    Instant Messaging
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000149"
    _name: ClassVar[str] = "Instant Messaging"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfReporting(ActOfRepresentativeCommunication, RDFEntity):
    """
    Act of Reporting
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000151"
    _name: ClassVar[str] = "Act of Reporting"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NearInfraredLightFrequency(InfraredLightFrequency, RDFEntity):
    """
    Near Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000155"
    _name: ClassVar[str] = "Near Infrared Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfInterpersonalRelationship(ActOfAssociation, RDFEntity):
    """
    Act of Interpersonal Relationship
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000168"
    _name: ClassVar[str] = "Act of Interpersonal Relationship"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VeryHighFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 10–1 m
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000169"
    _name: ClassVar[str] = "Very High Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfThanking(ActOfExpressiveCommunication, RDFEntity):
    """
    Act of Thanking
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000182"
    _name: ClassVar[str] = "Act of Thanking"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfChangeOfResidence(ActOfLocationChange, RDFEntity):
    """
    Act of Change of Residence
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000201"
    _name: ClassVar[str] = "Act of Change of Residence"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfTerroristTrainingInstruction(ActOfTrainingInstruction, RDFEntity):
    """
    Act of Terrorist Training Instruction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000202"
    _name: ClassVar[str] = "Act of Terrorist Training Instruction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCongratulating(ActOfExpressiveCommunication, RDFEntity):
    """
    Act of Congratulating
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000208"
    _name: ClassVar[str] = "Act of Congratulating"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PresenceFrequency(SonicFrequency, RDFEntity):
    """
    Presence Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000222"
    _name: ClassVar[str] = "Presence Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfVocationalTrainingAcquisition(ActOfTrainingAcquisition, RDFEntity):
    """
    Act of Vocational Training Acquisition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000235"
    _name: ClassVar[str] = "Act of Vocational Training Acquisition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfTerroristTrainingAcquisition(ActOfTrainingAcquisition, RDFEntity):
    """
    Act of Terrorist Training Acquisition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000237"
    _name: ClassVar[str] = "Act of Terrorist Training Acquisition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfOathTaking(ActOfCommissiveCommunication, RDFEntity):
    """
    Act of Oath Taking
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000240"
    _name: ClassVar[str] = "Act of Oath Taking"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MuzzleBlast(SoundWaveProcess, RDFEntity):
    """
    Muzzle Blast
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000260"
    _name: ClassVar[str] = "Muzzle Blast"
    _property_uris: ClassVar[dict] = {
        "bFO_0000062": "http://purl.obolibrary.org/obo/BFO_0000062",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000062", "ont00001777"}

    # Data properties
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
    bFO_0000062: Optional[
        Annotated[List[Union[URIRef, WaveProduction, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    ont00001777: Optional[
        Annotated[List[Union[LongitudinalWaveProfile, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ActOfFunding(ActOfFinancialInstrumentUse, RDFEntity):
    """
    Act of Funding
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000322"
    _name: ClassVar[str] = "Act of Funding"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCommanding(ActOfDirectiveCommunication, RDFEntity):
    """
    Act of Commanding
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000351"
    _name: ClassVar[str] = "Act of Commanding"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfTestifying(ActOfRepresentativeCommunication, RDFEntity):
    """
    Act of Testifying
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000354"
    _name: ClassVar[str] = "Act of Testifying"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPublishingMassMediaArticle(ActOfMassMediaCommunication, RDFEntity):
    """
    Act of Publishing Mass Media Article
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000356"
    _name: ClassVar[str] = "Act of Publishing Mass Media Article"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMilitaryTrainingInstruction(ActOfTrainingInstruction, RDFEntity):
    """
    Act of Military Training Instruction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000367"
    _name: ClassVar[str] = "Act of Military Training Instruction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCondoling(ActOfExpressiveCommunication, RDFEntity):
    """
    Act of Condoling
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000370"
    _name: ClassVar[str] = "Act of Condoling"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Webcast(ActOfCommunicationByMedia, RDFEntity):
    """
    Essentially, webcasting is “broadcasting” over the Internet.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000386"
    _name: ClassVar[str] = "Webcast"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ExtremelyLowFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 100,000–10,000 km
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000396"
    _name: ClassVar[str] = "Extremely Low Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPublishingMassMediaPressRelease(ActOfMassMediaCommunication, RDFEntity):
    """
    Act of Publishing Mass Media Press Release
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000416"
    _name: ClassVar[str] = "Act of Publishing Mass Media Press Release"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfOfficialDocumentation(ActOfDeclarativeCommunication, RDFEntity):
    """
    Act of Official Documentation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000438"
    _name: ClassVar[str] = "Act of Official Documentation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfEducationalTrainingInstruction(ActOfTrainingInstruction, RDFEntity):
    """
    Act of Educational Training Instruction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000463"
    _name: ClassVar[str] = "Act of Educational Training Instruction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EmailMessaging(ActOfCommunicationByMedia, RDFEntity):
    """
    Email Messaging
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000492"
    _name: ClassVar[str] = "Email Messaging"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfFinancialWithdrawal(ActOfFinancialInstrumentUse, RDFEntity):
    """
    Act of Financial Withdrawal
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000501"
    _name: ClassVar[str] = "Act of Financial Withdrawal"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class NearUltravioletLightFrequency(UltravioletLightFrequency, RDFEntity):
    """
    Near Ultraviolet Light Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000508"
    _name: ClassVar[str] = "Near Ultraviolet Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDeparture(ActOfLocationChange, RDFEntity):
    """
    Act of Departure
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000520"
    _name: ClassVar[str] = "Act of Departure"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DecreaseOfDisposition(DecreaseOfRealizableEntity, RDFEntity):
    """
    Decrease of Disposition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000543"
    _name: ClassVar[str] = "Decrease of Disposition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfNonMissionCapable(StasisOfMissionCapability, RDFEntity):
    """
    Stasis of Non-Mission Capable
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000557"
    _name: ClassVar[str] = "Stasis of Non-Mission Capable"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfReligiousTrainingAcquisition(ActOfTrainingAcquisition, RDFEntity):
    """
    Act of Religious Training Acquisition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000573"
    _name: ClassVar[str] = "Act of Religious Training Acquisition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCargoTransportation(ActOfLocationChange, RDFEntity):
    """
    Act of Cargo Transportation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000595"
    _name: ClassVar[str] = "Act of Cargo Transportation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfDisposition(GainOfRealizableEntity, RDFEntity):
    """
    This class should be used to demarcate the start of the temporal interval (through the BFO 'occupies temporal region' property) that the Entity bears the Disposition.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000609"
    _name: ClassVar[str] = "Gain of Disposition"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000057"}

    # Data properties
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
    bFO_0000057: Optional[Annotated[List[Union[BFO_0000016, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class LossOfRole(LossOfRealizableEntity, RDFEntity):
    """
    Loss of Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000613"
    _name: ClassVar[str] = "Loss of Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfEncounter(ActOfAssociation, RDFEntity):
    """
    Act of Encounter
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000615"
    _name: ClassVar[str] = "Act of Encounter"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfFullyMissionCapable(StasisOfMissionCapability, RDFEntity):
    """
    Stasis of Fully Mission Capable
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000622"
    _name: ClassVar[str] = "Stasis of Fully Mission Capable"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LowFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 10–1 km
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000643"
    _name: ClassVar[str] = "Low Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SuperLowFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 10,000–1,000 km
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000672"
    _name: ClassVar[str] = "Super Low Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Wedding(ActOfCeremony, RDFEntity):
    """
    Wedding
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000725"
    _name: ClassVar[str] = "Wedding"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MicrowaveFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 1,000–1 mm
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000732"
    _name: ClassVar[str] = "Microwave Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfSocialGroupMembership(ActOfAssociation, RDFEntity):
    """
    Act of Social Group Membership
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000744"
    _name: ClassVar[str] = "Act of Social Group Membership"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TextMessaging(ActOfCommunicationByMedia, RDFEntity):
    """
    Text Messaging
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000750"
    _name: ClassVar[str] = "Text Messaging"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UltraLowFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 1,000–100 km
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000753"
    _name: ClassVar[str] = "Ultra Low Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfRequesting(ActOfDirectiveCommunication, RDFEntity):
    """
    Act of Requesting
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000769"
    _name: ClassVar[str] = "Act of Requesting"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfRole(IncreaseOfRealizableEntity, RDFEntity):
    """
    Increase of Role
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000786"
    _name: ClassVar[str] = "Increase of Role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPromising(ActOfCommissiveCommunication, RDFEntity):
    """
    Act of Promising
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000821"
    _name: ClassVar[str] = "Act of Promising"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class VeryLowFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 100–10 km
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000822"
    _name: ClassVar[str] = "Very Low Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MidInfraredLightFrequency(InfraredLightFrequency, RDFEntity):
    """
    Mid Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000834"
    _name: ClassVar[str] = "Mid Infrared Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDonating(ActOfFinancialInstrumentUse, RDFEntity):
    """
    Act of Donating
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000839"
    _name: ClassVar[str] = "Act of Donating"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SubBassFrequency(SonicFrequency, RDFEntity):
    """
    Sub-Bass Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000842"
    _name: ClassVar[str] = "Sub-Bass Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActiveStasis(StasisOfArtifactOperationality, RDFEntity):
    """
    Active Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000847"
    _name: ClassVar[str] = "Active Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelevisionBroadcast(ActOfCommunicationByMedia, RDFEntity):
    """
    Television Broadcast
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000859"
    _name: ClassVar[str] = "Television Broadcast"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfConfessing(ActOfRepresentativeCommunication, RDFEntity):
    """
    Act of Confessing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000863"
    _name: ClassVar[str] = "Act of Confessing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RadioBroadcast(ActOfCommunicationByMedia, RDFEntity):
    """
    Radio Broadcast
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000866"
    _name: ClassVar[str] = "Radio Broadcast"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfReligiousGroupAffiliation(ActOfAssociation, RDFEntity):
    """
    Act of Religious Group Affiliation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000879"
    _name: ClassVar[str] = "Act of Religious Group Affiliation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfInviting(ActOfCommissiveCommunication, RDFEntity):
    """
    Act of Inviting
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000883"
    _name: ClassVar[str] = "Act of Inviting"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfLoaning(ActOfFinancialInstrumentUse, RDFEntity):
    """
    Act of Loaning
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000884"
    _name: ClassVar[str] = "Act of Loaning"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfTravel(ActOfLocationChange, RDFEntity):
    """
    Act of Travel
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000890"
    _name: ClassVar[str] = "Act of Travel"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfArrival(ActOfLocationChange, RDFEntity):
    """
    Act of Arrival
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000922"
    _name: ClassVar[str] = "Act of Arrival"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMilitaryTrainingAcquisition(ActOfTrainingAcquisition, RDFEntity):
    """
    Act of Military Training Acquisition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000925"
    _name: ClassVar[str] = "Act of Military Training Acquisition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfApologizing(ActOfExpressiveCommunication, RDFEntity):
    """
    Act of Apologizing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000926"
    _name: ClassVar[str] = "Act of Apologizing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BassFrequency(SonicFrequency, RDFEntity):
    """
    Bass Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000927"
    _name: ClassVar[str] = "Bass Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DeactivatedStasis(StasisOfArtifactOperationality, RDFEntity):
    """
    Deactivated Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000936"
    _name: ClassVar[str] = "Deactivated Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfReligiousWorship(ActOfCeremony, RDFEntity):
    """
    Act of Religious Worship
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000948"
    _name: ClassVar[str] = "Act of Religious Worship"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMaintenance(ActOfArtifactModification, RDFEntity):
    """
    Act of Maintenance
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000950"
    _name: ClassVar[str] = "Act of Maintenance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MediumFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 1,000–100 m
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000964"
    _name: ClassVar[str] = "Medium Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPublishingMassMediaDocumentary(ActOfMassMediaCommunication, RDFEntity):
    """
    Act of Publishing Mass Media Documentary
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000977"
    _name: ClassVar[str] = "Act of Publishing Mass Media Documentary"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DefunctStasis(StasisOfArtifactOperationality, RDFEntity):
    """
    Defunct Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000999"
    _name: ClassVar[str] = "Defunct Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfDenying(ActOfRepresentativeCommunication, RDFEntity):
    """
    Act of Denying
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001021"
    _name: ClassVar[str] = "Act of Denying"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfVolunteering(ActOfCommissiveCommunication, RDFEntity):
    """
    Act of Volunteering
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001031"
    _name: ClassVar[str] = "Act of Volunteering"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfAssignment(ActOfDeclarativeCommunication, RDFEntity):
    """
    Act of Assignment
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001032"
    _name: ClassVar[str] = "Act of Assignment"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfRepayment(ActOfFinancialInstrumentUse, RDFEntity):
    """
    Act of Repayment
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001039"
    _name: ClassVar[str] = "Act of Repayment"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfCollision(ActOfLocationChange, RDFEntity):
    """
    Act of Collision
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001053"
    _name: ClassVar[str] = "Act of Collision"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfIssuingMassMediaPressRelease(ActOfMassMediaCommunication, RDFEntity):
    """
    Act of Issuing Mass Media Press Release
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001057"
    _name: ClassVar[str] = "Act of Issuing Mass Media Press Release"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LossOfDisposition(LossOfRealizableEntity, RDFEntity):
    """
    Loss of Disposition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001066"
    _name: ClassVar[str] = "Loss of Disposition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfEducationalTrainingAcquisition(ActOfTrainingAcquisition, RDFEntity):
    """
    Act of Educational Training Acquisition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001074"
    _name: ClassVar[str] = "Act of Educational Training Acquisition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FarInfraredLightFrequency(InfraredLightFrequency, RDFEntity):
    """
    Far Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001080"
    _name: ClassVar[str] = "Far Infrared Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LowMidrangeFrequency(SonicFrequency, RDFEntity):
    """
    Low Midrange Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001111"
    _name: ClassVar[str] = "Low Midrange Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfReligiousTrainingInstruction(ActOfTrainingInstruction, RDFEntity):
    """
    Act of Religious Training Instruction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001120"
    _name: ClassVar[str] = "Act of Religious Training Instruction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FacsimileTransmission(ActOfCommunicationByMedia, RDFEntity):
    """
    Facsimile Transmission
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001143"
    _name: ClassVar[str] = "Facsimile Transmission"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MidrangeFrequency(SonicFrequency, RDFEntity):
    """
    Midrange Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001167"
    _name: ClassVar[str] = "Midrange Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HardXrayFrequency(XrayFrequency, RDFEntity):
    """
    Hard X-ray Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001170"
    _name: ClassVar[str] = "Hard X-ray Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class TelephoneCall(ActOfCommunicationByMedia, RDFEntity):
    """
    Telephone Call
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001190"
    _name: ClassVar[str] = "Telephone Call"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class OperationalStasis(StasisOfArtifactOperationality, RDFEntity):
    """
    Operational Stasis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001191"
    _name: ClassVar[str] = "Operational Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfRole(GainOfRealizableEntity, RDFEntity):
    """
    This class should be used to demarcate the start of the temporal interval (through the occurs_on property) that the Entity bears the Role.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001194"
    _name: ClassVar[str] = "Gain of Role"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000057"}

    # Data properties
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
    bFO_0000057: Optional[Annotated[List[Union[BFO_0000023, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class HighFrequency(RadioFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 100–10 m
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001208"
    _name: ClassVar[str] = "High Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Funeral(ActOfCeremony, RDFEntity):
    """
    Funeral
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001215"
    _name: ClassVar[str] = "Funeral"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfEmployment(ActOfAssociation, RDFEntity):
    """
    Act of Employment
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001226"
    _name: ClassVar[str] = "Act of Employment"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BrillianceFrequency(SonicFrequency, RDFEntity):
    """
    Brilliance Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001231"
    _name: ClassVar[str] = "Brilliance Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfIssuingMassMediaArticle(ActOfMassMediaCommunication, RDFEntity):
    """
    Act of Issuing Mass Media Article
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001244"
    _name: ClassVar[str] = "Act of Issuing Mass Media Article"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfIdentifying(ActOfRepresentativeCommunication, RDFEntity):
    """
    Act of Identifying
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001261"
    _name: ClassVar[str] = "Act of Identifying"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfIssuingMassMediaDocumentary(ActOfMassMediaCommunication, RDFEntity):
    """
    Act of Issuing Mass Media Documentary
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001263"
    _name: ClassVar[str] = "Act of Issuing Mass Media Documentary"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfVocationalTrainingInstruction(ActOfTrainingInstruction, RDFEntity):
    """
    Act of Vocational Training Instruction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001266"
    _name: ClassVar[str] = "Act of Vocational Training Instruction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPropaganda(ActOfDeceptiveCommunication, RDFEntity):
    """
    Act of Propaganda
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001267"
    _name: ClassVar[str] = "Act of Propaganda"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfWarning(ActOfDirectiveCommunication, RDFEntity):
    """
    Act of Warning
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001269"
    _name: ClassVar[str] = "Act of Warning"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMurder(ActOfHomicide, RDFEntity):
    """
    Act of Murder
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001272"
    _name: ClassVar[str] = "Act of Murder"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001803": "https://www.commoncoreontologies.org/ont00001803",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001803"}

    # Data properties
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
    ont00001803: Optional[Annotated[List[Union[Death, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ExtremeUltravioletLightFrequency(UltravioletLightFrequency, RDFEntity):
    """
    Extreme Ultraviolet Light Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001332"
    _name: ClassVar[str] = "Extreme Ultraviolet Light Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPurchasing(ActOfFinancialInstrumentUse, RDFEntity):
    """
    Act of Purchasing
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001334"
    _name: ClassVar[str] = "Act of Purchasing"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfDisposition(IncreaseOfRealizableEntity, RDFEntity):
    """
    Increase of Disposition
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001356"
    _name: ClassVar[str] = "Increase of Disposition"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfPilgrimage(ActOfTravel, RDFEntity):
    """
    Act of Pilgrimage
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000200"
    _name: ClassVar[str] = "Act of Pilgrimage"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfPartiallyMissionCapableMaintenance(
    StasisOfPartiallyMissionCapable, RDFEntity
):
    """
    Stasis of Partially Mission Capable Maintenance
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000286"
    _name: ClassVar[str] = "Stasis of Partially Mission Capable Maintenance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfMilitaryService(ActOfEmployment, RDFEntity):
    """
    Act of Military Service
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000308"
    _name: ClassVar[str] = "Act of Military Service"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class IncreaseOfFunction(IncreaseOfDisposition, RDFEntity):
    """
    Increase of Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000361"
    _name: ClassVar[str] = "Increase of Function"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfBuying(ActOfPurchasing, RDFEntity):
    """
    Act of Buying
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000389"
    _name: ClassVar[str] = "Act of Buying"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfRemuneration(ActOfPurchasing, RDFEntity):
    """
    Comment: Remuneration normally consists of salary or hourly wages, but also applies to commission, stock options, fringe benefits, etc.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000449"
    _name: ClassVar[str] = "Act of Remuneration"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GainOfFunction(GainOfDisposition, RDFEntity):
    """
    This class should be used to demarcate the start of the temporal interval (through the BFO 'occupies temporal region' property) that the Entity bears the Function.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000462"
    _name: ClassVar[str] = "Gain of Function"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000057"}

    # Data properties
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
    bFO_0000057: Optional[Annotated[List[Union[BFO_0000034, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ExtremelyHighFrequency(MicrowaveFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 10–1 mm
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000519"
    _name: ClassVar[str] = "Extremely High Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfAssassination(ActOfMurder, RDFEntity):
    """
    Act of Assassination
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000521"
    _name: ClassVar[str] = "Act of Assassination"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001803": "https://www.commoncoreontologies.org/ont00001803",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001803"}

    # Data properties
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
    ont00001803: Optional[Annotated[List[Union[Death, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ActOfContractFormation(ActOfPromising, RDFEntity):
    """
    Act of Contract Formation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000684"
    _name: ClassVar[str] = "Act of Contract Formation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class StasisOfNonMissionCapableMaintenance(StasisOfNonMissionCapable, RDFEntity):
    """
    Stasis of Non-Mission Capable Maintenance
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000783"
    _name: ClassVar[str] = "Stasis of Non-Mission Capable Maintenance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001819": "https://www.commoncoreontologies.org/ont00001819",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001819"}

    # Data properties
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
    ont00001819: Optional[
        Annotated[List[Union[ActOfMaintenance, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class BeginningOfLifeStasis(OperationalStasis, RDFEntity):
    """
    A Beginning of Life Stasis (BoL) is a relatively brief Operational Stasis that is primarily of interest for the purpose of establishing a baseline for operational parameters to be compared to the designed specifications as well as the Artifact's performance throughout its operational life.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000924"
    _name: ClassVar[str] = "Beginning of Life Stasis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FixedLineNetworkTelephoneCall(TelephoneCall, RDFEntity):
    """
    Fixed Line Network Telephone Call
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000960"
    _name: ClassVar[str] = "Fixed Line Network Telephone Call"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class DecreaseOfFunction(DecreaseOfDisposition, RDFEntity):
    """
    Decrease of Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000982"
    _name: ClassVar[str] = "Decrease of Function"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SuperHighFrequency(MicrowaveFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 100–10 mm
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000989"
    _name: ClassVar[str] = "Super High Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class FMRadioBroadcastFrequency(VeryHighFrequency, RDFEntity):
    """
    FM Radio Broadcast Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001072"
    _name: ClassVar[str] = "FM Radio Broadcast Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UltraHighFrequency(MicrowaveFrequency, RDFEntity):
    """
    The corresponding Wavelength range is 1–0.1 m.

    Note that the ITU definition of UHF is broader than the definition given by IEEE 521-2002 - IEEE Standard Letter Designations for Radar-Frequency Bands, which sets the frequency range at 300 MHz to 1 GHz.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001108"
    _name: ClassVar[str] = "Ultra High Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PrivateNetworkTelephoneCall(TelephoneCall, RDFEntity):
    """
    Private Network Telephone Call
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001115"
    _name: ClassVar[str] = "Private Network Telephone Call"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class WirelessNetworkTelephoneCall(TelephoneCall, RDFEntity):
    """
    Wireless Network Telephone Call
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001171"
    _name: ClassVar[str] = "Wireless Network Telephone Call"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class UnderActiveControl(ActiveStasis, RDFEntity):
    """
    Under Active Control
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001246"
    _name: ClassVar[str] = "Under Active Control"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "ont00001777": "https://www.commoncoreontologies.org/ont00001777",
    }
    _object_properties: ClassVar[set[str]] = {"ont00001777"}

    # Data properties
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
    ont00001777: Optional[
        Annotated[List[Union[ActOfArtifactEmployment, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LossOfFunction(LossOfDisposition, RDFEntity):
    """
    Loss of Function
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001305"
    _name: ClassVar[str] = "Loss of Function"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfRenting(ActOfPurchasing, RDFEntity):
    """
    Act of Renting
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001325"
    _name: ClassVar[str] = "Act of Renting"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ActOfWalking(ActOfTravel, RDFEntity):
    """
    Act of Walking
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001339"
    _name: ClassVar[str] = "Act of Walking"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
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
ProcessProfile.model_rebuild()
Change.model_rebuild()
Act.model_rebuild()
NaturalProcess.model_rebuild()
ProcessEnding.model_rebuild()
MechanicalProcess.model_rebuild()
ProcessBeginning.model_rebuild()
Target.model_rebuild()
Effect.model_rebuild()
Stasis.model_rebuild()
Cause.model_rebuild()
WaveProcess.model_rebuild()
StasisOfSpecificallyDependentContinuant.model_rebuild()
PlannedAct.model_rebuild()
Combustion.model_rebuild()
Momentum.model_rebuild()
PropulsionProcess.model_rebuild()
StasisOfGenericallyDependentContinuant.model_rebuild()
BiographicalLife.model_rebuild()
Power.model_rebuild()
UnplannedAct.model_rebuild()
GainOfDependentContinuant.model_rebuild()
Force.model_rebuild()
IgnitionProcess.model_rebuild()
OscillationProcess.model_rebuild()
Acceleration.model_rebuild()
DecreaseOfDependentContinuant.model_rebuild()
WaveProcessProfile.model_rebuild()
Velocity.model_rebuild()
WaveProduction.model_rebuild()
ImpulsiveForce.model_rebuild()
Speed.model_rebuild()
EffectOfLocationChange.model_rebuild()
SoundProcessProfile.model_rebuild()
LossOfDependentContinuant.model_rebuild()
Amplitude.model_rebuild()
Death.model_rebuild()
Frequency.model_rebuild()
IncreaseOfDependentContinuant.model_rebuild()
RadioInterference.model_rebuild()
Motion.model_rebuild()
Deltav.model_rebuild()
Birth.model_rebuild()
TelemetryProcess.model_rebuild()
Behavior.model_rebuild()
SoundFrequency.model_rebuild()
NominalStasis.model_rebuild()
GainOfGenericallyDependentContinuant.model_rebuild()
ActOfObservation.model_rebuild()
IncreaseOfGenericallyDependentContinuant.model_rebuild()
ActOfMilitaryForce.model_rebuild()
MaximumPower.model_rebuild()
ActOfGovernment.model_rebuild()
CriminalAct.model_rebuild()
WaveCycle.model_rebuild()
Thrust.model_rebuild()
ActOfTraining.model_rebuild()
StasisOfRealizableEntity.model_rebuild()
DecreaseOfSpecificallyDependentContinuant.model_rebuild()
AngularVelocity.model_rebuild()
Wavelength.model_rebuild()
ActOfMeasuring.model_rebuild()
ActOfMotion.model_rebuild()
ActOfInformationProcessing.model_rebuild()
RotationalMotion.model_rebuild()
ActOfPrediction.model_rebuild()
Pressure.model_rebuild()
GainOfSpecificallyDependentContinuant.model_rebuild()
ActOfCommunication.model_rebuild()
ActOfPlanning.model_rebuild()
TransverseWaveProfile.model_rebuild()
Loudness.model_rebuild()
LossOfGenericallyDependentContinuant.model_rebuild()
EnhancedStasis.model_rebuild()
VisibleLightReflectionProcess.model_rebuild()
ActOfArtifactEmployment.model_rebuild()
SoundProduction.model_rebuild()
ActOfInhabitancy.model_rebuild()
ActOfTargeting.model_rebuild()
ElectromagneticRadiationFrequency.model_rebuild()
SurfaceWaveProfile.model_rebuild()
TranslationalMotion.model_rebuild()
StasisOfQuality.model_rebuild()
LossOfSpecificallyDependentContinuant.model_rebuild()
Married.model_rebuild()
ActOfArtifactProcessing.model_rebuild()
ActOfConsumption.model_rebuild()
ElectromagneticWaveProcess.model_rebuild()
Pitch.model_rebuild()
AngularMomentum.model_rebuild()
MechanicalWaveProcess.model_rebuild()
ProperAcceleration.model_rebuild()
ActOfEntertainment.model_rebuild()
ActOfViolence.model_rebuild()
IncreaseOfSpecificallyDependentContinuant.model_rebuild()
LongitudinalWaveProfile.model_rebuild()
ActOfPossession.model_rebuild()
ActOfIntelligenceGathering.model_rebuild()
VibrationMotion.model_rebuild()
Waveform.model_rebuild()
DamagedStasis.model_rebuild()
LegalSystemAct.model_rebuild()
DecreaseOfGenericallyDependentContinuant.model_rebuild()
SocialAct.model_rebuild()
Timbre.model_rebuild()
Torque.model_rebuild()
TriangularWaveform.model_rebuild()
ActOfConstruction.model_rebuild()
ActOfLocationChange.model_rebuild()
ActOfEstimation.model_rebuild()
ActOfSocialMovement.model_rebuild()
StasisOfDisposition.model_rebuild()
ActOfExpressiveCommunication.model_rebuild()
IncreaseOfQuality.model_rebuild()
ActOfDirectiveCommunication.model_rebuild()
ClockwiseRotationalMotion.model_rebuild()
RadioFrequency.model_rebuild()
ActOfHomicide.model_rebuild()
SoundWavelength.model_rebuild()
LossOfRealizableEntity.model_rebuild()
GammaRayFrequency.model_rebuild()
Election.model_rebuild()
ActOfDecoyUse.model_rebuild()
SoundPressure.model_rebuild()
ActOfReconnaissance.model_rebuild()
WoundedStasis.model_rebuild()
ActOfRepresentativeCommunication.model_rebuild()
RectilinearMotion.model_rebuild()
TremendouslyHighFrequency.model_rebuild()
FundamentalFrequency.model_rebuild()
SquareWaveform.model_rebuild()
StableOrientation.model_rebuild()
ActOfAssociation.model_rebuild()
ActOfCeremony.model_rebuild()
XrayFrequency.model_rebuild()
ActOfToolUse.model_rebuild()
ActOfVehicleUse.model_rebuild()
ActOfCommunicationByMedia.model_rebuild()
SonicFrequency.model_rebuild()
DecreaseOfQuality.model_rebuild()
SineWaveform.model_rebuild()
ActOfPositionChange.model_rebuild()
SawtoothWaveform.model_rebuild()
ActOfMassMediaCommunication.model_rebuild()
UltravioletLightFrequency.model_rebuild()
IncreaseOfRealizableEntity.model_rebuild()
ActOfWeaponUse.model_rebuild()
InverseSawtoothWaveform.model_rebuild()
ActOfAppraisal.model_rebuild()
GainOfRealizableEntity.model_rebuild()
ActOfTerrorism.model_rebuild()
SoundWaveProcess.model_rebuild()
ActOfTrainingAcquisition.model_rebuild()
ActOfSojourn.model_rebuild()
CurvilinearMotion.model_rebuild()
ElectromagneticPulse.model_rebuild()
StasisOfFunction.model_rebuild()
StasisOfRole.model_rebuild()
ActOfFinancialInstrumentUse.model_rebuild()
DecreaseOfRealizableEntity.model_rebuild()
ActOfPersonalCommunication.model_rebuild()
VisibleObservation.model_rebuild()
ActOfFacilityUse.model_rebuild()
ActOfLegalInstrumentUse.model_rebuild()
ActOfArtifactModification.model_rebuild()
ActOfDeceptiveCommunication.model_rebuild()
ActOfPortionOfMaterialConsumption.model_rebuild()
ShearWaveProcess.model_rebuild()
VisibleLightFrequency.model_rebuild()
GainOfQuality.model_rebuild()
ActOfTrainingInstruction.model_rebuild()
ActOfEspionage.model_rebuild()
CounterClockwiseRotationalMotion.model_rebuild()
LossOfQuality.model_rebuild()
ActOfResiding.model_rebuild()
StasisOfMissionCapability.model_rebuild()
UltrasonicFrequency.model_rebuild()
ActOfDataTransformation.model_rebuild()
ActOfCommissiveCommunication.model_rebuild()
SpinningMotion.model_rebuild()
ActOfArtifactAssembly.model_rebuild()
StasisOfArtifactOperationality.model_rebuild()
ActOfSuicide.model_rebuild()
InfrasonicFrequency.model_rebuild()
RevolvingMotion.model_rebuild()
ActOfOwnership.model_rebuild()
InfraredLightFrequency.model_rebuild()
ActOfManufacturing.model_rebuild()
ActOfDeclarativeCommunication.model_rebuild()
UpperMidrangeFrequency.model_rebuild()
ActOfAdvising.model_rebuild()
Mailing.model_rebuild()
DecreaseOfRole.model_rebuild()
SoftXrayFrequency.model_rebuild()
StasisOfPartiallyMissionCapable.model_rebuild()
EndOfLifeStasis.model_rebuild()
ActOfConductingMassMediaInterview.model_rebuild()
ActOfFinancialDeposit.model_rebuild()
ActOfMeeting.model_rebuild()
InstantMessaging.model_rebuild()
ActOfReporting.model_rebuild()
NearInfraredLightFrequency.model_rebuild()
ActOfInterpersonalRelationship.model_rebuild()
VeryHighFrequency.model_rebuild()
ActOfThanking.model_rebuild()
ActOfChangeOfResidence.model_rebuild()
ActOfTerroristTrainingInstruction.model_rebuild()
ActOfCongratulating.model_rebuild()
PresenceFrequency.model_rebuild()
ActOfVocationalTrainingAcquisition.model_rebuild()
ActOfTerroristTrainingAcquisition.model_rebuild()
ActOfOathTaking.model_rebuild()
MuzzleBlast.model_rebuild()
ActOfFunding.model_rebuild()
ActOfCommanding.model_rebuild()
ActOfTestifying.model_rebuild()
ActOfPublishingMassMediaArticle.model_rebuild()
ActOfMilitaryTrainingInstruction.model_rebuild()
ActOfCondoling.model_rebuild()
Webcast.model_rebuild()
ExtremelyLowFrequency.model_rebuild()
ActOfPublishingMassMediaPressRelease.model_rebuild()
ActOfOfficialDocumentation.model_rebuild()
ActOfEducationalTrainingInstruction.model_rebuild()
EmailMessaging.model_rebuild()
ActOfFinancialWithdrawal.model_rebuild()
NearUltravioletLightFrequency.model_rebuild()
ActOfDeparture.model_rebuild()
DecreaseOfDisposition.model_rebuild()
StasisOfNonMissionCapable.model_rebuild()
ActOfReligiousTrainingAcquisition.model_rebuild()
ActOfCargoTransportation.model_rebuild()
GainOfDisposition.model_rebuild()
LossOfRole.model_rebuild()
ActOfEncounter.model_rebuild()
StasisOfFullyMissionCapable.model_rebuild()
LowFrequency.model_rebuild()
SuperLowFrequency.model_rebuild()
Wedding.model_rebuild()
MicrowaveFrequency.model_rebuild()
ActOfSocialGroupMembership.model_rebuild()
TextMessaging.model_rebuild()
UltraLowFrequency.model_rebuild()
ActOfRequesting.model_rebuild()
IncreaseOfRole.model_rebuild()
ActOfPromising.model_rebuild()
VeryLowFrequency.model_rebuild()
MidInfraredLightFrequency.model_rebuild()
ActOfDonating.model_rebuild()
SubBassFrequency.model_rebuild()
ActiveStasis.model_rebuild()
TelevisionBroadcast.model_rebuild()
ActOfConfessing.model_rebuild()
RadioBroadcast.model_rebuild()
ActOfReligiousGroupAffiliation.model_rebuild()
ActOfInviting.model_rebuild()
ActOfLoaning.model_rebuild()
ActOfTravel.model_rebuild()
ActOfArrival.model_rebuild()
ActOfMilitaryTrainingAcquisition.model_rebuild()
ActOfApologizing.model_rebuild()
BassFrequency.model_rebuild()
DeactivatedStasis.model_rebuild()
ActOfReligiousWorship.model_rebuild()
ActOfMaintenance.model_rebuild()
MediumFrequency.model_rebuild()
ActOfPublishingMassMediaDocumentary.model_rebuild()
DefunctStasis.model_rebuild()
ActOfDenying.model_rebuild()
ActOfVolunteering.model_rebuild()
ActOfAssignment.model_rebuild()
ActOfRepayment.model_rebuild()
ActOfCollision.model_rebuild()
ActOfIssuingMassMediaPressRelease.model_rebuild()
LossOfDisposition.model_rebuild()
ActOfEducationalTrainingAcquisition.model_rebuild()
FarInfraredLightFrequency.model_rebuild()
LowMidrangeFrequency.model_rebuild()
ActOfReligiousTrainingInstruction.model_rebuild()
FacsimileTransmission.model_rebuild()
MidrangeFrequency.model_rebuild()
HardXrayFrequency.model_rebuild()
TelephoneCall.model_rebuild()
OperationalStasis.model_rebuild()
GainOfRole.model_rebuild()
HighFrequency.model_rebuild()
Funeral.model_rebuild()
ActOfEmployment.model_rebuild()
BrillianceFrequency.model_rebuild()
ActOfIssuingMassMediaArticle.model_rebuild()
ActOfIdentifying.model_rebuild()
ActOfIssuingMassMediaDocumentary.model_rebuild()
ActOfVocationalTrainingInstruction.model_rebuild()
ActOfPropaganda.model_rebuild()
ActOfWarning.model_rebuild()
ActOfMurder.model_rebuild()
ExtremeUltravioletLightFrequency.model_rebuild()
ActOfPurchasing.model_rebuild()
IncreaseOfDisposition.model_rebuild()
ActOfPilgrimage.model_rebuild()
StasisOfPartiallyMissionCapableMaintenance.model_rebuild()
ActOfMilitaryService.model_rebuild()
IncreaseOfFunction.model_rebuild()
ActOfBuying.model_rebuild()
ActOfRemuneration.model_rebuild()
GainOfFunction.model_rebuild()
ExtremelyHighFrequency.model_rebuild()
ActOfAssassination.model_rebuild()
ActOfContractFormation.model_rebuild()
StasisOfNonMissionCapableMaintenance.model_rebuild()
BeginningOfLifeStasis.model_rebuild()
FixedLineNetworkTelephoneCall.model_rebuild()
DecreaseOfFunction.model_rebuild()
SuperHighFrequency.model_rebuild()
FMRadioBroadcastFrequency.model_rebuild()
UltraHighFrequency.model_rebuild()
PrivateNetworkTelephoneCall.model_rebuild()
WirelessNetworkTelephoneCall.model_rebuild()
UnderActiveControl.model_rebuild()
LossOfFunction.model_rebuild()
ActOfRenting.model_rebuild()
ActOfWalking.model_rebuild()
