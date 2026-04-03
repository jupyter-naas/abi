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


class MinorAxis(RDFEntity):
    """
    Minor Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000017"
    _name: ClassVar[str] = "Minor Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ThreeDimensionalPath(RDFEntity):
    """
    Three-Dimensional Path
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000068"
    _name: ClassVar[str] = "Three-Dimensional Path"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_spatial_part": "https://www.commoncoreontologies.org/ont00001855",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_spatial_part"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_spatial_part: Optional[
        Annotated[
            List[Union[ThreeDimensionalPosition, URIRef, str]],
            Field(
                description="y has_spatial_part x iff x, y, z, and q are instances of Immaterial Entity, such that for any z connected with x, z is also connected with y, and q is connected with y but not connected with x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GroundTrackPoint(RDFEntity):
    """
    Ground Track Point
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000070"
    _name: ClassVar[str] = "Ground Track Point"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CoordinateSystemAxis(RDFEntity):
    """
    Coordinate System Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000161"
    _name: ClassVar[str] = "Coordinate System Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ObjectTrackPoint(RDFEntity):
    """
    Object Track Point
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000170"
    _name: ClassVar[str] = "Object Track Point"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "spatial_part_of": "https://www.commoncoreontologies.org/ont00001944",
    }
    _object_properties: ClassVar[set[str]] = {"spatial_part_of"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    spatial_part_of: Optional[
        Annotated[
            List[Union[ObjectTrack, URIRef, str]],
            Field(
                description="x spatial_part_of y iff x, y, z, and q are instances of Immaterial Entity, such that for any z connected with x, z is also connected with y, and q is connected with y but not connected with x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GroundTrack(RDFEntity):
    """
    Ground Track
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000188"
    _name: ClassVar[str] = "Ground Track"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ObjectTrack(RDFEntity):
    """
    The exact line of the Object Track may be drawn based on the Center of Mass of the Object or another reference point, such as the location of a transponder beacon or the center of a radar cross-section, depending on the Object being tracked.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000205"
    _name: ClassVar[str] = "Object Track"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_spatial_part": "https://www.commoncoreontologies.org/ont00001855",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_spatial_part"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_spatial_part: Optional[
        Annotated[
            List[Union[ObjectTrackPoint, URIRef, str]],
            Field(
                description="y has_spatial_part x iff x, y, z, and q are instances of Immaterial Entity, such that for any z connected with x, z is also connected with y, and q is connected with y but not connected with x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OneDimensionalGeospatialBoundary(RDFEntity):
    """
    One-Dimensional Geospatial Boundary
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000207"
    _name: ClassVar[str] = "One-Dimensional Geospatial Boundary"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MajorAxis(RDFEntity):
    """
    Major Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000218"
    _name: ClassVar[str] = "Major Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SemiMinorAxis(RDFEntity):
    """
    Semi-Minor Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000221"
    _name: ClassVar[str] = "Semi-Minor Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfHydrosphere(RDFEntity):
    """
    Portion of Hydrosphere
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000297"
    _name: ClassVar[str] = "Portion of Hydrosphere"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialPosition(RDFEntity):
    """
    Geospatial Position
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000373"
    _name: ClassVar[str] = "Geospatial Position"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AxisOfRotation(RDFEntity):
    """
    Axis of Rotation
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000387"
    _name: ClassVar[str] = "Axis of Rotation"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialRegion(RDFEntity):
    """
    Geospatial Region
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000472"
    _name: ClassVar[str] = "Geospatial Region"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class EnvironmentalFeature(RDFEntity):
    """
    Environmental Feature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000574"
    _name: ClassVar[str] = "Environmental Feature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SeaLevel(RDFEntity):
    """
    Sea Level
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000722"
    _name: ClassVar[str] = "Sea Level"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Zenith(RDFEntity):
    """
    Zenith
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000755"
    _name: ClassVar[str] = "Zenith"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfCryosphere(RDFEntity):
    """
    Portion of Cryosphere
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000779"
    _name: ClassVar[str] = "Portion of Cryosphere"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class SemiMajorAxis(RDFEntity):
    """
    Semi-Major Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000911"
    _name: ClassVar[str] = "Semi-Major Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfLithosphere(RDFEntity):
    """
    Portion of Lithosphere
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001016"
    _name: ClassVar[str] = "Portion of Lithosphere"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Nadir(RDFEntity):
    """
    Nadir
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001040"
    _name: ClassVar[str] = "Nadir"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfAtmosphere(RDFEntity):
    """
    Portion of Atmosphere
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001259"
    _name: ClassVar[str] = "Portion of Atmosphere"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PortionOfGeosphere(RDFEntity):
    """
    Portion of Geosphere
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001341"
    _name: ClassVar[str] = "Portion of Geosphere"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ThreeDimensionalPosition(RDFEntity):
    """
    For an object in motion, its Three-Dimensional Position is part of its Three-Dimensional Path.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001348"
    _name: ClassVar[str] = "Three-Dimensional Position"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class CenterOfMass(RDFEntity):
    """
    Center of Mass
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002000"
    _name: ClassVar[str] = "Center of Mass"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class BoundingBoxPoint(GeospatialPosition, RDFEntity):
    """
    Bounding Box Point
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000125"
    _name: ClassVar[str] = "Bounding Box Point"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ZAxis(CoordinateSystemAxis, RDFEntity):
    """
    z-Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000163"
    _name: ClassVar[str] = "z-Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Subcontinent(GeospatialRegion, RDFEntity):
    """
    Subcontinent
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000213"
    _name: ClassVar[str] = "Subcontinent"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Continent(GeospatialRegion, RDFEntity):
    """
    Continent
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000251"
    _name: ClassVar[str] = "Continent"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class XAxis(CoordinateSystemAxis, RDFEntity):
    """
    x-Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000365"
    _name: ClassVar[str] = "x-Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class YawAxis(AxisOfRotation, RDFEntity):
    """
    Yaw Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000393"
    _name: ClassVar[str] = "Yaw Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialLocation(GeospatialRegion, RDFEntity):
    """
    Geospatial Location
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000487"
    _name: ClassVar[str] = "Geospatial Location"
    _property_uris: ClassVar[dict] = {
        "bFO_0000124": "http://purl.obolibrary.org/obo/BFO_0000124",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000124"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000124: Optional[Annotated[List[Union[BFO_0000001, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class GeospatialEllipse(OneDimensionalGeospatialBoundary, RDFEntity):
    """
    Geospatial Ellipse
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000794"
    _name: ClassVar[str] = "Geospatial Ellipse"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class YAxis(CoordinateSystemAxis, RDFEntity):
    """
    y-Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000801"
    _name: ClassVar[str] = "y-Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialLineString(OneDimensionalGeospatialBoundary, RDFEntity):
    """
    Geospatial Line String
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000817"
    _name: ClassVar[str] = "Geospatial Line String"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PitchAxis(AxisOfRotation, RDFEntity):
    """
    Pitch Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001035"
    _name: ClassVar[str] = "Pitch Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeographicFeature(EnvironmentalFeature, RDFEntity):
    """
    Geographic Feature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001081"
    _name: ClassVar[str] = "Geographic Feature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class RollAxis(AxisOfRotation, RDFEntity):
    """
    Roll Axis
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001106"
    _name: ClassVar[str] = "Roll Axis"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialErrorRegion(OneDimensionalGeospatialBoundary, RDFEntity):
    """
    Geospatial Error Region
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001195"
    _name: ClassVar[str] = "Geospatial Error Region"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AnthropogenicFeature(EnvironmentalFeature, RDFEntity):
    """
    Anthropogenic Feature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001197"
    _name: ClassVar[str] = "Anthropogenic Feature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AtmosphericFeature(GeographicFeature, RDFEntity):
    """
    Atmospheric Feature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000031"
    _name: ClassVar[str] = "Atmospheric Feature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PopulatedPlace(AnthropogenicFeature, RDFEntity):
    """
    Populated place
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000224"
    _name: ClassVar[str] = "Populated place"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Park(AnthropogenicFeature, RDFEntity):
    """
    Park
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000400"
    _name: ClassVar[str] = "Park"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HydrographicFeature(GeographicFeature, RDFEntity):
    """
    Hydrographic Feature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000563"
    _name: ClassVar[str] = "Hydrographic Feature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class PhysiographicFeature(GeographicFeature, RDFEntity):
    """
    Physiographic Feature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000873"
    _name: ClassVar[str] = "Physiographic Feature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialLine(GeospatialLineString, RDFEntity):
    """
    Geospatial Line
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000939"
    _name: ClassVar[str] = "Geospatial Line"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ConstructedFeature(AnthropogenicFeature, RDFEntity):
    """
    Constructed Feature
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001037"
    _name: ClassVar[str] = "Constructed Feature"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialPolygon(GeospatialLineString, RDFEntity):
    """
    Geospatial Polygon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001130"
    _name: ClassVar[str] = "Geospatial Polygon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LowDensityResidentialArea(PopulatedPlace, RDFEntity):
    """
    Low Density Residential Area
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000072"
    _name: ClassVar[str] = "Low Density Residential Area"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class GeospatialRegionBoundingBox(GeospatialPolygon, RDFEntity):
    """
    Geospatial Region Bounding Box
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000358"
    _name: ClassVar[str] = "Geospatial Region Bounding Box"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class HighDensityResidentialArea(PopulatedPlace, RDFEntity):
    """
    High Density Residential Area
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000489"
    _name: ClassVar[str] = "High Density Residential Area"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
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
MinorAxis.model_rebuild()
ThreeDimensionalPath.model_rebuild()
GroundTrackPoint.model_rebuild()
CoordinateSystemAxis.model_rebuild()
ObjectTrackPoint.model_rebuild()
GroundTrack.model_rebuild()
ObjectTrack.model_rebuild()
OneDimensionalGeospatialBoundary.model_rebuild()
MajorAxis.model_rebuild()
SemiMinorAxis.model_rebuild()
PortionOfHydrosphere.model_rebuild()
GeospatialPosition.model_rebuild()
AxisOfRotation.model_rebuild()
GeospatialRegion.model_rebuild()
EnvironmentalFeature.model_rebuild()
SeaLevel.model_rebuild()
Zenith.model_rebuild()
PortionOfCryosphere.model_rebuild()
SemiMajorAxis.model_rebuild()
PortionOfLithosphere.model_rebuild()
Nadir.model_rebuild()
PortionOfAtmosphere.model_rebuild()
PortionOfGeosphere.model_rebuild()
ThreeDimensionalPosition.model_rebuild()
CenterOfMass.model_rebuild()
BoundingBoxPoint.model_rebuild()
ZAxis.model_rebuild()
Subcontinent.model_rebuild()
Continent.model_rebuild()
XAxis.model_rebuild()
YawAxis.model_rebuild()
GeospatialLocation.model_rebuild()
GeospatialEllipse.model_rebuild()
YAxis.model_rebuild()
GeospatialLineString.model_rebuild()
PitchAxis.model_rebuild()
GeographicFeature.model_rebuild()
RollAxis.model_rebuild()
GeospatialErrorRegion.model_rebuild()
AnthropogenicFeature.model_rebuild()
AtmosphericFeature.model_rebuild()
PopulatedPlace.model_rebuild()
Park.model_rebuild()
HydrographicFeature.model_rebuild()
PhysiographicFeature.model_rebuild()
GeospatialLine.model_rebuild()
ConstructedFeature.model_rebuild()
GeospatialPolygon.model_rebuild()
LowDensityResidentialArea.model_rebuild()
GeospatialRegionBoundingBox.model_rebuild()
HighDensityResidentialArea.model_rebuild()
