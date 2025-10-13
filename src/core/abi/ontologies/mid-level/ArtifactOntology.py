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


class Ont00000038(RDFEntity):
    """
    System Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000038'
    _property_uris: ClassVar[dict] = {}
    pass

class N277759fb406a4e329e1bd31be5f6ad35b4(RDFEntity):
    _class_uri: ClassVar[str] = 'n277759fb406a4e329e1bd31be5f6ad35b4'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000170(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000170'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000205(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000205'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000253(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000253'
    _property_uris: ClassVar[dict] = {}
    pass

class N277759fb406a4e329e1bd31be5f6ad35b14(RDFEntity):
    _class_uri: ClassVar[str] = 'n277759fb406a4e329e1bd31be5f6ad35b14'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000323(RDFEntity):
    """
    Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000323'
    _property_uris: ClassVar[dict] = {}
    pass

class N277759fb406a4e329e1bd31be5f6ad35b21(RDFEntity):
    _class_uri: ClassVar[str] = 'n277759fb406a4e329e1bd31be5f6ad35b21'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000556(RDFEntity):
    """
    Depending on the nature of the Flight or Mission, the Payload of a Vehicle may include cargo, passengers, flight crew, munitions, scientific instruments or experiments, or other equipment. Extra fuel, when optionally carried, is also considered part of the payload.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000556'
    _property_uris: ClassVar[dict] = {}
    pass

class N277759fb406a4e329e1bd31be5f6ad35b32(RDFEntity):
    _class_uri: ClassVar[str] = 'n277759fb406a4e329e1bd31be5f6ad35b32'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000591(RDFEntity):
    """
    Artifact Location
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000591'
    _property_uris: ClassVar[dict] = {}
    pass

class N277759fb406a4e329e1bd31be5f6ad35b37(RDFEntity):
    _class_uri: ClassVar[str] = 'n277759fb406a4e329e1bd31be5f6ad35b37'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000627(RDFEntity):
    """
    Infrastructure Element
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000627'
    _property_uris: ClassVar[dict] = {}
    pass

class N277759fb406a4e329e1bd31be5f6ad35b44(RDFEntity):
    _class_uri: ClassVar[str] = 'n277759fb406a4e329e1bd31be5f6ad35b44'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000686(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000686'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000740(RDFEntity):
    """
    This class is designed to group continuants according to a very broad criterion and is not intended to be used as a parent class for entities that can be more specifically represented under another class. Hence, Natural Resource may be an appropriate subtype but Money, Oil, and Gold Mine are not.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000740'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000758(RDFEntity):
    """
    Component Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000758'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000856(RDFEntity):
    """
    Artifact History
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000856'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000870(RDFEntity):
    """
    Infrastructure System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000870'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000929(RDFEntity):
    """
    Part Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000929'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000958(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000958'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000965(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000965'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000995(RDFEntity):
    """
    Material Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000995'
    _property_uris: ClassVar[dict] = {}
    pass

class N277759fb406a4e329e1bd31be5f6ad35b67(RDFEntity):
    _class_uri: ClassVar[str] = 'n277759fb406a4e329e1bd31be5f6ad35b67'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001141(RDFEntity):
    """
    The disposition will typically be a function of an artifact, which is often designed to be part of some Infrastructure system. But not always. In some cases an entity may be repurposed to be an element of some Infrastructure. In those cases it is a capability of that entity that supports the functioning of the system.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001141'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001168(RDFEntity):
    """
    Reaction Mass
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001168'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001341(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001341'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000002(Ont00000323, RDFEntity):
    """
    Cooling Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000002'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000020(Ont00000995, RDFEntity):
    """
    Container
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000020'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000021(Ont00000995, RDFEntity):
    """
    Sensor Platform
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000021'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000023(Ont00000323, RDFEntity):
    """
    Sensor Deployment Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000023'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000095(Ont00000995, RDFEntity):
    """
    Control Surface
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000095'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000096(Ont00000995, RDFEntity):
    """
    Propulsion System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000096'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000098(Ont00000323, RDFEntity):
    """
    Electrical Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000098'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000103(Ont00000995, RDFEntity):
    """
    Vehicle Compartment
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000103'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000113(Ont00000323, RDFEntity):
    """
    Ventilation Control Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000113'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000117(Ont00000995, RDFEntity):
    """
    Information Processing Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000117'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000118(Ont00000965, RDFEntity):
    """
    Artifact Function Specification
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000118'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000122(Ont00000170, RDFEntity):
    """
    Vehicle Track Point
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000122'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000130(Ont00000995, RDFEntity):
    """
    Power Transformer
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000130'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000136(Ont00000995, RDFEntity):
    """
    Optical Instruments are typically constructed for the purpose of being used to aid in vision or the analysis of light.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000136'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000183(Ont00000323, RDFEntity):
    """
    Fragrance Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000183'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000192(Ont00000995, RDFEntity):
    """
    Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000192'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000206(Ont00000323, RDFEntity):
    """
    Friction Reduction Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000206'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000210(Ont00000995, RDFEntity):
    """
    Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000210'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000236(Ont00000995, RDFEntity):
    """
    Lighting System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000236'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000238(Ont00000995, RDFEntity):
    """
    Propeller
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000238'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000243(Ont00000995, RDFEntity):
    """
    Heat Sink
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000243'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000249(Ont00000995, RDFEntity):
    """
    A Shaft is usually used to connect other components of a drive train that cannot be connected directly either because of the distance between them or the need to allow for relative movement between those components.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000249'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000254(Ont00000995, RDFEntity):
    """
    Transportation Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000254'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000256(Ont00000995, RDFEntity):
    """
    Fluid Control Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000256'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000273(Ont00000323, RDFEntity):
    """
    Communication Interference Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000273'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000288(Ont00000995, RDFEntity):
    """
    Power Source
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000288'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000292(Ont00000686, RDFEntity):
    """
    Artifact Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000292'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000319(Ont00000965, RDFEntity):
    """
    Artifact Design
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000319'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000328(Ont00000870, RDFEntity):
    """
    Transportation Infrastructure
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000328'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000342(Ont00000995, RDFEntity):
    """
    Brake
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000342'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000346(Ont00000995, RDFEntity):
    """
    Communication Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000346'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000348(Ont00000995, RDFEntity):
    """
    Filter
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000348'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000353(Ont00000323, RDFEntity):
    """
    Research Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000353'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000372(Ont00000995, RDFEntity):
    """
    Power Transformer Rectifier Unit
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000372'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000397(Ont00000995, RDFEntity):
    """
    Combustion Chamber
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000397'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000403(Ont00000323, RDFEntity):
    """
    Diffraction Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000403'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000422(Ont00000323, RDFEntity):
    """
    Communication Reception Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000422'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000437(Ont00000323, RDFEntity):
    """
    Enhancing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000437'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000445(Ont00000995, RDFEntity):
    """
    Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000445'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000448(Ont00000323, RDFEntity):
    """
    Motion Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000448'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000451(Ont00000323, RDFEntity):
    """
    Collimation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000451'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000452(Ont00000323, RDFEntity):
    """
    Timekeeping Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000452'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000453(Ont00000995, RDFEntity):
    """
    Controlling air quality typically involves temperature control, oxygen replenishment, and removal of moisture, odor, smoke, heat, dust, airborne bacteria, carbon dioxide, and other undesired gases or particulates.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000453'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000458(Ont00000995, RDFEntity):
    """
    Coupling
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000458'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000466(Ont00000323, RDFEntity):
    """
    Orientation Control Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000466'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000480(Ont00000323, RDFEntity):
    """
    Life Support Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000480'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000488(Ont00000995, RDFEntity):
    """
    Tripod
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000488'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000491(Ont00000323, RDFEntity):
    """
    Detonating Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000491'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000504(Ont00000323, RDFEntity):
    """
    Optical Processing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000504'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000537(Ont00000995, RDFEntity):
    """
    Financial Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000537'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000561(Ont00000995, RDFEntity):
    """
    Dam
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000561'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000575(Ont00000965, RDFEntity):
    """
    Quality Specification
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000575'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000577(Ont00000995, RDFEntity):
    """
    Power Rectifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000577'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000581(Ont00000995, RDFEntity):
    """
    Tool
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000581'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000601(Ont00000323, RDFEntity):
    """
    Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000601'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000603(Ont00000323, RDFEntity):
    """
    Navigation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000603'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000623(Ont00000323, RDFEntity):
    """
    Impact Shielding Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000623'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000629(Ont00000323, RDFEntity):
    """
    Deception Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000629'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000635(Ont00000323, RDFEntity):
    """
    Refraction Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000635'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000651(Ont00000323, RDFEntity):
    """
    Containing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000651'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000652(Ont00000995, RDFEntity):
    """
    Decoy
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000652'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000663(Ont00000995, RDFEntity):
    """
    Power Transmission Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000663'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000665(Ont00000323, RDFEntity):
    """
    Cleaning Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000665'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000668(Ont00000995, RDFEntity):
    """
    Battery Terminal
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000668'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000679(Ont00000323, RDFEntity):
    """
    Attitude Control Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000679'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000689(Ont00000323, RDFEntity):
    """
    Switch Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000689'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000706(Ont00000995, RDFEntity):
    """
    Terminal Board
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000706'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000713(Ont00000995, RDFEntity):
    """
    Vehicle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000713'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000719(Ont00000995, RDFEntity):
    """
    Counterfeit Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000719'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000727(Ont00000323, RDFEntity):
    """
    Communication Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000727'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000730(Ont00000995, RDFEntity):
    """
    Hydraulic Power Transfer Unit
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000730'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000736(Ont00000995, RDFEntity):
    """
    Transducer
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000736'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000742(Ont00000995, RDFEntity):
    """
    Ignition System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000742'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000767(Ont00000995, RDFEntity):
    """
    A Lubrication System typical consists of a reservoir, pump, heat exchanger, filter, regulator, valves, sensors, pipes, and hoses. In some cases it also includes the passageways and openings within the artifact it is designed to lubricate. For example, the oil holes in a bearing and crankshaft.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000767'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000771(Ont00000995, RDFEntity):
    """
    Imaging Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000771'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000776(Ont00000323, RDFEntity):
    """
    Signal Detection Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000776'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000781(Ont00000995, RDFEntity):
    """
    Control System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000781'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000791(Ont00000323, RDFEntity):
    """
    Chemical Reaction Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000791'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000798(Ont00000995, RDFEntity):
    """
    This class continues to use the word ‘bearing’ in its rdfs:label for legacy reasons. It should be understood that all instances of this class are carriers of information content entities and only, strictly speaking, a bearer of their concretizations.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000798'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000809(Ont00000323, RDFEntity):
    """
    Submersible Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000809'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000811(Ont00000323, RDFEntity):
    """
    Radio Wave Conversion Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000811'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000893(Ont00000995, RDFEntity):
    """
    An empty notebook, when manufactured, is a medium but not yet a carrier of information content. However, a book, in the sense of a novel or collection of philosophical essays or poems, depends necessarily on it carrying some information content. Thus, there are no empty books. Likewise, there are no empty databases, only portions of digital storage that have not yet been configured to carry some information content according to a database software application.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000893'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000904(Ont00000205, RDFEntity):
    """
    Vehicle Track
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000904'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000932(Ont00000323, RDFEntity):
    """
    Computing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000932'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000937(Ont00000323, RDFEntity):
    """
    Inhibiting Motion Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000937'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000954(Ont00000870, RDFEntity):
    """
    Telecommunication Infrastructure
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000954'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001013(Ont00000323, RDFEntity):
    """
    Heating Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001013'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001036(Ont00000995, RDFEntity):
    """
    Communication System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001036'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001042(Ont00000995, RDFEntity):
    """
    Equipment Mount
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001042'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001044(Ont00000323, RDFEntity):
    """
    Nuclear Radiation Detection Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001044'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001060(Ont00000995, RDFEntity):
    """
    Fuel System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001060'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001067(Ont00000995, RDFEntity):
    """
    Laser
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001067'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001070(Ont00000323, RDFEntity):
    """
    Fluid Control Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001070'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001071(Ont00000323, RDFEntity):
    """
    Payload Capacity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001071'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001084(Ont00000995, RDFEntity):
    """
    Portion of Processed Material
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001084'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001085(Ont00000323, RDFEntity):
    """
    Reflection Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001085'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001100(Ont00000323, RDFEntity):
    """
    Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001100'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001103(Ont00000686, RDFEntity):
    """
    Artifact Model Name
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001103'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001134(Ont00000995, RDFEntity):
    """
    Vehicle Frame
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001134'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001140(Ont00000995, RDFEntity):
    """
    Flywheel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001140'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001153(Ont00000323, RDFEntity):
    """
    Damaging Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001153'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001169(Ont00000323, RDFEntity):
    """
    Communication Relay Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001169'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001174(Ont00000323, RDFEntity):
    """
    Electromagnetic Shielding Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001174'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001187(Ont00000995, RDFEntity):
    """
    Navigation System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001187'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001200(Ont00000323, RDFEntity):
    """
    Structural Support Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001200'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001211(Ont00000323, RDFEntity):
    """
    Lifting Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001211'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001218(Ont00000323, RDFEntity):
    """
    Signal Processing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001218'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001241(Ont00000323, RDFEntity):
    """
    Sensor Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001241'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001253(Ont00000323, RDFEntity):
    """
    Fuel Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001253'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001301(Ont00000323, RDFEntity):
    """
    Service Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001301'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001306(Ont00000323, RDFEntity):
    """
    Observation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001306'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001310(Ont00000323, RDFEntity):
    """
    Covering Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001310'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001313(Ont00000995, RDFEntity):
    """
    Article of Clothing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001313'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001323(Ont00000323, RDFEntity):
    """
    Bearing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001323'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001343(Ont00000995, RDFEntity):
    """
    Circuit Breaker
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001343'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001346(Ont00000995, RDFEntity):
    """
    Legal Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001346'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001350(Ont00000323, RDFEntity):
    """
    Thermal Control Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001350'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001361(Ont00000323, RDFEntity):
    """
    Healing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001361'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001366(Ont00000323, RDFEntity):
    """
    Powering Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001366'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001370(Ont00000995, RDFEntity):
    """
    Machine Bearing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001370'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001371(Ont00000323, RDFEntity):
    """
    Electromagnetic Induction Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001371'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001381(Ont00000995, RDFEntity):
    """
    Medical Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001381'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001999(Ont00000323, RDFEntity):
    """
    Although its basic function remains the same, a Filter can be used in 2 different ways:
    (1) to allow only the desired entities to pass through (e.g. removing dirt from engine oil); or
    (2) to allow everything except the desired entities to pass through (e.g. panning for gold).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001999'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000012(Ont00000781, RDFEntity):
    """
    Propulsion Control System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000012'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000018(Ont00001346, RDFEntity):
    """
    Title Document
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000018'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000022(Ont00000422, RDFEntity):
    """
    Radio Communication Reception Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000022'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000030(Ont00000288, RDFEntity):
    """
    Nuclear Reactor
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000030'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000034(Ont00000448, RDFEntity):
    """
    Conveyance Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000034'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000036(Ont00001301, RDFEntity):
    """
    Waste Management Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000036'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000056(Ont00000210, RDFEntity):
    """
    Reaction Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000056'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000062(Ont00001100, RDFEntity):
    """
    Frequency Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000062'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000066(Ont00001301, RDFEntity):
    """
    Military Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000066'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000076(Ont00000727, RDFEntity):
    """
    Wired Communication Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000076'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000081(Ont00000445, RDFEntity):
    """
    Cutting Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000081'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000092(Ont00000736, RDFEntity):
    """
    Bidirectional Transducer
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000092'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000111(Ont00000256, RDFEntity):
    """
    Air Inlet
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000111'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000116(Ont00000256, RDFEntity):
    """
    Pump
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000116'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000132(Ont00000117, RDFEntity):
    """
    Recording Device
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000132'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000143(Ont00000103, RDFEntity):
    """
    Cargo Cabin
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000143'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000145(Ont00000445, RDFEntity):
    """
    Incendiary Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000145'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000153(Ont00000781, RDFEntity):
    """
    Generator Control Unit
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000153'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000159(Ont00000798, RDFEntity):
    """
    Material Copy of a Timekeeping Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000159'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000160(Ont00000581, RDFEntity):
    """
    Manual Tool
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000160'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000189(Ont00000798, RDFEntity):
    """
    Material Copy of a Certificate
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000189'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000199(Ont00000771, RDFEntity):
    """
    Camera
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000199'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000212(Ont00000445, RDFEntity):
    """
    Chemical Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000212'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000230(Ont00000136, RDFEntity):
    """
    Diffraction Grating
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000230'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000244(Ont00001153, RDFEntity):
    """
    Fragmentation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000244'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000252(Ont00000256, RDFEntity):
    """
    Nozzle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000252'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000264(Ont00000020, RDFEntity):
    """
    Hydraulic Fluid Reservoir
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000264'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000266(Ont00001381, RDFEntity):
    """
    Hearing Aid
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000266'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000267(Ont00000791, RDFEntity):
    """
    Catalyst Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000267'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000277(Ont00000445, RDFEntity):
    """
    Nuclear Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000277'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000282(Ont00000719, RDFEntity):
    """
    Counterfeit Financial Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000282'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000287(Ont00001187, RDFEntity):
    """
    Inertial Navigation System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000287'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000289(Ont00000601, RDFEntity):
    """
    Radar Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000289'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000301(Ont00000663, RDFEntity):
    """
    Vehicle Transmission
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000301'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000303(Ont00001036, RDFEntity):
    """
    Intercommunication System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000303'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000304(Ont00000771, RDFEntity):
    """
    Microscope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000304'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000306(Ont00001370, RDFEntity):
    """
    Hinge
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000306'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000307(Ont00001084, RDFEntity):
    """
    Portion of Food
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000307'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000309(Ont00001301, RDFEntity):
    """
    Healthcare Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000309'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000311(Ont00001999, RDFEntity):
    """
    Filtration Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000311'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000317(Ont00001218, RDFEntity):
    """
    Electronic Signal Processing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000317'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000321(Ont00001301, RDFEntity):
    """
    Residential Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000321'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000338(Ont00000256, RDFEntity):
    """
    Fan
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000338'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000350(Ont00000453, RDFEntity):
    """
    Cooling System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000350'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000407(Ont00000098, RDFEntity):
    """
    Electrical Resistance Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000407'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000409(Ont00000742, RDFEntity):
    """
    Spark Ignition System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000409'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000411(Ont00001100, RDFEntity):
    """
    Speed Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000411'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000412(Ont00000791, RDFEntity):
    """
    Oxidizer Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000412'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000420(Ont00000117, RDFEntity):
    """
    Computer
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000420'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000440(Ont00000713, RDFEntity):
    """
    Watercraft
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000440'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000454(Ont00000742, RDFEntity):
    """
    Compression Ignition System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000454'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000457(Ont00001084, RDFEntity):
    """
    Portion of Material
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000457'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000475(Ont00000537, RDFEntity):
    """
    Portion of Cash
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000475'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000481(Ont00001301, RDFEntity):
    """
    Research and Development Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000481'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000495(Ont00000273, RDFEntity):
    """
    Radio Communication Interference Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000495'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000516(Ont00000288, RDFEntity):
    """
    Pneumatic Power Source
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000516'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000534(Ont00001153, RDFEntity):
    """
    Cutting Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000534'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000547(Ont00000771, RDFEntity):
    """
    Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000547'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000549(Ont00000254, RDFEntity):
    """
    Water Transportation Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000549'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000552(Ont00000445, RDFEntity):
    """
    Explosive Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000552'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000569(Ont00000736, RDFEntity):
    """
    Sensor
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000569'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000586(Ont00000238, RDFEntity):
    """
    Controllable Pitch Propeller
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000586'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000597(Ont00000798, RDFEntity):
    """
    Material Copy of a Instrument Display Panel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000597'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000598(Ont00000256, RDFEntity):
    """
    Valve
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000598'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000600(Ont00001301, RDFEntity):
    """
    Legal Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000600'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000618(Ont00000713, RDFEntity):
    """
    Ground Vehicle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000618'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000625(Ont00000256, RDFEntity):
    """
    Nozzle Throat
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000625'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000638(Ont00000210, RDFEntity):
    """
    Heat Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000638'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000656(Ont00000445, RDFEntity):
    """
    Radiological Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000656'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000657(Ont00001100, RDFEntity):
    """
    Distance Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000657'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000661(Ont00001301, RDFEntity):
    """
    Government Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000661'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000678(Ont00000098, RDFEntity):
    """
    Voltage Regulating Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000678'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000681(Ont00000236, RDFEntity):
    """
    External Navigation Lighting System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000681'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000682(Ont00000136, RDFEntity):
    """
    Mirror
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000682'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000690(Ont00000346, RDFEntity):
    """
    Telecommunication Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000690'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000691(Ont00000020, RDFEntity):
    """
    Fuel Tank
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000691'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000693(Ont00000575, RDFEntity):
    """
    Mass Specification
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000693'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000694(Ont00000256, RDFEntity):
    """
    Nozzle Mouth
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000694'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000702(Ont00000798, RDFEntity):
    """
    Material Copy of an Image
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000702'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000715(Ont00001381, RDFEntity):
    """
    Prosthesis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000715'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000720(Ont00000020, RDFEntity):
    """
    Cryogenic Storage Dewar
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000720'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000723(Ont00000781, RDFEntity):
    """
    Vehicle Control System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000723'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000756(Ont00000798, RDFEntity):
    """
    Material Copy of a Database
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000756'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000764(Ont00000504, RDFEntity):
    """
    Optical Focusing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000764'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000793(Ont00000256, RDFEntity):
    """
    Fuel Ventilation System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000793'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000795(Ont00000098, RDFEntity):
    """
    Electrical Conduction Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000795'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000799(Ont00000798, RDFEntity):
    """
    Material Copy of a List
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000799'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000804(Ont00000136, RDFEntity):
    """
    Prism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000804'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000806(Ont00000581, RDFEntity):
    """
    Power Tool
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000806'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000808(Ont00000791, RDFEntity):
    """
    Reactant Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000808'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000825(Ont00000346, RDFEntity):
    """
    Telecommunication Network Line
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000825'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000841(Ont00001153, RDFEntity):
    """
    Explosive Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000841'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000849(Ont00000453, RDFEntity):
    """
    Heating System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000849'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000864(Ont00001301, RDFEntity):
    """
    Public Safety Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000864'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000874(Ont00000798, RDFEntity):
    """
    Material Copy of a Video
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000874'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000880(Ont00001301, RDFEntity):
    """
    Religious Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000880'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000886(Ont00000422, RDFEntity):
    """
    Wired Communication Reception Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000886'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000900(Ont00001169, RDFEntity):
    """
    Radio Communication Relay Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000900'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000903(Ont00000346, RDFEntity):
    """
    Radio Communication Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000903'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000918(Ont00000346, RDFEntity):
    """
    Telecommunication Network Node
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000918'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000919(Ont00000575, RDFEntity):
    """
    Parts List
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000919'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000938(Ont00001301, RDFEntity):
    """
    Financial Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000938'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000944(Ont00000601, RDFEntity):
    """
    Thermal Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000944'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000947(Ont00001100, RDFEntity):
    """
    Temperature Measurement Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000947'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000952(Ont00000210, RDFEntity):
    """
    Electric Motor
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000952'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000961(Ont00000098, RDFEntity):
    """
    Current Conversion Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000961'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000963(Ont00000256, RDFEntity):
    """
    Fuel Transfer System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000963'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000980(Ont00001084, RDFEntity):
    """
    Portion of Waste Material
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000980'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000985(Ont00001350, RDFEntity):
    """
    Thermal Insulation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000985'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000994(Ont00000098, RDFEntity):
    """
    Electrical Power Production Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000994'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000998(Ont00001036, RDFEntity):
    """
    Telecommunication Network
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000998'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001002(Ont00000798, RDFEntity):
    """
    Material Copy of a Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001002'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001008(Ont00000445, RDFEntity):
    """
    Biological Weapon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001008'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001027(Ont00000095, RDFEntity):
    """
    Trim Tab
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001027'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001043(Ont00000713, RDFEntity):
    """
    Aircraft
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001043'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001045(Ont00000319, RDFEntity):
    """
    Artifact Model
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001045'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001049(Ont00000288, RDFEntity):
    """
    Electrical Power Source
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001049'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001051(Ont00000445, RDFEntity):
    """
    Projectile Launcher
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001051'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001064(Ont00000798, RDFEntity):
    """
    For information on types of barcodes, see: https://www.scandit.com/types-barcodes-choosing-right-barcode/
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001064'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001087(Ont00001306, RDFEntity):
    """
    Orientation Observation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001087'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001092(Ont00000098, RDFEntity):
    """
    Electrical Power Storage Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001092'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001123(Ont00001153, RDFEntity):
    """
    Poison Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001123'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001129(Ont00000113, RDFEntity):
    """
    Pressurization Control Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001129'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001139(Ont00000713, RDFEntity):
    """
    Spacecraft
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001139'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001148(Ont00000727, RDFEntity):
    """
    Electromagnetic Communication Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001148'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001150(Ont00000445, RDFEntity):
    """
    Portion of Ammunition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001150'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001151(Ont00000893, RDFEntity):
    """
    Portion of Paper
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001151'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001155(Ont00000601, RDFEntity):
    """
    Full Motion Video Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001155'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001156(Ont00000798, RDFEntity):
    """
    Material Copy of a Information Line
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001156'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001157(Ont00000288, RDFEntity):
    """
    Hydraulic Power Source
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001157'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001159(Ont00000537, RDFEntity):
    """
    Bond
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001159'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001160(Ont00000791, RDFEntity):
    """
    Solvent Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001160'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001161(Ont00000719, RDFEntity):
    """
    Counterfeit Legal Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001161'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001179(Ont00000893, RDFEntity):
    """
    Digital Storage Device
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001179'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001185(Ont00000713, RDFEntity):
    """
    Rocket
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001185'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001207(Ont00000136, RDFEntity):
    """
    Optical Lens
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001207'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001210(Ont00001301, RDFEntity):
    """
    Retail Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001210'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001216(Ont00000136, RDFEntity):
    """
    Periscope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001216'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001221(Ont00000210, RDFEntity):
    """
    Physically Powered Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001221'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001233(Ont00001153, RDFEntity):
    """
    Crushing Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001233'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001234(Ont00000791, RDFEntity):
    """
    Neutralization Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001234'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001242(Ont00000736, RDFEntity):
    """
    Actuator
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001242'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001243(Ont00000798, RDFEntity):
    """
    Material Copy of a Document Field
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001243'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001249(Ont00000453, RDFEntity):
    """
    Cabin Pressurization Control System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001249'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001250(Ont00000236, RDFEntity):
    """
    Interior Lighting System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001250'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001252(Ont00000448, RDFEntity):
    """
    Propulsion Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001252'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001265(Ont00001036, RDFEntity):
    """
    Public Address System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001265'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001271(Ont00001169, RDFEntity):
    """
    Wired Communication Relay Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001271'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001273(Ont00001241, RDFEntity):
    """
    Sensor Modality Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001273'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001278(Ont00000537, RDFEntity):
    """
    Stock
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001278'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001281(Ont00000791, RDFEntity):
    """
    Emulsifier Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001281'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001298(Ont00000798, RDFEntity):
    """
    Material Copy of a Document
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001298'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001303(Ont00001306, RDFEntity):
    """
    Position Observation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001303'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001304(Ont00000575, RDFEntity):
    """
    Dimension Specification
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001304'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001316(Ont00001042, RDFEntity):
    """
    Gimbal
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001316'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001326(Ont00000254, RDFEntity):
    """
    Land Transportation Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001326'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001329(Ont00001301, RDFEntity):
    """
    Education Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001329'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001353(Ont00000448, RDFEntity):
    """
    Speed Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001353'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001368(Ont00001306, RDFEntity):
    """
    Motion Observation Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001368'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001372(Ont00000437, RDFEntity):
    """
    Fertilizer Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001372'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001378(Ont00001301, RDFEntity):
    """
    Hospitality Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001378'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000001(Ont00000804, RDFEntity):
    """
    Deflecting Prism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000001'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000019(Ont00000961, RDFEntity):
    """
    Power Inverting Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000019'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000025(Ont00001278, RDFEntity):
    """
    Electronic Stock
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000025'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000028(Ont00000804, RDFEntity):
    """
    Dispersive Prism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000028'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000047(Ont00000598, RDFEntity):
    """
    Flow Control Valves are often more complex than a simple Valve and typically include an Actuator that is capable of automatically adjusting the state of the valve in response to signals from a connected Sensor or Controller.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000047'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000049(Ont00000475, RDFEntity):
    """
    Banknote
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000049'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000050(Ont00000903, RDFEntity):
    """
    Very High Frequency Communication Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000050'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000053(Ont00000618, RDFEntity):
    """
    Ground Motor Vehicle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000053'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000059(Ont00000825, RDFEntity):
    """
    Telephone Line
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000059'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000064(Ont00001298, RDFEntity):
    """
    Material Copy of a Book
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000064'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000069(Ont00001298, RDFEntity):
    """
    Material Copy of a Transcript
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000069'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000075(Ont00000304, RDFEntity):
    """
    Optical Microscope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000075'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000086(Ont00000723, RDFEntity):
    """
    Autopilot System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000086'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000088(Ont00001051, RDFEntity):
    """
    Firearm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000088'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000090(Ont00000547, RDFEntity):
    """
    Infrared Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000090'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000091(Ont00000457, RDFEntity):
    """
    Portion of Coolant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000091'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000093(Ont00001278, RDFEntity):
    """
    Preferred Stock
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000093'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000097(Ont00001207, RDFEntity):
    """
    Complex Optical Lens
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000097'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000152(Ont00000998, RDFEntity):
    """
    Telephone Network
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000152'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000162(Ont00000795, RDFEntity):
    """
    Electrical Connector Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000162'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000174(Ont00000547, RDFEntity):
    """
    Ultraviolet Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000174'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000178(Ont00001150, RDFEntity):
    """
    Arrow
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000178'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000190(Ont00001353, RDFEntity):
    """
    Minimum Speed Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000190'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000194(Ont00000795, RDFEntity):
    """
    Electrical Contact Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000194'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000214(Ont00000289, RDFEntity):
    """
    Moving Target Indication Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000214'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000215(Ont00000547, RDFEntity):
    """
    A Radio Telescope consists of a specialized Antenna and a Radio Receiver and is typically used to receive radio waves from sources in outer space.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000215'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000216(Ont00001150, RDFEntity):
    """
    Shell
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000216'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000231(Ont00001051, RDFEntity):
    """
    Torpedo Tube
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000231'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000233(Ont00001278, RDFEntity):
    """
    Stock Certificate
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000233'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000241(Ont00001064, RDFEntity):
    """
    Material Copy of a Two-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000241'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000247(Ont00001326, RDFEntity):
    """
    Road
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000247'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000255(Ont00000457, RDFEntity):
    """
    Portion of Cryogenic Material
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000255'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000258(Ont00001064, RDFEntity):
    """
    Material Copy of a One-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000258'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000268(Ont00001051, RDFEntity):
    """
    Cannon
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000268'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000269(Ont00000903, RDFEntity):
    """
    Radio Transmitter
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000269'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000299(Ont00000715, RDFEntity):
    """
    Prosthetic Leg
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000299'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000302(Ont00001049, RDFEntity):
    """
    Alternating Current Power Source
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000302'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000310(Ont00000552, RDFEntity):
    """
    Grenade
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000310'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000315(Ont00000918, RDFEntity):
    """
    Telecommunication Switching Node
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000315'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000325(Ont00000903, RDFEntity):
    """
    Radio Transponder
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000325'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000334(Ont00000303, RDFEntity):
    """
    Interphone
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000334'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000341(Ont00000715, RDFEntity):
    """
    Prosthetic Arm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000341'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000344(Ont00001281, RDFEntity):
    """
    Surfactant Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000344'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000347(Ont00001159, RDFEntity):
    """
    Electronic Bond
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000347'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000352(Ont00001139, RDFEntity):
    """
    Satellite Artifact
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000352'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000363(Ont00000998, RDFEntity):
    """
    Wireless Telecommunication Network
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000363'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000364(Ont00001221, RDFEntity):
    """
    Pneumatic Motor
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000364'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000376(Ont00000457, RDFEntity):
    """
    Portion of Gallium Arsenide
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000376'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000382(Ont00001298, RDFEntity):
    """
    Material Copy of a Spreadsheet
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000382'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000413(Ont00000304, RDFEntity):
    """
    Electron Microscope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000413'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000417(Ont00000715, RDFEntity):
    """
    Prosthetic Hand
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000417'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000428(Ont00001326, RDFEntity):
    """
    Railway Junction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000428'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000434(Ont00001207, RDFEntity):
    """
    Simple Optical Lens
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000434'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000436(Ont00000304, RDFEntity):
    """
    X-ray Microscope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000436'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000456(Ont00001326, RDFEntity):
    """
    Railway
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000456'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000470(Ont00000189, RDFEntity):
    """
    Material Copy of a Academic Degree
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000470'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000477(Ont00001049, RDFEntity):
    """
    Fuel Cell
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000477'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000482(Ont00000289, RDFEntity):
    """
    Synthetic Aperture Radar Imaging Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000482'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000493(Ont00000799, RDFEntity):
    """
    Material Copy of a Code List
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000493'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000524(Ont00000350, RDFEntity):
    """
    Air Conditioning Unit
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000524'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000526(Ont00000547, RDFEntity):
    """
    Gamma-ray Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000526'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000533(Ont00000056, RDFEntity):
    """
    Some (most) jet engines utilize turbines, but some do not. Most rocket engines do not utilize turbines, but some do.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000533'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000536(Ont00001159, RDFEntity):
    """
    Bond Certificate
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000536'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000571(Ont00000980, RDFEntity):
    """
    Article of Solid Waste
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000571'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000593(Ont00000457, RDFEntity):
    """
    Portion of Propellant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000593'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000617(Ont00000199, RDFEntity):
    """
    Infrared Camera
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000617'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000624(Ont00001298, RDFEntity):
    """
    Material Copy of a Report
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000624'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000640(Ont00001002, RDFEntity):
    """
    Material Copy of a Email Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000640'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000658(Ont00001051, RDFEntity):
    """
    Missile Launcher
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000658'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000673(Ont00000715, RDFEntity):
    """
    Prosthetic Foot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000673'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000698(Ont00000252, RDFEntity):
    """
    By increasing the Exhaust Velocity of the gas, the Nozzle increases the Thrust generated.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000698'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000700(Ont00000998, RDFEntity):
    """
    Computer Network
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000700'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000703(Ont00000159, RDFEntity):
    """
    Material Copy of a System Clock
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000703'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000704(Ont00001326, RDFEntity):
    """
    Tunnel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000704'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000716(Ont00001049, RDFEntity):
    """
    Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000716'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000721(Ont00000804, RDFEntity):
    """
    Polarizing Prism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000721'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000734(Ont00000552, RDFEntity):
    """
    Land Mine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000734'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000743(Ont00000702, RDFEntity):
    """
    Material Copy of a Chart
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000743'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000746(Ont00000638, RDFEntity):
    """
    Combustion Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000746'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000747(Ont00000549, RDFEntity):
    """
    Canal
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000747'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000748(Ont00001150, RDFEntity):
    """
    Bullet
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000748'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000774(Ont00000199, RDFEntity):
    """
    Video Camera
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000774'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000777(Ont00001221, RDFEntity):
    """
    Hydraulic Motor
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000777'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000790(Ont00001049, RDFEntity):
    """
    Direct Current Power Source
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000790'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000796(Ont00000618, RDFEntity):
    """
    Rail Transport Vehicle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000796'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000813(Ont00000457, RDFEntity):
    """
    Portion of Nuclear Fuel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000813'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000823(Ont00001148, RDFEntity):
    """
    Optical Communication Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000823'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000828(Ont00001123, RDFEntity):
    """
    Pesticide Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000828'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000838(Ont00000457, RDFEntity):
    """
    Portion of Fuel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000838'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000840(Ont00000618, RDFEntity):
    """
    Bicycle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000840'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000843(Ont00001049, RDFEntity):
    """
    Solar Panel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000843'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000857(Ont00000903, RDFEntity):
    """
    Ultra High Frequency Communication Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000857'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000858(Ont00000552, RDFEntity):
    """
    Improvised Explosive Device
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000858'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000869(Ont00000199, RDFEntity):
    """
    Optical Camera
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000869'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000877(Ont00000723, RDFEntity):
    """
    Brake Control System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000877'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000888(Ont00000903, RDFEntity):
    """
    High Frequency Communication Instrument
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000888'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000897(Ont00000457, RDFEntity):
    """
    Oxidizers are essential participants in many processes including combustion and rusting. Hence, a portion of oxidizer must always be present along with a portion of fuel in order for combustion to occur.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000897'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000906(Ont00000690, RDFEntity):
    """
    Email Box
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000906'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000907(Ont00000690, RDFEntity):
    """
    Telephone
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000907'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000909(Ont00001049, RDFEntity):
    """
    Emergency AC/DC Power Source
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000909'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000945(Ont00000547, RDFEntity):
    """
    X-ray Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000945'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000988(Ont00000804, RDFEntity):
    """
    Reflective Prism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000988'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000993(Ont00000961, RDFEntity):
    """
    Power Rectifying Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000993'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001000(Ont00000252, RDFEntity):
    """
    Spray Nozzle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001000'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001003(Ont00001150, RDFEntity):
    """
    Cartridge
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001003'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001009(Ont00000547, RDFEntity):
    """
    Optical Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001009'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001018(Ont00000350, RDFEntity):
    """
    Equipment Cooling System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001018'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001019(Ont00000723, RDFEntity):
    """
    Steering Control System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001019'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001025(Ont00001049, RDFEntity):
    """
    Electric Generator
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001025'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001029(Ont00001150, RDFEntity):
    """
    Unguided Rocket
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001029'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001046(Ont00001002, RDFEntity):
    """
    Material Copy of a Notification Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001046'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001083(Ont00000056, RDFEntity):
    """
    Air-Breathing Combustion Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001083'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001086(Ont00001326, RDFEntity):
    """
    Road Junction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001086'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001093(Ont00000475, RDFEntity):
    """
    Coin
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001093'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001097(Ont00001278, RDFEntity):
    """
    Common Stock
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001097'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001099(Ont00001326, RDFEntity):
    """
    Bridge
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001099'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001117(Ont00000252, RDFEntity):
    """
    Propelling Nozzle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001117'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001119(Ont00001298, RDFEntity):
    """
    Material Copy of a Form Document
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001119'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001124(Ont00001150, RDFEntity):
    """
    Precision-Guided Missile
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001124'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001145(Ont00000903, RDFEntity):
    """
    Radio Receiver
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001145'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001173(Ont00001051, RDFEntity):
    """
    Rocket Launcher
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001173'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001178(Ont00001326, RDFEntity):
    """
    Railway Crossing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001178'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001181(Ont00000287, RDFEntity):
    """
    Triple Inertial Navigation System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001181'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001188(Ont00000715, RDFEntity):
    """
    Denture
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001188'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001192(Ont00000092, RDFEntity):
    """
    Radio Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001192'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001201(Ont00001326, RDFEntity):
    """
    Trail
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001201'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001222(Ont00001049, RDFEntity):
    """
    Solar Panel System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001222'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001228(Ont00001298, RDFEntity):
    """
    Material Copy of a Journal Article
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001228'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001240(Ont00001148, RDFEntity):
    """
    Radio Communication Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001240'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001247(Ont00000918, RDFEntity):
    """
    Telecommunication Endpoint
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001247'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001248(Ont00000715, RDFEntity):
    """
    Artificial Eye
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001248'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001275(Ont00001353, RDFEntity):
    """
    Nominal Speed Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001275'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001282(Ont00000598, RDFEntity):
    """
    Hydraulic Valve
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001282'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001288(Ont00001150, RDFEntity):
    """
    Round Shot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001288'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001320(Ont00000903, RDFEntity):
    """
    Radio Transceiver
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001320'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001365(Ont00001353, RDFEntity):
    """
    Maximum Speed Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001365'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001373(Ont00001051, RDFEntity):
    """
    Bow
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001373'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001382(Ont00000475, RDFEntity):
    """
    Electronic Cash
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001382'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000014(Ont00000241, RDFEntity):
    """
    Material Copy of a Aztec Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000014'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000039(Ont00000838, RDFEntity):
    """
    Portion of Solid Fuel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000039'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000043(Ont00000593, RDFEntity):
    """
    Portion of Solid Propellant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000043'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000057(Ont00000907, RDFEntity):
    """
    Mobile Telephone
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000057'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000101(Ont00000255, RDFEntity):
    """
    Portion of Liquid Oxygen
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000101'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000128(Ont00000255, RDFEntity):
    """
    Portion of Liquid Hydrogen
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000128'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000147(Ont00000325, RDFEntity):
    """
    Flight Transponder
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000147'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000156(Ont00000088, RDFEntity):
    """
    Hand Gun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000156'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000167(Ont00001173, RDFEntity):
    """
    Large-Scale Rocket Launcher
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000167'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000171(Ont00000344, RDFEntity):
    """
    Detergent Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000171'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000193(Ont00000059, RDFEntity):
    """
    Telephone Subscriber Line
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000193'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000219(Ont00001009, RDFEntity):
    """
    Reflecting Optical Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000219'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000242(Ont00000241, RDFEntity):
    """
    Material Copy of a Data Matrix Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000242'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000280(Ont00001124, RDFEntity):
    """
    Torpedo
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000280'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000285(Ont00000269, RDFEntity):
    """
    Emergency Locator Transmitter
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000285'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000294(Ont00000533, RDFEntity):
    """
    Air-Breathing Jet Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000294'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000298(Ont00001173, RDFEntity):
    """
    Shoulder-Fired Rocket Launcher
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000298'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000316(Ont00000255, RDFEntity):
    """
    Portion of Liquid Helium
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000316'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000326(Ont00000258, RDFEntity):
    """
    Material Copy of a UPC Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000326'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000337(Ont00001029, RDFEntity):
    """
    Rocket-Propelled Grenade
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000337'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000340(Ont00000268, RDFEntity):
    """
    Mortar
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000340'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000355(Ont00001009, RDFEntity):
    """
    Refracting Optical Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000355'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000362(Ont00000533, RDFEntity):
    """
    Most rocket engines are also Internal Combustion Engines, however non-combusting forms also exist. For example, an untied balloon full of air that is released and allowed to zoom around the room may be both a Rocket Engine and a Physically Powered Engine.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000362'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000394(Ont00000746, RDFEntity):
    """
    Internal Combustion Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000394'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000415(Ont00000828, RDFEntity):
    """
    Anti-Microbial Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000415'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000427(Ont00000053, RDFEntity):
    """
    Armored Fighting Vehicle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000427'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000429(Ont00000258, RDFEntity):
    """
    Material Copy of a Codabar Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000429'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000431(Ont00000746, RDFEntity):
    """
    External Combustion Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000431'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000471(Ont00001046, RDFEntity):
    """
    Material Copy of a Warning Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000471'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000499(Ont00001192, RDFEntity):
    """
    Wire Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000499'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000559(Ont00000241, RDFEntity):
    """
    Material Copy of a QR Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000559'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000582(Ont00000258, RDFEntity):
    """
    Material Copy of a Code 93 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000582'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000602(Ont00000258, RDFEntity):
    """
    Material Copy of a ITF Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000602'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000606(Ont00000053, RDFEntity):
    """
    Trucks vary greatly in their size and power -- ranging from small ultra-light trucks to enormous heavy trucks. Trucks also vary greatly in their configurations -- ranging from very basic flatbeds or box trucks to highly specialized cargo carriers. Trucks may also be configured to mount specialized equipment, such as in the case of fire trucks, concrete mixers, and suction excavators.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000606'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000637(Ont00000593, RDFEntity):
    """
    Portion of Gaseous Propellant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000637'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000646(Ont00000247, RDFEntity):
    """
    Highway
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000646'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000650(Ont00000214, RDFEntity):
    """
    Ground Moving Target Indication Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000650'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000701(Ont00001145, RDFEntity):
    """
    Wire Receiver
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000701'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000709(Ont00001248, RDFEntity):
    """
    Visual Prosthesis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000709'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000714(Ont00001192, RDFEntity):
    """
    Horn Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000714'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000724(Ont00001192, RDFEntity):
    """
    Parabolic Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000724'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000728(Ont00000215, RDFEntity):
    """
    The submillimeter waveband is between the far-infrared and microwave wavebands and is typically taken to have a wavelength of between a few hundred micrometers and a millimeter.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000728'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000775(Ont00000796, RDFEntity):
    """
    Locomotive
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000775'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000785(Ont00001320, RDFEntity):
    """
    Radio Repeater
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000785'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000792(Ont00001009, RDFEntity):
    """
    Catadioptric Optical Telescope
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000792'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000816(Ont00000255, RDFEntity):
    """
    Portion of Liquid Nitrogen
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000816'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000831(Ont00000828, RDFEntity):
    """
    Herbicide Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000831'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000848(Ont00000088, RDFEntity):
    """
    Mounted Gun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000848'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000868(Ont00001173, RDFEntity):
    """
    Rocket Pod
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000868'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000878(Ont00000325, RDFEntity):
    """
    Identification Friend or Foe Transponder
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000878'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000899(Ont00000258, RDFEntity):
    """
    Material Copy of a MSI Plessey Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000899'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000928(Ont00000796, RDFEntity):
    """
    Train Car
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000928'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000933(Ont00000907, RDFEntity):
    """
    Landline Telephone
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000933'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000943(Ont00001248, RDFEntity):
    """
    Ocular Prosthesis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000943'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000956(Ont00001086, RDFEntity):
    """
    Highway Interchange
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000956'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000962(Ont00000593, RDFEntity):
    """
    Portion of Liquid Propellant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000962'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000966(Ont00000258, RDFEntity):
    """
    Material Copy of a EAN Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000966'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001011(Ont00000053, RDFEntity):
    """
    Automobile
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001011'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001012(Ont00000258, RDFEntity):
    """
    Further variants of GS1 DataBar have not been defined here.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001012'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001020(Ont00000838, RDFEntity):
    """
    Portion of Gaseous Fuel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001020'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001030(Ont00000796, RDFEntity):
    """
    Train
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001030'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001034(Ont00000774, RDFEntity):
    """
    Full Motion Video Camera
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001034'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001050(Ont00000716, RDFEntity):
    """
    Primary Cell Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001050'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001061(Ont00000053, RDFEntity):
    """
    Motorcycle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001061'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001082(Ont00001145, RDFEntity):
    """
    Patch Receiver
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001082'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001095(Ont00000363, RDFEntity):
    """
    Cellular Telecommunication Network
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001095'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001104(Ont00000088, RDFEntity):
    """
    Long Gun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001104'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001105(Ont00000716, RDFEntity):
    """
    Secondary Cell Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001105'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001135(Ont00000838, RDFEntity):
    """
    Portion of Liquid Fuel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001135'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001172(Ont00000593, RDFEntity):
    """
    Portion of Gelatinous Propellant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001172'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001198(Ont00000796, RDFEntity):
    """
    In American-English, the term 'Railcar' is often used in a broader sense that is interchangeable with 'Railroad Car'.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001198'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001223(Ont00001145, RDFEntity):
    """
    Dish Receiver
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001223'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001245(Ont00000241, RDFEntity):
    """
    Material Copy of a PDF417 Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001245'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001255(Ont00000828, RDFEntity):
    """
    Insecticide Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001255'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001260(Ont00000258, RDFEntity):
    """
    Material Copy of a Code 39 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001260'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001264(Ont00000258, RDFEntity):
    """
    Material Copy of a Code 128 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001264'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001270(Ont00000268, RDFEntity):
    """
    Howitzer
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001270'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001292(Ont00000053, RDFEntity):
    """
    Bus
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001292'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001299(Ont00000344, RDFEntity):
    """
    Wetting Agent Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001299'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001300(Ont00001192, RDFEntity):
    """
    Patch Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001300'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000015(Ont00001104, RDFEntity):
    """
    Shotgun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000015'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000048(Ont00000499, RDFEntity):
    """
    Random Wire Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000048'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000054(Ont00000431, RDFEntity):
    """
    Stirling Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000054'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000158(Ont00001105, RDFEntity):
    """
    Lithium-ion Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000158'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000204(Ont00001104, RDFEntity):
    """
    Rifle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000204'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000333(Ont00000394, RDFEntity):
    """
    Gas Turbine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000333'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000461(Ont00000966, RDFEntity):
    """
    Material Copy of a ISSN Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000461'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000467(Ont00000427, RDFEntity):
    """
    Armored Personnel Carrier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000467'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000522(Ont00000294, RDFEntity):
    """
    Pulsejet Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000522'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000538(Ont00000831, RDFEntity):
    """
    Defoliant Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000538'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000596(Ont00000966, RDFEntity):
    """
    Material Copy of a JAN-13 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000596'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000634(Ont00000431, RDFEntity):
    """
    Steam Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000634'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000671(Ont00000415, RDFEntity):
    """
    Anti-Bacterial Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000671'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000688(Ont00000294, RDFEntity):
    """
    Turbofan Air-Breathing Jet Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000688'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000711(Ont00000156, RDFEntity):
    """
    Semi-automatic Pistol
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000711'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000762(Ont00000415, RDFEntity):
    """
    Fungicide Artifact Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000762'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000807(Ont00000394, RDFEntity):
    """
    Compression Ignition Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000807'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000851(Ont00001104, RDFEntity):
    """
    Light Machine Gun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000851'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000930(Ont00001105, RDFEntity):
    """
    Nickel-metal Hydride Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000930'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000931(Ont00000326, RDFEntity):
    """
    Material Copy of a UPC-A Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000931'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000972(Ont00000966, RDFEntity):
    """
    Material Copy of a EAN-13 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000972'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000996(Ont00000294, RDFEntity):
    """
    Ramjet Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000996'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001005(Ont00000294, RDFEntity):
    """
    Turbojet Air-Breathing Jet Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001005'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001007(Ont00000928, RDFEntity):
    """
    Passenger Train Car
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001007'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001015(Ont00000646, RDFEntity):
    """
    Controlled-Access Highway
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001015'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001024(Ont00000394, RDFEntity):
    """
    Spark Ignition Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001024'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001038(Ont00001105, RDFEntity):
    """
    Nickel Cadmium Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001038'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001054(Ont00000499, RDFEntity):
    """
    Helical Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001054'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001077(Ont00000848, RDFEntity):
    """
    Heavy Machine Gun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001077'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001096(Ont00001104, RDFEntity):
    """
    Submachine Gun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001096'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001121(Ont00000294, RDFEntity):
    """
    Scramjet Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001121'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001131(Ont00000966, RDFEntity):
    """
    Material Copy of a EAN-8 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001131'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001138(Ont00000499, RDFEntity):
    """
    Beverage Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001138'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001217(Ont00000848, RDFEntity):
    """
    Medium Machine Gun
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001217'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001229(Ont00001050, RDFEntity):
    """
    Alkaline Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001229'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001230(Ont00000499, RDFEntity):
    """
    Rhombic Antenna
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001230'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001254(Ont00000156, RDFEntity):
    """
    Revolver
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001254'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001268(Ont00000966, RDFEntity):
    """
    Material Copy of a ISBN Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001268'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001319(Ont00000427, RDFEntity):
    """
    Tank firepower is normally provided by a large-caliber main gun mounted in a rotating turret, which is supported by secondary machine guns. A tank's heavy armour and all-terrain mobility provide protection for both the tank and its crew, allowing it to perform all primary tasks of the armoured troops on the battlefield.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001319'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001321(Ont00001105, RDFEntity):
    """
    Lead Acid Electric Battery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001321'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001342(Ont00000427, RDFEntity):
    """
    Infantry Fighting Vehicle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001342'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001355(Ont00000928, RDFEntity):
    """
    Freight Train Car
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001355'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001209(Ont00000326, RDFEntity):
    """
    Material Copy of a UPC-E Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001209'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000343(Ont00000634, RDFEntity):
    """
    Reciprocating Steam Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000343'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000788(Ont00000634, RDFEntity):
    """
    Turbine Steam Engine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000788'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000942(Ont00000204, RDFEntity):
    """
    Sniper Rifle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000942'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000968(Ont00000204, RDFEntity):
    """
    Assault Rifle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000968'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Ont00000038.model_rebuild()
N277759fb406a4e329e1bd31be5f6ad35b4.model_rebuild()
Ont00000170.model_rebuild()
Ont00000205.model_rebuild()
Ont00000253.model_rebuild()
N277759fb406a4e329e1bd31be5f6ad35b14.model_rebuild()
Ont00000323.model_rebuild()
N277759fb406a4e329e1bd31be5f6ad35b21.model_rebuild()
Ont00000556.model_rebuild()
N277759fb406a4e329e1bd31be5f6ad35b32.model_rebuild()
Ont00000591.model_rebuild()
N277759fb406a4e329e1bd31be5f6ad35b37.model_rebuild()
Ont00000627.model_rebuild()
N277759fb406a4e329e1bd31be5f6ad35b44.model_rebuild()
Ont00000686.model_rebuild()
Ont00000740.model_rebuild()
Ont00000758.model_rebuild()
Ont00000856.model_rebuild()
Ont00000870.model_rebuild()
Ont00000929.model_rebuild()
Ont00000958.model_rebuild()
Ont00000965.model_rebuild()
Ont00000995.model_rebuild()
N277759fb406a4e329e1bd31be5f6ad35b67.model_rebuild()
Ont00001141.model_rebuild()
Ont00001168.model_rebuild()
Ont00001341.model_rebuild()
Ont00000002.model_rebuild()
Ont00000020.model_rebuild()
Ont00000021.model_rebuild()
Ont00000023.model_rebuild()
Ont00000095.model_rebuild()
Ont00000096.model_rebuild()
Ont00000098.model_rebuild()
Ont00000103.model_rebuild()
Ont00000113.model_rebuild()
Ont00000117.model_rebuild()
Ont00000118.model_rebuild()
Ont00000122.model_rebuild()
Ont00000130.model_rebuild()
Ont00000136.model_rebuild()
Ont00000183.model_rebuild()
Ont00000192.model_rebuild()
Ont00000206.model_rebuild()
Ont00000210.model_rebuild()
Ont00000236.model_rebuild()
Ont00000238.model_rebuild()
Ont00000243.model_rebuild()
Ont00000249.model_rebuild()
Ont00000254.model_rebuild()
Ont00000256.model_rebuild()
Ont00000273.model_rebuild()
Ont00000288.model_rebuild()
Ont00000292.model_rebuild()
Ont00000319.model_rebuild()
Ont00000328.model_rebuild()
Ont00000342.model_rebuild()
Ont00000346.model_rebuild()
Ont00000348.model_rebuild()
Ont00000353.model_rebuild()
Ont00000372.model_rebuild()
Ont00000397.model_rebuild()
Ont00000403.model_rebuild()
Ont00000422.model_rebuild()
Ont00000437.model_rebuild()
Ont00000445.model_rebuild()
Ont00000448.model_rebuild()
Ont00000451.model_rebuild()
Ont00000452.model_rebuild()
Ont00000453.model_rebuild()
Ont00000458.model_rebuild()
Ont00000466.model_rebuild()
Ont00000480.model_rebuild()
Ont00000488.model_rebuild()
Ont00000491.model_rebuild()
Ont00000504.model_rebuild()
Ont00000537.model_rebuild()
Ont00000561.model_rebuild()
Ont00000575.model_rebuild()
Ont00000577.model_rebuild()
Ont00000581.model_rebuild()
Ont00000601.model_rebuild()
Ont00000603.model_rebuild()
Ont00000623.model_rebuild()
Ont00000629.model_rebuild()
Ont00000635.model_rebuild()
Ont00000651.model_rebuild()
Ont00000652.model_rebuild()
Ont00000663.model_rebuild()
Ont00000665.model_rebuild()
Ont00000668.model_rebuild()
Ont00000679.model_rebuild()
Ont00000689.model_rebuild()
Ont00000706.model_rebuild()
Ont00000713.model_rebuild()
Ont00000719.model_rebuild()
Ont00000727.model_rebuild()
Ont00000730.model_rebuild()
Ont00000736.model_rebuild()
Ont00000742.model_rebuild()
Ont00000767.model_rebuild()
Ont00000771.model_rebuild()
Ont00000776.model_rebuild()
Ont00000781.model_rebuild()
Ont00000791.model_rebuild()
Ont00000798.model_rebuild()
Ont00000809.model_rebuild()
Ont00000811.model_rebuild()
Ont00000893.model_rebuild()
Ont00000904.model_rebuild()
Ont00000932.model_rebuild()
Ont00000937.model_rebuild()
Ont00000954.model_rebuild()
Ont00001013.model_rebuild()
Ont00001036.model_rebuild()
Ont00001042.model_rebuild()
Ont00001044.model_rebuild()
Ont00001060.model_rebuild()
Ont00001067.model_rebuild()
Ont00001070.model_rebuild()
Ont00001071.model_rebuild()
Ont00001084.model_rebuild()
Ont00001085.model_rebuild()
Ont00001100.model_rebuild()
Ont00001103.model_rebuild()
Ont00001134.model_rebuild()
Ont00001140.model_rebuild()
Ont00001153.model_rebuild()
Ont00001169.model_rebuild()
Ont00001174.model_rebuild()
Ont00001187.model_rebuild()
Ont00001200.model_rebuild()
Ont00001211.model_rebuild()
Ont00001218.model_rebuild()
Ont00001241.model_rebuild()
Ont00001253.model_rebuild()
Ont00001301.model_rebuild()
Ont00001306.model_rebuild()
Ont00001310.model_rebuild()
Ont00001313.model_rebuild()
Ont00001323.model_rebuild()
Ont00001343.model_rebuild()
Ont00001346.model_rebuild()
Ont00001350.model_rebuild()
Ont00001361.model_rebuild()
Ont00001366.model_rebuild()
Ont00001370.model_rebuild()
Ont00001371.model_rebuild()
Ont00001381.model_rebuild()
Ont00001999.model_rebuild()
Ont00000012.model_rebuild()
Ont00000018.model_rebuild()
Ont00000022.model_rebuild()
Ont00000030.model_rebuild()
Ont00000034.model_rebuild()
Ont00000036.model_rebuild()
Ont00000056.model_rebuild()
Ont00000062.model_rebuild()
Ont00000066.model_rebuild()
Ont00000076.model_rebuild()
Ont00000081.model_rebuild()
Ont00000092.model_rebuild()
Ont00000111.model_rebuild()
Ont00000116.model_rebuild()
Ont00000132.model_rebuild()
Ont00000143.model_rebuild()
Ont00000145.model_rebuild()
Ont00000153.model_rebuild()
Ont00000159.model_rebuild()
Ont00000160.model_rebuild()
Ont00000189.model_rebuild()
Ont00000199.model_rebuild()
Ont00000212.model_rebuild()
Ont00000230.model_rebuild()
Ont00000244.model_rebuild()
Ont00000252.model_rebuild()
Ont00000264.model_rebuild()
Ont00000266.model_rebuild()
Ont00000267.model_rebuild()
Ont00000277.model_rebuild()
Ont00000282.model_rebuild()
Ont00000287.model_rebuild()
Ont00000289.model_rebuild()
Ont00000301.model_rebuild()
Ont00000303.model_rebuild()
Ont00000304.model_rebuild()
Ont00000306.model_rebuild()
Ont00000307.model_rebuild()
Ont00000309.model_rebuild()
Ont00000311.model_rebuild()
Ont00000317.model_rebuild()
Ont00000321.model_rebuild()
Ont00000338.model_rebuild()
Ont00000350.model_rebuild()
Ont00000407.model_rebuild()
Ont00000409.model_rebuild()
Ont00000411.model_rebuild()
Ont00000412.model_rebuild()
Ont00000420.model_rebuild()
Ont00000440.model_rebuild()
Ont00000454.model_rebuild()
Ont00000457.model_rebuild()
Ont00000475.model_rebuild()
Ont00000481.model_rebuild()
Ont00000495.model_rebuild()
Ont00000516.model_rebuild()
Ont00000534.model_rebuild()
Ont00000547.model_rebuild()
Ont00000549.model_rebuild()
Ont00000552.model_rebuild()
Ont00000569.model_rebuild()
Ont00000586.model_rebuild()
Ont00000597.model_rebuild()
Ont00000598.model_rebuild()
Ont00000600.model_rebuild()
Ont00000618.model_rebuild()
Ont00000625.model_rebuild()
Ont00000638.model_rebuild()
Ont00000656.model_rebuild()
Ont00000657.model_rebuild()
Ont00000661.model_rebuild()
Ont00000678.model_rebuild()
Ont00000681.model_rebuild()
Ont00000682.model_rebuild()
Ont00000690.model_rebuild()
Ont00000691.model_rebuild()
Ont00000693.model_rebuild()
Ont00000694.model_rebuild()
Ont00000702.model_rebuild()
Ont00000715.model_rebuild()
Ont00000720.model_rebuild()
Ont00000723.model_rebuild()
Ont00000756.model_rebuild()
Ont00000764.model_rebuild()
Ont00000793.model_rebuild()
Ont00000795.model_rebuild()
Ont00000799.model_rebuild()
Ont00000804.model_rebuild()
Ont00000806.model_rebuild()
Ont00000808.model_rebuild()
Ont00000825.model_rebuild()
Ont00000841.model_rebuild()
Ont00000849.model_rebuild()
Ont00000864.model_rebuild()
Ont00000874.model_rebuild()
Ont00000880.model_rebuild()
Ont00000886.model_rebuild()
Ont00000900.model_rebuild()
Ont00000903.model_rebuild()
Ont00000918.model_rebuild()
Ont00000919.model_rebuild()
Ont00000938.model_rebuild()
Ont00000944.model_rebuild()
Ont00000947.model_rebuild()
Ont00000952.model_rebuild()
Ont00000961.model_rebuild()
Ont00000963.model_rebuild()
Ont00000980.model_rebuild()
Ont00000985.model_rebuild()
Ont00000994.model_rebuild()
Ont00000998.model_rebuild()
Ont00001002.model_rebuild()
Ont00001008.model_rebuild()
Ont00001027.model_rebuild()
Ont00001043.model_rebuild()
Ont00001045.model_rebuild()
Ont00001049.model_rebuild()
Ont00001051.model_rebuild()
Ont00001064.model_rebuild()
Ont00001087.model_rebuild()
Ont00001092.model_rebuild()
Ont00001123.model_rebuild()
Ont00001129.model_rebuild()
Ont00001139.model_rebuild()
Ont00001148.model_rebuild()
Ont00001150.model_rebuild()
Ont00001151.model_rebuild()
Ont00001155.model_rebuild()
Ont00001156.model_rebuild()
Ont00001157.model_rebuild()
Ont00001159.model_rebuild()
Ont00001160.model_rebuild()
Ont00001161.model_rebuild()
Ont00001179.model_rebuild()
Ont00001185.model_rebuild()
Ont00001207.model_rebuild()
Ont00001210.model_rebuild()
Ont00001216.model_rebuild()
Ont00001221.model_rebuild()
Ont00001233.model_rebuild()
Ont00001234.model_rebuild()
Ont00001242.model_rebuild()
Ont00001243.model_rebuild()
Ont00001249.model_rebuild()
Ont00001250.model_rebuild()
Ont00001252.model_rebuild()
Ont00001265.model_rebuild()
Ont00001271.model_rebuild()
Ont00001273.model_rebuild()
Ont00001278.model_rebuild()
Ont00001281.model_rebuild()
Ont00001298.model_rebuild()
Ont00001303.model_rebuild()
Ont00001304.model_rebuild()
Ont00001316.model_rebuild()
Ont00001326.model_rebuild()
Ont00001329.model_rebuild()
Ont00001353.model_rebuild()
Ont00001368.model_rebuild()
Ont00001372.model_rebuild()
Ont00001378.model_rebuild()
Ont00000001.model_rebuild()
Ont00000019.model_rebuild()
Ont00000025.model_rebuild()
Ont00000028.model_rebuild()
Ont00000047.model_rebuild()
Ont00000049.model_rebuild()
Ont00000050.model_rebuild()
Ont00000053.model_rebuild()
Ont00000059.model_rebuild()
Ont00000064.model_rebuild()
Ont00000069.model_rebuild()
Ont00000075.model_rebuild()
Ont00000086.model_rebuild()
Ont00000088.model_rebuild()
Ont00000090.model_rebuild()
Ont00000091.model_rebuild()
Ont00000093.model_rebuild()
Ont00000097.model_rebuild()
Ont00000152.model_rebuild()
Ont00000162.model_rebuild()
Ont00000174.model_rebuild()
Ont00000178.model_rebuild()
Ont00000190.model_rebuild()
Ont00000194.model_rebuild()
Ont00000214.model_rebuild()
Ont00000215.model_rebuild()
Ont00000216.model_rebuild()
Ont00000231.model_rebuild()
Ont00000233.model_rebuild()
Ont00000241.model_rebuild()
Ont00000247.model_rebuild()
Ont00000255.model_rebuild()
Ont00000258.model_rebuild()
Ont00000268.model_rebuild()
Ont00000269.model_rebuild()
Ont00000299.model_rebuild()
Ont00000302.model_rebuild()
Ont00000310.model_rebuild()
Ont00000315.model_rebuild()
Ont00000325.model_rebuild()
Ont00000334.model_rebuild()
Ont00000341.model_rebuild()
Ont00000344.model_rebuild()
Ont00000347.model_rebuild()
Ont00000352.model_rebuild()
Ont00000363.model_rebuild()
Ont00000364.model_rebuild()
Ont00000376.model_rebuild()
Ont00000382.model_rebuild()
Ont00000413.model_rebuild()
Ont00000417.model_rebuild()
Ont00000428.model_rebuild()
Ont00000434.model_rebuild()
Ont00000436.model_rebuild()
Ont00000456.model_rebuild()
Ont00000470.model_rebuild()
Ont00000477.model_rebuild()
Ont00000482.model_rebuild()
Ont00000493.model_rebuild()
Ont00000524.model_rebuild()
Ont00000526.model_rebuild()
Ont00000533.model_rebuild()
Ont00000536.model_rebuild()
Ont00000571.model_rebuild()
Ont00000593.model_rebuild()
Ont00000617.model_rebuild()
Ont00000624.model_rebuild()
Ont00000640.model_rebuild()
Ont00000658.model_rebuild()
Ont00000673.model_rebuild()
Ont00000698.model_rebuild()
Ont00000700.model_rebuild()
Ont00000703.model_rebuild()
Ont00000704.model_rebuild()
Ont00000716.model_rebuild()
Ont00000721.model_rebuild()
Ont00000734.model_rebuild()
Ont00000743.model_rebuild()
Ont00000746.model_rebuild()
Ont00000747.model_rebuild()
Ont00000748.model_rebuild()
Ont00000774.model_rebuild()
Ont00000777.model_rebuild()
Ont00000790.model_rebuild()
Ont00000796.model_rebuild()
Ont00000813.model_rebuild()
Ont00000823.model_rebuild()
Ont00000828.model_rebuild()
Ont00000838.model_rebuild()
Ont00000840.model_rebuild()
Ont00000843.model_rebuild()
Ont00000857.model_rebuild()
Ont00000858.model_rebuild()
Ont00000869.model_rebuild()
Ont00000877.model_rebuild()
Ont00000888.model_rebuild()
Ont00000897.model_rebuild()
Ont00000906.model_rebuild()
Ont00000907.model_rebuild()
Ont00000909.model_rebuild()
Ont00000945.model_rebuild()
Ont00000988.model_rebuild()
Ont00000993.model_rebuild()
Ont00001000.model_rebuild()
Ont00001003.model_rebuild()
Ont00001009.model_rebuild()
Ont00001018.model_rebuild()
Ont00001019.model_rebuild()
Ont00001025.model_rebuild()
Ont00001029.model_rebuild()
Ont00001046.model_rebuild()
Ont00001083.model_rebuild()
Ont00001086.model_rebuild()
Ont00001093.model_rebuild()
Ont00001097.model_rebuild()
Ont00001099.model_rebuild()
Ont00001117.model_rebuild()
Ont00001119.model_rebuild()
Ont00001124.model_rebuild()
Ont00001145.model_rebuild()
Ont00001173.model_rebuild()
Ont00001178.model_rebuild()
Ont00001181.model_rebuild()
Ont00001188.model_rebuild()
Ont00001192.model_rebuild()
Ont00001201.model_rebuild()
Ont00001222.model_rebuild()
Ont00001228.model_rebuild()
Ont00001240.model_rebuild()
Ont00001247.model_rebuild()
Ont00001248.model_rebuild()
Ont00001275.model_rebuild()
Ont00001282.model_rebuild()
Ont00001288.model_rebuild()
Ont00001320.model_rebuild()
Ont00001365.model_rebuild()
Ont00001373.model_rebuild()
Ont00001382.model_rebuild()
Ont00000014.model_rebuild()
Ont00000039.model_rebuild()
Ont00000043.model_rebuild()
Ont00000057.model_rebuild()
Ont00000101.model_rebuild()
Ont00000128.model_rebuild()
Ont00000147.model_rebuild()
Ont00000156.model_rebuild()
Ont00000167.model_rebuild()
Ont00000171.model_rebuild()
Ont00000193.model_rebuild()
Ont00000219.model_rebuild()
Ont00000242.model_rebuild()
Ont00000280.model_rebuild()
Ont00000285.model_rebuild()
Ont00000294.model_rebuild()
Ont00000298.model_rebuild()
Ont00000316.model_rebuild()
Ont00000326.model_rebuild()
Ont00000337.model_rebuild()
Ont00000340.model_rebuild()
Ont00000355.model_rebuild()
Ont00000362.model_rebuild()
Ont00000394.model_rebuild()
Ont00000415.model_rebuild()
Ont00000427.model_rebuild()
Ont00000429.model_rebuild()
Ont00000431.model_rebuild()
Ont00000471.model_rebuild()
Ont00000499.model_rebuild()
Ont00000559.model_rebuild()
Ont00000582.model_rebuild()
Ont00000602.model_rebuild()
Ont00000606.model_rebuild()
Ont00000637.model_rebuild()
Ont00000646.model_rebuild()
Ont00000650.model_rebuild()
Ont00000701.model_rebuild()
Ont00000709.model_rebuild()
Ont00000714.model_rebuild()
Ont00000724.model_rebuild()
Ont00000728.model_rebuild()
Ont00000775.model_rebuild()
Ont00000785.model_rebuild()
Ont00000792.model_rebuild()
Ont00000816.model_rebuild()
Ont00000831.model_rebuild()
Ont00000848.model_rebuild()
Ont00000868.model_rebuild()
Ont00000878.model_rebuild()
Ont00000899.model_rebuild()
Ont00000928.model_rebuild()
Ont00000933.model_rebuild()
Ont00000943.model_rebuild()
Ont00000956.model_rebuild()
Ont00000962.model_rebuild()
Ont00000966.model_rebuild()
Ont00001011.model_rebuild()
Ont00001012.model_rebuild()
Ont00001020.model_rebuild()
Ont00001030.model_rebuild()
Ont00001034.model_rebuild()
Ont00001050.model_rebuild()
Ont00001061.model_rebuild()
Ont00001082.model_rebuild()
Ont00001095.model_rebuild()
Ont00001104.model_rebuild()
Ont00001105.model_rebuild()
Ont00001135.model_rebuild()
Ont00001172.model_rebuild()
Ont00001198.model_rebuild()
Ont00001223.model_rebuild()
Ont00001245.model_rebuild()
Ont00001255.model_rebuild()
Ont00001260.model_rebuild()
Ont00001264.model_rebuild()
Ont00001270.model_rebuild()
Ont00001292.model_rebuild()
Ont00001299.model_rebuild()
Ont00001300.model_rebuild()
Ont00000015.model_rebuild()
Ont00000048.model_rebuild()
Ont00000054.model_rebuild()
Ont00000158.model_rebuild()
Ont00000204.model_rebuild()
Ont00000333.model_rebuild()
Ont00000461.model_rebuild()
Ont00000467.model_rebuild()
Ont00000522.model_rebuild()
Ont00000538.model_rebuild()
Ont00000596.model_rebuild()
Ont00000634.model_rebuild()
Ont00000671.model_rebuild()
Ont00000688.model_rebuild()
Ont00000711.model_rebuild()
Ont00000762.model_rebuild()
Ont00000807.model_rebuild()
Ont00000851.model_rebuild()
Ont00000930.model_rebuild()
Ont00000931.model_rebuild()
Ont00000972.model_rebuild()
Ont00000996.model_rebuild()
Ont00001005.model_rebuild()
Ont00001007.model_rebuild()
Ont00001015.model_rebuild()
Ont00001024.model_rebuild()
Ont00001038.model_rebuild()
Ont00001054.model_rebuild()
Ont00001077.model_rebuild()
Ont00001096.model_rebuild()
Ont00001121.model_rebuild()
Ont00001131.model_rebuild()
Ont00001138.model_rebuild()
Ont00001217.model_rebuild()
Ont00001229.model_rebuild()
Ont00001230.model_rebuild()
Ont00001254.model_rebuild()
Ont00001268.model_rebuild()
Ont00001319.model_rebuild()
Ont00001321.model_rebuild()
Ont00001342.model_rebuild()
Ont00001355.model_rebuild()
Ont00001209.model_rebuild()
Ont00000343.model_rebuild()
Ont00000788.model_rebuild()
Ont00000942.model_rebuild()
Ont00000968.model_rebuild()
