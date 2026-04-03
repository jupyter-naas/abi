from __future__ import annotations
from typing import Annotated, Any, ClassVar, Optional
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


class Ont00000120(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000120"
    _name: ClassVar[str] = "Ont00000120"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfFlow(Ont00000120, RDFEntity):
    """
    Measurement Unit of Flow
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000061"
    _name: ClassVar[str] = "Measurement Unit of Flow"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfAcceleration(Ont00000120, RDFEntity):
    """
    Measurement Unit of Acceleration
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000074"
    _name: ClassVar[str] = "Measurement Unit of Acceleration"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfAmountOfSubstance(Ont00000120, RDFEntity):
    """
    The type of particle quantified is typically either atoms or molecules, but may also be protons, neutrons, electrons, quarks, or other particles. The type of particle being measured should always be specified along with the measurement and its unit.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000140"
    _name: ClassVar[str] = "Measurement Unit of Amount of Substance"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfSoundLevel(Ont00000120, RDFEntity):
    """
    Measurement Unit of Sound Level
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000198"
    _name: ClassVar[str] = "Measurement Unit of Sound Level"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfArea(Ont00000120, RDFEntity):
    """
    Measurement Unit of Area
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000217"
    _name: ClassVar[str] = "Measurement Unit of Area"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfPower(Ont00000120, RDFEntity):
    """
    Measurement Unit of Power
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000229"
    _name: ClassVar[str] = "Measurement Unit of Power"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfMass(Ont00000120, RDFEntity):
    """
    Measurement Unit of Mass
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000239"
    _name: ClassVar[str] = "Measurement Unit of Mass"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfEnergy(Ont00000120, RDFEntity):
    """
    Measurement Unit of Energy
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000444"
    _name: ClassVar[str] = "Measurement Unit of Energy"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfForce(Ont00000120, RDFEntity):
    """
    Measurement Unit of Force
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000497"
    _name: ClassVar[str] = "Measurement Unit of Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfAreaMomentOfInertia(Ont00000120, RDFEntity):
    """
    Measurement Unit of Area Moment of Inertia
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000502"
    _name: ClassVar[str] = "Measurement Unit of Area Moment of Inertia"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfRotationalInertia(Ont00000120, RDFEntity):
    """
    Measurement Unit of Rotational Inertia
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000527"
    _name: ClassVar[str] = "Measurement Unit of Rotational Inertia"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfTorque(Ont00000120, RDFEntity):
    """
    Measurement Unit of Torque
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000659"
    _name: ClassVar[str] = "Measurement Unit of Torque"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfAngle(Ont00000120, RDFEntity):
    """
    Measurement Unit of Angle
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000707"
    _name: ClassVar[str] = "Measurement Unit of Angle"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfDensity(Ont00000120, RDFEntity):
    """
    Measurement Unit of Density
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000770"
    _name: ClassVar[str] = "Measurement Unit of Density"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfTemperature(Ont00000120, RDFEntity):
    """
    Measurement Unit of Temperature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000844"
    _name: ClassVar[str] = "Measurement Unit of Temperature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfWork(Ont00000120, RDFEntity):
    """
    Measurement Unit of Work
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000852"
    _name: ClassVar[str] = "Measurement Unit of Work"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfMomentum(Ont00000120, RDFEntity):
    """
    Measurement Unit of Momentum
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000940"
    _name: ClassVar[str] = "Measurement Unit of Momentum"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfFrequency(Ont00000120, RDFEntity):
    """
    Measurement Unit of Frequency
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000959"
    _name: ClassVar[str] = "Measurement Unit of Frequency"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfSpeed(Ont00000120, RDFEntity):
    """
    Measurement Unit of Speed
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000969"
    _name: ClassVar[str] = "Measurement Unit of Speed"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfElectromagneticForce(Ont00000120, RDFEntity):
    """
    Measurement Unit of Electromagnetic Force
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001004"
    _name: ClassVar[str] = "Measurement Unit of Electromagnetic Force"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfPressure(Ont00000120, RDFEntity):
    """
    Measurement Unit of Pressure
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001090"
    _name: ClassVar[str] = "Measurement Unit of Pressure"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfLength(Ont00000120, RDFEntity):
    """
    Measurement Unit of Length
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001290"
    _name: ClassVar[str] = "Measurement Unit of Length"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfVolume(Ont00000120, RDFEntity):
    """
    Measurement Unit of Volume
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001317"
    _name: ClassVar[str] = "Measurement Unit of Volume"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfImpulse(Ont00000120, RDFEntity):
    """
    Measurement Unit of Impulse
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001345"
    _name: ClassVar[str] = "Measurement Unit of Impulse"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfTime(Ont00000120, RDFEntity):
    """
    Measurement Unit of Time
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001357"
    _name: ClassVar[str] = "Measurement Unit of Time"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfVolumetricFlowRate(MeasurementUnitOfFlow, RDFEntity):
    """
    Measurement Unit of Volumetric Flow Rate
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000374"
    _name: ClassVar[str] = "Measurement Unit of Volumetric Flow Rate"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MeasurementUnitOfMassFlowRate(MeasurementUnitOfFlow, RDFEntity):
    """
    Measurement Unit of Mass Flow Rate
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001307"
    _name: ClassVar[str] = "Measurement Unit of Mass Flow Rate"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
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
Ont00000120.model_rebuild()
MeasurementUnitOfFlow.model_rebuild()
MeasurementUnitOfAcceleration.model_rebuild()
MeasurementUnitOfAmountOfSubstance.model_rebuild()
MeasurementUnitOfSoundLevel.model_rebuild()
MeasurementUnitOfArea.model_rebuild()
MeasurementUnitOfPower.model_rebuild()
MeasurementUnitOfMass.model_rebuild()
MeasurementUnitOfEnergy.model_rebuild()
MeasurementUnitOfForce.model_rebuild()
MeasurementUnitOfAreaMomentOfInertia.model_rebuild()
MeasurementUnitOfRotationalInertia.model_rebuild()
MeasurementUnitOfTorque.model_rebuild()
MeasurementUnitOfAngle.model_rebuild()
MeasurementUnitOfDensity.model_rebuild()
MeasurementUnitOfTemperature.model_rebuild()
MeasurementUnitOfWork.model_rebuild()
MeasurementUnitOfMomentum.model_rebuild()
MeasurementUnitOfFrequency.model_rebuild()
MeasurementUnitOfSpeed.model_rebuild()
MeasurementUnitOfElectromagneticForce.model_rebuild()
MeasurementUnitOfPressure.model_rebuild()
MeasurementUnitOfLength.model_rebuild()
MeasurementUnitOfVolume.model_rebuild()
MeasurementUnitOfImpulse.model_rebuild()
MeasurementUnitOfTime.model_rebuild()
MeasurementUnitOfVolumetricFlowRate.model_rebuild()
MeasurementUnitOfMassFlowRate.model_rebuild()
