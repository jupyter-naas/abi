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


class Ont00000009(RDFEntity):
    """
    Mass Density
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000009'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000119(RDFEntity):
    """
    Spatial Orientation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000119'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000284(RDFEntity):
    """
    Strength
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000284'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000295(RDFEntity):
    """
    Wetness
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000295'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000327(RDFEntity):
    """
    Texture
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000327'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000441(RDFEntity):
    """
    Temperature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000441'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000442(RDFEntity):
    """
    Radioactive
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000442'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000614(RDFEntity):
    """
    'Matter' here can also refer to the inertial energy of an object.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000614'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000628(RDFEntity):
    """
    Disposition to Interact with Electromagnetic Radiation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000628'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000632(RDFEntity):
    """
    Magnetism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000632'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000633(RDFEntity):
    """
    When an object is "weighed", in the typical case, it is done so by taking into account the local force of gravity to determine the object's mass, whose standard of measure is the kilogram. The actual unit of measure of weight is the newton.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000633'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000766(RDFEntity):
    """
    Hardness
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000766'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000768(RDFEntity):
    """
    Amount
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000768'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000979(RDFEntity):
    """
    Closure
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000979'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000997(RDFEntity):
    """
    Disrupting Disposition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000997'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001059(RDFEntity):
    """
    Shape Quality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001059'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001118(RDFEntity):
    """
    Surface Tension
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001118'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001182(RDFEntity):
    """
    Phase Angle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001182'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001193(RDFEntity):
    """
    Fatigability
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001193'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001202(RDFEntity):
    """
    Size Quality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001202'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000042(Ont00001059, RDFEntity):
    """
    Semicircular
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000042'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000185(Ont00001059, RDFEntity):
    """
    Blunt
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000185'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000385(Ont00001059, RDFEntity):
    """
    Wide
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000385'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000424(Ont00001059, RDFEntity):
    """
    Sharp
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000424'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000447(Ont00001059, RDFEntity):
    """
    Triangular
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000447'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000464(Ont00001059, RDFEntity):
    """
    Oblong
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000464'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000474(Ont00001059, RDFEntity):
    """
    Curved
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000474'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000484(Ont00001059, RDFEntity):
    """
    Concave Shape
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000484'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000494(Ont00001059, RDFEntity):
    """
    Serrated
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000494'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000512(Ont00000628, RDFEntity):
    """
    Radiation Emissivity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000512'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000548(Ont00000997, RDFEntity):
    """
    Vulnerability
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000548'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000578(Ont00001059, RDFEntity):
    """
    Sloped
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000578'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000579(Ont00001059, RDFEntity):
    """
    Thin
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000579'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000590(Ont00001059, RDFEntity):
    """
    Convex Shape
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000590'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000784(Ont00000628, RDFEntity):
    """
    Optical Property
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000784'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000803(Ont00001059, RDFEntity):
    """
    Round
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000803'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000805(Ont00001059, RDFEntity):
    """
    Coiled
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000805'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000815(Ont00001059, RDFEntity):
    """
    Folded
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000815'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000835(Ont00001059, RDFEntity):
    """
    Body Shape
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000835'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000861(Ont00001059, RDFEntity):
    """
    Split
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000861'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000885(Ont00001059, RDFEntity):
    """
    Wavy
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000885'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000991(Ont00001059, RDFEntity):
    """
    Bent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000991'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001001(Ont00001059, RDFEntity):
    """
    Drooping
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001001'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001026(Ont00000119, RDFEntity):
    """
    Pointing Orientation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001026'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001055(Ont00001059, RDFEntity):
    """
    Branched
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001055'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001063(Ont00001059, RDFEntity):
    """
    Straight
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001063'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001065(Ont00001202, RDFEntity):
    """
    Two Dimensional Extent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001065'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001137(Ont00000628, RDFEntity):
    """
    Radiation Reflectivity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001137'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001177(Ont00000119, RDFEntity):
    """
    Roll Orientation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001177'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001199(Ont00001059, RDFEntity):
    """
    Protruding
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001199'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001280(Ont00001059, RDFEntity):
    """
    Flat
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001280'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001291(Ont00000628, RDFEntity):
    """
    Radiation Absorptivity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001291'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001294(Ont00001202, RDFEntity):
    """
    Three Dimensional Extent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001294'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001296(Ont00000119, RDFEntity):
    """
    Pitch Orientation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001296'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001318(Ont00000119, RDFEntity):
    """
    Yaw Orientation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001318'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001360(Ont00001059, RDFEntity):
    """
    Three Dimensional Shape
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001360'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001367(Ont00001202, RDFEntity):
    """
    Subclasses of one dimensional extent are included for usability. It is doubtful any of them can be objectively distinguished (on the side of the bearing entity) without some reference to external properties such as orientation and perspective.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001367'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001369(Ont00001059, RDFEntity):
    """
    Rectangular
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001369'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001384(Ont00000628, RDFEntity):
    """
    Note that it is important to specify the frequency of electromagnetic radiation when representing a bearer's Opacity since a bearer may be Opaque with respect to electromagnetic radiation of one frequency, but be transparent with respect to electromagnetic radiation of another frequency. Unless otherwise stated, statements about a bearer's Opacity are assumed to be about electromagnetic radiation with a frequency in the visible spectrum.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001384'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000105(Ont00001369, RDFEntity):
    """
    Square
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000105'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000112(Ont00001384, RDFEntity):
    """
    Translucent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000112'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000281(Ont00001137, RDFEntity):
    """
    Albedo
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000281'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000283(Ont00001360, RDFEntity):
    """
    Cylindrical
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000283'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000324(Ont00001367, RDFEntity):
    """
    Width
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000324'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000378(Ont00000784, RDFEntity):
    """
    Color
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000378'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000478(Ont00001360, RDFEntity):
    """
    Cuboidal
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000478'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000525(Ont00001384, RDFEntity):
    """
    Transparent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000525'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000541(Ont00001367, RDFEntity):
    """
    Diameter
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000541'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000560(Ont00001360, RDFEntity):
    """
    Cone Shape
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000560'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000620(Ont00001384, RDFEntity):
    """
    Radiopacity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000620'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000648(Ont00000784, RDFEntity):
    """
    Color Brightness
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000648'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000733(Ont00001360, RDFEntity):
    """
    Spherical
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000733'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000738(Ont00001367, RDFEntity):
    """
    Length
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000738'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000759(Ont00000784, RDFEntity):
    """
    Color Saturation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000759'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000826(Ont00001137, RDFEntity):
    """
    Refractivity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000826'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000892(Ont00001367, RDFEntity):
    """
    Depth
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000892'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000912(Ont00001360, RDFEntity):
    """
    Pyramidal
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000912'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000967(Ont00001367, RDFEntity):
    """
    Height
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000967'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001126(Ont00000784, RDFEntity):
    """
    There are a variety of photometric measurements, such as luminous flux/power or luminous intensity, whose units are lumen and candela respectively, which attempt to describe properties associated with the perception of light. These are weighted measurements, typically by the luminosity function, as thus exist on the side of information content. It is a point of further development to add the needed intrinsic properties of radiation that such measurements are about.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001126'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001186(Ont00000784, RDFEntity):
    """
    Color Hue
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001186'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001220(Ont00001384, RDFEntity):
    """
    Opaque
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001220'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001293(Ont00001367, RDFEntity):
    """
    Perimeter
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001293'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000082(Ont00000378, RDFEntity):
    """
    Green
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000082'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000196(Ont00000378, RDFEntity):
    """
    Purple
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000196'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000257(Ont00000620, RDFEntity):
    """
    Radiopaque
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000257'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000439(Ont00000378, RDFEntity):
    """
    Black
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000439'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000446(Ont00001293, RDFEntity):
    """
    Circumference
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000446'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000450(Ont00000378, RDFEntity):
    """
    Silver Color
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000450'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000459(Ont00001126, RDFEntity):
    """
    Fluorescence
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000459'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000528(Ont00000378, RDFEntity):
    """
    White
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000528'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000565(Ont00000478, RDFEntity):
    """
    Cube Shape
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000565'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000607(Ont00000892, RDFEntity):
    """
    Thickness
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000607'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000695(Ont00000620, RDFEntity):
    """
    Radiolucent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000695'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000787(Ont00000967, RDFEntity):
    """
    Altitude
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000787'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000797(Ont00000378, RDFEntity):
    """
    Hazel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000797'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000818(Ont00000378, RDFEntity):
    """
    Orange
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000818'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000872(Ont00000378, RDFEntity):
    """
    Brown
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000872'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000913(Ont00000378, RDFEntity):
    """
    Maroon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000913'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000941(Ont00001126, RDFEntity):
    """
    Phosphorescence
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000941'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000975(Ont00000378, RDFEntity):
    """
    Cyan
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000975'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001079(Ont00000378, RDFEntity):
    """
    Blond
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001079'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001113(Ont00000378, RDFEntity):
    """
    Magenta
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001113'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001142(Ont00000378, RDFEntity):
    """
    Violet
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001142'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001189(Ont00000378, RDFEntity):
    """
    Blue
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001189'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001225(Ont00000378, RDFEntity):
    """
    Yellow
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001225'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001277(Ont00000378, RDFEntity):
    """
    Red
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001277'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001333(Ont00000378, RDFEntity):
    """
    Rosy
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001333'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001349(Ont00000378, RDFEntity):
    """
    Grey
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001349'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001354(Ont00000378, RDFEntity):
    """
    Vermilion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001354'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001377(Ont00000378, RDFEntity):
    """
    Gold Color
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001377'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Ont00000009.model_rebuild()
Ont00000119.model_rebuild()
Ont00000284.model_rebuild()
Ont00000295.model_rebuild()
Ont00000327.model_rebuild()
Ont00000441.model_rebuild()
Ont00000442.model_rebuild()
Ont00000614.model_rebuild()
Ont00000628.model_rebuild()
Ont00000632.model_rebuild()
Ont00000633.model_rebuild()
Ont00000766.model_rebuild()
Ont00000768.model_rebuild()
Ont00000979.model_rebuild()
Ont00000997.model_rebuild()
Ont00001059.model_rebuild()
Ont00001118.model_rebuild()
Ont00001182.model_rebuild()
Ont00001193.model_rebuild()
Ont00001202.model_rebuild()
Ont00000042.model_rebuild()
Ont00000185.model_rebuild()
Ont00000385.model_rebuild()
Ont00000424.model_rebuild()
Ont00000447.model_rebuild()
Ont00000464.model_rebuild()
Ont00000474.model_rebuild()
Ont00000484.model_rebuild()
Ont00000494.model_rebuild()
Ont00000512.model_rebuild()
Ont00000548.model_rebuild()
Ont00000578.model_rebuild()
Ont00000579.model_rebuild()
Ont00000590.model_rebuild()
Ont00000784.model_rebuild()
Ont00000803.model_rebuild()
Ont00000805.model_rebuild()
Ont00000815.model_rebuild()
Ont00000835.model_rebuild()
Ont00000861.model_rebuild()
Ont00000885.model_rebuild()
Ont00000991.model_rebuild()
Ont00001001.model_rebuild()
Ont00001026.model_rebuild()
Ont00001055.model_rebuild()
Ont00001063.model_rebuild()
Ont00001065.model_rebuild()
Ont00001137.model_rebuild()
Ont00001177.model_rebuild()
Ont00001199.model_rebuild()
Ont00001280.model_rebuild()
Ont00001291.model_rebuild()
Ont00001294.model_rebuild()
Ont00001296.model_rebuild()
Ont00001318.model_rebuild()
Ont00001360.model_rebuild()
Ont00001367.model_rebuild()
Ont00001369.model_rebuild()
Ont00001384.model_rebuild()
Ont00000105.model_rebuild()
Ont00000112.model_rebuild()
Ont00000281.model_rebuild()
Ont00000283.model_rebuild()
Ont00000324.model_rebuild()
Ont00000378.model_rebuild()
Ont00000478.model_rebuild()
Ont00000525.model_rebuild()
Ont00000541.model_rebuild()
Ont00000560.model_rebuild()
Ont00000620.model_rebuild()
Ont00000648.model_rebuild()
Ont00000733.model_rebuild()
Ont00000738.model_rebuild()
Ont00000759.model_rebuild()
Ont00000826.model_rebuild()
Ont00000892.model_rebuild()
Ont00000912.model_rebuild()
Ont00000967.model_rebuild()
Ont00001126.model_rebuild()
Ont00001186.model_rebuild()
Ont00001220.model_rebuild()
Ont00001293.model_rebuild()
Ont00000082.model_rebuild()
Ont00000196.model_rebuild()
Ont00000257.model_rebuild()
Ont00000439.model_rebuild()
Ont00000446.model_rebuild()
Ont00000450.model_rebuild()
Ont00000459.model_rebuild()
Ont00000528.model_rebuild()
Ont00000565.model_rebuild()
Ont00000607.model_rebuild()
Ont00000695.model_rebuild()
Ont00000787.model_rebuild()
Ont00000797.model_rebuild()
Ont00000818.model_rebuild()
Ont00000872.model_rebuild()
Ont00000913.model_rebuild()
Ont00000941.model_rebuild()
Ont00000975.model_rebuild()
Ont00001079.model_rebuild()
Ont00001113.model_rebuild()
Ont00001142.model_rebuild()
Ont00001189.model_rebuild()
Ont00001225.model_rebuild()
Ont00001277.model_rebuild()
Ont00001333.model_rebuild()
Ont00001349.model_rebuild()
Ont00001354.model_rebuild()
Ont00001377.model_rebuild()
