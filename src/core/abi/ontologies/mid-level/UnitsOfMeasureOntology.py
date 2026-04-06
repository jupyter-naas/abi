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


class Ont00000120(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000120'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000061(Ont00000120, RDFEntity):
    """
    Measurement Unit of Flow
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000061'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000074(Ont00000120, RDFEntity):
    """
    Measurement Unit of Acceleration
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000074'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000140(Ont00000120, RDFEntity):
    """
    The type of particle quantified is typically either atoms or molecules, but may also be protons, neutrons, electrons, quarks, or other particles. The type of particle being measured should always be specified along with the measurement and its unit.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000140'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000198(Ont00000120, RDFEntity):
    """
    Measurement Unit of Sound Level
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000198'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000217(Ont00000120, RDFEntity):
    """
    Measurement Unit of Area
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000217'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000229(Ont00000120, RDFEntity):
    """
    Measurement Unit of Power
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000229'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000239(Ont00000120, RDFEntity):
    """
    Measurement Unit of Mass
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000239'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000444(Ont00000120, RDFEntity):
    """
    Measurement Unit of Energy
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000444'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000497(Ont00000120, RDFEntity):
    """
    Measurement Unit of Force
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000497'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000502(Ont00000120, RDFEntity):
    """
    Measurement Unit of Area Moment of Inertia
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000502'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000527(Ont00000120, RDFEntity):
    """
    Measurement Unit of Rotational Inertia
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000527'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000659(Ont00000120, RDFEntity):
    """
    Measurement Unit of Torque
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000659'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000707(Ont00000120, RDFEntity):
    """
    Measurement Unit of Angle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000707'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000770(Ont00000120, RDFEntity):
    """
    Measurement Unit of Density
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000770'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000844(Ont00000120, RDFEntity):
    """
    Measurement Unit of Temperature
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000844'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000852(Ont00000120, RDFEntity):
    """
    Measurement Unit of Work
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000852'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000940(Ont00000120, RDFEntity):
    """
    Measurement Unit of Momentum
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000940'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000959(Ont00000120, RDFEntity):
    """
    Measurement Unit of Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000959'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000969(Ont00000120, RDFEntity):
    """
    Measurement Unit of Speed
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000969'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001004(Ont00000120, RDFEntity):
    """
    Measurement Unit of Electromagnetic Force
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001004'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001090(Ont00000120, RDFEntity):
    """
    Measurement Unit of Pressure
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001090'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001290(Ont00000120, RDFEntity):
    """
    Measurement Unit of Length
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001290'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001317(Ont00000120, RDFEntity):
    """
    Measurement Unit of Volume
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001317'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001345(Ont00000120, RDFEntity):
    """
    Measurement Unit of Impulse
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001345'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001357(Ont00000120, RDFEntity):
    """
    Measurement Unit of Time
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001357'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000374(Ont00000061, RDFEntity):
    """
    Measurement Unit of Volumetric Flow Rate
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000374'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001307(Ont00000061, RDFEntity):
    """
    Measurement Unit of Mass Flow Rate
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001307'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Ont00000120.model_rebuild()
Ont00000061.model_rebuild()
Ont00000074.model_rebuild()
Ont00000140.model_rebuild()
Ont00000198.model_rebuild()
Ont00000217.model_rebuild()
Ont00000229.model_rebuild()
Ont00000239.model_rebuild()
Ont00000444.model_rebuild()
Ont00000497.model_rebuild()
Ont00000502.model_rebuild()
Ont00000527.model_rebuild()
Ont00000659.model_rebuild()
Ont00000707.model_rebuild()
Ont00000770.model_rebuild()
Ont00000844.model_rebuild()
Ont00000852.model_rebuild()
Ont00000940.model_rebuild()
Ont00000959.model_rebuild()
Ont00000969.model_rebuild()
Ont00001004.model_rebuild()
Ont00001090.model_rebuild()
Ont00001290.model_rebuild()
Ont00001317.model_rebuild()
Ont00001345.model_rebuild()
Ont00001357.model_rebuild()
Ont00000374.model_rebuild()
Ont00001307.model_rebuild()
