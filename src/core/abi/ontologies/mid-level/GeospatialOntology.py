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


class Ont00000017(RDFEntity):
    """
    Minor Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000017'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000068(RDFEntity):
    """
    Three-Dimensional Path
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000068'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000070(RDFEntity):
    """
    Ground Track Point
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000070'
    _property_uris: ClassVar[dict] = {}
    pass

class Neb67d9c858f34c2fb95b7ba17a1334f7b2(RDFEntity):
    _class_uri: ClassVar[str] = 'neb67d9c858f34c2fb95b7ba17a1334f7b2'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000161(RDFEntity):
    """
    Coordinate System Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000161'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000170(RDFEntity):
    """
    Object Track Point
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000170'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000188(RDFEntity):
    """
    Ground Track
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000188'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000205(RDFEntity):
    """
    The exact line of the Object Track may be drawn based on the Center of Mass of the Object or another reference point, such as the location of a transponder beacon or the center of a radar cross-section, depending on the Object being tracked.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000205'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000207(RDFEntity):
    """
    One-Dimensional Geospatial Boundary
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000207'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000218(RDFEntity):
    """
    Major Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000218'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000221(RDFEntity):
    """
    Semi-Minor Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000221'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000297(RDFEntity):
    """
    Portion of Hydrosphere
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000297'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000373(RDFEntity):
    """
    Geospatial Position
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000373'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000387(RDFEntity):
    """
    Axis of Rotation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000387'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000472(RDFEntity):
    """
    Geospatial Region
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000472'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000574(RDFEntity):
    """
    Environmental Feature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000574'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000722(RDFEntity):
    """
    Sea Level
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000722'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000755(RDFEntity):
    """
    Zenith
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000755'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000779(RDFEntity):
    """
    Portion of Cryosphere
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000779'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000911(RDFEntity):
    """
    Semi-Major Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000911'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001016(RDFEntity):
    """
    Portion of Lithosphere
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001016'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001040(RDFEntity):
    """
    Nadir
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001040'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001259(RDFEntity):
    """
    Portion of Atmosphere
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001259'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001341(RDFEntity):
    """
    Portion of Geosphere
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001341'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001348(RDFEntity):
    """
    For an object in motion, its Three-Dimensional Position is part of its Three-Dimensional Path.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001348'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00002000(RDFEntity):
    """
    Center of Mass
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002000'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000125(Ont00000373, RDFEntity):
    """
    Bounding Box Point
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000125'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000163(Ont00000161, RDFEntity):
    """
    z-Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000163'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000213(Ont00000472, RDFEntity):
    """
    Subcontinent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000213'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000251(Ont00000472, RDFEntity):
    """
    Continent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000251'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000365(Ont00000161, RDFEntity):
    """
    x-Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000365'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000393(Ont00000387, RDFEntity):
    """
    Yaw Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000393'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000487(Ont00000472, RDFEntity):
    """
    Geospatial Location
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000487'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000794(Ont00000207, RDFEntity):
    """
    Geospatial Ellipse
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000794'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000801(Ont00000161, RDFEntity):
    """
    y-Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000801'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000817(Ont00000207, RDFEntity):
    """
    Geospatial Line String
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000817'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001035(Ont00000387, RDFEntity):
    """
    Pitch Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001035'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001081(Ont00000574, RDFEntity):
    """
    Geographic Feature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001081'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001106(Ont00000387, RDFEntity):
    """
    Roll Axis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001106'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001195(Ont00000207, RDFEntity):
    """
    Geospatial Error Region
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001195'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001197(Ont00000574, RDFEntity):
    """
    Anthropogenic Feature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001197'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000031(Ont00001081, RDFEntity):
    """
    Atmospheric Feature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000031'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000224(Ont00001197, RDFEntity):
    """
    Populated place
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000224'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000400(Ont00001197, RDFEntity):
    """
    Park
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000400'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000563(Ont00001081, RDFEntity):
    """
    Hydrographic Feature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000563'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000873(Ont00001081, RDFEntity):
    """
    Physiographic Feature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000873'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000939(Ont00000817, RDFEntity):
    """
    Geospatial Line
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000939'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001037(Ont00001197, RDFEntity):
    """
    Constructed Feature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001037'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001130(Ont00000817, RDFEntity):
    """
    Geospatial Polygon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001130'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000072(Ont00000224, RDFEntity):
    """
    Low Density Residential Area
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000072'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000358(Ont00001130, RDFEntity):
    """
    Geospatial Region Bounding Box
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000358'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000489(Ont00000224, RDFEntity):
    """
    High Density Residential Area
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000489'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Ont00000017.model_rebuild()
Ont00000068.model_rebuild()
Ont00000070.model_rebuild()
Neb67d9c858f34c2fb95b7ba17a1334f7b2.model_rebuild()
Ont00000161.model_rebuild()
Ont00000170.model_rebuild()
Ont00000188.model_rebuild()
Ont00000205.model_rebuild()
Ont00000207.model_rebuild()
Ont00000218.model_rebuild()
Ont00000221.model_rebuild()
Ont00000297.model_rebuild()
Ont00000373.model_rebuild()
Ont00000387.model_rebuild()
Ont00000472.model_rebuild()
Ont00000574.model_rebuild()
Ont00000722.model_rebuild()
Ont00000755.model_rebuild()
Ont00000779.model_rebuild()
Ont00000911.model_rebuild()
Ont00001016.model_rebuild()
Ont00001040.model_rebuild()
Ont00001259.model_rebuild()
Ont00001341.model_rebuild()
Ont00001348.model_rebuild()
Ont00002000.model_rebuild()
Ont00000125.model_rebuild()
Ont00000163.model_rebuild()
Ont00000213.model_rebuild()
Ont00000251.model_rebuild()
Ont00000365.model_rebuild()
Ont00000393.model_rebuild()
Ont00000487.model_rebuild()
Ont00000794.model_rebuild()
Ont00000801.model_rebuild()
Ont00000817.model_rebuild()
Ont00001035.model_rebuild()
Ont00001081.model_rebuild()
Ont00001106.model_rebuild()
Ont00001195.model_rebuild()
Ont00001197.model_rebuild()
Ont00000031.model_rebuild()
Ont00000224.model_rebuild()
Ont00000400.model_rebuild()
Ont00000563.model_rebuild()
Ont00000873.model_rebuild()
Ont00000939.model_rebuild()
Ont00001037.model_rebuild()
Ont00001130.model_rebuild()
Ont00000072.model_rebuild()
Ont00000358.model_rebuild()
Ont00000489.model_rebuild()
