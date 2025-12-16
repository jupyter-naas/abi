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


class BFO_0000144(RDFEntity):
    """
    Process Profile
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000144'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000004(RDFEntity):
    """
    Change
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000004'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000005(RDFEntity):
    """
    Act
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000005'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000007(RDFEntity):
    """
    Natural Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000007'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b2(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b2'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000083(RDFEntity):
    """
    Process Ending
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000083'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000110(RDFEntity):
    """
    Mechanical Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000110'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000197(RDFEntity):
    """
    Process Beginning
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000197'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b11(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b11'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b16(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b16'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000544(RDFEntity):
    """
    Although people speak of targeting a process, say, a parade, what in fact are being targeted are the material participants of that process. The disruption or ceasing of the process is the objective of some plan, but not technically a target. Only material things can be targeted for action. Even if some dependent entity is described as being the target, the material thing for which that dependent entity depends is the object of a targeting process.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000544'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b20(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b20'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b25(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b25'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b30(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b30'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000660(RDFEntity):
    """
    Effect
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000660'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b34(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b34'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b40(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b40'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000819(RDFEntity):
    """
    Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000819'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b48(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b48'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000978(RDFEntity):
    """
    Cause
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000978'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b54(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b54'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b58(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b58'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b63(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b63'
    _property_uris: ClassVar[dict] = {}
    pass

class Ncfefe0bdcb60448a83e008e4e585a349b68(RDFEntity):
    _class_uri: ClassVar[str] = 'ncfefe0bdcb60448a83e008e4e585a349b68'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000099(Ont00000007, RDFEntity):
    """
    Wave Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000099'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000135(Ont00000819, RDFEntity):
    """
    Stasis of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000135'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000228(Ont00000005, RDFEntity):
    """
    Planned Act
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000228'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000272(Ont00000007, RDFEntity):
    """
    Combustion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000272'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000278(BFO_0000144, RDFEntity):
    """
    The SI unit of measure for Momentum is Newton seconds (N s).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000278'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000312(Ont00000007, RDFEntity):
    """
    Propulsion Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000312'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000335(Ont00000819, RDFEntity):
    """
    Stasis of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000335'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000418(Ont00000005, RDFEntity):
    """
    Biographical Life
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000418'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000503(BFO_0000144, RDFEntity):
    """
    Power
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000503'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000546(Ont00000005, RDFEntity):
    """
    Unplanned Act
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000546'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000554(Ont00000004, RDFEntity):
    """
    Gain of Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000554'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000570(BFO_0000144, RDFEntity):
    """
    Force
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000570'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000594(Ont00000007, RDFEntity):
    """
    Ignition Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000594'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000644(Ont00000004, RDFEntity):
    """
    Oscillation is often thought of in the sense of motion, e.g., a swinging clock pendulum. However, the repetitive variation in location around a central point is technically a process of vibration, sometimes referred to as mechanical oscillation. Use the term Vibration Motion for those cases.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000644'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000712(BFO_0000144, RDFEntity):
    """
    Acceleration
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000712'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000726(Ont00000004, RDFEntity):
    """
    Decrease of Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000726'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000752(BFO_0000144, RDFEntity):
    """
    This is a defined class used to group process profiles of Wave Processes. Note that not every relevant process profile can be asserted as a subtype, however, because they (e.g. Frequency and Amplitude) are applicable to other processes as well (e.g. Oscillation Process).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000752'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000763(BFO_0000144, RDFEntity):
    """
    Velocity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000763'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000765(Ont00000007, RDFEntity):
    """
    Wave Production
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000765'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000772(BFO_0000144, RDFEntity):
    """
    An Impulse changes the Momentum (and potentially also the direction of Motion) of the object it is applied to and is typically measured in Newton meters.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000772'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000830(BFO_0000144, RDFEntity):
    """
    An object's speed is the scalar absolute value of it's Velocity.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000830'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000855(Ont00000660, RDFEntity):
    """
    Effect of Location Change
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000855'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000862(BFO_0000144, RDFEntity):
    """
    Sound Process Profile
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000862'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000876(Ont00000004, RDFEntity):
    """
    Loss of Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000876'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000910(BFO_0000144, RDFEntity):
    """
    Amplitude
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000910'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000920(Ont00000007, RDFEntity):
    """
    Death
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000920'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001047(BFO_0000144, RDFEntity):
    """
    Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001047'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001048(Ont00000004, RDFEntity):
    """
    Increase of Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001048'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001122(Ont00000007, RDFEntity):
    """
    Radio Interference
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001122'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001133(Ont00000007, RDFEntity):
    """
    Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001133'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001219(BFO_0000144, RDFEntity):
    """
    Delta-v is not equivalent to and should not be confused with Acceleration, which is the rate of change of Velocity.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001219'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001237(Ont00000007, RDFEntity):
    """
    Birth
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001237'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001330(Ont00000110, RDFEntity):
    """
    Telemetry Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001330'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001347(Ont00000005, RDFEntity):
    """
    Behavior
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001347'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000008(Ont00001047, RDFEntity):
    """
    Sound Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000008'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000011(Ont00000135, RDFEntity):
    """
    Nominal Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000011'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000013(Ont00000554, RDFEntity):
    """
    Gain of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000013'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000037(Ont00000228, RDFEntity):
    """
    Act of Observation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000037'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000107(Ont00001048, RDFEntity):
    """
    Increase of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000107'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000109(Ont00000228, RDFEntity):
    """
    Act of Military Force
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000109'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000138(Ont00000503, RDFEntity):
    """
    Maximum Power
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000138'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000142(Ont00000228, RDFEntity):
    """
    Act of Government
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000142'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000165(Ont00000228, RDFEntity):
    """
    Criminal Act
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000165'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000166(Ont00000099, RDFEntity):
    """
    Wave Cycle
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000166'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000179(Ont00000570, RDFEntity):
    """
    More generally, Thrust is the propulsive Force of a Rocket.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000179'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000234(Ont00000228, RDFEntity):
    """
    Act of Training
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000234'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000246(Ont00000135, RDFEntity):
    """
    Stasis of Realizable Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000246'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000290(Ont00000726, RDFEntity):
    """
    Decrease of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000290'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000296(Ont00000763, RDFEntity):
    """
    Angular Velocity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000296'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000313(Ont00000752, RDFEntity):
    """
    Assuming a non-dispersive media, the Wavelength will be the inverse of the Frequency.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000313'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000345(Ont00000228, RDFEntity):
    """
    Act of Measuring
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000345'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000357(Ont00000228, RDFEntity):
    """
    Act of Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000357'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000366(Ont00000228, RDFEntity):
    """
    Act of Information Processing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000366'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000368(Ont00001133, RDFEntity):
    """
    Rotational Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000368'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000371(Ont00000228, RDFEntity):
    """
    An Act of Prediction may involve the use of some or no relevant information. An Act of Prediction that utilizes relevant information may also be (or at least involve) an Act of Estimation. Hence, these two classes are not disjoint. Furthermore, neither class subsumes the other since estimates can be made about existing entities and not all predictions produce measurements (e.g. predicting that it will rain tomorrow).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000371'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000380(Ont00000570, RDFEntity):
    """
    Pressure
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000380'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000395(Ont00000554, RDFEntity):
    """
    Gain of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000395'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000402(Ont00000228, RDFEntity):
    """
    Act of Communication
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000402'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000511(Ont00000228, RDFEntity):
    """
    Act of Planning
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000511'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000514(Ont00000752, RDFEntity):
    """
    Transverse Wave Profile
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000514'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000523(Ont00000862, RDFEntity):
    """
    Loudness
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000523'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000542(Ont00000876, RDFEntity):
    """
    Loss of Generically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000542'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000555(Ont00000135, RDFEntity):
    """
    Enhanced Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000555'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000558(Ont00000099, RDFEntity):
    """
    Visible Light Reflection Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000558'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000566(Ont00000228, RDFEntity):
    """
    Act of Artifact Employment
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000566'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000572(Ont00000765, RDFEntity):
    """
    Sound Production
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000572'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000676(Ont00000228, RDFEntity):
    """
    Act of Inhabitancy
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000676'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000741(Ont00000228, RDFEntity):
    """
    Act of Targeting
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000741'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000754(Ont00001047, RDFEntity):
    """
    Divisions between EM radiation frequencies are fiat and sources vary on where to draw boundaries.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000754'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000760(Ont00000752, RDFEntity):
    """
    Surface Wave Profile
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000760'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000789(Ont00001133, RDFEntity):
    """
    Translational Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000789'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000850(Ont00000135, RDFEntity):
    """
    Stasis of Quality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000850'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000865(Ont00000876, RDFEntity):
    """
    Loss of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000865'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000895(Ont00000335, RDFEntity):
    """
    Married
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000895'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000908(Ont00000228, RDFEntity):
    """
    Act of Artifact Processing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000908'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000949(Ont00000228, RDFEntity):
    """
    Act of Consumption
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000949'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000951(Ont00000099, RDFEntity):
    """
    Electromagnetic Wave Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000951'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000953(Ont00000862, RDFEntity):
    """
    Pitch
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000953'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000955(Ont00000278, RDFEntity):
    """
    Angular Momentum
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000955'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001028(Ont00000099, RDFEntity):
    """
    Mechanical Wave Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001028'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001112(Ont00000712, RDFEntity):
    """
    Proper Acceleration
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001112'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001144(Ont00000228, RDFEntity):
    """
    Act of Entertainment
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001144'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001147(Ont00000228, RDFEntity):
    """
    Act of Violence
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001147'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001214(Ont00001048, RDFEntity):
    """
    Increase of Specifically Dependent Continuant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001214'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001227(Ont00000752, RDFEntity):
    """
    Longitudinal Wave Profile
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001227'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001232(Ont00000228, RDFEntity):
    """
    In all cases, to possess something, an agent must have an intention to possess it.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001232'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001251(Ont00000228, RDFEntity):
    """
    Act of Intelligence Gathering
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001251'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001279(Ont00001133, RDFEntity):
    """
    Vibration Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001279'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001286(Ont00000752, RDFEntity):
    """
    Waveform
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001286'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001289(Ont00000135, RDFEntity):
    """
    Damaged Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001289'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001314(Ont00000228, RDFEntity):
    """
    Legal System Act
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001314'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001322(Ont00000726, RDFEntity):
    """
    For the most part Generically Dependent Continuants do not inhere in their bearers over some continuous scale. The primary exception is religion and this class allows annotation of those cases where an Agent is described as becoming less religious. Other cases would include the decrease of an organization's bearing of some objective.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001322'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001327(Ont00000228, RDFEntity):
    """
    Social Act
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001327'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001338(Ont00000862, RDFEntity):
    """
    Timbre
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001338'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001376(Ont00000570, RDFEntity):
    """
    Torque
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001376'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000016(Ont00001286, RDFEntity):
    """
    Triangular Waveform
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000016'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000051(Ont00000908, RDFEntity):
    """
    An Act of Construction typically involves the production of only one or a limited number of goods, such as in the construction of an airport or a community of condominiums.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000051'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000065(Ont00000357, RDFEntity):
    """
    Act of Location Change
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000065'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000078(Ont00000345, RDFEntity):
    """
    Although the boundary between Act of Estimation and guessing is vague, estimation can be partially distinguished from guessing in that every Act of Estimation has as input some relevant information; whereas an act of guessing can occur sans information (or at least sans pertinent information). For example, if Mr. Green were asked how many blades of grass are in his lawn, he could simply choose a number (i.e. he could guess) or he could estimate the number by counting how many baldes of grass are in 1 square foot of his lawn, measuring the square footage of his lawn, and then multiplying these values to arrive at a number. Hence, many estimates may be loosely considered to be educated guesses.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000078'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000079(Ont00001327, RDFEntity):
    """
    Act of Social Movement
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000079'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000115(Ont00000246, RDFEntity):
    """
    Stasis of Disposition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000115'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000123(Ont00000402, RDFEntity):
    """
    Examples: apologizing, condoling, congratulating, greeting, thanking, accepting (acknowledging an acknowledgment)
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000123'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000131(Ont00001214, RDFEntity):
    """
    Increase of Quality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000131'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000133(Ont00000402, RDFEntity):
    """
    Examples: advising, admonishing, asking, begging, dismissing, excusing, forbidding, instructing, ordering, permitting, requesting, requiring, suggesting, urging, warning
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000133'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000148(Ont00000368, RDFEntity):
    """
    Clockwise Rotational Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000148'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000150(Ont00000754, RDFEntity):
    """
    Radio Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000150'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000191(Ont00001147, RDFEntity):
    """
    Act of Homicide
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000191'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000209(Ont00000313, RDFEntity):
    """
    Sound Wavelength
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000209'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000250(Ont00000865, RDFEntity):
    """
    Loss of Realizable Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000250'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000261(Ont00000754, RDFEntity):
    """
    Currently gamma radiation is distinguished from x-rays by their source--either inside or outside of the nucleus--rather than by frequency, energy, and wavelength.
    https://en.wikipedia.org/wiki/Gamma_ray#Naming_conventions_and_overlap_in_terminology
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000261'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000265(Ont00001327, RDFEntity):
    """
    Election
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000265'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000291(Ont00000566, RDFEntity):
    """
    Act of Decoy Use
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000291'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000305(Ont00000380, RDFEntity):
    """
    Sound Pressure
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000305'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000320(Ont00001251, RDFEntity):
    """
    Act of Reconnaissance
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000320'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000360(Ont00001289, RDFEntity):
    """
    Wounded Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000360'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000379(Ont00000402, RDFEntity):
    """
    Examples: affirming, alleging, announcing, answering, attributing, claiming, classifying, concurring, confirming, conjecturing, denying, disagreeing, disclosing, disputing, identifying, informing, insisting, predicting, ranking, reporting, stating, stipulating
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000379'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000384(Ont00000789, RDFEntity):
    """
    Rectilinear Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000384'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000391(Ont00000754, RDFEntity):
    """
    The corresponding Wavelength range is 1–0.1 mm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000391'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000401(Ont00000008, RDFEntity):
    """
    Fundamental Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000401'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000414(Ont00001286, RDFEntity):
    """
    Square Waveform
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000414'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000430(Ont00000850, RDFEntity):
    """
    Stable Orientation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000430'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000433(Ont00001327, RDFEntity):
    """
    Act of Association
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000433'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000455(Ont00001327, RDFEntity):
    """
    Act of Ceremony
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000455'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000490(Ont00000754, RDFEntity):
    """
    X-ray Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000490'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000513(Ont00000566, RDFEntity):
    """
    Act of Tool Use
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000513'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000515(Ont00000566, RDFEntity):
    """
    Act of Vehicle Use
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000515'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000517(Ont00000402, RDFEntity):
    """
    Act of Communication by Media
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000517'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000530(Ont00000008, RDFEntity):
    """
    Sound waves with frequencies in this range are typically audible to humans.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000530'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000535(Ont00000290, RDFEntity):
    """
    Decrease of Quality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000535'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000580(Ont00001286, RDFEntity):
    """
    Sine Waveform
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000580'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000584(Ont00000357, RDFEntity):
    """
    An Act of Position Change does not entail a change of location.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000584'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000585(Ont00001286, RDFEntity):
    """
    Sawtooth Waveform
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000585'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000588(Ont00000402, RDFEntity):
    """
    Act of Mass Media Communication
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000588'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000610(Ont00000754, RDFEntity):
    """
    Ultraviolet Light Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000610'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000611(Ont00001214, RDFEntity):
    """
    Increase of Realizable Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000611'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000612(Ont00000566, RDFEntity):
    """
    Act of Weapon Use
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000612'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000621(Ont00001286, RDFEntity):
    """
    Inverse Sawtooth Waveform
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000621'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000636(Ont00000345, RDFEntity):
    """
    Note that, while most if not all Acts of Appraisal involve some estimating and many Acts of Estimation involve some appraising (i.e. these classes are not disjoint), neither class subsumes the other. For example, some Acts of Appraisal (e.g. a tax assessor appraising the value of a building) impart a normative element to the measured value while others (e.g. a gustatory appraisal that fresh green beans taste better than canned green beans) involve complete information. Furthermore, many Acts of Estimation (e.g. estimating the height of a tree) are concerned solely with determining a numerical value (as opposed to the nature, value, importance, condition, or quality).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000636'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000642(Ont00000395, RDFEntity):
    """
    Gain of Realizable Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000642'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000654(Ont00001147, RDFEntity):
    """
    Act of Terrorism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000654'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000675(Ont00001028, RDFEntity):
    """
    Sound Wave Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000675'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000687(Ont00000234, RDFEntity):
    """
    Act of Training Acquisition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000687'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000739(Ont00000676, RDFEntity):
    """
    Act of Sojourn
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000739'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000773(Ont00000789, RDFEntity):
    """
    Curvilinear Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000773'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000812(Ont00000951, RDFEntity):
    """
    Electromagnetic Pulse
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000812'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000820(Ont00000246, RDFEntity):
    """
    Stasis of Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000820'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000824(Ont00000246, RDFEntity):
    """
    Stasis of Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000824'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000836(Ont00000566, RDFEntity):
    """
    Act of Financial Instrument Use
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000836'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000854(Ont00000290, RDFEntity):
    """
    Decrease of Realizable Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000854'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000875(Ont00000402, RDFEntity):
    """
    Act of Personal Communication
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000875'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000889(Ont00000037, RDFEntity):
    """
    Visible Observation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000889'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000902(Ont00000566, RDFEntity):
    """
    Act of Facility Use
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000902'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000935(Ont00000566, RDFEntity):
    """
    Act of Legal Instrument Use
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000935'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000970(Ont00000908, RDFEntity):
    """
    Excluded from this class are instances of role change or role creation such as the introduction of an artifact as a piece of evidence in a trial or the loading of artifacts onto a ship for transport.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000970'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000971(Ont00000402, RDFEntity):
    """
    Act of Deceptive Communication
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000971'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000981(Ont00000566, RDFEntity):
    """
    Act of Portion of Material Consumption
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000981'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000983(Ont00001028, RDFEntity):
    """
    Shear Wave Process
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000983'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001056(Ont00000754, RDFEntity):
    """
    Visible light overlaps with near infrared and near ultraviolet.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001056'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001068(Ont00000395, RDFEntity):
    """
    Gain of Quality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001068'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001075(Ont00000234, RDFEntity):
    """
    Act of Training Instruction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001075'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001094(Ont00001251, RDFEntity):
    """
    Act of Espionage
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001094'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001109(Ont00000368, RDFEntity):
    """
    Counter-Clockwise Rotational Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001109'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001127(Ont00000865, RDFEntity):
    """
    Loss of Quality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001127'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001128(Ont00000676, RDFEntity):
    """
    Act of Residing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001128'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001132(Ont00000246, RDFEntity):
    """
    Stasis of Mission Capability
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001132'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001136(Ont00000008, RDFEntity):
    """
    Ultrasonic Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001136'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001158(Ont00000366, RDFEntity):
    """
    Act of Data Transformation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001158'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001162(Ont00000402, RDFEntity):
    """
    Examples: agreeing, betting, guaranteeing, inviting, offering, promising, swearing, volunteering
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001162'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001184(Ont00000368, RDFEntity):
    """
    Spinning Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001184'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001196(Ont00000908, RDFEntity):
    """
    Many Acts of Manufacturing and Construction involve one or more Acts of Artifact Assembly, but Acts of Artifact Assembly can also occur in isolation from these activities.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001196'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001213(Ont00000246, RDFEntity):
    """
    Stasis of Artifact Operationality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001213'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001236(Ont00001147, RDFEntity):
    """
    Act of Suicide
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001236'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001274(Ont00000008, RDFEntity):
    """
    Infrasonic Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001274'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001285(Ont00000368, RDFEntity):
    """
    Revolving Motion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001285'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001336(Ont00001232, RDFEntity):
    """
    The relation between the owner and property may be private, collective, or common and the property may be objects, land, real estate, or intellectual property.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001336'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001337(Ont00000754, RDFEntity):
    """
    Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001337'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001359(Ont00000908, RDFEntity):
    """
    An Act of Manufacturing typically involves the mass production of goods.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001359'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001374(Ont00000402, RDFEntity):
    """
    Examples: Baptism, Sentencing a person to imprisonment, Pronouncing a couple husband and wife, Declaring war
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001374'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000006(Ont00000530, RDFEntity):
    """
    Upper Midrange Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000006'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000024(Ont00000133, RDFEntity):
    """
    Act of Advising
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000024'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000027(Ont00000517, RDFEntity):
    """
    Mailing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000027'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000033(Ont00000854, RDFEntity):
    """
    Decrease of Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000033'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000035(Ont00000490, RDFEntity):
    """
    Soft X-ray Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000035'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000100(Ont00001132, RDFEntity):
    """
    Stasis of Partially Mission Capable
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000100'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000106(Ont00001213, RDFEntity):
    """
    An End of Life Stasis (EoL) is distinguished from a Stasis of Partially Mission Capable or Stasis of Non-Mission Capable in that EoL is more inclusive such that the participating Artifact may be either Partially or Non-Mission Capable. Additionally, EoL applies only to Artifacts and is typically determined in relation to its original mission and designed primary functions. In contrast, an Artifact's level of Mission Capability depends on the requirements of the mission under consideration such that a given Artifact may simultaneously be Fully Mission Capable for mission1, Partially Mission Capable for mission2, and Non-Mission Capable for mission3.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000106'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000121(Ont00000588, RDFEntity):
    """
    Act of Conducting Mass Media Interview
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000121'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000137(Ont00000836, RDFEntity):
    """
    Act of Financial Deposit
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000137'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000144(Ont00000433, RDFEntity):
    """
    Act of Meeting
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000144'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000149(Ont00000517, RDFEntity):
    """
    Instant Messaging
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000149'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000151(Ont00000379, RDFEntity):
    """
    Act of Reporting
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000151'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000155(Ont00001337, RDFEntity):
    """
    Near Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000155'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000168(Ont00000433, RDFEntity):
    """
    Act of Interpersonal Relationship
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000168'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000169(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 10–1 m
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000169'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000182(Ont00000123, RDFEntity):
    """
    Act of Thanking
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000182'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000201(Ont00000065, RDFEntity):
    """
    Act of Change of Residence
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000201'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000202(Ont00001075, RDFEntity):
    """
    Act of Terrorist Training Instruction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000202'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000208(Ont00000123, RDFEntity):
    """
    Act of Congratulating
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000208'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000222(Ont00000530, RDFEntity):
    """
    Presence Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000222'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000235(Ont00000687, RDFEntity):
    """
    Act of Vocational Training Acquisition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000235'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000237(Ont00000687, RDFEntity):
    """
    Act of Terrorist Training Acquisition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000237'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000240(Ont00001162, RDFEntity):
    """
    Act of Oath Taking
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000240'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000260(Ont00000675, RDFEntity):
    """
    Muzzle Blast
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000260'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000322(Ont00000836, RDFEntity):
    """
    Act of Funding
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000322'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000351(Ont00000133, RDFEntity):
    """
    Act of Commanding
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000351'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000354(Ont00000379, RDFEntity):
    """
    Act of Testifying
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000354'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000356(Ont00000588, RDFEntity):
    """
    Act of Publishing Mass Media Article
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000356'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000367(Ont00001075, RDFEntity):
    """
    Act of Military Training Instruction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000367'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000370(Ont00000123, RDFEntity):
    """
    Act of Condoling
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000370'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000386(Ont00000517, RDFEntity):
    """
    Essentially, webcasting is “broadcasting” over the Internet.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000386'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000396(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 100,000–10,000 km
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000396'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000416(Ont00000588, RDFEntity):
    """
    Act of Publishing Mass Media Press Release
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000416'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000438(Ont00001374, RDFEntity):
    """
    Act of Official Documentation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000438'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000463(Ont00001075, RDFEntity):
    """
    Act of Educational Training Instruction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000463'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000492(Ont00000517, RDFEntity):
    """
    Email Messaging
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000492'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000501(Ont00000836, RDFEntity):
    """
    Act of Financial Withdrawal
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000501'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000508(Ont00000610, RDFEntity):
    """
    Near Ultraviolet Light Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000508'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000520(Ont00000065, RDFEntity):
    """
    Act of Departure
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000520'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000543(Ont00000854, RDFEntity):
    """
    Decrease of Disposition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000543'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000557(Ont00001132, RDFEntity):
    """
    Stasis of Non-Mission Capable
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000557'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000573(Ont00000687, RDFEntity):
    """
    Act of Religious Training Acquisition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000573'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000595(Ont00000065, RDFEntity):
    """
    Act of Cargo Transportation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000595'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000609(Ont00000642, RDFEntity):
    """
    This class should be used to demarcate the start of the temporal interval (through the BFO 'occupies temporal region' property) that the Entity bears the Disposition.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000609'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000613(Ont00000250, RDFEntity):
    """
    Loss of Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000613'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000615(Ont00000433, RDFEntity):
    """
    Act of Encounter
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000615'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000622(Ont00001132, RDFEntity):
    """
    Stasis of Fully Mission Capable
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000622'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000643(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 10–1 km
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000643'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000672(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 10,000–1,000 km
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000672'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000725(Ont00000455, RDFEntity):
    """
    Wedding
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000725'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000732(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 1,000–1 mm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000732'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000744(Ont00000433, RDFEntity):
    """
    Act of Social Group Membership
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000744'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000750(Ont00000517, RDFEntity):
    """
    Text Messaging
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000750'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000753(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 1,000–100 km
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000753'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000769(Ont00000133, RDFEntity):
    """
    Act of Requesting
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000769'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000786(Ont00000611, RDFEntity):
    """
    Increase of Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000786'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000821(Ont00001162, RDFEntity):
    """
    Act of Promising
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000821'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000822(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 100–10 km
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000822'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000834(Ont00001337, RDFEntity):
    """
    Mid Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000834'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000839(Ont00000836, RDFEntity):
    """
    Act of Donating
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000839'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000842(Ont00000530, RDFEntity):
    """
    Sub-Bass Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000842'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000847(Ont00001213, RDFEntity):
    """
    Active Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000847'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000859(Ont00000517, RDFEntity):
    """
    Television Broadcast
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000859'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000863(Ont00000379, RDFEntity):
    """
    Act of Confessing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000863'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000866(Ont00000517, RDFEntity):
    """
    Radio Broadcast
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000866'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000879(Ont00000433, RDFEntity):
    """
    Act of Religious Group Affiliation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000879'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000883(Ont00001162, RDFEntity):
    """
    Act of Inviting
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000883'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000884(Ont00000836, RDFEntity):
    """
    Act of Loaning
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000884'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000890(Ont00000065, RDFEntity):
    """
    Act of Travel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000890'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000922(Ont00000065, RDFEntity):
    """
    Act of Arrival
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000922'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000925(Ont00000687, RDFEntity):
    """
    Act of Military Training Acquisition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000925'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000926(Ont00000123, RDFEntity):
    """
    Act of Apologizing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000926'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000927(Ont00000530, RDFEntity):
    """
    Bass Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000927'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000936(Ont00001213, RDFEntity):
    """
    Deactivated Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000936'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000948(Ont00000455, RDFEntity):
    """
    Act of Religious Worship
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000948'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000950(Ont00000970, RDFEntity):
    """
    Act of Maintenance
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000950'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000964(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 1,000–100 m
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000964'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000977(Ont00000588, RDFEntity):
    """
    Act of Publishing Mass Media Documentary
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000977'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000999(Ont00001213, RDFEntity):
    """
    Defunct Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000999'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001021(Ont00000379, RDFEntity):
    """
    Act of Denying
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001021'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001031(Ont00001162, RDFEntity):
    """
    Act of Volunteering
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001031'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001032(Ont00001374, RDFEntity):
    """
    Act of Assignment
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001032'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001039(Ont00000836, RDFEntity):
    """
    Act of Repayment
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001039'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001053(Ont00000065, RDFEntity):
    """
    Act of Collision
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001053'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001057(Ont00000588, RDFEntity):
    """
    Act of Issuing Mass Media Press Release
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001057'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001066(Ont00000250, RDFEntity):
    """
    Loss of Disposition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001066'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001074(Ont00000687, RDFEntity):
    """
    Act of Educational Training Acquisition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001074'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001080(Ont00001337, RDFEntity):
    """
    Far Infrared Light Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001080'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001111(Ont00000530, RDFEntity):
    """
    Low Midrange Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001111'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001120(Ont00001075, RDFEntity):
    """
    Act of Religious Training Instruction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001120'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001143(Ont00000517, RDFEntity):
    """
    Facsimile Transmission
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001143'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001167(Ont00000530, RDFEntity):
    """
    Midrange Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001167'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001170(Ont00000490, RDFEntity):
    """
    Hard X-ray Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001170'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001190(Ont00000517, RDFEntity):
    """
    Telephone Call
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001190'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001191(Ont00001213, RDFEntity):
    """
    Operational Stasis
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001191'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001194(Ont00000642, RDFEntity):
    """
    This class should be used to demarcate the start of the temporal interval (through the occurs_on property) that the Entity bears the Role.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001194'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001208(Ont00000150, RDFEntity):
    """
    The corresponding Wavelength range is 100–10 m
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001208'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001215(Ont00000455, RDFEntity):
    """
    Funeral
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001215'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001226(Ont00000433, RDFEntity):
    """
    Act of Employment
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001226'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001231(Ont00000530, RDFEntity):
    """
    Brilliance Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001231'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001244(Ont00000588, RDFEntity):
    """
    Act of Issuing Mass Media Article
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001244'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001261(Ont00000379, RDFEntity):
    """
    Act of Identifying
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001261'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001263(Ont00000588, RDFEntity):
    """
    Act of Issuing Mass Media Documentary
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001263'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001266(Ont00001075, RDFEntity):
    """
    Act of Vocational Training Instruction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001266'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001267(Ont00000971, RDFEntity):
    """
    Act of Propaganda
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001267'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001269(Ont00000133, RDFEntity):
    """
    Act of Warning
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001269'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001272(Ont00000191, RDFEntity):
    """
    Act of Murder
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001272'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001332(Ont00000610, RDFEntity):
    """
    Extreme Ultraviolet Light Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001332'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001334(Ont00000836, RDFEntity):
    """
    Act of Purchasing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001334'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001356(Ont00000611, RDFEntity):
    """
    Increase of Disposition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001356'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000200(Ont00000890, RDFEntity):
    """
    Act of Pilgrimage
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000200'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000286(Ont00000100, RDFEntity):
    """
    Stasis of Partially Mission Capable Maintenance
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000286'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000308(Ont00001226, RDFEntity):
    """
    Act of Military Service
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000308'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000361(Ont00001356, RDFEntity):
    """
    Increase of Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000361'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000389(Ont00001334, RDFEntity):
    """
    Act of Buying
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000389'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000449(Ont00001334, RDFEntity):
    """
    Comment: Remuneration normally consists of salary or hourly wages, but also applies to commission, stock options, fringe benefits, etc.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000449'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000462(Ont00000609, RDFEntity):
    """
    This class should be used to demarcate the start of the temporal interval (through the BFO 'occupies temporal region' property) that the Entity bears the Function.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000462'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000519(Ont00000732, RDFEntity):
    """
    The corresponding Wavelength range is 10–1 mm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000519'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000521(Ont00001272, RDFEntity):
    """
    Act of Assassination
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000521'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000684(Ont00000821, RDFEntity):
    """
    Act of Contract Formation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000684'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000783(Ont00000557, RDFEntity):
    """
    Stasis of Non-Mission Capable Maintenance
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000783'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000924(Ont00001191, RDFEntity):
    """
    A Beginning of Life Stasis (BoL) is a relatively brief Operational Stasis that is primarily of interest for the purpose of establishing a baseline for operational parameters to be compared to the designed specifications as well as the Artifact's performance throughout its operational life.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000924'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000960(Ont00001190, RDFEntity):
    """
    Fixed Line Network Telephone Call
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000960'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000982(Ont00000543, RDFEntity):
    """
    Decrease of Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000982'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000989(Ont00000732, RDFEntity):
    """
    The corresponding Wavelength range is 100–10 mm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000989'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001072(Ont00000169, RDFEntity):
    """
    FM Radio Broadcast Frequency
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001072'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001108(Ont00000732, RDFEntity):
    """
    The corresponding Wavelength range is 1–0.1 m.
    
    Note that the ITU definition of UHF is broader than the definition given by IEEE 521-2002 - IEEE Standard Letter Designations for Radar-Frequency Bands, which sets the frequency range at 300 MHz to 1 GHz.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001108'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001115(Ont00001190, RDFEntity):
    """
    Private Network Telephone Call
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001115'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001171(Ont00001190, RDFEntity):
    """
    Wireless Network Telephone Call
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001171'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001246(Ont00000847, RDFEntity):
    """
    Under Active Control
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001246'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001305(Ont00001066, RDFEntity):
    """
    Loss of Function
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001305'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001325(Ont00001334, RDFEntity):
    """
    Act of Renting
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001325'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001339(Ont00000890, RDFEntity):
    """
    Act of Walking
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001339'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
BFO_0000144.model_rebuild()
Ont00000004.model_rebuild()
Ont00000005.model_rebuild()
Ont00000007.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b2.model_rebuild()
Ont00000083.model_rebuild()
Ont00000110.model_rebuild()
Ont00000197.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b11.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b16.model_rebuild()
Ont00000544.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b20.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b25.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b30.model_rebuild()
Ont00000660.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b34.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b40.model_rebuild()
Ont00000819.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b48.model_rebuild()
Ont00000978.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b54.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b58.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b63.model_rebuild()
Ncfefe0bdcb60448a83e008e4e585a349b68.model_rebuild()
Ont00000099.model_rebuild()
Ont00000135.model_rebuild()
Ont00000228.model_rebuild()
Ont00000272.model_rebuild()
Ont00000278.model_rebuild()
Ont00000312.model_rebuild()
Ont00000335.model_rebuild()
Ont00000418.model_rebuild()
Ont00000503.model_rebuild()
Ont00000546.model_rebuild()
Ont00000554.model_rebuild()
Ont00000570.model_rebuild()
Ont00000594.model_rebuild()
Ont00000644.model_rebuild()
Ont00000712.model_rebuild()
Ont00000726.model_rebuild()
Ont00000752.model_rebuild()
Ont00000763.model_rebuild()
Ont00000765.model_rebuild()
Ont00000772.model_rebuild()
Ont00000830.model_rebuild()
Ont00000855.model_rebuild()
Ont00000862.model_rebuild()
Ont00000876.model_rebuild()
Ont00000910.model_rebuild()
Ont00000920.model_rebuild()
Ont00001047.model_rebuild()
Ont00001048.model_rebuild()
Ont00001122.model_rebuild()
Ont00001133.model_rebuild()
Ont00001219.model_rebuild()
Ont00001237.model_rebuild()
Ont00001330.model_rebuild()
Ont00001347.model_rebuild()
Ont00000008.model_rebuild()
Ont00000011.model_rebuild()
Ont00000013.model_rebuild()
Ont00000037.model_rebuild()
Ont00000107.model_rebuild()
Ont00000109.model_rebuild()
Ont00000138.model_rebuild()
Ont00000142.model_rebuild()
Ont00000165.model_rebuild()
Ont00000166.model_rebuild()
Ont00000179.model_rebuild()
Ont00000234.model_rebuild()
Ont00000246.model_rebuild()
Ont00000290.model_rebuild()
Ont00000296.model_rebuild()
Ont00000313.model_rebuild()
Ont00000345.model_rebuild()
Ont00000357.model_rebuild()
Ont00000366.model_rebuild()
Ont00000368.model_rebuild()
Ont00000371.model_rebuild()
Ont00000380.model_rebuild()
Ont00000395.model_rebuild()
Ont00000402.model_rebuild()
Ont00000511.model_rebuild()
Ont00000514.model_rebuild()
Ont00000523.model_rebuild()
Ont00000542.model_rebuild()
Ont00000555.model_rebuild()
Ont00000558.model_rebuild()
Ont00000566.model_rebuild()
Ont00000572.model_rebuild()
Ont00000676.model_rebuild()
Ont00000741.model_rebuild()
Ont00000754.model_rebuild()
Ont00000760.model_rebuild()
Ont00000789.model_rebuild()
Ont00000850.model_rebuild()
Ont00000865.model_rebuild()
Ont00000895.model_rebuild()
Ont00000908.model_rebuild()
Ont00000949.model_rebuild()
Ont00000951.model_rebuild()
Ont00000953.model_rebuild()
Ont00000955.model_rebuild()
Ont00001028.model_rebuild()
Ont00001112.model_rebuild()
Ont00001144.model_rebuild()
Ont00001147.model_rebuild()
Ont00001214.model_rebuild()
Ont00001227.model_rebuild()
Ont00001232.model_rebuild()
Ont00001251.model_rebuild()
Ont00001279.model_rebuild()
Ont00001286.model_rebuild()
Ont00001289.model_rebuild()
Ont00001314.model_rebuild()
Ont00001322.model_rebuild()
Ont00001327.model_rebuild()
Ont00001338.model_rebuild()
Ont00001376.model_rebuild()
Ont00000016.model_rebuild()
Ont00000051.model_rebuild()
Ont00000065.model_rebuild()
Ont00000078.model_rebuild()
Ont00000079.model_rebuild()
Ont00000115.model_rebuild()
Ont00000123.model_rebuild()
Ont00000131.model_rebuild()
Ont00000133.model_rebuild()
Ont00000148.model_rebuild()
Ont00000150.model_rebuild()
Ont00000191.model_rebuild()
Ont00000209.model_rebuild()
Ont00000250.model_rebuild()
Ont00000261.model_rebuild()
Ont00000265.model_rebuild()
Ont00000291.model_rebuild()
Ont00000305.model_rebuild()
Ont00000320.model_rebuild()
Ont00000360.model_rebuild()
Ont00000379.model_rebuild()
Ont00000384.model_rebuild()
Ont00000391.model_rebuild()
Ont00000401.model_rebuild()
Ont00000414.model_rebuild()
Ont00000430.model_rebuild()
Ont00000433.model_rebuild()
Ont00000455.model_rebuild()
Ont00000490.model_rebuild()
Ont00000513.model_rebuild()
Ont00000515.model_rebuild()
Ont00000517.model_rebuild()
Ont00000530.model_rebuild()
Ont00000535.model_rebuild()
Ont00000580.model_rebuild()
Ont00000584.model_rebuild()
Ont00000585.model_rebuild()
Ont00000588.model_rebuild()
Ont00000610.model_rebuild()
Ont00000611.model_rebuild()
Ont00000612.model_rebuild()
Ont00000621.model_rebuild()
Ont00000636.model_rebuild()
Ont00000642.model_rebuild()
Ont00000654.model_rebuild()
Ont00000675.model_rebuild()
Ont00000687.model_rebuild()
Ont00000739.model_rebuild()
Ont00000773.model_rebuild()
Ont00000812.model_rebuild()
Ont00000820.model_rebuild()
Ont00000824.model_rebuild()
Ont00000836.model_rebuild()
Ont00000854.model_rebuild()
Ont00000875.model_rebuild()
Ont00000889.model_rebuild()
Ont00000902.model_rebuild()
Ont00000935.model_rebuild()
Ont00000970.model_rebuild()
Ont00000971.model_rebuild()
Ont00000981.model_rebuild()
Ont00000983.model_rebuild()
Ont00001056.model_rebuild()
Ont00001068.model_rebuild()
Ont00001075.model_rebuild()
Ont00001094.model_rebuild()
Ont00001109.model_rebuild()
Ont00001127.model_rebuild()
Ont00001128.model_rebuild()
Ont00001132.model_rebuild()
Ont00001136.model_rebuild()
Ont00001158.model_rebuild()
Ont00001162.model_rebuild()
Ont00001184.model_rebuild()
Ont00001196.model_rebuild()
Ont00001213.model_rebuild()
Ont00001236.model_rebuild()
Ont00001274.model_rebuild()
Ont00001285.model_rebuild()
Ont00001336.model_rebuild()
Ont00001337.model_rebuild()
Ont00001359.model_rebuild()
Ont00001374.model_rebuild()
Ont00000006.model_rebuild()
Ont00000024.model_rebuild()
Ont00000027.model_rebuild()
Ont00000033.model_rebuild()
Ont00000035.model_rebuild()
Ont00000100.model_rebuild()
Ont00000106.model_rebuild()
Ont00000121.model_rebuild()
Ont00000137.model_rebuild()
Ont00000144.model_rebuild()
Ont00000149.model_rebuild()
Ont00000151.model_rebuild()
Ont00000155.model_rebuild()
Ont00000168.model_rebuild()
Ont00000169.model_rebuild()
Ont00000182.model_rebuild()
Ont00000201.model_rebuild()
Ont00000202.model_rebuild()
Ont00000208.model_rebuild()
Ont00000222.model_rebuild()
Ont00000235.model_rebuild()
Ont00000237.model_rebuild()
Ont00000240.model_rebuild()
Ont00000260.model_rebuild()
Ont00000322.model_rebuild()
Ont00000351.model_rebuild()
Ont00000354.model_rebuild()
Ont00000356.model_rebuild()
Ont00000367.model_rebuild()
Ont00000370.model_rebuild()
Ont00000386.model_rebuild()
Ont00000396.model_rebuild()
Ont00000416.model_rebuild()
Ont00000438.model_rebuild()
Ont00000463.model_rebuild()
Ont00000492.model_rebuild()
Ont00000501.model_rebuild()
Ont00000508.model_rebuild()
Ont00000520.model_rebuild()
Ont00000543.model_rebuild()
Ont00000557.model_rebuild()
Ont00000573.model_rebuild()
Ont00000595.model_rebuild()
Ont00000609.model_rebuild()
Ont00000613.model_rebuild()
Ont00000615.model_rebuild()
Ont00000622.model_rebuild()
Ont00000643.model_rebuild()
Ont00000672.model_rebuild()
Ont00000725.model_rebuild()
Ont00000732.model_rebuild()
Ont00000744.model_rebuild()
Ont00000750.model_rebuild()
Ont00000753.model_rebuild()
Ont00000769.model_rebuild()
Ont00000786.model_rebuild()
Ont00000821.model_rebuild()
Ont00000822.model_rebuild()
Ont00000834.model_rebuild()
Ont00000839.model_rebuild()
Ont00000842.model_rebuild()
Ont00000847.model_rebuild()
Ont00000859.model_rebuild()
Ont00000863.model_rebuild()
Ont00000866.model_rebuild()
Ont00000879.model_rebuild()
Ont00000883.model_rebuild()
Ont00000884.model_rebuild()
Ont00000890.model_rebuild()
Ont00000922.model_rebuild()
Ont00000925.model_rebuild()
Ont00000926.model_rebuild()
Ont00000927.model_rebuild()
Ont00000936.model_rebuild()
Ont00000948.model_rebuild()
Ont00000950.model_rebuild()
Ont00000964.model_rebuild()
Ont00000977.model_rebuild()
Ont00000999.model_rebuild()
Ont00001021.model_rebuild()
Ont00001031.model_rebuild()
Ont00001032.model_rebuild()
Ont00001039.model_rebuild()
Ont00001053.model_rebuild()
Ont00001057.model_rebuild()
Ont00001066.model_rebuild()
Ont00001074.model_rebuild()
Ont00001080.model_rebuild()
Ont00001111.model_rebuild()
Ont00001120.model_rebuild()
Ont00001143.model_rebuild()
Ont00001167.model_rebuild()
Ont00001170.model_rebuild()
Ont00001190.model_rebuild()
Ont00001191.model_rebuild()
Ont00001194.model_rebuild()
Ont00001208.model_rebuild()
Ont00001215.model_rebuild()
Ont00001226.model_rebuild()
Ont00001231.model_rebuild()
Ont00001244.model_rebuild()
Ont00001261.model_rebuild()
Ont00001263.model_rebuild()
Ont00001266.model_rebuild()
Ont00001267.model_rebuild()
Ont00001269.model_rebuild()
Ont00001272.model_rebuild()
Ont00001332.model_rebuild()
Ont00001334.model_rebuild()
Ont00001356.model_rebuild()
Ont00000200.model_rebuild()
Ont00000286.model_rebuild()
Ont00000308.model_rebuild()
Ont00000361.model_rebuild()
Ont00000389.model_rebuild()
Ont00000449.model_rebuild()
Ont00000462.model_rebuild()
Ont00000519.model_rebuild()
Ont00000521.model_rebuild()
Ont00000684.model_rebuild()
Ont00000783.model_rebuild()
Ont00000924.model_rebuild()
Ont00000960.model_rebuild()
Ont00000982.model_rebuild()
Ont00000989.model_rebuild()
Ont00001072.model_rebuild()
Ont00001108.model_rebuild()
Ont00001115.model_rebuild()
Ont00001171.model_rebuild()
Ont00001246.model_rebuild()
Ont00001305.model_rebuild()
Ont00001325.model_rebuild()
Ont00001339.model_rebuild()
