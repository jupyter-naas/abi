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


class MultiHourTemporalInterval(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000063"
    _name: ClassVar[str] = "Multi-Hour Temporal Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_contains": "https://www.commoncoreontologies.org/ont00001924",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_contains"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_contains: Optional[
        Annotated[
            List[Union[Hour, URIRef, str]],
            Field(
                description="x interval_contains y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before or identical to u, and v is before or identical to z, and it is not the case that both w is identical to u and v is identical to z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Minute(RDFEntity):
    """
    Minute
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000085"
    _name: ClassVar[str] = "Minute"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Hour, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class UnixTemporalInstant(RDFEntity):
    """
    Unix Temporal Instant
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000114"
    _name: ClassVar[str] = "Unix Temporal Instant"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class AxialRotationPeriod(RDFEntity):
    """
    Axial Rotation Period
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000184"
    _name: ClassVar[str] = "Axial Rotation Period"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MultiDayTemporalInterval(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000211"
    _name: ClassVar[str] = "Multi-Day Temporal Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_contains": "https://www.commoncoreontologies.org/ont00001924",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_contains"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_contains: Optional[
        Annotated[
            List[Union[Day, URIRef, str]],
            Field(
                description="x interval_contains y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before or identical to u, and v is before or identical to z, and it is not the case that both w is identical to u and v is identical to z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TimeOfDay(RDFEntity):
    """
    Time of Day
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000223"
    _name: ClassVar[str] = "Time of Day"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000132: Optional[Annotated[List[Union[Day, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class Month(RDFEntity):
    """
    Month
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000225"
    _name: ClassVar[str] = "Month"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[URIRef, Year, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MultiMonthTemporalInterval(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000329"
    _name: ClassVar[str] = "Multi-Month Temporal Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_contains": "https://www.commoncoreontologies.org/ont00001924",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_contains"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_contains: Optional[
        Annotated[
            List[Union[Month, URIRef, str]],
            Field(
                description="x interval_contains y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before or identical to u, and v is before or identical to z, and it is not the case that both w is identical to u and v is identical to z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Morning(RDFEntity):
    """
    Morning
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000550"
    _name: ClassVar[str] = "Morning"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Week(RDFEntity):
    """
    Week
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000619"
    _name: ClassVar[str] = "Week"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Month, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Afternoon(RDFEntity):
    """
    Afternoon
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000699"
    _name: ClassVar[str] = "Afternoon"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Day(RDFEntity):
    """
    Day
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000800"
    _name: ClassVar[str] = "Day"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[URIRef, Week, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MultiWeekTemporalInterval(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000810"
    _name: ClassVar[str] = "Multi-Week Temporal Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_contains": "https://www.commoncoreontologies.org/ont00001924",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_contains"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_contains: Optional[
        Annotated[
            List[Union[URIRef, Week, str]],
            Field(
                description="x interval_contains y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before or identical to u, and v is before or identical to z, and it is not the case that both w is identical to u and v is identical to z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Year(RDFEntity):
    """
    Year
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000832"
    _name: ClassVar[str] = "Year"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Decade, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Second(RDFEntity):
    """
    The Second is used as the basic SI unit of time.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000992"
    _name: ClassVar[str] = "Second"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Minute, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Hour(RDFEntity):
    """
    Hour
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001058"
    _name: ClassVar[str] = "Hour"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Day, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Decade(RDFEntity):
    """
    Decade
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001088"
    _name: ClassVar[str] = "Decade"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Evening(RDFEntity):
    """
    Evening
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001110"
    _name: ClassVar[str] = "Evening"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class ReferenceTime(RDFEntity):
    """
    Reference Time
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001116"
    _name: ClassVar[str] = "Reference Time"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MultiSecondTemporalInterval(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001154"
    _name: ClassVar[str] = "Multi-Second Temporal Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_contains": "https://www.commoncoreontologies.org/ont00001924",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_contains"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_contains: Optional[
        Annotated[
            List[Union[Second, URIRef, str]],
            Field(
                description="x interval_contains y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before or identical to u, and v is before or identical to z, and it is not the case that both w is identical to u and v is identical to z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MultiMinuteTemporalInterval(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001166"
    _name: ClassVar[str] = "Multi-Minute Temporal Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_contains": "https://www.commoncoreontologies.org/ont00001924",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_contains"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_contains: Optional[
        Annotated[
            List[Union[Minute, URIRef, str]],
            Field(
                description="x interval_contains y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before or identical to u, and v is before or identical to z, and it is not the case that both w is identical to u and v is identical to z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Night(RDFEntity):
    """
    Night
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001204"
    _name: ClassVar[str] = "Night"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class MultiYearTemporalInterval(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001206"
    _name: ClassVar[str] = "Multi-Year Temporal Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_contains": "https://www.commoncoreontologies.org/ont00001924",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_contains"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_contains: Optional[
        Annotated[
            List[Union[URIRef, Year, str]],
            Field(
                description="x interval_contains y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before or identical to u, and v is before or identical to z, and it is not the case that both w is identical to u and v is identical to z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CalendarMonth(Month, RDFEntity):
    """
    Calendar Month
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000259"
    _name: ClassVar[str] = "Calendar Month"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[URIRef, Year, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JulianDate(TimeOfDay, RDFEntity):
    """
    Julian Date
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000359"
    _name: ClassVar[str] = "Julian Date"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000132: Optional[Annotated[List[Union[JulianDay, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class ModifiedJulianDate(TimeOfDay, RDFEntity):
    """
    A Day begins at midnight GMT within the Modified Julian Date reference system. The Modified Julian Date (MJD) is related to the Julian Date (JD) by the formula:
    MJD = JD - 2400000.5
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000465"
    _name: ClassVar[str] = "Modified Julian Date"
    _property_uris: ClassVar[dict] = {
        "bFO_0000132": "http://purl.obolibrary.org/obo/BFO_0000132",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000132"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    bFO_0000132: Optional[Annotated[List[Union[Day, URIRef, str]], Field()]] = [
        "http://ontology.naas.ai/abi/unknown"
    ]


class CalendarYear(Year, RDFEntity):
    """
    Calendar Year
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000674"
    _name: ClassVar[str] = "Calendar Year"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Decade, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CalendarDay(Day, RDFEntity):
    """
    Calendar Day
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000921"
    _name: ClassVar[str] = "Calendar Day"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[URIRef, Week, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CalendarWeek(Week, RDFEntity):
    """
    Calendar Week
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001023"
    _name: ClassVar[str] = "Calendar Week"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Month, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JulianYear(CalendarYear, RDFEntity):
    """
    A Julian Year begins concurrently with January 1, ends concurrently with December 31, and has an average duration of exactly 365.25 Julian Days. Julian Years are typically indicated by prefixing a capital 'J' in front of the Year number, e.g. J2000.0 or J2018.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000227"
    _name: ClassVar[str] = "Julian Year"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Decade, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GregorianYear(CalendarYear, RDFEntity):
    """
    A Gregorian Year begins concurrently with January 1, ends concurrently with December 31, and has an average duration of exactly 365.2425 Gregorian Days. The Gregorian Year is based upon the vernal equinox year. Unless otherwise stated, instances of Calendar Year are assumed to be instances of Gregorian Year since the Gregorian Calendar is the most widely used civil Calendar System.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000425"
    _name: ClassVar[str] = "Gregorian Year"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[Decade, URIRef, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GregorianDay(CalendarDay, RDFEntity):
    """
    A Gregorian Day is twenty-four Hours in duration.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000435"
    _name: ClassVar[str] = "Gregorian Day"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[URIRef, Week, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JulianDay(CalendarDay, RDFEntity):
    """
    A Julian Day begins at noon Universal Time and is twenty-four Hours in duration.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000498"
    _name: ClassVar[str] = "Julian Day"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "interval_during": "https://www.commoncoreontologies.org/ont00001869",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"interval_during"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    interval_during: Optional[
        Annotated[
            List[Union[URIRef, Week, str]],
            Field(
                description="x interval_during y iff x and y are both instances of Temporal Interval and there exist instances of Temporal Instant u, v, w, and z such that u is the starting instant of x, v is the ending instant of x, w is the starting instant of y, z is the ending instant of y, w is before u, and v is before z."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


# Rebuild models to resolve forward references
MultiHourTemporalInterval.model_rebuild()
Minute.model_rebuild()
UnixTemporalInstant.model_rebuild()
AxialRotationPeriod.model_rebuild()
MultiDayTemporalInterval.model_rebuild()
TimeOfDay.model_rebuild()
Month.model_rebuild()
MultiMonthTemporalInterval.model_rebuild()
Morning.model_rebuild()
Week.model_rebuild()
Afternoon.model_rebuild()
Day.model_rebuild()
MultiWeekTemporalInterval.model_rebuild()
Year.model_rebuild()
Second.model_rebuild()
Hour.model_rebuild()
Decade.model_rebuild()
Evening.model_rebuild()
ReferenceTime.model_rebuild()
MultiSecondTemporalInterval.model_rebuild()
MultiMinuteTemporalInterval.model_rebuild()
Night.model_rebuild()
MultiYearTemporalInterval.model_rebuild()
CalendarMonth.model_rebuild()
JulianDate.model_rebuild()
ModifiedJulianDate.model_rebuild()
CalendarYear.model_rebuild()
CalendarDay.model_rebuild()
CalendarWeek.model_rebuild()
JulianYear.model_rebuild()
GregorianYear.model_rebuild()
GregorianDay.model_rebuild()
JulianDay.model_rebuild()
