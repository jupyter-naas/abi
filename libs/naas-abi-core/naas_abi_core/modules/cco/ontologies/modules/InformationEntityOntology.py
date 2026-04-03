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


class Ont00000223(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000223"
    _name: ClassVar[str] = "Ont00000223"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InformationBearingEntity(RDFEntity):
    """
    This class continues to use the word ‘bearing’ in its rdfslabel because of potential confusion with the acronym ‘ICE’, which is widely used for information content entity.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000253"
    _name: ClassVar[str] = "Information Bearing Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_boolean_value": "https://www.commoncoreontologies.org/ont00001772",
        "has_date_value": "https://www.commoncoreontologies.org/ont00001771",
        "has_datetime_value": "https://www.commoncoreontologies.org/ont00001767",
        "has_decimal_value": "https://www.commoncoreontologies.org/ont00001769",
        "has_double_value": "https://www.commoncoreontologies.org/ont00001770",
        "has_integer_value": "https://www.commoncoreontologies.org/ont00001773",
        "has_text_value": "https://www.commoncoreontologies.org/ont00001765",
        "has_uri_value": "https://www.commoncoreontologies.org/ont00001768",
        "is_excerpted_from": "https://www.commoncoreontologies.org/ont00001824",
        "is_mention_of": "https://www.commoncoreontologies.org/ont00001878",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "uses_geospatial_coordinate_reference_system": "https://www.commoncoreontologies.org/ont00001913",
        "uses_language": "https://www.commoncoreontologies.org/ont00001976",
        "uses_measurement_unit": "https://www.commoncoreontologies.org/ont00001863",
        "uses_reference_system": "https://www.commoncoreontologies.org/ont00001912",
        "uses_time_zone_identifier": "https://www.commoncoreontologies.org/ont00001908",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_excerpted_from",
        "is_mention_of",
        "uses_geospatial_coordinate_reference_system",
        "uses_language",
        "uses_measurement_unit",
        "uses_reference_system",
        "uses_time_zone_identifier",
    }

    # Data properties
    has_text_value: Optional[
        Annotated[
            Any,
            Field(description="A data property that has as its range a string value."),
        ]
    ] = "unknown"
    has_datetime_value: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="A data property that has as its value a datetime value."
            ),
        ]
    ] = "unknown"
    has_uri_value: Optional[
        Annotated[
            Any, Field(description="A data property that has as its range a URI value.")
        ]
    ] = "unknown"
    has_decimal_value: Optional[
        Annotated[
            Any,
            Field(description="A data property that has as its range a decimal value."),
        ]
    ] = "unknown"
    has_double_value: Optional[
        Annotated[
            float,
            Field(description="A data property that has as its range a double value."),
        ]
    ] = "unknown"
    has_date_value: Optional[
        Annotated[
            Any,
            Field(description="A data property that has as its range a date value."),
        ]
    ] = "unknown"
    has_boolean_value: Optional[
        Annotated[
            bool,
            Field(description="A data property that has as its range a boolean value."),
        ]
    ] = "unknown"
    has_integer_value: Optional[
        Annotated[
            int,
            Field(
                description="A data property that has as its range an integer value."
            ),
        ]
    ] = "unknown"
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_excerpted_from: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="An Information Bearing Entity b1 is excerpted from another Information Bearing Entity B2 iff b1 is part of some Information Bearing Entity B1 that is carrier of some Information Content Entity C1, B2 is carrier of some Information Content Entity C2, C1 is not identical with C2, b1 is carrier of some Information Content Entity c1, b2 is an Information Bearing Entity that is part of B2 and b2 is carrier of c1 (i.e. the same Information Content Entity as borne by b1)."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_mention_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_mention_of y iff x is an instance Information Bearing Entity and y is an instance of Entity, such that x is used as a reference to y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    uses_geospatial_coordinate_reference_system: Optional[
        Annotated[
            List[Union[GeospatialCoordinateReferenceSystem, URIRef, str]],
            Field(
                description="y uses_geospatial_coordinate_reference_system x iff y is an instance of Information Bearing Entity and x is an instance of Geospatial Coordinate Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    uses_language: Optional[
        Annotated[
            List[Union[Language, URIRef, str]],
            Field(
                description="x uses_language y iff x is an instance of an Information Bearing Entity and y is an instance of a Language such that the literal value of x is a string that is encoded according to the syntax of y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    uses_measurement_unit: Optional[
        Annotated[
            List[Union[MeasurementUnit, URIRef, str]],
            Field(
                description="y uses_measurement_unit x iff y is an instance of Information Bearing Entity and x is an instance of Measurement Unit, such that x describes the magnitude of measured physical quantity mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    uses_reference_system: Optional[
        Annotated[
            List[Union[ReferenceSystem, URIRef, str]],
            Field(
                description="y uses_reference_system x iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    uses_time_zone_identifier: Optional[
        Annotated[
            List[Union[TimeZoneIdentifier, URIRef, str]],
            Field(
                description="x uses_time_zone_identifier y iff x is an instance of Information Bearing Entity and y is an instance of Time Zone Identifier, such that y designates the spatial region associated with the time zone mentioned in x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class InformationQualityEntity(RDFEntity):
    """
    Typically, an IQE will be a complex pattern made up of multiple qualities joined together spatially.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000314"
    _name: ClassVar[str] = "Information Quality Entity"
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
        Annotated[List[Union[InformationBearingEntity, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Ont00000498(RDFEntity):
    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000498"
    _name: ClassVar[str] = "Ont00000498"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class InformationContentEntity(RDFEntity):
    """
    Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000958"
    _name: ClassVar[str] = "Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DesignativeInformationContentEntity(InformationContentEntity, RDFEntity):
    """
    Designative Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000686"
    _name: ClassVar[str] = "Designative Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DescriptiveInformationContentEntity(InformationContentEntity, RDFEntity):
    """
    Descriptive Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000853"
    _name: ClassVar[str] = "Descriptive Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"describes", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PrescriptiveInformationContentEntity(InformationContentEntity, RDFEntity):
    """
    Prescriptive Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000965"
    _name: ClassVar[str] = "Prescriptive Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "prescribes": "https://www.commoncoreontologies.org/ont00001942",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "prescribes", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prescribes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x prescribes y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x serves as a rule or guide for y if y an Occurrent, or x serves as a model for y if y is a Continuant."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RepresentationalInformationContentEntity(InformationContentEntity, RDFEntity):
    """
    Representational Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001069"
    _name: ClassVar[str] = "Representational Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MediaContentEntity(InformationContentEntity, RDFEntity):
    """
    By 'canonical', it is intended that the media format is of a commonly recognized format, such as mass media formats such as books, magazines, and journals, as well as digital media forms (e.g. ebooks), to include, too, file types, such as those recognized by the Internet Assigned Numbers Authority (IANA)'s Media Types standard [RFC2046].
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002001"
    _name: ClassVar[str] = "Media Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DesignativeName(DesignativeInformationContentEntity, RDFEntity):
    """
    Designative Name
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000003"
    _name: ClassVar[str] = "Designative Name"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MeasurementUnit(DescriptiveInformationContentEntity, RDFEntity):
    """
    Measurement Unit
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000120"
    _name: ClassVar[str] = "Measurement Unit"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_measurement_unit_of": "https://www.commoncoreontologies.org/ont00001961",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_measurement_unit_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_measurement_unit_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_measurement_unit_of y iff y is an instance of Information Bearing Entity and x is an instance of Measurement Unit, such that x describes the magnitude of measured physical quantity mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PerformanceSpecification(PrescriptiveInformationContentEntity, RDFEntity):
    """
    Performance Specification
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000127"
    _name: ClassVar[str] = "Performance Specification"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes_condition": "https://www.commoncoreontologies.org/ont00001980",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "prescribes": "https://www.commoncoreontologies.org/ont00001942",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes_condition",
        "is_about",
        "prescribes",
        "represents",
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
    describes_condition: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="p describes_condition c iff p is an instance of a Performance Specification and c is an instance of Entity and p has part d, and d is an instance of a Descriptive Information Content Entity, and p prescribes an entity s, and d describes c, and c is an entity that is causally relevant to s existing as prescribed by p."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prescribes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x prescribes y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x serves as a rule or guide for y if y an Occurrent, or x serves as a model for y if y is a Continuant."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SpatialRegionIdentifier(DesignativeInformationContentEntity, RDFEntity):
    """
    Spatial Region Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000390"
    _name: ClassVar[str] = "Spatial Region Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ReferenceSystem(DescriptiveInformationContentEntity, RDFEntity):
    """
    Reference System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000398"
    _name: ClassVar[str] = "Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TemporalRegionIdentifier(DesignativeInformationContentEntity, RDFEntity):
    """
    Temporal Region Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000399"
    _name: ClassVar[str] = "Temporal Region Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PredictiveInformationContentEntity(
    DescriptiveInformationContentEntity, RDFEntity
):
    """
    Since predictions are inherently about not-yet-existant things, the Modal Relation Ontology term 'describes' (i.e. mro:describes) should be used (instead of the standard cco:describes) to relate instances of Predictive Information Content Entity to the entities they are about.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000626"
    _name: ClassVar[str] = "Predictive Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"describes", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NonNameIdentifier(DesignativeInformationContentEntity, RDFEntity):
    """
    Non-Name Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000649"
    _name: ClassVar[str] = "Non-Name Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Algorithm(PrescriptiveInformationContentEntity, RDFEntity):
    """
    Algorithm
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000653"
    _name: ClassVar[str] = "Algorithm"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "prescribes": "https://www.commoncoreontologies.org/ont00001942",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "prescribes", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prescribes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x prescribes y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x serves as a rule or guide for y if y an Occurrent, or x serves as a model for y if y is a Continuant."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MeasurementInformationContentEntity(
    DescriptiveInformationContentEntity, RDFEntity
):
    """
    Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001163"
    _name: ClassVar[str] = "Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Language(PrescriptiveInformationContentEntity, RDFEntity):
    """
    Language
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001175"
    _name: ClassVar[str] = "Language"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "language_used_in": "https://www.commoncoreontologies.org/ont00001899",
        "prescribes": "https://www.commoncoreontologies.org/ont00001942",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_about",
        "language_used_in",
        "prescribes",
        "represents",
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
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    language_used_in: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x language_used_by y iff y is an instance of Information Bearing Entity and x is an instance of Language, such that the literal value of y is a string that is encoded according to the syntax of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prescribes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x prescribes y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x serves as a rule or guide for y if y an Occurrent, or x serves as a model for y if y is a Continuant."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Certificate(MediaContentEntity, RDFEntity):
    """
    Certificate
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002002"
    _name: ClassVar[str] = "Certificate"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Image(MediaContentEntity, RDFEntity):
    """
    Image
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002004"
    _name: ClassVar[str] = "Image"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Database(MediaContentEntity, RDFEntity):
    """
    Database
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002006"
    _name: ClassVar[str] = "Database"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class List(MediaContentEntity, RDFEntity):
    """
    List
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002007"
    _name: ClassVar[str] = "List"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Video(MediaContentEntity, RDFEntity):
    """
    Video
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002009"
    _name: ClassVar[str] = "Video"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Message(MediaContentEntity, RDFEntity):
    """
    Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002010"
    _name: ClassVar[str] = "Message"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Barcode(MediaContentEntity, RDFEntity):
    """
    For information on types of barcodes, see: https://www.scandit.com/types-barcodes-choosing-right-barcode/
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002014"
    _name: ClassVar[str] = "Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class InformationLine(MediaContentEntity, RDFEntity):
    """
    Information Line
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002037"
    _name: ClassVar[str] = "Information Line"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DocumentFieldContent(MediaContentEntity, RDFEntity):
    """
    Document Field Content
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002038"
    _name: ClassVar[str] = "Document Field Content"
    _property_uris: ClassVar[dict] = {
        "bFO_0000176": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000176", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
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
        Annotated[List[Union[DocumentContentEntity, URIRef, str]], Field()]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DocumentContentEntity(MediaContentEntity, RDFEntity):
    """
    Document Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002039"
    _name: ClassVar[str] = "Document Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TemporalIntervalIdentifier(TemporalRegionIdentifier, RDFEntity):
    """
    Temporal Interval Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000073"
    _name: ClassVar[str] = "Temporal Interval Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CodeIdentifier(NonNameIdentifier, RDFEntity):
    """
    Code Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000077"
    _name: ClassVar[str] = "Code Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArtificialLanguage(Language, RDFEntity):
    """
    Artificial Language
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000146"
    _name: ClassVar[str] = "Artificial Language"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "language_used_in": "https://www.commoncoreontologies.org/ont00001899",
        "prescribes": "https://www.commoncoreontologies.org/ont00001942",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_about",
        "language_used_in",
        "prescribes",
        "represents",
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
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    language_used_in: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x language_used_by y iff y is an instance of Information Bearing Entity and x is an instance of Language, such that the literal value of y is a string that is encoded according to the syntax of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prescribes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x prescribes y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x serves as a rule or guide for y if y an Occurrent, or x serves as a model for y if y is a Continuant."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SpatialReferenceSystem(ReferenceSystem, RDFEntity):
    """
    Note that, while reference systems and reference frames are treated as synonyms here, some people treat them as related but separate entities. See: http://www.ggos-portal.org/lang_en/GGOS-Portal/EN/Topics/GeodeticApplications/GeodeticReferenceSystemsAndFrames/GeodeticReferenceSystemsAndFrames.html
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000275"
    _name: ClassVar[str] = "Spatial Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NominalMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000293"
    _name: ClassVar[str] = "Nominal Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_a_nominal_measurement_of": "https://www.commoncoreontologies.org/ont00001868",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_a_nominal_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_nominal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_nominal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x classifies y relative to some set of shared, possibly arbitrary, characteristics."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MeasurementUnitOfGeocoordinate(MeasurementUnit, RDFEntity):
    """
    Measurement Unit of Geocoordinate
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000406"
    _name: ClassVar[str] = "Measurement Unit of Geocoordinate"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_measurement_unit_of": "https://www.commoncoreontologies.org/ont00001961",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_measurement_unit_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_measurement_unit_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_measurement_unit_of y iff y is an instance of Information Bearing Entity and x is an instance of Measurement Unit, such that x describes the magnitude of measured physical quantity mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NaturalLanguage(Language, RDFEntity):
    """
    Natural Language
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000496"
    _name: ClassVar[str] = "Natural Language"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "language_used_in": "https://www.commoncoreontologies.org/ont00001899",
        "prescribes": "https://www.commoncoreontologies.org/ont00001942",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_about",
        "language_used_in",
        "prescribes",
        "represents",
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
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    language_used_in: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x language_used_by y iff y is an instance of Information Bearing Entity and x is an instance of Language, such that the literal value of y is a string that is encoded according to the syntax of x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    prescribes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x prescribes y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x serves as a rule or guide for y if y an Occurrent, or x serves as a model for y if y is a Continuant."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TemporalInstantIdentifier(TemporalRegionIdentifier, RDFEntity):
    """
    Temporal Instant Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000540"
    _name: ClassVar[str] = "Temporal Instant Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class VeracityMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    'Deviation Measurement Information Content Entity' and 'Veracity Measurement Information Content Entity' are complementary notions. Deviation is a measure of whether reality conforms to an ICE (e.g., a plan or prediction), whereas Veracity is a measure of whether a Descriptive ICE conforms to reality.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000592"
    _name: ClassVar[str] = "Veracity Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class AbbreviatedName(DesignativeName, RDFEntity):
    """
    Abbreviated Name
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000605"
    _name: ClassVar[str] = "Abbreviated Name"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ProbabilityMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    Every probability measurement is made within a particular context given certain background assumptions.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000692"
    _name: ClassVar[str] = "Probability Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DeviationMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    'Deviation Measurement Information Content Entity' and 'Veracity Measurement Information Content Entity' are complementary notions. Deviation is a measure of whether reality conforms to an ICE (e.g., a plan or prediction), whereas Veracity is a measure of whether a Descriptive ICE conforms to reality.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000731"
    _name: ClassVar[str] = "Deviation Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TimeZoneIdentifier(SpatialRegionIdentifier, RDFEntity):
    """
    Standards of date, time, and time zone data formats:
    ISO/WD 8601-2 (http://www.loc.gov/standards/datetime/iso-tc154-wg5_n0039_iso_wd_8601-2_2016-02-16.pdf)
    W3C (https://www.w3.org/TR/NOTE-datetime)
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000829"
    _name: ClassVar[str] = "Time Zone Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
        "time_zone_identifier_used_by": "https://www.commoncoreontologies.org/ont00001837",
    }
    _object_properties: ClassVar[set[str]] = {
        "designates",
        "is_about",
        "represents",
        "time_zone_identifier_used_by",
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
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    time_zone_identifier_used_by: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x time_zone_identifier_used_by y iff y is an instance of Information Bearing Entity and x is an instance of Time Zone Identifier, such that x designates the spatial region associated with the time zone mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArbitraryIdentifier(NonNameIdentifier, RDFEntity):
    """
    Arbitrary Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000923"
    _name: ClassVar[str] = "Arbitrary Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Nickname(DesignativeName, RDFEntity):
    """
    Nickname
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000990"
    _name: ClassVar[str] = "Nickname"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OrdinalMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001010"
    _name: ClassVar[str] = "Ordinal Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_an_ordinal_measurement_of": "https://www.commoncoreontologies.org/ont00001811",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "is_an_ordinal_measurement_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_an_ordinal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_an_ordinal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity and y is_measured_by_ordinal x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ProperName(DesignativeName, RDFEntity):
    """
    Proper Name
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001014"
    _name: ClassVar[str] = "Proper Name"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class RatioMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001022"
    _name: ClassVar[str] = "Ratio Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_a_ratio_measurement_of": "https://www.commoncoreontologies.org/ont00001983",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_a_ratio_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_ratio_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_ratio_measurement_of y iff x is an instance of Ratio Measurement Information Content Entity and y is an instance of Entity and x describes some attribute of y relative to a scale having equal unit values and a zero value that corresponds to the absence of the attribute being measured."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EstimateInformationContentEntity(MeasurementInformationContentEntity, RDFEntity):
    """
    Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001176"
    _name: ClassVar[str] = "Estimate Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PriorityScale(ReferenceSystem, RDFEntity):
    """
    Priority Scale
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001205"
    _name: ClassVar[str] = "Priority Scale"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ReliabilityMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    Note, the term 'accuracy' is avoided due to its ambiguity between: correctness-of-performance ('Reliability Measurement Information Content Entity'), correctness-of-information (see: 'Veracity Measurement Information Content Entity'), and adherance-to-expectations (see: 'Deviation Measurement Information Content Entity').
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001256"
    _name: ClassVar[str] = "Reliability Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TemporalReferenceSystem(ReferenceSystem, RDFEntity):
    """
    Temporal Reference System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001328"
    _name: ClassVar[str] = "Temporal Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class IntervalMeasurementInformationContentEntity(
    MeasurementInformationContentEntity, RDFEntity
):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001364"
    _name: ClassVar[str] = "Interval Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_an_interval_measurement_of": "https://www.commoncoreontologies.org/ont00001877",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "is_an_interval_measurement_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_an_interval_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_an_interval_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity and y is_measured_by_interval x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class AcademicDegree(Certificate, RDFEntity):
    """
    Academic Degree
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002003"
    _name: ClassVar[str] = "Academic Degree"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Chart(Image, RDFEntity):
    """
    Chart
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002005"
    _name: ClassVar[str] = "Chart"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CodeList(List, RDFEntity):
    """
    Code List
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002008"
    _name: ClassVar[str] = "Code List"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class WarningMessage(Message, RDFEntity):
    """
    Warning Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002011"
    _name: ClassVar[str] = "Warning Message"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EmailMessage(Message, RDFEntity):
    """
    Email Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002012"
    _name: ClassVar[str] = "Email Message"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class NotificationMessage(Message, RDFEntity):
    """
    Notification Message
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002013"
    _name: ClassVar[str] = "Notification Message"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TwoDimensionalBarcode(Barcode, RDFEntity):
    """
    Two-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002015"
    _name: ClassVar[str] = "Two-Dimensional Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OneDimensionalBarcode(Barcode, RDFEntity):
    """
    One-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002020"
    _name: ClassVar[str] = "One-Dimensional Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Book(DocumentContentEntity, RDFEntity):
    """
    Book
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002040"
    _name: ClassVar[str] = "Book"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Transcript(DocumentContentEntity, RDFEntity):
    """
    Transcript
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002041"
    _name: ClassVar[str] = "Transcript"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Spreadsheet(DocumentContentEntity, RDFEntity):
    """
    Spreadsheet
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002042"
    _name: ClassVar[str] = "Spreadsheet"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Report(DocumentContentEntity, RDFEntity):
    """
    Report
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002043"
    _name: ClassVar[str] = "Report"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class FormDocument(DocumentContentEntity, RDFEntity):
    """
    Form Document
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002044"
    _name: ClassVar[str] = "Form Document"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JournalArticle(DocumentContentEntity, RDFEntity):
    """
    Journal Article
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002045"
    _name: ClassVar[str] = "Journal Article"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CivilTimeReferenceSystem(TemporalReferenceSystem, RDFEntity):
    """
    In traditional astronomical usage, civil time is mean solar time as calculated from midnight as the beginning of the Civil Day.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000067"
    _name: ClassVar[str] = "Civil Time Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SolarTimeReferenceSystem(TemporalReferenceSystem, RDFEntity):
    """
    Solar Time Reference System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000124"
    _name: ClassVar[str] = "Solar Time Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MinimumOrdinalMeasurementInformationContentEntity(
    OrdinalMeasurementInformationContentEntity, RDFEntity
):
    """
    Minimum Ordinal Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000164"
    _name: ClassVar[str] = "Minimum Ordinal Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_an_ordinal_measurement_of": "https://www.commoncoreontologies.org/ont00001811",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "is_an_ordinal_measurement_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_an_ordinal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_an_ordinal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity and y is_measured_by_ordinal x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ArtifactVersionOrdinality(OrdinalMeasurementInformationContentEntity, RDFEntity):
    """
    Artifact Version Ordinality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000186"
    _name: ClassVar[str] = "Artifact Version Ordinality"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_an_ordinal_measurement_of": "https://www.commoncoreontologies.org/ont00001811",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "is_an_ordinal_measurement_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_an_ordinal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_an_ordinal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity and y is_measured_by_ordinal x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EventStatusNominalInformationContentEntity(
    NominalMeasurementInformationContentEntity, RDFEntity
):
    """
    Event Status Nominal Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000203"
    _name: ClassVar[str] = "Event Status Nominal Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_a_nominal_measurement_of": "https://www.commoncoreontologies.org/ont00001868",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_a_nominal_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_nominal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_nominal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x classifies y relative to some set of shared, possibly arbitrary, characteristics."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ClockTimeSystem(TemporalReferenceSystem, RDFEntity):
    """
    A single Clock Time System does not provide a complete means for identifying or measuring times. Depending on the particular Clock Time System, it may be compatible for use with one or more other Temporal Reference Systems.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000263"
    _name: ClassVar[str] = "Clock Time System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PriorityMeasurementInformationContentEntity(
    OrdinalMeasurementInformationContentEntity, RDFEntity
):
    """
    Priority Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000369"
    _name: ClassVar[str] = "Priority Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_an_ordinal_measurement_of": "https://www.commoncoreontologies.org/ont00001811",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "is_an_ordinal_measurement_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_an_ordinal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_an_ordinal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity and y is_measured_by_ordinal x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PartNumber(CodeIdentifier, RDFEntity):
    """
    Part Number
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000419"
    _name: ClassVar[str] = "Part Number"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GeospatialCoordinateReferenceSystem(SpatialReferenceSystem, RDFEntity):
    """
    Geospatial Coordinate Reference System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000469"
    _name: ClassVar[str] = "Geospatial Coordinate Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_geospatial_coordinate_reference_system_of": "https://www.commoncoreontologies.org/ont00001900",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_geospatial_coordinate_reference_system_of",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_geospatial_coordinate_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_geospatial_coordinate_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Geospatial Coordinate Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DateIdentifier(TemporalIntervalIdentifier, RDFEntity):
    """
    Date Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000529"
    _name: ClassVar[str] = "Date Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CountMeasurementInformationContentEntity(
    RatioMeasurementInformationContentEntity, RDFEntity
):
    """
    Count Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000539"
    _name: ClassVar[str] = "Count Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_a_ratio_measurement_of": "https://www.commoncoreontologies.org/ont00001983",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_a_ratio_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_ratio_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_ratio_measurement_of y iff x is an instance of Ratio Measurement Information Content Entity and y is an instance of Entity and x describes some attribute of y relative to a scale having equal unit values and a zero value that corresponds to the absence of the attribute being measured."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MaximumOrdinalMeasurementInformationContentEntity(
    OrdinalMeasurementInformationContentEntity, RDFEntity
):
    """
    Maximum Ordinal Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000604"
    _name: ClassVar[str] = "Maximum Ordinal Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_an_ordinal_measurement_of": "https://www.commoncoreontologies.org/ont00001811",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "is_an_ordinal_measurement_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_an_ordinal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_an_ordinal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity and y is_measured_by_ordinal x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DistanceMeasurementInformationContentEntity(
    RatioMeasurementInformationContentEntity, RDFEntity
):
    """
    Distance Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000669"
    _name: ClassVar[str] = "Distance Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_a_ratio_measurement_of": "https://www.commoncoreontologies.org/ont00001983",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_a_ratio_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_ratio_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_ratio_measurement_of y iff x is an instance of Ratio Measurement Information Content Entity and y is an instance of Entity and x describes some attribute of y relative to a scale having equal unit values and a zero value that corresponds to the absence of the attribute being measured."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DiminutiveName(AbbreviatedName, RDFEntity):
    """
    Diminutive Name
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000683"
    _name: ClassVar[str] = "Diminutive Name"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SphericalCoordinateSystem(SpatialReferenceSystem, RDFEntity):
    """
    Spherical Coordinate System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000729"
    _name: ClassVar[str] = "Spherical Coordinate System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GeospatialRegionBoundingBoxIdentifierList(
    MeasurementUnitOfGeocoordinate, RDFEntity
):
    """
    Geospatial Region Bounding Box Identifier List
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000735"
    _name: ClassVar[str] = "Geospatial Region Bounding Box Identifier List"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_measurement_unit_of": "https://www.commoncoreontologies.org/ont00001961",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_measurement_unit_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_measurement_unit_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_measurement_unit_of y iff y is an instance of Information Bearing Entity and x is an instance of Measurement Unit, such that x describes the magnitude of measured physical quantity mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PointEstimateInformationContentEntity(
    EstimateInformationContentEntity, RDFEntity
):
    """
    Point Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000745"
    _name: ClassVar[str] = "Point Estimate Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class TimeOfDayIdentifier(TemporalInstantIdentifier, RDFEntity):
    """
    Time of Day Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000827"
    _name: ClassVar[str] = "Time of Day Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ProportionalRatioMeasurementInformationContentEntity(
    RatioMeasurementInformationContentEntity, RDFEntity
):
    """
    A percentage is one way to express a proportional measure where the decimal expression of the proportion is multiplied by 100, thus giving the proportional value with respect to a whole of 100. E.g., the ratio of pigs to cows on a farm is 44 to 79 (44:79 or 44/79). The proportion of pigs to total animals is 44 to 123 or 44/123. The percentage of pigs is the decimal equivalent of the proportion (0.36) multiplied by a 100 (36%). The percentage can be expressed as a proportion where the numerator value is transformed for a denominator of 100, i.e., 36 of a 100 animals are pigs (36/100).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000845"
    _name: ClassVar[str] = "Proportional Ratio Measurement Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_a_ratio_measurement_of": "https://www.commoncoreontologies.org/ont00001983",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_a_ratio_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_ratio_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_ratio_measurement_of y iff x is an instance of Ratio Measurement Information Content Entity and y is an instance of Entity and x describes some attribute of y relative to a scale having equal unit values and a zero value that corresponds to the absence of the attribute being measured."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CalendarSystem(TemporalReferenceSystem, RDFEntity):
    """
    Calendar System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000891"
    _name: ClassVar[str] = "Calendar System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Acronym(AbbreviatedName, RDFEntity):
    """
    Acronym
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000915"
    _name: ClassVar[str] = "Acronym"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SequencePositionOrdinality(OrdinalMeasurementInformationContentEntity, RDFEntity):
    """
    Sequence Position Ordinality
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001041"
    _name: ClassVar[str] = "Sequence Position Ordinality"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_an_ordinal_measurement_of": "https://www.commoncoreontologies.org/ont00001811",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "is_an_ordinal_measurement_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_an_ordinal_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_an_ordinal_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity and y is_measured_by_ordinal x."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class IntervalEstimateInformationContentEntity(
    EstimateInformationContentEntity, RDFEntity
):
    """
    Interval Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001101"
    _name: ClassVar[str] = "Interval Estimate Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SiderealTimeReferenceSystem(TemporalReferenceSystem, RDFEntity):
    """
    Sidereal Time is the angle measured from an observer's meridian along the celestial equator to the Great Circle that passes through the March equinox and both poles. This angle is usually expressed in Hours, Minutes, and Seconds.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001146"
    _name: ClassVar[str] = "Sidereal Time Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MilitaryTimeZoneIdentifier(TimeZoneIdentifier, RDFEntity):
    """
    Military Time Zone Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001235"
    _name: ClassVar[str] = "Military Time Zone Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
        "time_zone_identifier_used_by": "https://www.commoncoreontologies.org/ont00001837",
    }
    _object_properties: ClassVar[set[str]] = {
        "designates",
        "is_about",
        "represents",
        "time_zone_identifier_used_by",
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
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    time_zone_identifier_used_by: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x time_zone_identifier_used_by y iff y is an instance of Information Bearing Entity and x is an instance of Time Zone Identifier, such that x designates the spatial region associated with the time zone mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Initialism(AbbreviatedName, RDFEntity):
    """
    Initialism
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001238"
    _name: ClassVar[str] = "Initialism"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LotNumber(CodeIdentifier, RDFEntity):
    """
    Lot Number
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001309"
    _name: ClassVar[str] = "Lot Number"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LegalName(ProperName, RDFEntity):
    """
    Legal Name
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001331"
    _name: ClassVar[str] = "Legal Name"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CartesianCoordinateSystem(SpatialReferenceSystem, RDFEntity):
    """
    Cartesian Coordinate System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001351"
    _name: ClassVar[str] = "Cartesian Coordinate System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GreenwichMeanTimeZoneIdentifier(TimeZoneIdentifier, RDFEntity):
    """
    Greenwich Mean Time (GMT) is the mean solar time at the Royal Observatory in Greenwich, London and has been superseded by Coordinated Universal Time (UTC).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001352"
    _name: ClassVar[str] = "Greenwich Mean Time Zone Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
        "time_zone_identifier_used_by": "https://www.commoncoreontologies.org/ont00001837",
    }
    _object_properties: ClassVar[set[str]] = {
        "designates",
        "is_about",
        "represents",
        "time_zone_identifier_used_by",
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
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    time_zone_identifier_used_by: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x time_zone_identifier_used_by y iff y is an instance of Information Bearing Entity and x is an instance of Time Zone Identifier, such that x designates the spatial region associated with the time zone mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class AztecCode(TwoDimensionalBarcode, RDFEntity):
    """
    Aztec Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002016"
    _name: ClassVar[str] = "Aztec Code"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DataMatrixCode(TwoDimensionalBarcode, RDFEntity):
    """
    Data Matrix Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002017"
    _name: ClassVar[str] = "Data Matrix Code"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class QRCode(TwoDimensionalBarcode, RDFEntity):
    """
    QR Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002018"
    _name: ClassVar[str] = "QR Code"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class PDF417Code(TwoDimensionalBarcode, RDFEntity):
    """
    PDF417 Code
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002019"
    _name: ClassVar[str] = "PDF417 Code"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CodabarBarcode(OneDimensionalBarcode, RDFEntity):
    """
    Codabar Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002021"
    _name: ClassVar[str] = "Codabar Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Code93Barcode(OneDimensionalBarcode, RDFEntity):
    """
    Code 93 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002022"
    _name: ClassVar[str] = "Code 93 Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ITFBarcode(OneDimensionalBarcode, RDFEntity):
    """
    ITF Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002023"
    _name: ClassVar[str] = "ITF Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MSIPlesseyBarcode(OneDimensionalBarcode, RDFEntity):
    """
    MSI Plessey Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002024"
    _name: ClassVar[str] = "MSI Plessey Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EANBarcode(OneDimensionalBarcode, RDFEntity):
    """
    EAN Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002025"
    _name: ClassVar[str] = "EAN Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class GS1DataBarBarcode(OneDimensionalBarcode, RDFEntity):
    """
    Further variants of GS1 DataBar have not been defined here.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002031"
    _name: ClassVar[str] = "GS1 DataBar Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Code39Barcode(OneDimensionalBarcode, RDFEntity):
    """
    Code 39 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002032"
    _name: ClassVar[str] = "Code 39 Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Code128Barcode(OneDimensionalBarcode, RDFEntity):
    """
    Code 128 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002033"
    _name: ClassVar[str] = "Code 128 Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class UPCBarcode(OneDimensionalBarcode, RDFEntity):
    """
    UPC Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002034"
    _name: ClassVar[str] = "UPC Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MedianPointEstimateInformationContentEntity(
    PointEstimateInformationContentEntity, RDFEntity
):
    """
    Median Point Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000029"
    _name: ClassVar[str] = "Median Point Estimate Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class StandardTimeOfDayIdentifier(TimeOfDayIdentifier, RDFEntity):
    """
    Standard Time of Day Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000080"
    _name: ClassVar[str] = "Standard Time of Day Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ModePointEstimateInformationContentEntity(
    PointEstimateInformationContentEntity, RDFEntity
):
    """
    While there is always at least one Mode for every set of data, it is possible for any given set of data to have multiple Modes. The Mode is typically most useful when the members of the set are all Nominal Measurement Information Content Entities.
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000154"
    _name: ClassVar[str] = "Mode Point Estimate Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class SolarCalendarSystem(CalendarSystem, RDFEntity):
    """
    Solar Calendar System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000276"
    _name: ClassVar[str] = "Solar Calendar System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class UniversalTimeReferenceSystem(SolarTimeReferenceSystem, RDFEntity):
    """
    Universal Time Reference System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000630"
    _name: ClassVar[str] = "Universal Time Reference System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DecimalDateIdentifier(DateIdentifier, RDFEntity):
    """
    Decimal Date Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000894"
    _name: ClassVar[str] = "Decimal Date Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class MeanPointEstimateInformationContentEntity(
    PointEstimateInformationContentEntity, RDFEntity
):
    """
    Mean Point Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000896"
    _name: ClassVar[str] = "Mean Point Estimate Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LunarCalendarSystem(CalendarSystem, RDFEntity):
    """
    Lunar Calendar System
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000916"
    _name: ClassVar[str] = "Lunar Calendar System"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "is_reference_system_of": "https://www.commoncoreontologies.org/ont00001997",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_about",
        "is_reference_system_of",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_reference_system_of: Optional[
        Annotated[
            List[Union[InformationBearingEntity, URIRef, str]],
            Field(
                description="x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DecimalTimeOfDayIdentifier(TimeOfDayIdentifier, RDFEntity):
    """
    Decimal Time of Day Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000973"
    _name: ClassVar[str] = "Decimal Time of Day Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class DataRangeIntervalEstimateInformationContentEntity(
    IntervalEstimateInformationContentEntity, RDFEntity
):
    """
    Data Range Interval Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001149"
    _name: ClassVar[str] = "Data Range Interval Estimate Information Content Entity"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "describes": "https://www.commoncoreontologies.org/ont00001982",
        "is_a_measurement_of": "https://www.commoncoreontologies.org/ont00001966",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "describes",
        "is_a_measurement_of",
        "is_about",
        "represents",
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
    describes: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x describes y iff x is an instance of Descriptive Information Content Entity, and y is an instance of Entity, such that x is_about the characteristics that identify y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_a_measurement_of: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_a_measurement_of y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x describes some attribute of y relative to some scale or classification scheme."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class CalendarDateIdentifier(DateIdentifier, RDFEntity):
    """
    Calendar Date Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001340"
    _name: ClassVar[str] = "Calendar Date Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ISSNBarcode(EANBarcode, RDFEntity):
    """
    ISSN Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002026"
    _name: ClassVar[str] = "ISSN Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JAN13Barcode(EANBarcode, RDFEntity):
    """
    JAN-13 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002027"
    _name: ClassVar[str] = "JAN-13 Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EAN13Barcode(EANBarcode, RDFEntity):
    """
    EAN-13 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002028"
    _name: ClassVar[str] = "EAN-13 Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class EAN8Barcode(EANBarcode, RDFEntity):
    """
    EAN-8 Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002029"
    _name: ClassVar[str] = "EAN-8 Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ISBNBarcode(EANBarcode, RDFEntity):
    """
    ISBN Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002030"
    _name: ClassVar[str] = "ISBN Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class UPCABarcode(UPCBarcode, RDFEntity):
    """
    UPC-A Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002035"
    _name: ClassVar[str] = "UPC-A Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class UPCEBarcode(UPCBarcode, RDFEntity):
    """
    UPC-E Barcode
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00002036"
    _name: ClassVar[str] = "UPC-E Barcode"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class OrdinalDateIdentifier(DecimalDateIdentifier, RDFEntity):
    """
    An Ordinal Date Identifier may or may not also contain a number indicating a specific Year. If both numbers are included, the ISO 8601 ordinal date format stipulates that the two numbers be formatted as YYYY-DDD or YYYYDDD where [YYYY] indicates a year and [DDD] is the day of that year, from 001 through 365 (or 366 in leap years).
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000087"
    _name: ClassVar[str] = "Ordinal Date Identifier"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JulianDateFraction(DecimalTimeOfDayIdentifier, RDFEntity):
    """
    Julian Date Fraction
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000589"
    _name: ClassVar[str] = "Julian Date Fraction"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JulianDayNumber(DecimalDateIdentifier, RDFEntity):
    """
    Julian Day Number
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000749"
    _name: ClassVar[str] = "Julian Day Number"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {"designates", "is_about", "represents"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    designates: Optional[
        Annotated[
            List[Union[Ont00000498, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class JulianDateIdentifier(DecimalTimeOfDayIdentifier, RDFEntity):
    """
    Julian Date Identifier
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00000833"
    _name: ClassVar[str] = "Julian Date Identifier"
    _property_uris: ClassVar[dict] = {
        "bFO_0000178": "http://purl.obolibrary.org/obo/BFO_0000178",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "designates": "https://www.commoncoreontologies.org/ont00001916",
        "is_about": "https://www.commoncoreontologies.org/ont00001808",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "represents": "https://www.commoncoreontologies.org/ont00001938",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000178",
        "designates",
        "is_about",
        "represents",
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
    bFO_0000178: Optional[
        Annotated[
            List[Union[JulianDateFraction, JulianDayNumber, URIRef, str]], Field()
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    designates: Optional[
        Annotated[
            List[Union[Ont00000359, URIRef, str]],
            Field(
                description="x designates y iff x is an instance of a Designative Information Content Entity, and y is an instance of an Entity, such that given some context, x uniquely distinguishes y from other entities."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_about: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x is_about y is a primitive relationship between an instance of Information Content Entity x and an instance of Entity y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    represents: Optional[
        Annotated[
            List[Union[BFO_0000001, URIRef, str]],
            Field(
                description="x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


# Rebuild models to resolve forward references
Ont00000223.model_rebuild()
InformationBearingEntity.model_rebuild()
InformationQualityEntity.model_rebuild()
Ont00000498.model_rebuild()
InformationContentEntity.model_rebuild()
DesignativeInformationContentEntity.model_rebuild()
DescriptiveInformationContentEntity.model_rebuild()
PrescriptiveInformationContentEntity.model_rebuild()
RepresentationalInformationContentEntity.model_rebuild()
MediaContentEntity.model_rebuild()
DesignativeName.model_rebuild()
MeasurementUnit.model_rebuild()
PerformanceSpecification.model_rebuild()
SpatialRegionIdentifier.model_rebuild()
ReferenceSystem.model_rebuild()
TemporalRegionIdentifier.model_rebuild()
PredictiveInformationContentEntity.model_rebuild()
NonNameIdentifier.model_rebuild()
Algorithm.model_rebuild()
MeasurementInformationContentEntity.model_rebuild()
Language.model_rebuild()
Certificate.model_rebuild()
Image.model_rebuild()
Database.model_rebuild()
List.model_rebuild()
Video.model_rebuild()
Message.model_rebuild()
Barcode.model_rebuild()
InformationLine.model_rebuild()
DocumentFieldContent.model_rebuild()
DocumentContentEntity.model_rebuild()
TemporalIntervalIdentifier.model_rebuild()
CodeIdentifier.model_rebuild()
ArtificialLanguage.model_rebuild()
SpatialReferenceSystem.model_rebuild()
NominalMeasurementInformationContentEntity.model_rebuild()
MeasurementUnitOfGeocoordinate.model_rebuild()
NaturalLanguage.model_rebuild()
TemporalInstantIdentifier.model_rebuild()
VeracityMeasurementInformationContentEntity.model_rebuild()
AbbreviatedName.model_rebuild()
ProbabilityMeasurementInformationContentEntity.model_rebuild()
DeviationMeasurementInformationContentEntity.model_rebuild()
TimeZoneIdentifier.model_rebuild()
ArbitraryIdentifier.model_rebuild()
Nickname.model_rebuild()
OrdinalMeasurementInformationContentEntity.model_rebuild()
ProperName.model_rebuild()
RatioMeasurementInformationContentEntity.model_rebuild()
EstimateInformationContentEntity.model_rebuild()
PriorityScale.model_rebuild()
ReliabilityMeasurementInformationContentEntity.model_rebuild()
TemporalReferenceSystem.model_rebuild()
IntervalMeasurementInformationContentEntity.model_rebuild()
AcademicDegree.model_rebuild()
Chart.model_rebuild()
CodeList.model_rebuild()
WarningMessage.model_rebuild()
EmailMessage.model_rebuild()
NotificationMessage.model_rebuild()
TwoDimensionalBarcode.model_rebuild()
OneDimensionalBarcode.model_rebuild()
Book.model_rebuild()
Transcript.model_rebuild()
Spreadsheet.model_rebuild()
Report.model_rebuild()
FormDocument.model_rebuild()
JournalArticle.model_rebuild()
CivilTimeReferenceSystem.model_rebuild()
SolarTimeReferenceSystem.model_rebuild()
MinimumOrdinalMeasurementInformationContentEntity.model_rebuild()
ArtifactVersionOrdinality.model_rebuild()
EventStatusNominalInformationContentEntity.model_rebuild()
ClockTimeSystem.model_rebuild()
PriorityMeasurementInformationContentEntity.model_rebuild()
PartNumber.model_rebuild()
GeospatialCoordinateReferenceSystem.model_rebuild()
DateIdentifier.model_rebuild()
CountMeasurementInformationContentEntity.model_rebuild()
MaximumOrdinalMeasurementInformationContentEntity.model_rebuild()
DistanceMeasurementInformationContentEntity.model_rebuild()
DiminutiveName.model_rebuild()
SphericalCoordinateSystem.model_rebuild()
GeospatialRegionBoundingBoxIdentifierList.model_rebuild()
PointEstimateInformationContentEntity.model_rebuild()
TimeOfDayIdentifier.model_rebuild()
ProportionalRatioMeasurementInformationContentEntity.model_rebuild()
CalendarSystem.model_rebuild()
Acronym.model_rebuild()
SequencePositionOrdinality.model_rebuild()
IntervalEstimateInformationContentEntity.model_rebuild()
SiderealTimeReferenceSystem.model_rebuild()
MilitaryTimeZoneIdentifier.model_rebuild()
Initialism.model_rebuild()
LotNumber.model_rebuild()
LegalName.model_rebuild()
CartesianCoordinateSystem.model_rebuild()
GreenwichMeanTimeZoneIdentifier.model_rebuild()
AztecCode.model_rebuild()
DataMatrixCode.model_rebuild()
QRCode.model_rebuild()
PDF417Code.model_rebuild()
CodabarBarcode.model_rebuild()
Code93Barcode.model_rebuild()
ITFBarcode.model_rebuild()
MSIPlesseyBarcode.model_rebuild()
EANBarcode.model_rebuild()
GS1DataBarBarcode.model_rebuild()
Code39Barcode.model_rebuild()
Code128Barcode.model_rebuild()
UPCBarcode.model_rebuild()
MedianPointEstimateInformationContentEntity.model_rebuild()
StandardTimeOfDayIdentifier.model_rebuild()
ModePointEstimateInformationContentEntity.model_rebuild()
SolarCalendarSystem.model_rebuild()
UniversalTimeReferenceSystem.model_rebuild()
DecimalDateIdentifier.model_rebuild()
MeanPointEstimateInformationContentEntity.model_rebuild()
LunarCalendarSystem.model_rebuild()
DecimalTimeOfDayIdentifier.model_rebuild()
DataRangeIntervalEstimateInformationContentEntity.model_rebuild()
CalendarDateIdentifier.model_rebuild()
ISSNBarcode.model_rebuild()
JAN13Barcode.model_rebuild()
EAN13Barcode.model_rebuild()
EAN8Barcode.model_rebuild()
ISBNBarcode.model_rebuild()
UPCABarcode.model_rebuild()
UPCEBarcode.model_rebuild()
OrdinalDateIdentifier.model_rebuild()
JulianDateFraction.model_rebuild()
JulianDayNumber.model_rebuild()
JulianDateIdentifier.model_rebuild()
