from __future__ import annotations
from typing import ClassVar
from pydantic import BaseModel
import uuid
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF

# Generated classes from TTL file

# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""
    _namespace: ClassVar[str] = "http://example.org/instance/"
    _uri: str = ""
    
    model_config = {
        'arbitrary_types_allowed': True,
        'extra': 'forbid'
    }
    
    def __init__(self, **kwargs):
        uri = kwargs.pop('_uri', None)
        super().__init__(**kwargs)
        if uri is not None:
            self._uri = uri
        elif not self._uri:
            self._uri = f"{self._namespace}{uuid.uuid4()}"
    
    @classmethod
    def set_namespace(cls, namespace: str):
        """Set the namespace for generating URIs"""
        cls._namespace = namespace
        
    def rdf(self, subject_uri: str | None = None) -> Graph:
        """Generate RDF triples for this instance"""
        g = Graph()
        
        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)
        
        # Add class type
        if hasattr(self, '_class_uri'):
            g.add((subject, RDF.type, URIRef(self._class_uri)))
        
        # Add properties
        if hasattr(self, '_property_uris'):
            for prop_name, prop_uri in self._property_uris.items():
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, 'rdf'):
                                # Add triples from related object
                                g += item.rdf()
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, 'rdf'):
                        # Add triples from related object
                        g += prop_value.rdf()
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))
        
        return g


class Ont00000063(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000063'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000085(RDFEntity):
    """
    Minute
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000085'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000114(RDFEntity):
    """
    Unix Temporal Instant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000114'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000184(RDFEntity):
    """
    Axial Rotation Period
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000184'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000211(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000211'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000223(RDFEntity):
    """
    Time of Day
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000223'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000225(RDFEntity):
    """
    Month
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000225'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000329(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000329'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000550(RDFEntity):
    """
    Morning
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000550'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000619(RDFEntity):
    """
    Week
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000619'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000699(RDFEntity):
    """
    Afternoon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000699'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000800(RDFEntity):
    """
    Day
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000800'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000810(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000810'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000832(RDFEntity):
    """
    Year
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000832'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000992(RDFEntity):
    """
    The Second is used as the basic SI unit of time.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000992'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001058(RDFEntity):
    """
    Hour
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001058'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001088(RDFEntity):
    """
    Decade
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001088'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001110(RDFEntity):
    """
    Evening
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001110'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001116(RDFEntity):
    """
    Reference Time
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001116'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001154(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001154'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001166(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001166'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001204(RDFEntity):
    """
    Night
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001204'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001206(RDFEntity):
    """
    This is a defined class.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001206'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000259(Ont00000225, RDFEntity):
    """
    Calendar Month
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000259'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000359(Ont00000223, RDFEntity):
    """
    Julian Date
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000359'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000465(Ont00000223, RDFEntity):
    """
    A Day begins at midnight GMT within the Modified Julian Date reference system. The Modified Julian Date (MJD) is related to the Julian Date (JD) by the formula:
    MJD = JD - 2400000.5
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000465'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000674(Ont00000832, RDFEntity):
    """
    Calendar Year
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000674'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000921(Ont00000800, RDFEntity):
    """
    Calendar Day
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000921'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001023(Ont00000619, RDFEntity):
    """
    Calendar Week
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001023'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000227(Ont00000674, RDFEntity):
    """
    A Julian Year begins concurrently with January 1, ends concurrently with December 31, and has an average duration of exactly 365.25 Julian Days. Julian Years are typically indicated by prefixing a capital 'J' in front of the Year number, e.g. J2000.0 or J2018.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000227'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000425(Ont00000674, RDFEntity):
    """
    A Gregorian Year begins concurrently with January 1, ends concurrently with December 31, and has an average duration of exactly 365.2425 Gregorian Days. The Gregorian Year is based upon the vernal equinox year. Unless otherwise stated, instances of Calendar Year are assumed to be instances of Gregorian Year since the Gregorian Calendar is the most widely used civil Calendar System.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000425'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000435(Ont00000921, RDFEntity):
    """
    A Gregorian Day is twenty-four Hours in duration.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000435'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000498(Ont00000921, RDFEntity):
    """
    A Julian Day begins at noon Universal Time and is twenty-four Hours in duration.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000498'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Ont00000063.model_rebuild()
Ont00000085.model_rebuild()
Ont00000114.model_rebuild()
Ont00000184.model_rebuild()
Ont00000211.model_rebuild()
Ont00000223.model_rebuild()
Ont00000225.model_rebuild()
Ont00000329.model_rebuild()
Ont00000550.model_rebuild()
Ont00000619.model_rebuild()
Ont00000699.model_rebuild()
Ont00000800.model_rebuild()
Ont00000810.model_rebuild()
Ont00000832.model_rebuild()
Ont00000992.model_rebuild()
Ont00001058.model_rebuild()
Ont00001088.model_rebuild()
Ont00001110.model_rebuild()
Ont00001116.model_rebuild()
Ont00001154.model_rebuild()
Ont00001166.model_rebuild()
Ont00001204.model_rebuild()
Ont00001206.model_rebuild()
Ont00000259.model_rebuild()
Ont00000359.model_rebuild()
Ont00000465.model_rebuild()
Ont00000674.model_rebuild()
Ont00000921.model_rebuild()
Ont00001023.model_rebuild()
Ont00000227.model_rebuild()
Ont00000425.model_rebuild()
Ont00000435.model_rebuild()
Ont00000498.model_rebuild()
